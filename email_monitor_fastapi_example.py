"""
FastAPI Email Monitor - Windows VM Example

Simple setup and usage examples for the FastAPI-based email monitoring service.
Perfect for Windows environments where cron jobs aren't available.
"""

import os
import time
import requests
from pathlib import Path


def setup_environment_variables():
    """
    Example: Set up environment variables for the service
    """
    print("=== Environment Setup ===")
    print("Set these environment variables in Windows:")
    print()
    print("# PowerShell:")
    print('$env:AZURE_CLIENT_ID="your-client-id"')
    print('$env:AZURE_CLIENT_SECRET="your-client-secret"')
    print('$env:AZURE_TENANT_ID="your-tenant-id"')
    print('$env:EMAIL_GROUPS="support@company.com,billing@company.com"')
    print('$env:FILE_TYPES=".pdf,.docx,.xlsx"')
    print()
    print("# Command Prompt:")
    print('set AZURE_CLIENT_ID=your-client-id')
    print('set AZURE_CLIENT_SECRET=your-client-secret')
    print('set AZURE_TENANT_ID=your-tenant-id')
    print('set EMAIL_GROUPS=support@company.com,billing@company.com')
    print('set FILE_TYPES=.pdf,.docx,.xlsx')


def start_service_example():
    """
    Example: How to start the service
    """
    print("\n=== Starting the Service ===")
    print("1. Install dependencies:")
    print("   pip install -r requirements_fastapi.txt")
    print()
    print("2. Set environment variables (see above)")
    print()
    print("3. Start the service:")
    print("   python email_monitor_fastapi.py")
    print()
    print("4. Service will:")
    print("   • Start web server on http://localhost:8000")
    print("   • Begin monitoring emails every 5 minutes")
    print("   • Save attachments to email_attachments/ folder")
    print("   • Provide web interface for monitoring")


def monitoring_examples():
    """
    Example: How to monitor the service
    """
    print("\n=== Monitoring the Service ===")
    
    # Check if service is running
    try:
        response = requests.get("http://localhost:8000/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print("✅ Service is running!")
            print(f"Last run: {status['stats']['last_run']}")
            print(f"Total runs: {status['stats']['total_runs']}")
            print(f"Messages processed: {status['stats']['messages_processed']}")
            print(f"Attachments processed: {status['stats']['attachments_processed']}")
            print(f"Errors: {status['stats']['errors']}")
        else:
            print("❌ Service returned error")
    except requests.exceptions.ConnectionError:
        print("❌ Service not running or not accessible")
    except Exception as e:
        print(f"❌ Error checking service: {e}")


def trigger_manual_processing():
    """
    Example: Trigger immediate email processing
    """
    print("\n=== Manual Processing ===")
    
    try:
        response = requests.post("http://localhost:8000/process-now", timeout=10)
        if response.status_code == 200:
            print("✅ Manual processing triggered!")
            print("Check logs or /status endpoint for results")
        else:
            print("❌ Failed to trigger processing")
    except Exception as e:
        print(f"❌ Error: {e}")


def check_results():
    """
    Example: Check recent processing results
    """
    print("\n=== Recent Results ===")
    
    try:
        response = requests.get("http://localhost:8000/recent-results", timeout=5)
        if response.status_code == 200:
            data = response.json()
            results = data.get("recent_results", [])
            
            if results:
                print(f"Found {len(results)} recent processing results:")
                for result in results[:5]:  # Show last 5
                    print(f"  • {result['subject'][:50]} - {result.get('attachments_processed', 0)} attachments")
            else:
                print("No recent results found")
        else:
            print("❌ Failed to get results")
    except Exception as e:
        print(f"❌ Error: {e}")


def check_saved_files():
    """
    Example: Check what files were saved locally
    """
    print("\n=== Saved Files ===")
    
    attachments_dir = Path("email_attachments")
    
    if not attachments_dir.exists():
        print("No attachments directory found")
        return
    
    message_dirs = [d for d in attachments_dir.iterdir() if d.is_dir()]
    
    if not message_dirs:
        print("No processed emails found")
        return
    
    print(f"Found {len(message_dirs)} processed email directories:")
    
    for message_dir in sorted(message_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        print(f"\n📁 {message_dir.name}")
        
        # List files in directory
        files = list(message_dir.iterdir())
        attachments = [f for f in files if not f.name.endswith('.json')]
        processed = [f for f in files if f.name.endswith('.processed.json')]
        
        print(f"   📎 {len(attachments)} attachments")
        print(f"   📄 {len(processed)} processed files")
        
        # Show summary if exists
        summary_file = message_dir / "processing_summary.json"
        if summary_file.exists():
            try:
                import json
                with open(summary_file) as f:
                    summary = json.load(f)
                    email_info = summary.get("email_info", {})
                    print(f"   ✉️  {email_info.get('subject', 'No subject')}")
                    print(f"   👤 {email_info.get('sender', 'Unknown sender')}")
            except Exception:
                pass


def idempotency_explanation():
    """
    Explain how idempotency works
    """
    print("\n=== How Idempotency Works ===")
    print()
    print("🔄 Email Idempotency (No Duplicate Processing):")
    print("   • Uses Microsoft Graph API 'delta queries'")
    print("   • First run: Processes all emails, gets 'delta link'")
    print("   • Subsequent runs: Only processes NEW emails since delta link") 
    print("   • Delta link stored in 'delta_link.txt' file")
    print("   • Result: Same emails NEVER processed twice!")
    print()
    print("📁 Attachment Idempotency (No Duplicate Storage):")
    print("   • Each email gets unique directory: {message_id}_{subject}")
    print("   • Same email = same directory = files get overwritten")
    print("   • Different emails = different directories = no conflicts")
    print("   • Result: Same attachments don't waste disk space!")
    print()
    print("⏰ Timing Idempotency (Reliable 5-minute intervals):")
    print("   • APScheduler handles timing automatically") 
    print("   • Runs every 5 minutes regardless of processing time")
    print("   • If processing takes longer than 5 minutes, next run waits")
    print("   • Result: Consistent, non-overlapping processing!")


def windows_service_setup():
    """
    Example: How to run as Windows service
    """
    print("\n=== Running as Windows Service ===")
    print()
    print("Option 1: Task Scheduler")
    print("1. Open Task Scheduler")
    print("2. Create Basic Task")
    print("3. Trigger: When computer starts")
    print("4. Action: Start a program")
    print("5. Program: python.exe")
    print("6. Arguments: C:\\path\\to\\email_monitor_fastapi.py")
    print()
    print("Option 2: NSSM (Non-Sucking Service Manager)")
    print("1. Download NSSM")
    print("2. nssm install EmailMonitor")
    print("3. Set path to python.exe and script")
    print("4. nssm start EmailMonitor")
    print()
    print("Option 3: Just run in background")
    print("1. Open PowerShell as Administrator")
    print("2. cd to your project directory")
    print("3. python email_monitor_fastapi.py")
    print("4. Minimize window - service keeps running!")


def main():
    """Run all examples"""
    print("FastAPI Email Monitor - Windows VM Examples")
    print("=" * 60)
    
    setup_environment_variables()
    start_service_example()
    
    # Only run monitoring examples if service might be running
    monitoring_examples()
    trigger_manual_processing()
    check_results()
    check_saved_files()
    
    idempotency_explanation()
    windows_service_setup()
    
    print("\n" + "=" * 60)
    print("🎯 Quick Start Summary:")
    print("1. Set environment variables")
    print("2. pip install -r requirements_fastapi.txt")
    print("3. python email_monitor_fastapi.py")
    print("4. Open http://localhost:8000 to monitor")
    print("5. Emails processed every 5 minutes automatically!")


if __name__ == "__main__":
    main()