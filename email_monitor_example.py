"""
Email Monitoring Service Examples

Demonstrates how to use the Prefect-based email monitoring service
for 24/7 email processing with attachment handling.
"""

import os
import asyncio
from datetime import timedelta
from email_monitor_prefect import (
    email_monitoring_flow,
    create_deployment,
    GraphEmailClient
)


def basic_email_monitoring_example():
    """
    Example 1: Basic email monitoring setup
    """
    print("=== Basic Email Monitoring Setup ===")
    
    # Configuration
    config = {
        'client_id': 'your-azure-client-id',
        'client_secret': 'your-azure-client-secret',  # Optional for daemon apps
        'tenant_id': 'your-azure-tenant-id',
        'email_groups': ['support@company.com', 'billing@company.com'],
        'attachments_dir': 'email_attachments',
        'file_types': ['.pdf', '.docx', '.xlsx']  # Empty list for all types
    }
    
    print("Configuration:")
    for key, value in config.items():
        if 'secret' in key.lower():
            print(f"  {key}: {'*' * len(str(value))}")
        else:
            print(f"  {key}: {value}")
    
    print("\nTo start monitoring:")
    print("1. Update the config with your actual Azure credentials")
    print("2. Run: python email_monitor_prefect.py")
    print("3. Start Prefect server: prefect server start")
    print("4. Start agent: prefect agent start --pool default-agent-pool")


def manual_flow_execution_example():
    """
    Example 2: Manual flow execution for testing
    """
    print("\n=== Manual Flow Execution ===")
    
    # Test configuration
    test_config = {
        'client_id': 'test-client-id',
        'email_groups': ['test@example.com'],
        'attachments_dir': 'test_attachments',
        'file_types': ['.pdf', '.docx']
    }
    
    print("For testing purposes, you can run the flow manually:")
    print(f"""
import asyncio
from email_monitor_prefect import email_monitoring_flow

# Run flow once for testing
result = asyncio.run(email_monitoring_flow(
    client_id="{test_config['client_id']}",
    email_groups={test_config['email_groups']},
    attachments_dir="{test_config['attachments_dir']}",
    file_types={test_config['file_types']}
))

print(f"Flow result: {{result}}")
""")


def deployment_configuration_example():
    """
    Example 3: Advanced deployment configuration
    """
    print("\n=== Advanced Deployment Configuration ===")
    
    print("Customize deployment parameters:")
    print("""
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import IntervalSchedule
from datetime import timedelta
from email_monitor_prefect import email_monitoring_flow

# Create custom deployment
deployment = Deployment.build_from_flow(
    flow=email_monitoring_flow,
    name="email-monitoring-custom",
    schedule=IntervalSchedule(interval=timedelta(minutes=10)),  # Every 10 minutes
    parameters={
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "tenant_id": "your-tenant-id",
        "email_groups": ["sales@company.com", "support@company.com"],
        "attachments_dir": "processed_emails",
        "file_types": [".pdf", ".xlsx", ".docx"]
    },
    tags=["email", "production", "high-priority"]
)

deployment.apply()
""")


def monitoring_and_debugging_example():
    """
    Example 4: Monitoring and debugging
    """
    print("\n=== Monitoring and Debugging ===")
    
    print("Monitor your email processing:")
    print("""
1. Access Prefect UI at http://localhost:4200
2. View flow runs in real-time
3. Check logs for each task execution
4. Review processing artifacts and summaries

Key metrics to monitor:
- Flow run frequency and success rate
- Number of emails processed per run
- Attachment processing errors
- Disk space usage in attachments directory
""")
    
    print("Debugging common issues:")
    print("""
# Check concurrency limits
from prefect.concurrency import read_concurrency_limit
limit = read_concurrency_limit(tag="email-monitoring")
print(f"Concurrency limit: {limit}")

# View recent flow runs
from prefect import get_client
client = get_client()
# Use client to query flow runs programmatically
""")


def attachment_processing_example():
    """
    Example 5: Understanding attachment processing
    """
    print("\n=== Attachment Processing Structure ===")
    
    print("Output directory structure:")
    print("""
email_attachments/
├── a1b2c3d4_Invoice_from_Vendor/
│   ├── invoice_march.pdf                    # Original attachment
│   ├── invoice_march.pdf.processed.json    # Processed content
│   ├── contract_terms.docx                 # Another attachment
│   ├── contract_terms.docx.processed.json  # Processed content
│   └── processing_results.json             # Summary of all attachments
├── e5f6g7h8_Weekly_Report/
│   ├── weekly_data.xlsx
│   ├── weekly_data.xlsx.processed.json
│   └── processing_results.json
""")
    
    print("Each .processed.json contains:")
    print("""
{
  "text": "Extracted text content...",
  "tables": [[["Header1", "Header2"], ["Row1Col1", "Row1Col2"]]],
  "metadata": {
    "file_type": "pdf",
    "pages": 3,
    "tables_detected": 2
  },
  "file_type": "pdf"
}
""")


def troubleshooting_example():
    """
    Example 6: Common troubleshooting scenarios
    """
    print("\n=== Troubleshooting Guide ===")
    
    print("Common issues and solutions:")
    print("""
1. Authentication Errors:
   - Verify Azure app registration credentials
   - Check app permissions for Mail.Read
   - Ensure tenant ID is correct

2. No Emails Found:
   - Check email_groups filter
   - Verify delta sync is working (first run gets all emails)
   - Confirm emails exist in the specified timeframe

3. Attachment Processing Failures:
   - Check file_types filter
   - Verify disk space in attachments_dir
   - Review processing errors in logs

4. Prefect Issues:
   - Ensure Prefect server is running
   - Check agent is connected to correct work pool
   - Verify concurrency limits are properly set

5. Performance Issues:
   - Adjust polling interval (default: 5 minutes)
   - Monitor attachment directory size
   - Consider file type filtering for large volumes
""")


def integration_example():
    """
    Example 7: Integration with other systems
    """
    print("\n=== Integration Examples ===")
    
    print("Post-processing integration:")
    print("""
# Custom post-processing hook
import json
from pathlib import Path

def process_new_attachments(attachments_dir="email_attachments"):
    '''Process newly saved attachments'''
    
    for message_dir in Path(attachments_dir).iterdir():
        if message_dir.is_dir():
            results_file = message_dir / "processing_results.json"
            
            if results_file.exists():
                with open(results_file) as f:
                    results = json.load(f)
                
                # Example: Send processed data to database
                for attachment in results['attachments']:
                    if attachment['file_type'] == '.pdf':
                        # Process invoices
                        pass
                    elif attachment['file_type'] == '.xlsx':
                        # Process spreadsheets
                        pass

# Run this as a separate Prefect flow or cron job
""")


def main():
    """Run all examples"""
    print("Email Monitoring Service Examples")
    print("=" * 50)
    
    basic_email_monitoring_example()
    manual_flow_execution_example()
    deployment_configuration_example()
    monitoring_and_debugging_example()
    attachment_processing_example()
    troubleshooting_example()
    integration_example()
    
    print("\n" + "=" * 50)
    print("Next Steps:")
    print("1. Update configuration with your Azure credentials")
    print("2. Install Prefect dependencies: pip install -r requirements_prefect.txt")
    print("3. Run: python email_monitor_prefect.py")
    print("4. Start Prefect server and agent")
    print("5. Monitor at http://localhost:4200")


if __name__ == "__main__":
    main()