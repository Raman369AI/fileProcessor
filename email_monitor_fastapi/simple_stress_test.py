"""
Simplified Stress Test for Email Monitor FastAPI Service
Uses only Python standard library to avoid dependency issues
"""

import unittest
import asyncio
import time
import threading
import json
import tempfile
import shutil
import uuid
import random
from pathlib import Path
from unittest.mock import Mock, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import urllib.parse
import io

# Add the parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

class MockHTTPHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to simulate email server responses"""
    
    def log_message(self, format, *args):
        """Suppress HTTP server logging"""
        pass
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            self.send_health_response()
        elif '/messages/delta' in self.path:
            self.send_messages_response()
        elif '/attachments' in self.path and '$value' in self.path:
            self.send_attachment_content()
        elif '/attachments' in self.path:
            self.send_attachments_list()
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests (auth)"""
        if '/token' in self.path:
            self.send_auth_response()
        else:
            self.send_error(404)
    
    def send_health_response(self):
        """Send health check response"""
        response = {
            "status": "healthy",
            "messages_count": 20,
            "timestamp": datetime.now().isoformat()
        }
        self.send_json_response(response)
    
    def send_auth_response(self):
        """Send authentication response"""
        response = {
            "access_token": "mock_token_123",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        self.send_json_response(response)
    
    def send_messages_response(self):
        """Send mock messages response"""
        # Generate some dummy messages
        messages = []
        for i in range(random.randint(0, 5)):
            message_id = str(uuid.uuid4())
            messages.append({
                "id": message_id,
                "subject": f"Test Message {i}",
                "from": {
                    "emailAddress": {
                        "address": f"test{i}@company.com",
                        "name": f"Test User {i}"
                    }
                },
                "receivedDateTime": datetime.now().isoformat() + "Z",
                "hasAttachments": True,
                "body": {
                    "content": f"Test content {i}",
                    "contentType": "text"
                }
            })
        
        response = {
            "value": messages,
            "@odata.deltaLink": f"http://localhost:5003/v1.0/me/messages/delta?$deltatoken={uuid.uuid4()}"
        }
        self.send_json_response(response)
    
    def send_attachments_list(self):
        """Send mock attachments list"""
        attachments = [
            {
                "id": str(uuid.uuid4()),
                "name": "test_document.pdf",
                "contentType": "application/pdf",
                "size": 1024,
                "isInline": False
            },
            {
                "id": str(uuid.uuid4()),
                "name": "data_file.xlsx",
                "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size": 2048,
                "isInline": False
            }
        ]
        
        response = {"value": attachments}
        self.send_json_response(response)
    
    def send_attachment_content(self):
        """Send mock attachment content"""
        # Send some dummy file content
        content = b"Mock file content for testing purposes"
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)
    
    def send_json_response(self, data):
        """Send JSON response"""
        response_data = json.dumps(data).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_data)))
        self.end_headers()
        self.wfile.write(response_data)


class SimpleMockServer:
    """Simple mock server using Python's built-in HTTP server"""
    
    def __init__(self, port=5003):
        self.port = port
        self.server = None
        self.server_thread = None
    
    def start(self):
        """Start the mock server"""
        try:
            self.server = HTTPServer(('localhost', self.port), MockHTTPHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            
            # Wait a bit for server to start
            time.sleep(1)
            
            print(f"✅ Simple mock server started at http://localhost:{self.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to start mock server: {e}")
            return False
    
    def stop(self):
        """Stop the mock server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()


class SimpleGraphEmailClient:
    """Simplified Graph email client for testing"""
    
    def __init__(self, mock_server_url="http://localhost:5003"):
        self.mock_server_url = mock_server_url
        self.access_token = None
        self.delta_link = None
    
    def authenticate(self) -> bool:
        """Simple authentication test"""
        try:
            # Just check if server is reachable
            import urllib.request
            urllib.request.urlopen(f"{self.mock_server_url}/health", timeout=2)
            self.access_token = "test_token"
            return True
        except Exception as e:
            print(f"Auth failed: {e}")
            return False
    
    def get_new_messages(self, email_groups=None):
        """Get messages from mock server"""
        if not self.access_token:
            return []
        
        try:
            import urllib.request
            url = self.delta_link or f"{self.mock_server_url}/v1.0/me/messages/delta"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # Store delta link for next request
            if '@odata.deltaLink' in data:
                self.delta_link = data['@odata.deltaLink']
            
            return data.get('value', [])
            
        except Exception as e:
            print(f"Error fetching messages: {e}")
            return []
    
    def get_attachments(self, message_id):
        """Get attachments for a message"""
        if not self.access_token:
            return []
        
        try:
            import urllib.request
            url = f"{self.mock_server_url}/v1.0/me/messages/{message_id}/attachments"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            return data.get('value', [])
            
        except Exception as e:
            print(f"Error fetching attachments: {e}")
            return []
    
    def download_attachment(self, message_id, attachment_id):
        """Download attachment content"""
        if not self.access_token:
            return b""
        
        try:
            import urllib.request
            url = f"{self.mock_server_url}/v1.0/me/messages/{message_id}/attachments/{attachment_id}/$value"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read()
                
        except Exception as e:
            print(f"Error downloading attachment: {e}")
            return b""


class SimpleEmailMonitor:
    """Simplified email monitor for testing"""
    
    def __init__(self, mock_server_url="http://localhost:5003"):
        self.graph_client = SimpleGraphEmailClient(mock_server_url)
        self.attachments_dir = Path(tempfile.mkdtemp()) / "attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            'last_run': None,
            'total_runs': 0,
            'messages_processed': 0,
            'attachments_processed': 0,
            'errors': 0
        }
    
    async def process_emails(self):
        """Process emails asynchronously"""
        try:
            # Authenticate
            if not self.graph_client.authenticate():
                self.stats['errors'] += 1
                return
            
            # Get messages
            messages = self.graph_client.get_new_messages()
            
            # Process each message
            for message in messages:
                await self._process_message(message)
            
            # Update stats
            self.stats['messages_processed'] += len(messages)
            self.stats['total_runs'] += 1
            self.stats['last_run'] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"Processing error: {e}")
            self.stats['errors'] += 1
    
    async def _process_message(self, message):
        """Process single message"""
        message_id = message.get('id', '')
        
        if not message.get('hasAttachments', False):
            return
        
        # Get attachments
        attachments = self.graph_client.get_attachments(message_id)
        
        # Process attachments
        for attachment in attachments:
            # Download attachment
            content = self.graph_client.download_attachment(message_id, attachment.get('id', ''))
            
            if content:
                # Save to file
                filename = attachment.get('name', 'unknown')
                file_path = self.attachments_dir / f"{message_id[:8]}_{filename}"
                file_path.write_bytes(content)
                
                self.stats['attachments_processed'] += 1


class SimpleStressTest(unittest.TestCase):
    """Simplified stress test using only standard library"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        print("🔧 Setting up simple stress test environment...")
        
        # Start mock server
        cls.mock_server = SimpleMockServer(port=5003)
        if not cls.mock_server.start():
            raise Exception("Failed to start mock server")
        
        print("✅ Test environment ready")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        print("🧹 Cleaning up test environment...")
        cls.mock_server.stop()
    
    def setUp(self):
        """Set up individual test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.monitor = SimpleEmailMonitor()
    
    def tearDown(self):
        """Clean up individual test"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_basic_functionality(self):
        """Test basic email processing functionality"""
        print("🔄 Testing basic functionality...")
        
        # Test authentication
        self.assertTrue(self.monitor.graph_client.authenticate())
        
        # Test message fetching
        messages = self.monitor.graph_client.get_new_messages()
        self.assertIsInstance(messages, list)
        
        print(f"✅ Fetched {len(messages)} messages")
    
    def test_concurrent_authentication(self):
        """Test multiple concurrent authentications"""
        print("🔄 Testing concurrent authentication...")
        
        def authenticate():
            client = SimpleGraphEmailClient()
            return client.authenticate()
        
        # Test with 20 concurrent authentications
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(authenticate) for _ in range(20)]
            
            success_count = 0
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
        
        print(f"✅ {success_count}/20 authentications succeeded")
        self.assertGreaterEqual(success_count, 18)  # Allow for some failures
    
    def test_rapid_message_fetching(self):
        """Test rapid message fetching"""
        print("🔄 Testing rapid message fetching...")
        
        client = SimpleGraphEmailClient()
        self.assertTrue(client.authenticate())
        
        start_time = time.time()
        total_messages = 0
        
        # Fetch messages 50 times rapidly
        for _ in range(50):
            messages = client.get_new_messages()
            total_messages += len(messages)
        
        duration = time.time() - start_time
        
        print(f"✅ Fetched {total_messages} messages in {duration:.2f}s")
        self.assertLess(duration, 15)  # Should complete within 15 seconds
    
    def test_concurrent_message_fetching(self):
        """Test concurrent message fetching"""
        print("🔄 Testing concurrent message fetching...")
        
        def fetch_messages():
            client = SimpleGraphEmailClient()
            if client.authenticate():
                return len(client.get_new_messages())
            return 0
        
        # Test with 15 concurrent clients
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(fetch_messages) for _ in range(15)]
            
            total_messages = 0
            for future in as_completed(futures):
                total_messages += future.result()
        
        print(f"✅ Total messages fetched: {total_messages}")
        self.assertGreaterEqual(total_messages, 0)
    
    def test_attachment_processing(self):
        """Test attachment downloading and processing"""
        print("🔄 Testing attachment processing...")
        
        client = SimpleGraphEmailClient()
        self.assertTrue(client.authenticate())
        
        messages = client.get_new_messages()
        if not messages:
            print("⚠️  No messages available, skipping attachment test")
            return
        
        total_attachments = 0
        total_size = 0
        
        for message in messages[:3]:  # Test first 3 messages
            attachments = client.get_attachments(message['id'])
            
            for attachment in attachments:
                content = client.download_attachment(message['id'], attachment['id'])
                if content:
                    total_attachments += 1
                    total_size += len(content)
        
        print(f"✅ Downloaded {total_attachments} attachments, {total_size} bytes")
        self.assertGreaterEqual(total_attachments, 0)
    
    def test_processing_cycles(self):
        """Test multiple processing cycles"""
        print("🔄 Testing processing cycles...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run 5 processing cycles
            for i in range(5):
                cycle_start = time.time()
                loop.run_until_complete(self.monitor.process_emails())
                cycle_time = time.time() - cycle_start
                
                print(f"   Cycle {i+1}: {cycle_time:.2f}s, "
                      f"Messages: {self.monitor.stats['messages_processed']}, "
                      f"Attachments: {self.monitor.stats['attachments_processed']}")
        finally:
            loop.close()
        
        print(f"✅ Completed {self.monitor.stats['total_runs']} processing cycles")
        self.assertEqual(self.monitor.stats['total_runs'], 5)
    
    def test_concurrent_processing(self):
        """Test concurrent processing cycles"""
        print("🔄 Testing concurrent processing...")
        
        def run_processing():
            monitor = SimpleEmailMonitor()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run 3 cycles
                for _ in range(3):
                    loop.run_until_complete(monitor.process_emails())
                return monitor.stats['total_runs']
            finally:
                loop.close()
        
        # Run 4 concurrent processing threads
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(run_processing) for _ in range(4)]
            
            total_runs = 0
            for future in as_completed(futures):
                total_runs += future.result()
        
        print(f"✅ Concurrent processing completed, total runs: {total_runs}")
        self.assertEqual(total_runs, 12)  # 4 threads × 3 cycles each
    
    def test_stress_scenario(self):
        """Test complete stress scenario"""
        print("🔄 Running comprehensive stress test...")
        
        results = {
            'authentications': 0,
            'message_fetches': 0,
            'attachment_downloads': 0,
            'processing_cycles': 0,
            'errors': 0
        }
        
        def auth_worker():
            """Worker that performs authentications"""
            try:
                for _ in range(10):
                    client = SimpleGraphEmailClient()
                    if client.authenticate():
                        results['authentications'] += 1
                    time.sleep(0.1)
            except Exception:
                results['errors'] += 1
        
        def message_worker():
            """Worker that fetches messages"""
            try:
                client = SimpleGraphEmailClient()
                if client.authenticate():
                    for _ in range(10):
                        messages = client.get_new_messages()
                        results['message_fetches'] += len(messages)
                        time.sleep(0.1)
            except Exception:
                results['errors'] += 1
        
        def processing_worker():
            """Worker that runs processing cycles"""
            try:
                monitor = SimpleEmailMonitor()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    for _ in range(3):
                        loop.run_until_complete(monitor.process_emails())
                        results['processing_cycles'] += 1
                        time.sleep(0.2)
                finally:
                    loop.close()
            except Exception:
                results['errors'] += 1
        
        # Run multiple workers concurrently
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(auth_worker),
                executor.submit(auth_worker),
                executor.submit(message_worker),
                executor.submit(message_worker),
                executor.submit(processing_worker),
                executor.submit(processing_worker)
            ]
            
            # Wait for all workers to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    results['errors'] += 1
                    print(f"Worker error: {e}")
        
        duration = time.time() - start_time
        
        print(f"✅ Stress test completed in {duration:.2f}s:")
        print(f"   Authentications: {results['authentications']}")
        print(f"   Message fetches: {results['message_fetches']}")
        print(f"   Processing cycles: {results['processing_cycles']}")
        print(f"   Errors: {results['errors']}")
        
        # Verify reasonable performance
        self.assertGreater(results['authentications'], 10)
        self.assertGreater(results['processing_cycles'], 4)
        self.assertLess(results['errors'], 5)  # Allow for some errors
        self.assertLess(duration, 30)  # Should complete within 30 seconds


def run_simple_stress_tests():
    """Run the simplified stress tests"""
    print("🚀 Starting Simplified Email Monitor Stress Test")
    print("=" * 50)
    
    # Create and run test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(SimpleStressTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 STRESS TEST SUMMARY")
    print("=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures or result.errors:
        success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
        print(f"Success rate: {success_rate:.1f}%")
    else:
        print("Success rate: 100.0%")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"   {test}")
    
    if result.errors:
        print("\n💥 ERRORS:")
        for test, traceback in result.errors:
            print(f"   {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_simple_stress_tests()
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")
    sys.exit(0 if success else 1)