"""
Email Monitoring Service with FastAPI

Perfect for Windows VM - runs as background service with web monitoring.
Handles email idempotency via Graph API delta queries.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import requests
import asyncio

from fastapi import FastAPI, BackgroundTasks
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import uvicorn

try:
    from msal import ConfidentialClientApplication
    HAS_MSAL = True
except ImportError:
    HAS_MSAL = False

from file_processor import AttachmentReader


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
        
        # Store delta link persistently to avoid reprocessing emails on restart
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
        """
        Get NEW messages only using delta query (ensures idempotency)
        
        How idempotency works:
        1. First run: Gets all emails, returns delta link
        2. Subsequent runs: Only gets emails added/changed since last delta link
        3. No duplicates ever processed!
        """
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
                
                # Filter out deleted items (marked with @removed)
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
                    # Save delta link for next run (idempotency!)
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
    """Main email monitoring service"""
    
    def __init__(self):
        # Get config from environment
        self.client_id = os.getenv('AZURE_CLIENT_ID')
        self.client_secret = os.getenv('AZURE_CLIENT_SECRET')
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.email_groups = [g.strip() for g in os.getenv('EMAIL_GROUPS', '').split(',') if g.strip()]
        self.attachments_dir = Path(os.getenv('ATTACHMENTS_DIR', 'email_attachments'))
        self.file_types = [f.strip() for f in os.getenv('FILE_TYPES', '.pdf,.docx,.xlsx').split(',') if f.strip()]
        
        # Create directories
        self.attachments_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.graph_client = None
        self.attachment_reader = AttachmentReader()
        
        # Stats
        self.stats = {
            'last_run': None,
            'total_runs': 0,
            'messages_processed': 0,
            'attachments_processed': 0,
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
        """
        Main processing function - runs every 5 minutes
        Idempotency guaranteed by Graph API delta queries
        """
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
        """
        Process single message and attachments
        Attachment idempotency: Same message = same directory = overwrites duplicates
        """
        message_id = message.get("id", "")
        subject = message.get("subject", "No Subject")
        
        # Skip if no attachments
        if not message.get("hasAttachments", False):
            return
        
        try:
            # Get attachments
            attachments = self.graph_client.get_attachments(message_id)
            if not attachments:
                return
            
            logger.info(f"Processing {len(attachments)} attachments for: {subject[:50]}")
            
            # Create message directory (same message = same directory = idempotent)
            safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            message_dir = self.attachments_dir / f"{message_id[:8]}_{safe_subject}"
            message_dir.mkdir(exist_ok=True)
            
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
                
                # Save attachment (overwrites if exists = idempotent)
                attachment_path = message_dir / attachment_name
                attachment_path.write_bytes(attachment_data)
                
                # Process content
                processed = self.attachment_reader.read_attachment(
                    attachment_data, 
                    attachment_name,
                    {"email_id": message_id, "email_subject": subject}
                )
                
                # Save processed content
                if processed.get("processed_content"):
                    content_file = message_dir / f"{attachment_name}.processed.json"
                    content = processed["processed_content"]
                    
                    with open(content_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            "text": content.text,
                            "tables": content.tables,
                            "metadata": content.metadata,
                            "file_type": content.file_type
                        }, f, indent=2, ensure_ascii=False)
                
                processed_count += 1
                self.stats['attachments_processed'] += 1
            
            # Save processing summary
            if processed_count > 0:
                summary = {
                    "email_info": {
                        "message_id": message_id,
                        "subject": subject,
                        "sender": message.get("from", {}).get("emailAddress", {}).get("address", ""),
                        "processed_date": datetime.now().isoformat(),
                        "attachments_processed": processed_count
                    }
                }
                
                summary_file = message_dir / "processing_summary.json"
                with open(summary_file, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")


# Initialize monitor
monitor = EmailMonitor()

# Create FastAPI app
app = FastAPI(
    title="Email Monitor", 
    description="24/7 Email Monitoring for Windows VM",
    version="1.0.0"
)

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


@app.get("/")
async def root():
    """Service status"""
    return {
        "service": "Email Monitor",
        "status": "running",
        "monitoring_interval": "5 minutes",
        "idempotency": "Graph API delta queries ensure no duplicates"
    }


@app.get("/status")
async def get_status():
    """Detailed status"""
    return {
        "status": "running",
        "stats": monitor.stats,
        "config": {
            "email_groups": monitor.email_groups,
            "attachments_dir": str(monitor.attachments_dir),
            "file_types": monitor.file_types
        },
        "idempotency_info": {
            "email_deduplication": "Graph API delta queries",
            "attachment_deduplication": "Directory-based file overwriting",
            "delta_link_stored": monitor.graph_client.delta_link is not None if monitor.graph_client else False
        }
    }


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


def main():
    """Run the service"""
    print("🚀 Email Monitoring Service for Windows VM")
    print("=" * 50)
    print("Features:")
    print("• Runs every 5 minutes automatically")
    print("• Email idempotency via Graph API delta queries") 
    print("• Attachment idempotency via directory-based storage")
    print("• Web interface at http://localhost:8000")
    print("• Persistent across restarts")
    print()
    print("Required environment variables:")
    print("• AZURE_CLIENT_ID")
    print("• AZURE_CLIENT_SECRET")
    print("• AZURE_TENANT_ID")
    print("• EMAIL_GROUPS (comma-separated)")
    print()
    print("Optional:")
    print("• ATTACHMENTS_DIR (default: email_attachments)")
    print("• FILE_TYPES (default: .pdf,.docx,.xlsx)")
    print("=" * 50)
    
    # Run FastAPI server
    uvicorn.run(
        "email_monitor_fastapi:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()