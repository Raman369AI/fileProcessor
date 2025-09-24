#!/usr/bin/env python3
"""
Test script for file upload monitoring functionality.

This script demonstrates both upload methods:
1. Folder monitoring (copying files to upload directory)
2. Web API upload (HTTP POST to /upload-file)
"""

import os
import time
import requests
import tempfile
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
UPLOAD_DIR = Path("file_uploads")

def create_test_file(filename: str, content: str) -> Path:
    """Create a test file with the given content."""
    test_file = Path(tempfile.gettempdir()) / filename
    test_file.write_text(content, encoding='utf-8')
    return test_file

def test_folder_monitoring():
    """Test file upload monitoring by copying files to upload directory."""
    print("🗂️  Testing Folder Monitoring")
    print("=" * 50)
    
    # Create test file
    test_file = create_test_file("test_document.txt", "This is a test document for folder monitoring.")
    print(f"Created test file: {test_file}")
    
    # Copy to upload directory
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(exist_ok=True)
        print(f"Created upload directory: {UPLOAD_DIR}")
    
    dest_file = UPLOAD_DIR / test_file.name
    dest_file.write_bytes(test_file.read_bytes())
    print(f"Copied file to upload directory: {dest_file}")
    
    # Wait for processing
    print("⏳ Waiting for file to be detected and queued...")
    time.sleep(2)
    
    # Check if file was moved to processed directory
    processed_dir = UPLOAD_DIR / "processed"
    if processed_dir.exists():
        processed_files = list(processed_dir.glob(f"*{test_file.name}"))
        if processed_files:
            print(f"✅ File moved to processed directory: {processed_files[0]}")
        else:
            print("❌ File not found in processed directory")
    else:
        print("❌ Processed directory not created")
    
    # Cleanup
    test_file.unlink(missing_ok=True)
    print()

def test_api_upload():
    """Test file upload via web API."""
    print("🌐 Testing API Upload")
    print("=" * 50)
    
    # Create test file
    test_file = create_test_file("api_test.txt", "This is a test document for API upload.")
    print(f"Created test file: {test_file}")
    
    try:
        # Upload via API
        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/upload-file", files=files, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ File uploaded successfully via API")
            print(f"   Original filename: {result['filename']}")
            print(f"   Saved as: {result['saved_as']}")
            print(f"   Size: {result['size']} bytes")
            print(f"   Upload time: {result['upload_time']}")
        else:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - is the FastAPI server running?")
    except Exception as e:
        print(f"❌ Upload error: {e}")
    
    # Cleanup
    test_file.unlink(missing_ok=True)
    print()

def check_upload_status():
    """Check the upload monitoring status."""
    print("📊 Checking Upload Status")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/upload-status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            print("✅ Upload status retrieved successfully")
            print(f"   Upload directory: {status['upload_dir']}")
            print(f"   Monitoring active: {status['upload_monitoring_active']}")
            print(f"   Redis queue enabled: {status['redis_queue_enabled']}")
            print(f"   Supported file types: {status['supported_file_types']}")
            print(f"   Processed files count: {status['processed_files_count']}")
        else:
            print(f"❌ Status check failed: {response.status_code} - {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - is the FastAPI server running?")
    except Exception as e:
        print(f"❌ Status check error: {e}")
    
    print()

def check_queue_status():
    """Check the Redis queue status."""
    print("⚡ Checking Redis Queue Status")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/redis-queue/status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            print("✅ Queue status retrieved successfully")
            print(f"   Queue length: {status.get('queue_length', 'N/A')}")
            print(f"   Redis connected: {status.get('redis_connected', False)}")
        else:
            print(f"❌ Queue status check failed: {response.status_code} - {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - is the FastAPI server running?")
    except Exception as e:
        print(f"❌ Queue status check error: {e}")
    
    print()

def main():
    """Run all tests."""
    print("🚀 File Upload Monitoring Test Suite")
    print("=" * 60)
    print("This script tests the file upload functionality.")
    print("Make sure the FastAPI server is running with Redis queue enabled.")
    print("=" * 60)
    print()
    
    # Check server status first
    try:
        response = requests.get(f"{BASE_URL}/status", timeout=5)
        if response.status_code != 200:
            print("❌ Server not responding properly. Please start the FastAPI server.")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Please start the FastAPI server at http://localhost:8000")
        return
    
    # Run tests
    check_upload_status()
    check_queue_status()
    test_folder_monitoring()
    test_api_upload()
    
    print("🎉 Test suite completed!")
    print()
    print("Next steps:")
    print("1. Check the queue status: GET /redis-queue/status")
    print("2. Start worker processes to process the queued files")
    print("3. Monitor processing results through the web dashboard")

if __name__ == "__main__":
    main()