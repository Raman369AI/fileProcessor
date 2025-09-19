"""
Redis Queue Integration for Email Monitoring
Simplified version for enqueuing email attachments without workers.
"""

import os
import json
import uuid
import base64
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = logging.getLogger(__name__)


@dataclass
class EmailAttachmentData:
    """Data structure for email attachment queue items"""
    task_id: str
    email_id: str
    email_subject: str
    email_sender: str
    email_sender_email: str
    email_content: str
    email_received_date: str
    attachment_id: str
    attachment_filename: str
    attachment_content: bytes
    attachment_mime_type: str
    attachment_size: int
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        return {
            "task_id": self.task_id,
            "email_id": self.email_id,
            "email_subject": self.email_subject,
            "email_sender": self.email_sender,
            "email_sender_email": self.email_sender_email,
            "email_content": self.email_content,
            "email_received_date": self.email_received_date,
            "attachment_id": self.attachment_id,
            "attachment_filename": self.attachment_filename,
            "attachment_content_b64": base64.b64encode(self.attachment_content).decode('utf-8'),
            "attachment_mime_type": self.attachment_mime_type,
            "attachment_size": self.attachment_size,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailAttachmentData':
        """Create from dictionary"""
        # Convert base64 back to bytes
        content_data = base64.b64decode(data['attachment_content_b64'].encode('utf-8'))
        return cls(
            task_id=data['task_id'],
            email_id=data['email_id'],
            email_subject=data['email_subject'],
            email_sender=data['email_sender'],
            email_sender_email=data['email_sender_email'],
            email_content=data['email_content'],
            email_received_date=data['email_received_date'],
            attachment_id=data['attachment_id'],
            attachment_filename=data['attachment_filename'],
            attachment_content=content_data,
            attachment_mime_type=data['attachment_mime_type'],
            attachment_size=data['attachment_size'],
            created_at=data.get('created_at')
        )


class RedisEmailQueue:
    """Redis queue for email attachments"""
    
    def __init__(self):
        if not HAS_REDIS:
            raise ImportError("Redis not available. Install with: pip install redis")
        
        # Redis configuration from environment
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.redis_password = os.getenv('REDIS_PASSWORD')
        
        # Queue configuration
        self.queue_name = os.getenv('EMAIL_QUEUE_NAME', 'email_attachments')
        self.max_queue_size = int(os.getenv('MAX_QUEUE_SIZE', 1000))
        self.max_attachment_size = int(os.getenv('MAX_ATTACHMENT_SIZE', 50 * 1024 * 1024))  # 50MB
        
        # Initialize Redis connection
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=False,  # Keep binary data as bytes
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis connected: {self.redis_host}:{self.redis_port}/{self.redis_db}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def enqueue_attachment(self, attachment_data: EmailAttachmentData) -> bool:
        """
        Enqueue email attachment for processing
        
        Args:
            attachment_data: EmailAttachmentData object containing email and attachment info
            
        Returns:
            bool: True if successfully enqueued, False otherwise
        """
        try:
            # Validate attachment size
            if attachment_data.attachment_size > self.max_attachment_size:
                logger.warning(f"Attachment {attachment_data.attachment_filename} too large: {attachment_data.attachment_size} bytes")
                return False
            
            # Check queue size limit
            current_size = self.redis_client.llen(self.queue_name)
            if current_size >= self.max_queue_size:
                logger.warning(f"Queue {self.queue_name} is full: {current_size} items")
                return False
            
            # Convert to JSON string
            json_data = json.dumps(attachment_data.to_dict())
            
            # Push to Redis queue (LPUSH for FIFO with RPOP)
            self.redis_client.lpush(self.queue_name, json_data)
            
            logger.info(f"Enqueued attachment: {attachment_data.attachment_filename} from email {attachment_data.email_subject[:50]}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue attachment {attachment_data.attachment_filename}: {e}")
            return False
    
    def enqueue_multiple_attachments(self, attachments: List[EmailAttachmentData]) -> int:
        """
        Enqueue multiple attachments in batch
        
        Args:
            attachments: List of EmailAttachmentData objects
            
        Returns:
            int: Number of successfully enqueued attachments
        """
        enqueued_count = 0
        
        try:
            # Use pipeline for better performance
            pipe = self.redis_client.pipeline()
            valid_attachments = []
            
            for attachment in attachments:
                # Validate attachment
                if attachment.attachment_size <= self.max_attachment_size:
                    json_data = json.dumps(attachment.to_dict())
                    pipe.lpush(self.queue_name, json_data)
                    valid_attachments.append(attachment)
                else:
                    logger.warning(f"Skipping large attachment: {attachment.attachment_filename}")
            
            # Check if we would exceed queue size
            current_size = self.redis_client.llen(self.queue_name)
            if current_size + len(valid_attachments) > self.max_queue_size:
                logger.warning(f"Batch would exceed queue limit, enqueuing individually")
                # Fallback to individual enqueuing
                for attachment in valid_attachments:
                    if self.enqueue_attachment(attachment):
                        enqueued_count += 1
            else:
                # Execute pipeline
                results = pipe.execute()
                enqueued_count = len([r for r in results if r])
                
                logger.info(f"Batch enqueued {enqueued_count} attachments from {len(attachments)} total")
        
        except Exception as e:
            logger.error(f"Failed to batch enqueue attachments: {e}")
            # Fallback to individual enqueuing
            for attachment in attachments:
                if self.enqueue_attachment(attachment):
                    enqueued_count += 1
        
        return enqueued_count
    
    def get_queue_info(self) -> Dict[str, Any]:
        """Get information about the queue"""
        try:
            info = self.redis_client.info()
            queue_length = self.redis_client.llen(self.queue_name)
            
            return {
                "queue_name": self.queue_name,
                "queue_length": queue_length,
                "max_queue_size": self.max_queue_size,
                "max_attachment_size": self.max_attachment_size,
                "redis_info": {
                    "redis_version": info.get('redis_version'),
                    "used_memory": info.get('used_memory'),
                    "used_memory_human": info.get('used_memory_human'),
                    "connected_clients": info.get('connected_clients'),
                    "total_commands_processed": info.get('total_commands_processed')
                }
            }
        except Exception as e:
            logger.error(f"Failed to get queue info: {e}")
            return {
                "queue_name": self.queue_name,
                "error": str(e)
            }
    
    def peek_queue(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Peek at items in the queue without removing them
        
        Args:
            count: Number of items to peek at
            
        Returns:
            List of dictionaries containing queue item data
        """
        try:
            # Get items from the end of the list (oldest items)
            items = self.redis_client.lrange(self.queue_name, -count, -1)
            
            result = []
            for item in reversed(items):  # Reverse to show oldest first
                try:
                    data = json.loads(item.decode('utf-8') if isinstance(item, bytes) else item)
                    # Remove large content for preview
                    preview_data = data.copy()
                    if 'attachment_content_b64' in preview_data:
                        content_size = len(preview_data['attachment_content_b64'])
                        preview_data['attachment_content_b64'] = f"<{content_size} characters>"
                    result.append(preview_data)
                except Exception as parse_error:
                    logger.warning(f"Failed to parse queue item: {parse_error}")
                    result.append({"error": "Failed to parse item"})
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to peek queue: {e}")
            return []
    
    def clear_queue(self) -> int:
        """
        Clear all items from the queue
        
        Returns:
            int: Number of items removed
        """
        try:
            removed_count = self.redis_client.delete(self.queue_name)
            logger.info(f"Cleared {removed_count} items from queue {self.queue_name}")
            return removed_count
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return 0
    
    def get_attachment_by_task_id(self, task_id: str) -> Optional[EmailAttachmentData]:
        """
        Find attachment in queue by task ID (linear search)
        Note: This is expensive for large queues
        
        Args:
            task_id: Task ID to search for
            
        Returns:
            EmailAttachmentData if found, None otherwise
        """
        try:
            # Get all items in queue
            items = self.redis_client.lrange(self.queue_name, 0, -1)
            
            for item in items:
                try:
                    data = json.loads(item.decode('utf-8') if isinstance(item, bytes) else item)
                    if data.get('task_id') == task_id:
                        return EmailAttachmentData.from_dict(data)
                except Exception as parse_error:
                    logger.warning(f"Failed to parse queue item during search: {parse_error}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to search queue for task {task_id}: {e}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis connection and queue
        
        Returns:
            Dictionary with health check results
        """
        health_status = {
            "redis_connected": False,
            "queue_accessible": False,
            "queue_length": 0,
            "errors": []
        }
        
        try:
            # Test Redis connection
            self.redis_client.ping()
            health_status["redis_connected"] = True
            
            # Test queue access
            queue_length = self.redis_client.llen(self.queue_name)
            health_status["queue_accessible"] = True
            health_status["queue_length"] = queue_length
            
        except Exception as e:
            health_status["errors"].append(f"Health check failed: {str(e)}")
        
        return health_status
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get detailed queue statistics
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            queue_length = self.redis_client.llen(self.queue_name)
            
            # Sample some items to get size statistics
            sample_size = min(10, queue_length)
            sample_items = self.redis_client.lrange(self.queue_name, 0, sample_size - 1) if sample_size > 0 else []
            
            total_sample_size = 0
            file_types = {}
            
            for item in sample_items:
                try:
                    data = json.loads(item.decode('utf-8') if isinstance(item, bytes) else item)
                    size = data.get('attachment_size', 0)
                    total_sample_size += size
                    
                    filename = data.get('attachment_filename', '')
                    ext = os.path.splitext(filename)[1].lower()
                    file_types[ext] = file_types.get(ext, 0) + 1
                    
                except Exception:
                    continue
            
            avg_size = total_sample_size / len(sample_items) if sample_items else 0
            
            return {
                "queue_length": queue_length,
                "sample_size": len(sample_items),
                "avg_attachment_size": avg_size,
                "file_type_distribution": file_types,
                "estimated_total_size": avg_size * queue_length if queue_length > 0 else 0,
                "queue_utilization": (queue_length / self.max_queue_size) * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"error": str(e)}