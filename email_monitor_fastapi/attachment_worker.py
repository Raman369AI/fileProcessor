#!/usr/bin/env python3
"""
Attachment Processing Worker

Consumes email attachments from Redis queue and processes them through 
the AI pipeline. Each attachment is processed separately along with the
email text content.
"""

import os
import sys
import json
import uuid
import asyncio
import logging
import tempfile
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import base64

# Add the parent directory to the path to access shared modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    print("Redis not available. Install with: pip install redis")
    sys.exit(1)

# Import from the app
from app.redis_queue import RedisEmailQueue, EmailAttachmentData

# Placeholder imports for your pipeline - replace with your actual imports
# from your_pipeline import Runner, types, main_pipeline_agent, InMemorySessionService, InMemoryArtifactService
# from your_pipeline import StateParser, ImageProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('attachment_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AttachmentWorker:
    """
    Worker that consumes email attachments from Redis queue and processes them
    through the AI pipeline. Each attachment is processed individually along
    with the email text content.
    """
    
    def __init__(self):
        """Initialize the worker with configuration"""
        # Redis configuration
        self.redis_client = self._init_redis()
        self.queue_name = os.getenv('EMAIL_QUEUE_NAME', 'email_attachments')
        
        # Pipeline configuration
        self.app_name = os.getenv('PIPELINE_APP_NAME', 'EMAIL_PROCESSOR')
        self.user_id = os.getenv('PIPELINE_USER_ID', 'worker_001')
        self.max_retries = int(os.getenv('MAX_PIPELINE_RETRIES', '3'))
        
        # Worker configuration  
        self.poll_interval = int(os.getenv('WORKER_POLL_INTERVAL', '5'))  # seconds
        self.processing_timeout = int(os.getenv('PROCESSING_TIMEOUT', '300'))  # 5 minutes
        self.temp_dir = Path(os.getenv('WORKER_TEMP_DIR', '/tmp/attachment_worker'))
        self.temp_dir.mkdir(exist_ok=True)
        
        # Statistics
        self.stats = {
            'processed_count': 0,
            'success_count': 0,
            'error_count': 0,
            'started_at': datetime.now().isoformat(),
            'last_processed_at': None
        }
        
        logger.info(f"AttachmentWorker initialized - Queue: {self.queue_name}")
        logger.info(f"Pipeline App: {self.app_name}, User: {self.user_id}")
        logger.info(f"Poll interval: {self.poll_interval}s, Timeout: {self.processing_timeout}s")
    
    def _init_redis(self) -> redis.Redis:
        """Initialize Redis connection"""
        try:
            redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=int(os.getenv('REDIS_DB', 0)),
                password=os.getenv('REDIS_PASSWORD'),
                decode_responses=False,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            redis_client.ping()
            logger.info("Redis connection established")
            return redis_client
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def run(self):
        """Main worker loop - continuously process items from the queue"""
        logger.info("Starting attachment worker loop...")
        
        while True:
            try:
                # Get next item from queue (blocking with timeout)
                queue_item = self.redis_client.brpop(self.queue_name, timeout=self.poll_interval)
                
                if queue_item is None:
                    # No items in queue, continue polling
                    logger.debug("No items in queue, continuing...")
                    continue
                
                # Extract the actual data (brpop returns tuple: (queue_name, data))
                _, raw_data = queue_item
                
                # Parse the attachment data
                try:
                    attachment_data = self._parse_queue_item(raw_data)
                    if attachment_data is None:
                        continue
                        
                    logger.info(f"Processing attachment: {attachment_data.attachment_filename} "
                               f"from email: {attachment_data.email_subject[:50]}")
                    
                    # Process the attachment
                    success = await self._process_attachment(attachment_data)
                    
                    # Update statistics
                    self._update_stats(success)
                    
                except Exception as e:
                    logger.error(f"Error processing queue item: {e}")
                    logger.error(traceback.format_exc())
                    self.stats['error_count'] += 1
                    
            except KeyboardInterrupt:
                logger.info("Worker shutdown requested")
                break
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}")
                logger.error(traceback.format_exc())
                # Brief pause before retrying
                await asyncio.sleep(1)
        
        logger.info("Attachment worker stopped")
    
    def _parse_queue_item(self, raw_data: bytes) -> Optional[EmailAttachmentData]:
        """Parse raw queue data into EmailAttachmentData object"""
        try:
            # Decode JSON data
            json_str = raw_data.decode('utf-8') if isinstance(raw_data, bytes) else raw_data
            data_dict = json.loads(json_str)
            
            # Create EmailAttachmentData object
            attachment_data = EmailAttachmentData.from_dict(data_dict)
            return attachment_data
            
        except Exception as e:
            logger.error(f"Failed to parse queue item: {e}")
            return None
    
    async def _process_attachment(self, attachment_data: EmailAttachmentData) -> bool:
        """
        Process a single attachment through the AI pipeline
        
        Args:
            attachment_data: EmailAttachmentData containing email and attachment info
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Create temporary file for the attachment
            temp_file_path = await self._save_temp_attachment(attachment_data)
            
            if temp_file_path is None:
                return False
            
            try:
                # Process through pipeline
                result = await self._run_pipeline(attachment_data, temp_file_path)
                
                # Save results
                await self._save_processing_results(attachment_data, result)
                
                end_time = asyncio.get_event_loop().time()
                logger.info(f"Successfully processed {attachment_data.attachment_filename} "
                           f"in {end_time - start_time:.2f} seconds")
                
                return True
                
            finally:
                # Clean up temporary file
                if temp_file_path and temp_file_path.exists():
                    temp_file_path.unlink()
                    
        except Exception as e:
            logger.error(f"Error processing attachment {attachment_data.attachment_filename}: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _save_temp_attachment(self, attachment_data: EmailAttachmentData) -> Optional[Path]:
        """Save attachment to temporary file for processing"""
        try:
            # Create unique temporary file
            file_ext = Path(attachment_data.attachment_filename).suffix
            temp_file = self.temp_dir / f"{attachment_data.task_id}_{uuid.uuid4().hex[:8]}{file_ext}"
            
            # Write attachment content to file
            temp_file.write_bytes(attachment_data.attachment_content)
            
            logger.debug(f"Saved attachment to temp file: {temp_file}")
            return temp_file
            
        except Exception as e:
            logger.error(f"Failed to save temp attachment: {e}")
            return None
    
    async def _run_pipeline(self, attachment_data: EmailAttachmentData, attachment_path: Path) -> Dict[str, Any]:
        """
        Run the AI pipeline for processing the attachment
        
        This is adapted from your pipeline pattern. Replace the placeholder code
        with your actual pipeline implementation.
        """
        
        # TODO: Replace this placeholder with your actual pipeline implementation
        # Here's the structure based on your example:
        
        retry_count = 0
        success = False
        pipeline_result = None
        
        while retry_count <= self.max_retries and not success:
            try:
                logger.info(f"Pipeline attempt {retry_count + 1}/{self.max_retries + 1} "
                           f"for {attachment_data.attachment_filename}")
                
                # TODO: Replace with your actual service initialization
                # session_service = InMemorySessionService()
                # artifact_service = InMemoryArtifactService()
                session_id = str(uuid.uuid4())
                
                # TODO: Replace with your actual session creation
                # await session_service.create_session(
                #     app_name=self.app_name,
                #     user_id=self.user_id,
                #     session_id=session_id
                # )
                
                # TODO: Replace with your actual runner initialization
                # runner = Runner(
                #     agent=main_pipeline_agent,
                #     app_name=self.app_name,
                #     session_service=session_service,
                #     artifact_service=artifact_service
                # )
                
                # Prepare the content for processing
                pipeline_input = await self._prepare_pipeline_input(attachment_data, attachment_path)
                
                # TODO: Replace with your actual pipeline execution
                # This is where you would run your pipeline with both email text and attachment
                pipeline_result = await self._execute_pipeline_placeholder(
                    attachment_data, pipeline_input, session_id
                )
                
                # TODO: Add your success validation logic here
                # For example, check for normalized coordinates as in your example:
                # bboxes = StateParser.get_bounding_boxes(final_state)
                # normalized_detected = any(...)
                
                success = True  # Replace with your actual success criteria
                
            except Exception as e:
                logger.error(f"Pipeline error (attempt {retry_count + 1}): {e}")
                retry_count += 1
                
                if retry_count > self.max_retries:
                    raise
                    
                # Brief pause before retry
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
        
        if not success:
            raise Exception("Pipeline failed after maximum retries")
        
        return pipeline_result or {}
    
    async def _prepare_pipeline_input(self, attachment_data: EmailAttachmentData, attachment_path: Path) -> Dict[str, Any]:
        """
        Prepare input for the pipeline including email text and attachment
        
        This creates the structure you need to send both email text and attachment
        data to your pipeline, along with MIME type information.
        """
        
        # Read attachment content for pipeline
        attachment_bytes = attachment_path.read_bytes()
        
        # Prepare the input structure
        pipeline_input = {
            # Email context (sent with every attachment)
            "email_context": {
                "email_id": attachment_data.email_id,
                "subject": attachment_data.email_subject,
                "sender": attachment_data.email_sender,
                "sender_email": attachment_data.email_sender_email,
                "content": attachment_data.email_content,  # Email text content
                "received_date": attachment_data.email_received_date
            },
            
            # Attachment information
            "attachment": {
                "task_id": attachment_data.task_id,
                "attachment_id": attachment_data.attachment_id,
                "filename": attachment_data.attachment_filename,
                "mime_type": attachment_data.attachment_mime_type,  # MIME type as requested
                "size": attachment_data.attachment_size,
                "content_bytes": attachment_bytes,
                "file_path": str(attachment_path)
            },
            
            # Processing metadata
            "processing": {
                "worker_id": f"{self.user_id}_{os.getpid()}",
                "started_at": datetime.now().isoformat(),
                "app_name": self.app_name
            }
        }
        
        logger.info(f"Prepared pipeline input for {attachment_data.attachment_filename}")
        logger.info(f"Email text length: {len(attachment_data.email_content)} chars")
        logger.info(f"Attachment MIME type: {attachment_data.attachment_mime_type}")
        logger.info(f"Attachment size: {attachment_data.attachment_size} bytes")
        
        return pipeline_input
    
    async def _execute_pipeline_placeholder(self, attachment_data: EmailAttachmentData, 
                                          pipeline_input: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """
        Placeholder for actual pipeline execution
        
        TODO: Replace this with your actual pipeline code.
        This should integrate with your existing pipeline that processes images/attachments.
        """
        
        # This is a placeholder - replace with your actual pipeline execution
        logger.info("PLACEHOLDER: Pipeline execution would happen here")
        logger.info(f"Processing attachment: {pipeline_input['attachment']['filename']}")
        logger.info(f"With email context: {pipeline_input['email_context']['subject']}")
        logger.info(f"MIME type: {pipeline_input['attachment']['mime_type']}")
        
        # TODO: Here's where you would integrate your actual pipeline:
        # 
        # if pipeline_input['attachment']['mime_type'].startswith('image/'):
        #     # Set the current image for processing
        #     ImageProcessor.set_current_image(pipeline_input['attachment']['file_path'])
        #     
        #     # Create the content message for your pipeline
        #     message = types.Content(
        #         role='user',
        #         parts=[types.Part(
        #             inline_data=types.Blob(
        #                 mime_type=pipeline_input['attachment']['mime_type'],
        #                 data=pipeline_input['attachment']['content_bytes']
        #             )
        #         )]
        #     )
        #     
        #     # Run your pipeline
        #     final_response = None
        #     for event in runner.run(
        #         user_id=self.user_id,
        #         session_id=session_id,
        #         new_message=message
        #     ):
        #         if event.is_final_response():
        #             final_response = event
        #             if event.content and event.content.parts:
        #                 logger.info(f"Final response: {event.content.parts[0].text}")
        #     
        #     # Get final session state
        #     session = await session_service.get_session(
        #         app_name=self.app_name,
        #         user_id=self.user_id,
        #         session_id=session_id
        #     )
        #     
        #     final_state = StateParser.parse_state(session.state)
        #     return {
        #         "final_response": final_response,
        #         "final_state": final_state,
        #         "processed_successfully": True
        #     }
        
        # Simulate processing time
        await asyncio.sleep(1)
        
        # Return placeholder result
        return {
            "status": "success",
            "attachment_filename": attachment_data.attachment_filename,
            "email_subject": attachment_data.email_subject,
            "mime_type": attachment_data.attachment_mime_type,
            "processed_at": datetime.now().isoformat(),
            "placeholder": True
        }
    
    async def _save_processing_results(self, attachment_data: EmailAttachmentData, result: Dict[str, Any]):
        """Save processing results to file or database"""
        try:
            # Create results directory
            results_dir = Path('processing_results')
            results_dir.mkdir(exist_ok=True)
            
            # Create result file
            result_filename = f"{attachment_data.task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            result_file = results_dir / result_filename
            
            # Prepare result data
            result_data = {
                "task_id": attachment_data.task_id,
                "email_info": {
                    "email_id": attachment_data.email_id,
                    "subject": attachment_data.email_subject,
                    "sender": attachment_data.email_sender,
                    "sender_email": attachment_data.email_sender_email,
                    "received_date": attachment_data.email_received_date
                },
                "attachment_info": {
                    "attachment_id": attachment_data.attachment_id,
                    "filename": attachment_data.attachment_filename,
                    "mime_type": attachment_data.attachment_mime_type,
                    "size": attachment_data.attachment_size
                },
                "processing_result": result,
                "processed_at": datetime.now().isoformat(),
                "worker_info": {
                    "worker_id": f"{self.user_id}_{os.getpid()}",
                    "app_name": self.app_name
                }
            }
            
            # Save to file
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved processing results to: {result_file}")
            
        except Exception as e:
            logger.error(f"Failed to save processing results: {e}")
    
    def _update_stats(self, success: bool):
        """Update worker statistics"""
        self.stats['processed_count'] += 1
        self.stats['last_processed_at'] = datetime.now().isoformat()
        
        if success:
            self.stats['success_count'] += 1
        else:
            self.stats['error_count'] += 1
        
        # Log stats every 10 processed items
        if self.stats['processed_count'] % 10 == 0:
            self._log_stats()
    
    def _log_stats(self):
        """Log current worker statistics"""
        logger.info("=== Worker Statistics ===")
        logger.info(f"Processed: {self.stats['processed_count']}")
        logger.info(f"Success: {self.stats['success_count']}")
        logger.info(f"Errors: {self.stats['error_count']}")
        
        if self.stats['processed_count'] > 0:
            success_rate = (self.stats['success_count'] / self.stats['processed_count']) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")
        
        logger.info(f"Started at: {self.stats['started_at']}")
        logger.info(f"Last processed: {self.stats['last_processed_at']}")
        logger.info("========================")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current worker statistics"""
        return self.stats.copy()


async def main():
    """Main entry point for the worker"""
    logger.info("Starting Email Attachment Worker")
    
    try:
        # Create and run the worker
        worker = AttachmentWorker()
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    # Run the worker
    asyncio.run(main())