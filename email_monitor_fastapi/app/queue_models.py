"""
Redis Queue Models and Configuration for Email Monitoring
Defines data models and configurations for queuing email attachments.
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid
from enum import Enum

import redis
from rq import Queue, Worker, Connection


class TaskStatus(Enum):
    """Task processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class AttachmentType(Enum):
    """Supported attachment types"""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    TXT = "txt"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class EmailMetadata:
    """Email metadata for attachment processing"""
    message_id: str
    subject: str
    sender: str
    received_date: str
    has_attachments: bool
    attachment_count: int
    email_groups_matched: List[str]
    processing_timestamp: str = None
    
    def __post_init__(self):
        if self.processing_timestamp is None:
            self.processing_timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailMetadata':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class AttachmentTask:
    """Task data for processing individual attachments"""
    task_id: str
    email_metadata: EmailMetadata
    attachment_id: str
    filename: str
    content_data: bytes  # Base64 encoded attachment content
    mime_type: str
    file_size: int
    attachment_type: AttachmentType
    processing_priority: int = 5  # 1-10, 1 being highest priority
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if isinstance(self.email_metadata, dict):
            self.email_metadata = EmailMetadata.from_dict(self.email_metadata)
        if isinstance(self.attachment_type, str):
            self.attachment_type = AttachmentType(self.attachment_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert bytes to base64 for JSON serialization
        import base64
        data['content_data'] = base64.b64encode(self.content_data).decode('utf-8')
        data['attachment_type'] = self.attachment_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AttachmentTask':
        """Create from dictionary"""
        # Convert base64 back to bytes
        import base64
        content_data = base64.b64decode(data['content_data'].encode('utf-8'))
        data['content_data'] = content_data
        return cls(**data)
    
    def get_unique_filename(self) -> str:
        """Generate unique filename for saving"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        task_uuid = self.task_id[:8]
        file_ext = os.path.splitext(self.filename)[1]
        return f"{date_str}_{task_uuid}_{self.filename}"
    
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self) -> None:
        """Increment retry counter"""
        self.retry_count += 1


@dataclass
class ProcessingResult:
    """Result of attachment processing"""
    task_id: str
    status: TaskStatus
    processed_content: Dict[str, Any] = None
    saved_paths: Dict[str, str] = None  # {"attachment": "path", "processed": "path"}
    processing_errors: List[str] = None
    processing_time: float = 0.0
    processed_at: str = None
    worker_id: str = None
    
    def __post_init__(self):
        if self.processed_at is None:
            self.processed_at = datetime.now().isoformat()
        if self.processing_errors is None:
            self.processing_errors = []
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingResult':
        """Create from dictionary"""
        return cls(**data)


class RedisQueueConfig:
    """Redis queue configuration"""
    
    def __init__(self):
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.redis_password = os.getenv('REDIS_PASSWORD')
        
        # Queue configuration
        self.attachment_queue_name = 'email_attachments'
        self.result_queue_name = 'processing_results'
        self.failed_queue_name = 'failed_tasks'
        
        # Worker configuration
        self.worker_timeout = int(os.getenv('WORKER_TIMEOUT', 300))  # 5 minutes
        self.worker_result_ttl = int(os.getenv('WORKER_RESULT_TTL', 3600))  # 1 hour
        self.worker_failure_ttl = int(os.getenv('WORKER_FAILURE_TTL', 86400))  # 24 hours
        
        # Processing configuration
        self.max_attachment_size = int(os.getenv('MAX_ATTACHMENT_SIZE', 50 * 1024 * 1024))  # 50MB
        self.supported_mime_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
            'text/csv',
            'text/plain',
            'image/jpeg',
            'image/png',
            'image/tiff',
            'image/bmp'
        ]
        
        # Retry configuration
        self.default_max_retries = int(os.getenv('DEFAULT_MAX_RETRIES', 3))
        self.retry_delays = [60, 300, 900]  # 1min, 5min, 15min
    
    def get_redis_connection(self) -> redis.Redis:
        """Get Redis connection"""
        return redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            password=self.redis_password,
            decode_responses=False  # Keep binary data as bytes
        )
    
    def get_redis_url(self) -> str:
        """Get Redis URL for RQ"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def validate_attachment(self, attachment_task: AttachmentTask) -> tuple[bool, List[str]]:
        """Validate attachment for processing"""
        errors = []
        
        # Check file size
        if attachment_task.file_size > self.max_attachment_size:
            errors.append(f"File size {attachment_task.file_size} exceeds maximum {self.max_attachment_size}")
        
        # Check MIME type
        if attachment_task.mime_type not in self.supported_mime_types:
            errors.append(f"MIME type {attachment_task.mime_type} not supported")
        
        # Check filename
        if not attachment_task.filename or len(attachment_task.filename.strip()) == 0:
            errors.append("Empty filename")
        
        # Check content data
        if not attachment_task.content_data or len(attachment_task.content_data) == 0:
            errors.append("Empty content data")
        
        return len(errors) == 0, errors


class QueueManager:
    """Manages Redis queues for email attachment processing"""
    
    def __init__(self, config: RedisQueueConfig = None):
        self.config = config or RedisQueueConfig()
        self.redis_conn = self.config.get_redis_connection()
        
        # Initialize queues
        self.attachment_queue = Queue(
            self.config.attachment_queue_name,
            connection=self.redis_conn,
            default_timeout=self.config.worker_timeout
        )
        self.result_queue = Queue(
            self.config.result_queue_name,
            connection=self.redis_conn,
            default_timeout=self.config.worker_timeout
        )
        self.failed_queue = Queue(
            self.config.failed_queue_name,
            connection=self.redis_conn,
            default_timeout=self.config.worker_timeout
        )
    
    def enqueue_attachment(self, attachment_task: AttachmentTask, delay: int = 0) -> str:
        """Enqueue attachment for processing"""
        # Validate attachment
        is_valid, errors = self.config.validate_attachment(attachment_task)
        if not is_valid:
            raise ValueError(f"Invalid attachment: {'; '.join(errors)}")
        
        # Enqueue task
        job_timeout = f"{self.config.worker_timeout}s"
        job = self.attachment_queue.enqueue_in(
            delay,
            'app.workers.process_attachment',  # Worker function
            attachment_task.to_dict(),
            job_id=attachment_task.task_id,
            job_timeout=job_timeout,
            result_ttl=self.config.worker_result_ttl,
            failure_ttl=self.config.worker_failure_ttl,
            retry_delays=self.config.retry_delays
        )
        
        return job.id
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get status of all queues"""
        return {
            "attachment_queue": {
                "name": self.config.attachment_queue_name,
                "length": len(self.attachment_queue),
                "workers": len(Worker.all(queue=self.attachment_queue))
            },
            "result_queue": {
                "name": self.config.result_queue_name,
                "length": len(self.result_queue),
                "workers": len(Worker.all(queue=self.result_queue))
            },
            "failed_queue": {
                "name": self.config.failed_queue_name,
                "length": len(self.failed_queue),
                "workers": len(Worker.all(queue=self.failed_queue))
            },
            "redis_info": {
                "host": self.config.redis_host,
                "port": self.config.redis_port,
                "db": self.config.redis_db,
                "connected": self.redis_conn.ping()
            }
        }
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific job"""
        from rq import job
        try:
            job_obj = job.Job.fetch(job_id, connection=self.redis_conn)
            return {
                "job_id": job_id,
                "status": job_obj.status,
                "created_at": job_obj.created_at.isoformat() if job_obj.created_at else None,
                "started_at": job_obj.started_at.isoformat() if job_obj.started_at else None,
                "ended_at": job_obj.ended_at.isoformat() if job_obj.ended_at else None,
                "result": job_obj.result,
                "exc_info": job_obj.exc_info,
                "meta": job_obj.meta
            }
        except Exception as e:
            return {
                "job_id": job_id,
                "status": "not_found",
                "error": str(e)
            }
    
    def cleanup_finished_jobs(self, max_age_hours: int = 24):
        """Cleanup old finished jobs"""
        from rq.registry import FinishedJobRegistry
        registry = FinishedJobRegistry(queue=self.attachment_queue)
        registry.cleanup(max_age_hours * 3600)
        
    def get_failed_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get list of failed jobs"""
        from rq.registry import FailedJobRegistry
        registry = FailedJobRegistry(queue=self.attachment_queue)
        
        failed_jobs = []
        for job_id in registry.get_job_ids()[:limit]:
            job_info = self.get_job_status(job_id)
            failed_jobs.append(job_info)
        
        return failed_jobs
    
    def retry_failed_job(self, job_id: str) -> bool:
        """Retry a failed job"""
        from rq import job
        try:
            job_obj = job.Job.fetch(job_id, connection=self.redis_conn)
            job_obj.retry()
            return True
        except Exception:
            return False
    
    def clear_queue(self, queue_name: str = None) -> int:
        """Clear a specific queue or all queues"""
        if queue_name:
            if queue_name == self.config.attachment_queue_name:
                return self.attachment_queue.empty()
            elif queue_name == self.config.result_queue_name:
                return self.result_queue.empty()
            elif queue_name == self.config.failed_queue_name:
                return self.failed_queue.empty()
        else:
            # Clear all queues
            total = 0
            total += self.attachment_queue.empty()
            total += self.result_queue.empty()
            total += self.failed_queue.empty()
            return total