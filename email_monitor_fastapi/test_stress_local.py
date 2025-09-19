"""
Comprehensive Stress Test for Local Email Monitor FastAPI Service

This test suite performs stress testing on the email monitoring service
using a local mock server and unittest framework.
"""

import unittest
import asyncio
import time
import threading
import requests
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os

# Add the app directory to path
sys.path.append(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import our modules
from mock_email_server import MockEmailServer
from app.main_local import EmailMonitor, MockGraphEmailClient, app
from fastapi.testclient import TestClient


class EmailMonitorStressTest(unittest.TestCase):
    """Comprehensive stress test suite for email monitoring service"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment - start mock server"""
        print("🔧 Setting up stress test environment...")
        
        # Start mock email server
        cls.mock_server = MockEmailServer(port=5002)  # Use different port for testing
        cls.server_thread = cls.mock_server.start_server()
        
        # Wait for server to be ready
        cls._wait_for_server("http://localhost:5002")
        
        # Create test client for FastAPI
        cls.client = TestClient(app)
        
        print("✅ Test environment ready")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        print("🧹 Cleaning up test environment...")
        # Note: Mock server runs in daemon thread, will be cleaned up automatically
    
    @staticmethod
    def _wait_for_server(url: str, timeout: int = 10):
        """Wait for server to be ready"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{url}/health", timeout=1)
                if response.status_code == 200:
                    print(f"✅ Server at {url} is ready")
                    return
            except:
                pass
            time.sleep(0.1)
        raise Exception(f"Server at {url} not ready within {timeout} seconds")
    
    def setUp(self):
        """Set up individual test"""
        # Create temporary directory for each test
        self.temp_dir = Path(tempfile.mkdtemp())
        self.monitor = EmailMonitor(mock_server_url="http://localhost:5002")
        # Override attachments directory to use temp dir
        self.monitor.attachments_dir = self.temp_dir / "attachments"
        self.monitor.attachments_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Clean up individual test"""
        # Clean up temporary directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


class TestMockServerStress(EmailMonitorStressTest):
    """Test mock server under stress conditions"""
    
    def test_concurrent_authentication_requests(self):
        """Test multiple concurrent authentication requests"""
        print("🔄 Testing concurrent authentication...")
        
        def authenticate():
            client = MockGraphEmailClient(mock_server_url="http://localhost:5002")
            return client.authenticate()
        
        # Test with 50 concurrent authentication requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(authenticate) for _ in range(50)]
            
            success_count = 0
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
        
        # All authentications should succeed
        self.assertEqual(success_count, 50)
        print(f"✅ {success_count}/50 authentications succeeded")
    
    def test_rapid_message_fetching(self):
        """Test rapid consecutive message fetching"""
        print("🔄 Testing rapid message fetching...")
        
        client = MockGraphEmailClient(mock_server_url="http://localhost:5002")
        self.assertTrue(client.authenticate())
        
        # Fetch messages rapidly 100 times
        start_time = time.time()
        total_messages = 0
        
        for i in range(100):
            messages = client.get_new_messages()
            total_messages += len(messages)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Fetched {total_messages} messages in {duration:.2f}s ({total_messages/duration:.1f} msg/s)")
        self.assertLess(duration, 30)  # Should complete within 30 seconds
    
    def test_concurrent_message_fetching(self):
        """Test concurrent message fetching from multiple clients"""
        print("🔄 Testing concurrent message fetching...")
        
        def fetch_messages():
            client = MockGraphEmailClient(mock_server_url="http://localhost:5002")
            client.authenticate()
            messages = client.get_new_messages()
            return len(messages)
        
        # Test with 20 concurrent clients
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_messages) for _ in range(20)]
            
            total_messages = 0
            for future in as_completed(futures):
                total_messages += future.result()
        
        print(f"✅ Total messages fetched by all clients: {total_messages}")
        self.assertGreater(total_messages, 0)
    
    def test_attachment_download_stress(self):
        """Test downloading attachments under stress"""
        print("🔄 Testing attachment download stress...")
        
        client = MockGraphEmailClient(mock_server_url="http://localhost:5002")
        self.assertTrue(client.authenticate())
        
        messages = client.get_new_messages()
        if not messages:
            self.skipTest("No messages available for attachment testing")
        
        # Find messages with attachments
        messages_with_attachments = [m for m in messages if m.get('hasAttachments', False)]
        if not messages_with_attachments:
            self.skipTest("No messages with attachments available")
        
        download_count = 0
        total_size = 0
        
        for message in messages_with_attachments[:5]:  # Test first 5 messages
            attachments = client.get_attachments(message['id'])
            
            for attachment in attachments[:2]:  # Test first 2 attachments per message
                data = client.download_attachment(message['id'], attachment['id'])
                if data:
                    download_count += 1
                    total_size += len(data)
        
        print(f"✅ Downloaded {download_count} attachments, total size: {total_size} bytes")
        self.assertGreater(download_count, 0)
        self.assertGreater(total_size, 0)


class TestEmailProcessingStress(EmailMonitorStressTest):
    """Test email processing under stress conditions"""
    
    def test_single_processing_cycle(self):
        """Test single email processing cycle"""
        print("🔄 Testing single processing cycle...")
        
        start_time = time.time()
        
        # Run processing cycle
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.monitor.process_emails())
        finally:
            loop.close()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Processing cycle completed in {duration:.2f}s")
        print(f"   Messages processed: {self.monitor.stats['messages_processed']}")
        print(f"   Attachments processed: {self.monitor.stats['attachments_processed']}")
        
        # Check that stats were updated
        self.assertGreater(self.monitor.stats['total_runs'], 0)
        self.assertIsNotNone(self.monitor.stats['last_run'])
    
    def test_multiple_processing_cycles(self):
        """Test multiple consecutive processing cycles"""
        print("🔄 Testing multiple processing cycles...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        total_messages = 0
        total_attachments = 0
        
        try:
            # Run 10 processing cycles
            for i in range(10):
                await_start = time.time()
                loop.run_until_complete(self.monitor.process_emails())
                cycle_time = time.time() - await_start
                
                total_messages += self.monitor.stats['messages_processed']
                total_attachments += self.monitor.stats['attachments_processed']
                
                print(f"   Cycle {i+1}: {cycle_time:.2f}s")
        finally:
            loop.close()
        
        print(f"✅ 10 cycles completed")
        print(f"   Total messages: {total_messages}")
        print(f"   Total attachments: {total_attachments}")
        print(f"   Total runs: {self.monitor.stats['total_runs']}")
        
        self.assertEqual(self.monitor.stats['total_runs'], 10)
    
    def test_concurrent_processing_cycles(self):
        """Test concurrent processing cycles (simulating multiple workers)"""
        print("🔄 Testing concurrent processing cycles...")
        
        async def run_processing_cycle(monitor_instance):
            """Run a single processing cycle"""
            await monitor_instance.process_emails()
            return monitor_instance.stats['messages_processed']
        
        def create_and_run_monitor():
            """Create a monitor instance and run processing in new event loop"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                monitor = EmailMonitor(mock_server_url="http://localhost:5002")
                monitor.attachments_dir = self.temp_dir / f"attachments_{threading.current_thread().ident}"
                monitor.attachments_dir.mkdir(exist_ok=True)
                
                return loop.run_until_complete(run_processing_cycle(monitor))
            finally:
                loop.close()
        
        # Run 5 concurrent processing cycles
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_and_run_monitor) for _ in range(5)]
            
            total_processed = 0
            for future in as_completed(futures):
                processed = future.result()
                total_processed += processed
        
        print(f"✅ Concurrent processing completed, total messages: {total_processed}")


class TestFastAPIStress(EmailMonitorStressTest):
    """Test FastAPI endpoints under stress"""
    
    def test_status_endpoint_stress(self):
        """Test status endpoint under load"""
        print("🔄 Testing status endpoint under load...")
        
        def get_status():
            response = requests.get("http://localhost:8001/status", timeout=5)
            return response.status_code == 200
        
        # Test with 100 concurrent requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(get_status) for _ in range(100)]
            
            success_count = 0
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
        
        print(f"✅ {success_count}/100 status requests succeeded")
        self.assertGreaterEqual(success_count, 95)  # Allow for 5% failure rate
    
    def test_process_now_endpoint_stress(self):
        """Test manual processing trigger under load"""
        print("🔄 Testing process-now endpoint under load...")
        
        def trigger_processing():
            try:
                response = requests.post("http://localhost:8001/process-now", timeout=10)
                return response.status_code == 200
            except:
                return False
        
        # Test with 20 concurrent trigger requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(trigger_processing) for _ in range(20)]
            
            success_count = 0
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
        
        print(f"✅ {success_count}/20 process-now requests succeeded")
        self.assertGreaterEqual(success_count, 18)  # Allow for some failures
    
    def test_dashboard_load(self):
        """Test dashboard loading under load"""
        print("🔄 Testing dashboard under load...")
        
        def load_dashboard():
            try:
                response = requests.get("http://localhost:8001/", timeout=5)
                return response.status_code == 200
            except:
                return False
        
        # Test with 50 concurrent dashboard loads
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(load_dashboard) for _ in range(50)]
            
            success_count = 0
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
        
        print(f"✅ {success_count}/50 dashboard loads succeeded")
        self.assertGreaterEqual(success_count, 45)  # Allow for some failures


class TestSystemIntegrationStress(EmailMonitorStressTest):
    """Test full system integration under stress"""
    
    def test_end_to_end_stress_scenario(self):
        """Test complete end-to-end workflow under stress"""
        print("🔄 Running end-to-end stress test...")
        
        # Start multiple processing cycles concurrently while hitting API endpoints
        results = {
            'processing_cycles': 0,
            'api_calls': 0,
            'errors': 0
        }
        
        def run_processing_cycles():
            """Run multiple processing cycles"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                for _ in range(5):
                    loop.run_until_complete(self.monitor.process_emails())
                    results['processing_cycles'] += 1
                    time.sleep(0.1)
            except Exception as e:
                results['errors'] += 1
                print(f"Processing error: {e}")
            finally:
                loop.close()
        
        def hit_api_endpoints():
            """Hit various API endpoints"""
            endpoints = [
                "http://localhost:8001/status",
                "http://localhost:8001/recent-results",
                "http://localhost:5002/health",
                "http://localhost:5002/v1.0/me/messages/delta"
            ]
            
            try:
                for _ in range(20):
                    for endpoint in endpoints:
                        try:
                            response = requests.get(endpoint, timeout=2)
                            if response.status_code == 200:
                                results['api_calls'] += 1
                        except:
                            results['errors'] += 1
                        time.sleep(0.05)
            except Exception as e:
                results['errors'] += 1
                print(f"API error: {e}")
        
        # Run both workloads concurrently
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(run_processing_cycles),
                executor.submit(run_processing_cycles),
                executor.submit(hit_api_endpoints),
                executor.submit(hit_api_endpoints)
            ]
            
            # Wait for all to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    results['errors'] += 1
                    print(f"Future error: {e}")
        
        print(f"✅ End-to-end test completed:")
        print(f"   Processing cycles: {results['processing_cycles']}")
        print(f"   API calls: {results['api_calls']}")
        print(f"   Errors: {results['errors']}")
        
        # Ensure reasonable success rate
        total_operations = results['processing_cycles'] + results['api_calls']
        if total_operations > 0:
            error_rate = results['errors'] / total_operations
            self.assertLess(error_rate, 0.1)  # Less than 10% error rate
        
        self.assertGreater(results['processing_cycles'], 0)
        self.assertGreater(results['api_calls'], 0)


def run_stress_tests():
    """Run all stress tests with detailed reporting"""
    print("🚀 Starting Email Monitor Stress Test Suite")
    print("=" * 60)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestMockServerStress,
        TestEmailProcessingStress,
        TestFastAPIStress,
        TestSystemIntegrationStress
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Summary report
    print("\n" + "=" * 60)
    print("🏁 STRESS TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"   {test}: {traceback}")
    
    if result.errors:
        print("\n💥 ERRORS:")
        for test, traceback in result.errors:
            print(f"   {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_stress_tests()
    sys.exit(0 if success else 1)