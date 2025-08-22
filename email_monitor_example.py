"""
Email Monitoring Service Examples

Simple examples for the Prefect-based email monitoring service.
Assumes environment variables are set for Azure credentials.
"""

import os
import asyncio
from email_monitor_prefect import email_monitoring_flow


def setup_environment():
    """
    Set up environment variables for Azure Graph API
    """
    print("Required environment variables:")
    print("export AZURE_CLIENT_ID='your-client-id'")
    print("export AZURE_CLIENT_SECRET='your-client-secret'")
    print("export AZURE_TENANT_ID='your-tenant-id'")
    print()


def basic_example():
    """
    Example 1: Run email monitoring once
    """
    print("=== Basic Email Monitoring ===")
    
    # Get credentials from environment
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    tenant_id = os.getenv('AZURE_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        print("Missing environment variables!")
        setup_environment()
        return
    
    # Run the flow once
    result = asyncio.run(email_monitoring_flow(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        email_groups=['support@company.com'],
        attachments_dir='email_attachments',
        file_types=['.pdf', '.docx']
    ))
    
    print(f"Processing result: {result}")


def deployment_example():
    """
    Example 2: Create 24/7 deployment
    """
    print("\n=== 24/7 Deployment ===")
    
    print("Create deployment and start monitoring:")
    print("""
# 1. Create deployment
python email_monitor_prefect.py

# 2. Start Prefect (in separate terminals)
prefect server start
prefect agent start --pool default-agent-pool

# 3. Monitor at http://localhost:4200
""")


def custom_config_example():
    """
    Example 3: Custom configuration
    """
    print("\n=== Custom Configuration ===")
    
    print("Customize for your needs:")
    print("""
from email_monitor_prefect import email_monitoring_flow
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import IntervalSchedule
from datetime import timedelta

# Custom deployment
deployment = Deployment.build_from_flow(
    flow=email_monitoring_flow,
    name="my-email-monitor",
    schedule=IntervalSchedule(interval=timedelta(minutes=10)),
    parameters={
        "client_id": os.getenv('AZURE_CLIENT_ID'),
        "client_secret": os.getenv('AZURE_CLIENT_SECRET'),
        "tenant_id": os.getenv('AZURE_TENANT_ID'),
        "email_groups": ["billing@company.com", "invoices@company.com"],
        "attachments_dir": "invoice_attachments",
        "file_types": [".pdf"]  # Only PDFs
    }
)
deployment.apply()
""")


def check_results_example():
    """
    Example 4: Check processing results
    """
    print("\n=== Check Results ===")
    
    print("View processed attachments:")
    print("""
import json
from pathlib import Path

# Check what was processed
attachments_dir = Path("email_attachments")

for message_dir in attachments_dir.iterdir():
    if message_dir.is_dir():
        results_file = message_dir / "processing_results.json"
        
        if results_file.exists():
            with open(results_file) as f:
                results = json.load(f)
            
            print(f"Email: {results['email_info']['subject']}")
            print(f"Attachments: {len(results['attachments'])}")
            
            for att in results['attachments']:
                print(f"  - {att['filename']} ({att['file_type']})")
""")


def main():
    """Run all examples"""
    print("Email Monitoring Service - Simple Examples")
    print("=" * 50)
    
    setup_environment()
    basic_example()
    deployment_example() 
    custom_config_example()
    check_results_example()
    
    print("\n" + "=" * 50)
    print("Quick Start:")
    print("1. Set environment variables for Azure")
    print("2. Run: python email_monitor_prefect.py")
    print("3. Start: prefect server start")
    print("4. Start: prefect agent start --pool default-agent-pool")


if __name__ == "__main__":
    main()