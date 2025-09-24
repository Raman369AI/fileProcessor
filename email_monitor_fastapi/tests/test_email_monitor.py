#!/usr/bin/env python3
"""
Comprehensive test suite for Email Monitor FastAPI Service

Tests cover:
- Email monitoring functionality
- Redis queue operations
- Worker management
- API endpoints
- Error handling
- Integration scenarios
"""

import os
import sys
import pytest
import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from fastapi import FastAPI
import redis

# Import modules to test
from app.redis_queue import RedisEmailQueue, EmailAttachmentData
from attachment_worker import AttachmentWorker
from worker_runner import WorkerManager, FastAPIWorkerManager


class TestEmailAttachmentData:
    """Test the EmailAttachmentData dataclass"""
    
    def test_create_email_attachment_data(self):
        """Test creating EmailAttachmentData object"""
        data = EmailAttachmentData(
            task_id="test_123",
            email_id="email_456",
            email_subject="Test Subject",
            email_sender="John Doe",
            email_sender_email="john@example.com",
            email_content="Test email content",
            email_received_date="2023-01-01T10:00:00Z",
            attachment_id="attach_789",
            attachment_filename="test.pdf",
            attachment_content=b"test content",
            attachment_mime_type="application/pdf",
            attachment_size=12
        )
        
        assert data.task_id == "test_123"
        assert data.email_subject == "Test Subject"
        assert data.attachment_size == 12
        assert data.created_at is not None
    
    def test_to_dict_conversion(self):
        """Test converting EmailAttachmentData to dictionary"""
        content = b"test attachment content"
        data = EmailAttachmentData(
            task_id="test_123",
            email_id="email_456",
            email_subject="Test Subject",
            email_sender="John Doe",
            email_sender_email="john@example.com",
            email_content="Test email content",
            email_received_date="2023-01-01T10:00:00Z",
            attachment_id="attach_789",
            attachment_filename="test.pdf",
            attachment_content=content,
            attachment_mime_type="application/pdf",
            attachment_size=len(content)
        )
        
        data_dict = data.to_dict()
        
        assert "attachment_content_b64" in data_dict
        assert data_dict["task_id"] == "test_123"
        assert data_dict["email_subject"] == "Test Subject"
        
        # Test round-trip conversion
        restored_data = EmailAttachmentData.from_dict(data_dict)
        assert restored_data.attachment_content == content
        assert restored_data.task_id == data.task_id


class TestRedisEmailQueue:
    """Test Redis queue operations"""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        with patch('app.redis_queue.redis.Redis') as mock_redis_class:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.llen.return_value = 0
            mock_client.lpush.return_value = 1
            mock_client.info.return_value = {
                'redis_version': '6.0.0',
                'used_memory': 1024,
                'used_memory_human': '1K',
                'connected_clients': 1,
                'total_commands_processed': 100
            }
            mock_redis_class.return_value = mock_client
            yield mock_client
    
    def test_redis_queue_initialization(self, mock_redis):
        """Test Redis queue initialization"""
        with patch.dict(os.environ, {
            'REDIS_HOST': 'localhost',
            'REDIS_PORT': '6379',
            'EMAIL_QUEUE_NAME': 'test_queue'
        }):
            queue = RedisEmailQueue()
            assert queue.queue_name == 'test_queue'
            assert queue.redis_host == 'localhost'
            mock_redis.ping.assert_called_once()
    
    def test_enqueue_attachment(self, mock_redis):
        """Test enqueuing an attachment"""
        with patch.dict(os.environ, {'MAX_ATTACHMENT_SIZE': '1048576'}):  # 1MB
            queue = RedisEmailQueue()
            
            attachment_data = EmailAttachmentData(
                task_id="test_123",
                email_id="email_456",
                email_subject="Test Subject",
                email_sender="John Doe",
                email_sender_email="john@example.com",
                email_content="Test email content",
                email_received_date="2023-01-01T10:00:00Z",
                attachment_id="attach_789",
                attachment_filename="test.pdf",
                attachment_content=b"small content",
                attachment_mime_type="application/pdf",
                attachment_size=13
            )
            
            result = queue.enqueue_attachment(attachment_data)
            
            assert result is True
            mock_redis.lpush.assert_called_once()
    
    def test_enqueue_large_attachment_rejected(self, mock_redis):
        """Test that large attachments are rejected"""
        with patch.dict(os.environ, {'MAX_ATTACHMENT_SIZE': '10'}):  # Very small limit
            queue = RedisEmailQueue()
            
            attachment_data = EmailAttachmentData(
                task_id="test_123",
                email_id="email_456",
                email_subject="Test Subject",
                email_sender="John Doe",
                email_sender_email="john@example.com",
                email_content="Test email content",
                email_received_date="2023-01-01T10:00:00Z",
                attachment_id="attach_789",
                attachment_filename="test.pdf",
                attachment_content=b"this is too large content",
                attachment_mime_type="application/pdf",
                attachment_size=25
            )
            
            result = queue.enqueue_attachment(attachment_data)
            
            assert result is False
            mock_redis.lpush.assert_not_called()
    
    def test_queue_info(self, mock_redis):
        """Test getting queue information"""
        queue = RedisEmailQueue()
        info = queue.get_queue_info()
        
        assert "queue_name" in info
        assert "queue_length" in info
        assert "redis_info" in info
        mock_redis.llen.assert_called()
        mock_redis.info.assert_called()
    
    def test_peek_queue(self, mock_redis):
        """Test peeking at queue items"""
        # Mock queue data
        mock_item = json.dumps({
            "task_id": "test_123",
            "attachment_filename": "test.pdf",
            "attachment_content_b64": "dGVzdA=="  # base64 for "test"
        })
        mock_redis.lrange.return_value = [mock_item.encode()]
        
        queue = RedisEmailQueue()
        items = queue.peek_queue(1)
        
        assert len(items) == 1
        assert items[0]["task_id"] == "test_123"
        assert "attachment_content_b64" in items[0]
        mock_redis.lrange.assert_called_once()


class TestAttachmentWorker:
    """Test attachment worker functionality"""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for worker"""
        with patch('attachment_worker.redis.Redis') as mock_redis_class:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.brpop.return_value = None  # Default no items
            mock_redis_class.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_worker_initialization(self, mock_redis_client, temp_dir):
        """Test worker initialization"""
        with patch.dict(os.environ, {
            'PIPELINE_APP_NAME': 'TEST_APP',
            'PIPELINE_USER_ID': 'test_user',
            'WORKER_TEMP_DIR': str(temp_dir)
        }):
            worker = AttachmentWorker()
            
            assert worker.app_name == 'TEST_APP'
            assert worker.user_id == 'test_user'
            assert worker.temp_dir == temp_dir
            mock_redis_client.ping.assert_called_once()
    
    def test_parse_queue_item(self, mock_redis_client, temp_dir):
        """Test parsing queue items"""
        with patch.dict(os.environ, {'WORKER_TEMP_DIR': str(temp_dir)}):
            worker = AttachmentWorker()
            
            # Create test queue item
            attachment_data = EmailAttachmentData(
                task_id="test_123",
                email_id="email_456",
                email_subject="Test Subject",
                email_sender="John Doe",
                email_sender_email="john@example.com",
                email_content="Test email content",
                email_received_date="2023-01-01T10:00:00Z",
                attachment_id="attach_789",
                attachment_filename="test.pdf",
                attachment_content=b"test content",
                attachment_mime_type="application/pdf",
                attachment_size=12
            )
            
            json_data = json.dumps(attachment_data.to_dict())
            raw_data = json_data.encode('utf-8')
            
            parsed_data = worker._parse_queue_item(raw_data)
            
            assert parsed_data is not None
            assert parsed_data.task_id == "test_123"
            assert parsed_data.email_subject == "Test Subject"
            assert parsed_data.attachment_content == b"test content"
    
    @pytest.mark.asyncio
    async def test_save_temp_attachment(self, mock_redis_client, temp_dir):
        """Test saving attachment to temporary file"""
        with patch.dict(os.environ, {'WORKER_TEMP_DIR': str(temp_dir)}):
            worker = AttachmentWorker()
            
            attachment_data = EmailAttachmentData(
                task_id="test_123",
                email_id="email_456",
                email_subject="Test Subject",
                email_sender="John Doe",
                email_sender_email="john@example.com",
                email_content="Test email content",
                email_received_date="2023-01-01T10:00:00Z",
                attachment_id="attach_789",
                attachment_filename="test.pdf",
                attachment_content=b"test file content",
                attachment_mime_type="application/pdf",
                attachment_size=17
            )
            
            temp_file = await worker._save_temp_attachment(attachment_data)
            
            assert temp_file is not None
            assert temp_file.exists()
            assert temp_file.read_bytes() == b"test file content"
            assert temp_file.suffix == ".pdf"
    
    @pytest.mark.asyncio
    async def test_prepare_pipeline_input(self, mock_redis_client, temp_dir):
        """Test preparing input for pipeline"""
        with patch.dict(os.environ, {
            'WORKER_TEMP_DIR': str(temp_dir),
            'PIPELINE_APP_NAME': 'TEST_APP'
        }):
            worker = AttachmentWorker()
            
            attachment_data = EmailAttachmentData(
                task_id="test_123",
                email_id="email_456",
                email_subject="Test Subject",
                email_sender="John Doe",
                email_sender_email="john@example.com",
                email_content="This is the email content",
                email_received_date="2023-01-01T10:00:00Z",
                attachment_id="attach_789",
                attachment_filename="image.jpg",
                attachment_content=b"fake image content",
                attachment_mime_type="image/jpeg",
                attachment_size=18
            )
            
            # Create temp file
            temp_file = temp_dir / "test_image.jpg"
            temp_file.write_bytes(attachment_data.attachment_content)
            
            pipeline_input = await worker._prepare_pipeline_input(attachment_data, temp_file)
            
            # Verify structure
            assert "email_context" in pipeline_input
            assert "attachment" in pipeline_input
            assert "processing" in pipeline_input
            
            # Verify email context
            email_ctx = pipeline_input["email_context"]
            assert email_ctx["subject"] == "Test Subject"
            assert email_ctx["content"] == "This is the email content"
            assert email_ctx["sender"] == "John Doe"
            
            # Verify attachment info
            attachment_info = pipeline_input["attachment"]
            assert attachment_info["filename"] == "image.jpg"
            assert attachment_info["mime_type"] == "image/jpeg"
            assert attachment_info["size"] == 18
            assert attachment_info["content_bytes"] == b"fake image content"


class TestWorkerManager:
    """Test worker manager functionality"""
    
    @pytest.fixture
    def mock_process(self):
        """Mock multiprocessing.Process"""
        with patch('worker_runner.mp.Process') as mock_process_class:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.is_alive.return_value = True
            mock_process_class.return_value = mock_process
            yield mock_process
    
    def test_worker_manager_init(self):
        """Test worker manager initialization"""
        with patch.dict(os.environ, {'MAX_CONCURRENT_WORKERS': '3'}):
            manager = WorkerManager()
            assert manager.num_workers == 3
            assert len(manager.workers) == 0
            assert manager.running is False
    
    @pytest.mark.asyncio
    async def test_start_workers(self, mock_process):
        """Test starting worker processes"""
        manager = WorkerManager(num_workers=2)
        
        await manager.start_workers()
        
        assert len(manager.workers) == 2
        assert manager.running is True
        assert manager.stats['workers_started'] == 2
        assert mock_process.start.call_count == 2
    
    @pytest.mark.asyncio
    async def test_stop_workers(self, mock_process):
        """Test stopping worker processes"""
        manager = WorkerManager(num_workers=1)
        
        # Start workers first
        await manager.start_workers()
        assert manager.running is True
        
        # Stop workers
        await manager.stop_workers()
        
        assert manager.running is False
        assert len(manager.workers) == 0
        mock_process.terminate.assert_called_once()
        mock_process.join.assert_called()
    
    def test_get_stats(self, mock_process):
        """Test getting worker statistics"""
        manager = WorkerManager(num_workers=2)
        manager.workers = [mock_process, mock_process]  # Simulate 2 workers
        
        stats = manager.get_stats()
        
        assert "num_workers_configured" in stats
        assert "active_workers" in stats
        assert "worker_pids" in stats
        assert stats["num_workers_configured"] == 2
        assert stats["active_workers"] == 2  # Both are alive
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_process):
        """Test worker health check"""
        manager = WorkerManager(num_workers=1)
        manager.workers = [mock_process]
        
        health = await manager.health_check()
        
        assert "manager_running" in health
        assert "workers_running" in health
        assert "worker_details" in health
        assert len(health["worker_details"]) == 1
        assert health["workers_running"] == 1


class TestFastAPIIntegration:
    """Test FastAPI endpoints and integration"""
    
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app"""
        from app.main_with_workers import app
        return app
    
    @pytest.fixture
    def client(self, test_app):
        """Create test client"""
        return TestClient(test_app)
    
    @pytest.fixture
    def mock_monitor(self):
        """Mock the email monitor"""
        with patch('app.main_with_workers.monitor') as mock_monitor:
            mock_monitor.stats = {
                'last_run': '2023-01-01T10:00:00',
                'total_runs': 10,
                'messages_processed': 5,
                'attachments_processed': 15,
                'errors': 0
            }
            mock_monitor.email_groups = ['test@example.com']
            mock_monitor.attachments_dir = Path('/tmp/test')
            mock_monitor.file_types = ['.pdf', '.docx']
            mock_monitor.use_redis_queue = True
            mock_monitor.redis_queue = None
            mock_monitor.graph_client = None
            yield mock_monitor
    
    @pytest.fixture
    def mock_worker_manager(self):
        """Mock the worker manager"""
        with patch('app.main_with_workers.worker_manager') as mock_wm:
            mock_wm.get_stats.return_value = {
                'processed_count': 100,
                'success_count': 95,
                'error_count': 5,
                'active_workers': 2
            }
            mock_wm.health_check.return_value = {
                'manager_running': True,
                'workers_running': 2,
                'workers_healthy': 2
            }
            yield mock_wm
    
    def test_dashboard_endpoint(self, client, mock_monitor, mock_worker_manager):
        """Test dashboard endpoint"""
        response = client.get("/")
        assert response.status_code == 200
    
    def test_status_endpoint(self, client, mock_monitor, mock_worker_manager):
        """Test status API endpoint"""
        response = client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "stats" in data
        assert "config" in data
        assert "attachment_workers" in data
        assert data["status"] == "running"
    
    def test_worker_stats_endpoint(self, client, mock_monitor, mock_worker_manager):
        """Test worker stats endpoint"""
        response = client.get("/worker-stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "processed_count" in data
        assert "active_workers" in data
        assert data["processed_count"] == 100
    
    def test_worker_health_endpoint(self, client, mock_monitor, mock_worker_manager):
        """Test worker health endpoint"""
        response = client.get("/worker-health")
        assert response.status_code == 200
        
        data = response.json()
        assert "manager_running" in data
        assert "workers_running" in data
        assert data["workers_running"] == 2
    
    def test_system_overview_endpoint(self, client, mock_monitor, mock_worker_manager):
        """Test system overview endpoint"""
        response = client.get("/system-overview")
        assert response.status_code == 200
        
        data = response.json()
        assert "email_monitor" in data
        assert "attachment_workers" in data
        assert "system_info" in data
        
        system_info = data["system_info"]
        assert system_info["integrated_workers"] is True
        assert system_info["total_components"] == 2
    
    def test_process_now_endpoint(self, client, mock_monitor, mock_worker_manager):
        """Test manual processing trigger"""
        response = client.post("/process-now")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "immediately" in data["message"]


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_redis_connection_failure(self):
        """Test handling of Redis connection failures"""
        with patch('app.redis_queue.redis.Redis') as mock_redis_class:
            mock_client = Mock()
            mock_client.ping.side_effect = Exception("Connection failed")
            mock_redis_class.return_value = mock_client
            
            with pytest.raises(Exception):
                RedisEmailQueue()
    
    def test_invalid_queue_item_parsing(self):
        """Test handling of invalid queue items"""
        with patch('attachment_worker.redis.Redis'):
            worker = AttachmentWorker()
            
            # Test invalid JSON
            result = worker._parse_queue_item(b"invalid json")
            assert result is None
            
            # Test missing required fields
            incomplete_data = json.dumps({"task_id": "123"})
            result = worker._parse_queue_item(incomplete_data.encode())
            assert result is None
    
    @pytest.mark.asyncio
    async def test_worker_process_attachment_failure(self):
        """Test worker handling of attachment processing failures"""
        with patch('attachment_worker.redis.Redis'):
            worker = AttachmentWorker()
            
            # Create attachment data with invalid file path
            attachment_data = EmailAttachmentData(
                task_id="test_123",
                email_id="email_456", 
                email_subject="Test Subject",
                email_sender="John Doe",
                email_sender_email="john@example.com",
                email_content="Test email content",
                email_received_date="2023-01-01T10:00:00Z",
                attachment_id="attach_789",
                attachment_filename="test.pdf",
                attachment_content=b"test content",
                attachment_mime_type="application/pdf",
                attachment_size=12
            )
            
            # Mock temp file creation to fail
            with patch.object(worker, '_save_temp_attachment', return_value=None):
                result = await worker._process_attachment(attachment_data)
                assert result is False


class TestIntegrationScenarios:
    """Test complete integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_email_processing_workflow(self):
        """Test complete workflow from email to worker processing"""
        # This would be a comprehensive integration test
        # covering email ingestion -> queue -> worker processing
        pass
    
    @pytest.mark.asyncio 
    async def test_worker_restart_scenario(self):
        """Test worker restart and recovery scenarios"""
        with patch('worker_runner.mp.Process') as mock_process_class:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.is_alive.return_value = True
            mock_process_class.return_value = mock_process
            
            manager = WorkerManager(num_workers=1)
            
            # Start workers
            await manager.start_workers()
            assert len(manager.workers) == 1
            
            # Simulate worker death
            mock_process.is_alive.return_value = False
            
            # This would trigger restart in monitor_workers
            # (simplified test - in reality would need async monitoring)
            dead_workers = [i for i, w in enumerate(manager.workers) if not w.is_alive()]
            assert len(dead_workers) == 1
    
    def test_redis_queue_full_scenario(self):
        """Test behavior when Redis queue is full"""
        with patch('app.redis_queue.redis.Redis') as mock_redis_class:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.llen.return_value = 1000  # Queue is full
            mock_redis_class.return_value = mock_client
            
            with patch.dict(os.environ, {'MAX_QUEUE_SIZE': '1000'}):
                queue = RedisEmailQueue()
                
                attachment_data = EmailAttachmentData(
                    task_id="test_123",
                    email_id="email_456",
                    email_subject="Test Subject", 
                    email_sender="John Doe",
                    email_sender_email="john@example.com",
                    email_content="Test email content",
                    email_received_date="2023-01-01T10:00:00Z",
                    attachment_id="attach_789",
                    attachment_filename="test.pdf",
                    attachment_content=b"test content",
                    attachment_mime_type="application/pdf",
                    attachment_size=12
                )
                
                result = queue.enqueue_attachment(attachment_data)
                assert result is False  # Should reject when queue is full


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])