"""
Email Monitoring Service with FastAPI and HTML Interface

Enhanced version with web dashboard for monitoring email processing.
Perfect for Windows VM environments.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import requests
import asyncio
import uuid
import mimetypes

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import uvicorn

try:
    from msal import ConfidentialClientApplication
    HAS_MSAL = True
except ImportError:
    HAS_MSAL = False

# Import from parent directory
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from file_processor import AttachmentReader

# Import Redis queue
try:
    from .redis_queue import RedisEmailQueue, EmailAttachmentData
    HAS_REDIS_QUEUE = True
except ImportError:
    HAS_REDIS_QUEUE = False


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GraphEmailClient:
    """Microsoft Graph API client with delta query for idempotency"""
    
    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        if not HAS_MSAL:
            raise ImportError("Install msal: pip install msal")
        
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.access_token = None
        self.delta_link = None
        
        # Store delta link persistently
        self.delta_file = Path("delta_link.txt")
        self._load_delta_link()
    
    def _load_delta_link(self):
        """Load delta link from file for persistence across restarts"""
        try:
            if self.delta_file.exists():
                self.delta_link = self.delta_file.read_text().strip()
                logger.info("Loaded existing delta link - will only process new emails")
        except Exception as e:
            logger.warning(f"Could not load delta link: {e}")
    
    def _save_delta_link(self):
        """Save delta link to file for persistence"""
        try:
            if self.delta_link:
                self.delta_file.write_text(self.delta_link)
        except Exception as e:
            logger.warning(f"Could not save delta link: {e}")
    
    def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph API"""
        try:
            app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}"
            )
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                return True
            else:
                logger.error(f"Auth failed: {result.get('error_description', 'Unknown')}")
                return False
                
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return False
    
    def get_new_messages(self, email_groups: List[str] = None) -> List[Dict[str, Any]]:
        """Get NEW messages only using delta query (ensures idempotency)"""
        if not self.access_token:
            return []
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # Use stored delta link for incremental sync, or start fresh
        if self.delta_link:
            url = self.delta_link
            logger.info("Using delta sync - only processing new emails")
        else:
            url = "https://graph.microsoft.com/v1.0/me/messages/delta"
            logger.info("First run - processing all emails")
        
        new_messages = []
        
        try:
            while url:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                # Filter out deleted items
                messages = [msg for msg in data.get("value", []) if "@removed" not in msg]
                
                # Filter by email groups if specified
                if email_groups and messages:
                    filtered = []
                    for msg in messages:
                        sender = msg.get("from", {}).get("emailAddress", {}).get("address", "").lower()
                        if any(group.lower() in sender for group in email_groups):
                            filtered.append(msg)
                    messages = filtered
                
                new_messages.extend(messages)
                
                # Handle pagination and delta link
                next_link = data.get("@odata.nextLink")
                delta_link = data.get("@odata.deltaLink")
                
                if delta_link:
                    self.delta_link = delta_link
                    self._save_delta_link()
                    break
                elif next_link:
                    url = next_link
                else:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []
        
        logger.info(f"Found {len(new_messages)} new messages")
        return new_messages
    
    def get_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """Get attachments for a message"""
        if not self.access_token:
            return []
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json().get("value", [])
        except Exception as e:
            logger.error(f"Error getting attachments: {e}")
            return []
    
    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment content"""
        if not self.access_token:
            return b""
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments/{attachment_id}/$value"
        
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return b""


class EmailMonitor:
    """Main email monitoring service with Redis queue support"""
    
    def __init__(self):
        # Get config from environment
        self.client_id = os.getenv('AZURE_CLIENT_ID')
        self.client_secret = os.getenv('AZURE_CLIENT_SECRET')
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.email_groups = [g.strip() for g in os.getenv('EMAIL_GROUPS', '').split(',') if g.strip()]
        self.attachments_dir = Path(os.getenv('ATTACHMENTS_DIR', 'email_attachments'))
        self.file_types = [f.strip() for f in os.getenv('FILE_TYPES', '.pdf,.docx,.xlsx').split(',') if f.strip()]
        
        # Redis queue configuration
        self.use_redis_queue = os.getenv('USE_REDIS_QUEUE', 'false').lower() == 'true'
        self.redis_queue = None
        
        # Create directories
        self.attachments_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.graph_client = None
        self.attachment_reader = AttachmentReader()
        
        # Initialize Redis queue if enabled
        if self.use_redis_queue:
            try:
                if HAS_REDIS_QUEUE:
                    self.redis_queue = RedisEmailQueue()
                    logger.info("Redis queue initialized successfully")
                else:
                    logger.warning("Redis queue requested but not available. Install redis: pip install redis")
                    self.use_redis_queue = False
            except Exception as e:
                logger.error(f"Failed to initialize Redis queue: {e}")
                self.use_redis_queue = False
        
        # Stats
        self.stats = {
            'last_run': None,
            'total_runs': 0,
            'messages_processed': 0,
            'attachments_processed': 0,
            'attachments_queued': 0,
            'queue_errors': 0,
            'errors': 0
        }
        
        # Validate config and initialize
        if self._validate_config():
            self.graph_client = GraphEmailClient(self.client_id, self.client_secret, self.tenant_id)
            logger.info("Email monitor initialized successfully")
        else:
            logger.error("Invalid configuration")
    
    def _validate_config(self) -> bool:
        """Validate required configuration"""
        required = ['AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET', 'AZURE_TENANT_ID']
        missing = [var for var in required if not os.getenv(var)]
        
        if missing:
            logger.error(f"Missing environment variables: {missing}")
            return False
        return True
    
    async def process_emails(self):
        """Main processing function - runs every 5 minutes"""
        if not self.graph_client:
            logger.error("Graph client not initialized")
            return
        
        try:
            logger.info("Starting email processing cycle")
            
            # Authenticate
            if not self.graph_client.authenticate():
                self.stats['errors'] += 1
                return
            
            # Get only NEW messages (idempotency handled by delta query)
            messages = self.graph_client.get_new_messages(self.email_groups)
            
            if not messages:
                logger.info("No new messages to process")
            else:
                # Process each message
                for message in messages:
                    await self._process_message(message)
                
                self.stats['messages_processed'] += len(messages)
                logger.info(f"Processed {len(messages)} new messages")
            
            # Update stats
            self.stats['total_runs'] += 1
            self.stats['last_run'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error in email processing: {e}")
            self.stats['errors'] += 1
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process single message and enqueue attachments to Redis or process directly"""
        message_id = message.get("id", "")
        subject = message.get("subject", "No Subject")
        sender = message.get("from", {}).get("emailAddress", {}).get("address", "")
        received_date = message.get("receivedDateTime", datetime.now().isoformat())
        
        # Skip if no attachments
        if not message.get("hasAttachments", False):
            return
        
        try:
            # Get attachments
            attachments = self.graph_client.get_attachments(message_id)
            if not attachments:
                return
            
            logger.info(f"Processing {len(attachments)} attachments for: {subject[:50]}")
            
            if self.use_redis_queue and self.redis_queue:
                # Enqueue attachments to Redis
                await self._enqueue_attachments_to_redis(
                    message_id, subject, sender, received_date, attachments
                )
            else:
                # Process attachments directly (original behavior)
                await self._process_attachments_directly(
                    message_id, subject, sender, attachments
                )
            
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            self.stats['errors'] += 1
    
    async def _enqueue_attachments_to_redis(self, message_id: str, subject: str, 
                                           sender: str, received_date: str, 
                                           attachments: List[Dict[str, Any]]):
        """Enqueue attachments to Redis queue for processing"""
        queued_count = 0
        attachment_tasks = []
        
        try:
            for attachment in attachments:
                attachment_name = attachment.get("name", "unknown")
                attachment_id = attachment.get("id", "")
                
                # Filter by file type
                if self.file_types:
                    file_ext = os.path.splitext(attachment_name)[1].lower()
                    if file_ext not in self.file_types:
                        continue
                
                # Download attachment
                attachment_data = self.graph_client.download_attachment(message_id, attachment_id)
                
                if not attachment_data:
                    continue
                
                # Get MIME type
                mime_type, _ = mimetypes.guess_type(attachment_name)
                if not mime_type:
                    # Fallback MIME type based on extension
                    ext_to_mime = {
                        '.pdf': 'application/pdf',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        '.csv': 'text/csv',
                        '.txt': 'text/plain',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png'
                    }
                    file_ext = os.path.splitext(attachment_name)[1].lower()
                    mime_type = ext_to_mime.get(file_ext, 'application/octet-stream')
                
                # Create attachment task
                task_id = f"{message_id[:8]}_{attachment_id[:8]}_{uuid.uuid4().hex[:8]}"
                
                attachment_task = EmailAttachmentData(
                    task_id=task_id,
                    email_id=message_id,
                    email_subject=subject,
                    email_sender=sender,
                    email_received_date=received_date,
                    attachment_id=attachment_id,
                    attachment_filename=attachment_name,
                    attachment_content=attachment_data,
                    attachment_mime_type=mime_type,
                    attachment_size=len(attachment_data)
                )
                
                attachment_tasks.append(attachment_task)
            
            # Batch enqueue to Redis
            if attachment_tasks:
                queued_count = self.redis_queue.enqueue_multiple_attachments(attachment_tasks)
                self.stats['attachments_queued'] += queued_count
                logger.info(f"Enqueued {queued_count}/{len(attachment_tasks)} attachments from email: {subject[:50]}")
                
                # Save enqueue summary
                await self._save_enqueue_summary(message_id, subject, sender, attachment_tasks, queued_count)
            
        except Exception as e:
            logger.error(f"Error enqueuing attachments for message {message_id}: {e}")
            self.stats['queue_errors'] += 1
    
    async def _save_enqueue_summary(self, message_id: str, subject: str, sender: str, 
                                  attachment_tasks: List[EmailAttachmentData], queued_count: int):
        """Save summary of enqueued attachments"""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            summary_uuid = str(uuid.uuid4())[:8]
            summary_filename = f"{date_str}_{summary_uuid}_enqueue_summary_{message_id[:8]}.json"
            
            summary = {
                "email_info": {
                    "message_id": message_id,
                    "subject": subject,
                    "sender": sender,
                    "enqueued_date": datetime.now().isoformat(),
                    "total_attachments": len(attachment_tasks),
                    "attachments_enqueued": queued_count
                },
                "enqueued_attachments": [
                    {
                        "task_id": task.task_id,
                        "filename": task.attachment_filename,
                        "mime_type": task.attachment_mime_type,
                        "size": task.attachment_size,
                        "attachment_id": task.attachment_id
                    }
                    for task in attachment_tasks
                ]
            }
            
            summary_file = self.attachments_dir / summary_filename
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving enqueue summary: {e}")
    
    async def _process_attachments_directly(self, message_id: str, subject: str, 
                                          sender: str, attachments: List[Dict[str, Any]]):
        """Process attachments directly (original behavior)"""
        message_dir = self.attachments_dir
        processed_attachments = []
        processed_count = 0
        
        for attachment in attachments:
            attachment_name = attachment.get("name", "unknown")
            
            # Filter by file type
            if self.file_types:
                file_ext = os.path.splitext(attachment_name)[1].lower()
                if file_ext not in self.file_types:
                    continue
            
            # Download attachment
            attachment_data = self.graph_client.download_attachment(
                message_id, attachment.get("id", "")
            )
            
            if not attachment_data:
                continue
            
            # Create unique filename with date and UUID
            date_str = datetime.now().strftime("%Y-%m-%d")
            file_uuid = str(uuid.uuid4())[:8]
            file_ext = os.path.splitext(attachment_name)[1]
            unique_filename = f"{date_str}_{file_uuid}_{attachment_name}"
            
            # Save attachment with unique name
            attachment_path = message_dir / unique_filename
            attachment_path.write_bytes(attachment_data)
            
            # Process content
            processed = self.attachment_reader.read_attachment(
                attachment_data, 
                attachment_name,
                {"email_id": message_id, "email_subject": subject}
            )
            
            # Save processed content
            if processed.get("processed_content"):
                content_file = message_dir / f"{unique_filename}.processed.json"
                content = processed["processed_content"]
                
                with open(content_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "text": content.text,
                        "tables": content.tables,
                        "metadata": content.metadata,
                        "file_type": content.file_type
                    }, f, indent=2, ensure_ascii=False)
            
            processed_attachments.append({
                "original_filename": attachment_name,
                "saved_filename": unique_filename,
                "file_type": os.path.splitext(attachment_name)[1].lower(),
                "file_size": len(attachment_data),
                "saved_path": str(attachment_path),
                "processing_method": processed.get("processing_method", "none"),
                "errors": processed.get("errors", [])
            })
            
            processed_count += 1
            self.stats['attachments_processed'] += 1
        
        # Save processing summary
        if processed_count > 0:
            date_str = datetime.now().strftime("%Y-%m-%d")
            summary_uuid = str(uuid.uuid4())[:8]
            summary_filename = f"{date_str}_{summary_uuid}_processing_summary_{message_id[:8]}.json"
            
            summary = {
                "email_info": {
                    "message_id": message_id,
                    "subject": subject,
                    "sender": sender,
                    "processed_date": datetime.now().isoformat(),
                    "attachments_processed": processed_count
                },
                "attachments": processed_attachments
            }
            
            summary_file = message_dir / summary_filename
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)


# Initialize monitor
monitor = EmailMonitor()

# Create FastAPI app
app = FastAPI(
    title="Email Monitor Dashboard", 
    description="24/7 Email Monitoring with Web Interface",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Background scheduler
scheduler = BackgroundScheduler()


@app.on_event("startup")
async def startup():
    """Start monitoring every 5 minutes"""
    scheduler.add_job(
        func=lambda: asyncio.create_task(monitor.process_emails()),
        trigger=IntervalTrigger(minutes=5),
        id='email_monitor_job',
        name='Email Monitor',
        replace_existing=True
    )
    scheduler.start()
    logger.info("✅ Email monitoring started - checking every 5 minutes")


@app.on_event("shutdown")
async def shutdown():
    """Clean shutdown"""
    scheduler.shutdown(wait=False)
    logger.info("Email monitoring stopped")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/status")
async def get_status():
    """Detailed status API"""
    base_status = {
        "status": "running",
        "stats": monitor.stats,
        "config": {
            "email_groups": monitor.email_groups,
            "attachments_dir": str(monitor.attachments_dir),
            "file_types": monitor.file_types,
            "redis_queue_enabled": monitor.use_redis_queue
        },
        "idempotency_info": {
            "email_deduplication": "Graph API delta queries",
            "attachment_deduplication": "Directory-based file overwriting",
            "delta_link_stored": monitor.graph_client.delta_link is not None if monitor.graph_client else False
        }
    }
    
    # Add Redis queue information if enabled
    if monitor.use_redis_queue and monitor.redis_queue:
        try:
            queue_info = monitor.redis_queue.get_queue_info()
            base_status["redis_queue"] = queue_info
        except Exception as e:
            base_status["redis_queue"] = {"error": str(e)}
    
    return base_status


@app.post("/process-now")
async def process_now(background_tasks: BackgroundTasks):
    """Trigger immediate processing"""
    background_tasks.add_task(monitor.process_emails)
    return {"message": "Email processing triggered immediately"}


@app.get("/recent-results")
async def get_recent_results():
    """Get recent processing results"""
    results = []
    
    try:
        for message_dir in monitor.attachments_dir.iterdir():
            if message_dir.is_dir():
                summary_file = message_dir / "processing_summary.json"
                if summary_file.exists():
                    with open(summary_file) as f:
                        summary = json.load(f)
                        results.append(summary["email_info"])
        
        # Sort by processed date
        results.sort(key=lambda x: x.get("processed_date", ""), reverse=True)
        return {"recent_results": results[:10]}
        
    except Exception as e:
        return {"error": str(e), "recent_results": []}


@app.get("/email-details/{message_id}")
async def get_email_details(message_id: str):
    """Get detailed information about a processed email"""
    try:
        # Find the message directory
        message_dir = None
        for dir_path in monitor.attachments_dir.iterdir():
            if dir_path.is_dir() and dir_path.name.startswith(message_id[:8]):
                message_dir = dir_path
                break
        
        if not message_dir:
            raise HTTPException(status_code=404, detail="Email not found")
        
        summary_file = message_dir / "processing_summary.json"
        if not summary_file.exists():
            raise HTTPException(status_code=404, detail="Processing summary not found")
        
        with open(summary_file) as f:
            summary = json.load(f)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/email-json/{message_id}")
async def get_email_json(message_id: str):
    """Get complete JSON data for an email"""
    try:
        # Find the message directory
        message_dir = None
        for dir_path in monitor.attachments_dir.iterdir():
            if dir_path.is_dir() and dir_path.name.startswith(message_id[:8]):
                message_dir = dir_path
                break
        
        if not message_dir:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Collect all JSON files
        result = {"email_summary": None, "attachments": []}
        
        # Get summary
        summary_file = message_dir / "processing_summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                result["email_summary"] = json.load(f)
        
        # Get all processed attachments
        for file_path in message_dir.glob("*.processed.json"):
            with open(file_path) as f:
                attachment_data = json.load(f)
                result["attachments"].append({
                    "filename": file_path.name.replace(".processed.json", ""),
                    "processed_content": attachment_data
                })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/attachment-json/{message_id}/{filename}")
async def get_attachment_json(message_id: str, filename: str):
    """Get JSON processing results for a specific attachment"""
    try:
        # Find the message directory
        message_dir = None
        for dir_path in monitor.attachments_dir.iterdir():
            if dir_path.is_dir() and dir_path.name.startswith(message_id[:8]):
                message_dir = dir_path
                break
        
        if not message_dir:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Find the processed JSON file
        json_file = message_dir / f"{filename}.processed.json"
        if not json_file.exists():
            raise HTTPException(status_code=404, detail="Processed file not found")
        
        with open(json_file) as f:
            return json.load(f)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/redis-queue/status")
async def get_redis_queue_status():
    """Get Redis queue status and information"""
    if not monitor.use_redis_queue:
        return {"error": "Redis queue not enabled"}
    
    if not monitor.redis_queue:
        return {"error": "Redis queue not initialized"}
    
    try:
        return monitor.redis_queue.get_queue_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/redis-queue/stats")
async def get_redis_queue_stats():
    """Get detailed Redis queue statistics"""
    if not monitor.use_redis_queue or not monitor.redis_queue:
        raise HTTPException(status_code=400, detail="Redis queue not available")
    
    try:
        return monitor.redis_queue.get_queue_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/redis-queue/peek")
async def peek_redis_queue(count: int = 5):
    """Peek at items in Redis queue without removing them"""
    if not monitor.use_redis_queue or not monitor.redis_queue:
        raise HTTPException(status_code=400, detail="Redis queue not available")
    
    if count <= 0 or count > 50:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 50")
    
    try:
        return {
            "queue_peek": monitor.redis_queue.peek_queue(count),
            "peek_count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/redis-queue/clear")
async def clear_redis_queue():
    """Clear all items from Redis queue"""
    if not monitor.use_redis_queue or not monitor.redis_queue:
        raise HTTPException(status_code=400, detail="Redis queue not available")
    
    try:
        removed_count = monitor.redis_queue.clear_queue()
        return {
            "message": f"Cleared {removed_count} items from queue",
            "removed_count": removed_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/redis-queue/health")
async def redis_queue_health_check():
    """Perform health check on Redis queue"""
    if not monitor.use_redis_queue or not monitor.redis_queue:
        return {
            "redis_queue_enabled": False,
            "redis_connected": False,
            "queue_accessible": False,
            "errors": ["Redis queue not enabled or initialized"]
        }
    
    try:
        health_status = monitor.redis_queue.health_check()
        health_status["redis_queue_enabled"] = True
        return health_status
    except Exception as e:
        return {
            "redis_queue_enabled": True,
            "redis_connected": False,
            "queue_accessible": False,
            "errors": [str(e)]
        }


def main():
    """Run the FastAPI server with web interface"""
    print("🚀 Email Monitor Dashboard with Redis Queue Support")
    print("=" * 60)
    print("Features:")
    print("• Web dashboard at http://localhost:8000")
    print("• Real-time monitoring and stats")
    print("• JSON processing results viewer")
    print("• Email and attachment details")
    print("• Manual processing trigger")
    print("• Redis queue for attachment processing")
    print("• Queue monitoring and management APIs")
    print()
    print("Environment variables required:")
    print("• AZURE_CLIENT_ID")
    print("• AZURE_CLIENT_SECRET")
    print("• AZURE_TENANT_ID")
    print("• EMAIL_GROUPS (comma-separated)")
    print()
    print("Environment variables optional (Redis):")
    print("• USE_REDIS_QUEUE=true (enable Redis queue)")
    print("• REDIS_HOST=localhost")
    print("• REDIS_PORT=6379")
    print("• REDIS_DB=0")
    print("• REDIS_PASSWORD (if required)")
    print("• EMAIL_QUEUE_NAME=email_attachments")
    print("• MAX_QUEUE_SIZE=1000")
    print("• MAX_ATTACHMENT_SIZE=52428800 (50MB)")
    print()
    print("Redis Queue APIs:")
    print("• GET /redis-queue/status - Queue status")
    print("• GET /redis-queue/stats - Queue statistics")
    print("• GET /redis-queue/peek?count=5 - Peek queue items")
    print("• POST /redis-queue/clear - Clear queue")
    print("• GET /redis-queue/health - Health check")
    print("=" * 60)
    
    # Run FastAPI server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()