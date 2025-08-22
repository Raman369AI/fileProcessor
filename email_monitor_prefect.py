"""
Email Monitoring Service with Prefect Orchestration

Simple 24/7 email monitoring using Prefect for orchestration.
Ensures only one task executes at a time with proper flow management.
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests

import prefect
from prefect import flow, task, get_run_logger
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import IntervalSchedule
from prefect.task_runners import SequentialTaskRunner
from prefect.artifacts import create_markdown_artifact
from prefect.blocks.system import Secret
from prefect.concurrency import concurrency

try:
    from msal import ConfidentialClientApplication, PublicClientApplication
    HAS_MSAL = True
except ImportError:
    HAS_MSAL = False

# Import our main processor components
from file_processor import AttachmentReader, ExtractedContent


class GraphEmailClient:
    """Microsoft Graph API client for email operations"""
    
    def __init__(self, client_id: str, client_secret: str = None, tenant_id: str = None):
        if not HAS_MSAL:
            raise ImportError("Microsoft Authentication Library (msal) not available. Install with: pip install msal")
        
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id or "common"
        self.access_token = None
        self.token_expires_at = None
        self.delta_link = None
    
    def authenticate(self, username: str = None, password: str = None) -> bool:
        """Authenticate with Microsoft Graph API"""
        try:
            if self.client_secret:
                app = ConfidentialClientApplication(
                    client_id=self.client_id,
                    client_credential=self.client_secret,
                    authority=f"https://login.microsoftonline.com/{self.tenant_id}"
                )
                result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            else:
                app = PublicClientApplication(
                    client_id=self.client_id,
                    authority=f"https://login.microsoftonline.com/{self.tenant_id}"
                )
                
                if username and password:
                    result = app.acquire_token_by_username_password(
                        username=username,
                        password=password,
                        scopes=["https://graph.microsoft.com/Mail.Read"]
                    )
                else:
                    result = app.acquire_token_interactive(
                        scopes=["https://graph.microsoft.com/Mail.Read"]
                    )
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                expires_in = result.get("expires_in", 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                return True
            else:
                return False
                
        except Exception:
            return False
    
    def is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.now() < self.token_expires_at
    
    def get_delta_messages(self, folder_id: str = None) -> List[Dict[str, Any]]:
        """Get email messages using delta query for incremental sync"""
        if not self.is_token_valid():
            raise ValueError("Token expired or invalid. Re-authenticate required.")
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Use stored delta link or build initial URL
        if self.delta_link:
            url = self.delta_link
        else:
            base_url = "https://graph.microsoft.com/v1.0/me/messages"
            if folder_id:
                base_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/messages"
            url = f"{base_url}/delta"
        
        messages = []
        
        try:
            while url:
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 401:
                    raise ValueError("Access token expired. Re-authenticate required.")
                
                response.raise_for_status()
                data = response.json()
                
                # Filter out deleted items
                current_messages = []
                for item in data.get("value", []):
                    if "@removed" not in item:
                        current_messages.append(item)
                
                messages.extend(current_messages)
                
                # Check for next page or delta link
                next_link = data.get("@odata.nextLink")
                delta_link = data.get("@odata.deltaLink")
                
                if delta_link:
                    self.delta_link = delta_link
                    break
                elif next_link:
                    url = next_link
                else:
                    break
                    
        except requests.exceptions.RequestException:
            return []
        
        return messages
    
    def filter_messages_by_groups(self, messages: List[Dict[str, Any]], email_groups: List[str]) -> List[Dict[str, Any]]:
        """Filter messages by email groups after retrieval"""
        if not email_groups:
            return messages
        
        filtered_messages = []
        
        for message in messages:
            sender = message.get("from", {}).get("emailAddress", {}).get("address", "").lower()
            
            recipients = []
            for to_recipient in message.get("toRecipients", []):
                recipients.append(to_recipient.get("emailAddress", {}).get("address", "").lower())
            for cc_recipient in message.get("ccRecipients", []):
                recipients.append(cc_recipient.get("emailAddress", {}).get("address", "").lower())
            
            # Check if sender or any recipient matches email groups
            group_match = False
            for group in email_groups:
                group_lower = group.lower()
                if (group_lower in sender or 
                    any(group_lower in recipient for recipient in recipients)):
                    group_match = True
                    break
            
            if group_match:
                filtered_messages.append(message)
        
        return filtered_messages
    
    def get_message_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """Get attachments for a specific message"""
        if not self.is_token_valid():
            raise ValueError("Token expired or invalid. Re-authenticate required.")
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 401:
                raise ValueError("Access token expired. Re-authenticate required.")
            
            response.raise_for_status()
            data = response.json()
            
            return data.get("value", [])
            
        except requests.exceptions.RequestException:
            return []
    
    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment content"""
        if not self.is_token_valid():
            raise ValueError("Token expired or invalid. Re-authenticate required.")
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments/{attachment_id}/$value"
        
        try:
            response = requests.get(url, headers=headers, timeout=60)
            
            if response.status_code == 401:
                raise ValueError("Access token expired. Re-authenticate required.")
            
            response.raise_for_status()
            return response.content
            
        except requests.exceptions.RequestException:
            return b""


@task(name="authenticate_graph_api")
def authenticate_graph_api(client_id: str, client_secret: str = None, tenant_id: str = None) -> GraphEmailClient:
    """Authenticate with Microsoft Graph API"""
    logger = get_run_logger()
    
    try:
        client = GraphEmailClient(client_id, client_secret, tenant_id)
        if client.authenticate():
            logger.info("Successfully authenticated with Microsoft Graph API")
            return client
        else:
            logger.error("Authentication failed")
            raise Exception("Authentication failed")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise


@task(name="fetch_new_emails")
def fetch_new_emails(graph_client: GraphEmailClient, email_groups: List[str] = None) -> List[Dict[str, Any]]:
    """Fetch new emails using delta query"""
    logger = get_run_logger()
    
    try:
        # Get new messages
        messages = graph_client.get_delta_messages()
        
        if messages:
            # Filter by email groups if specified
            if email_groups:
                messages = graph_client.filter_messages_by_groups(messages, email_groups)
            
            logger.info(f"Found {len(messages)} new messages")
            return messages
        else:
            logger.info("No new messages found")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching emails: {str(e)}")
        return []


@task(name="process_message_attachments")
def process_message_attachments(
    graph_client: GraphEmailClient, 
    message: Dict[str, Any], 
    attachments_dir: str,
    file_types: List[str] = None
) -> Dict[str, Any]:
    """Process attachments for a single message"""
    logger = get_run_logger()
    
    message_id = message.get("id", "")
    subject = message.get("subject", "No Subject")
    
    try:
        # Skip if no attachments
        if not message.get("hasAttachments", False):
            return {"message_id": message_id, "attachments_processed": 0, "status": "no_attachments"}
        
        # Get attachments
        attachments = graph_client.get_message_attachments(message_id)
        
        if not attachments:
            return {"message_id": message_id, "attachments_processed": 0, "status": "no_attachments"}
        
        logger.info(f"Processing {len(attachments)} attachments for message: {subject}")
        
        # Create message-specific directory
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        message_dir = Path(attachments_dir) / f"{message_id[:8]}_{safe_subject[:50]}"
        message_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize attachment reader
        attachment_reader = AttachmentReader()
        
        processed_attachments = []
        
        # Process each attachment
        for attachment in attachments:
            try:
                attachment_name = attachment.get("name", "unknown")
                attachment_id = attachment.get("id", "")
                
                # Check file type filter
                if file_types:
                    file_ext = os.path.splitext(attachment_name)[1].lower()
                    if file_ext not in file_types:
                        continue
                
                # Download attachment
                attachment_data = graph_client.download_attachment(message_id, attachment_id)
                
                if not attachment_data:
                    continue
                
                # Save attachment to disk
                attachment_path = message_dir / attachment_name
                with open(attachment_path, 'wb') as f:
                    f.write(attachment_data)
                
                # Process attachment content
                processed_attachment = attachment_reader.read_attachment(
                    attachment_data, 
                    attachment_name,
                    {
                        "email_id": message_id,
                        "email_subject": subject,
                        "email_sender": message.get("from", {}).get("emailAddress", {}).get("address", ""),
                        "email_date": message.get("receivedDateTime", "")
                    }
                )
                
                # Save processed content
                content_file = message_dir / f"{attachment_name}.processed.json"
                if processed_attachment.get("processed_content"):
                    content = processed_attachment["processed_content"]
                    with open(content_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            "text": content.text,
                            "tables": content.tables,
                            "metadata": content.metadata,
                            "file_type": content.file_type
                        }, f, indent=2, ensure_ascii=False)
                
                processed_attachments.append({
                    "filename": attachment_name,
                    "file_type": os.path.splitext(attachment_name)[1].lower(),
                    "file_size": len(attachment_data),
                    "saved_path": str(attachment_path),
                    "content_file": str(content_file),
                    "processing_method": processed_attachment.get("processing_method", "none"),
                    "errors": processed_attachment.get("errors", [])
                })
                
            except Exception as e:
                logger.error(f"Error processing attachment {attachment.get('name', 'unknown')}: {str(e)}")
                continue
        
        # Save processing results summary
        results = {
            "email_info": {
                "message_id": message_id,
                "subject": subject,
                "sender": message.get("from", {}).get("emailAddress", {}).get("address", ""),
                "received_date": message.get("receivedDateTime", ""),
                "processed_date": datetime.now().isoformat()
            },
            "attachments": processed_attachments
        }
        
        results_file = message_dir / "processing_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return {
            "message_id": message_id,
            "attachments_processed": len(processed_attachments),
            "status": "success",
            "results_file": str(results_file)
        }
        
    except Exception as e:
        logger.error(f"Error processing message {message_id}: {str(e)}")
        return {
            "message_id": message_id,
            "attachments_processed": 0,
            "status": "error",
            "error": str(e)
        }


@flow(
    name="email-monitoring-flow",
    task_runner=SequentialTaskRunner(),  # Ensures sequential execution
    description="24/7 Email monitoring with attachment processing"
)
async def email_monitoring_flow(
    client_id: str,
    client_secret: str = None,
    tenant_id: str = None,
    email_groups: List[str] = None,
    attachments_dir: str = "email_attachments",
    file_types: List[str] = None
):
    """
    Main email monitoring flow
    
    Uses Prefect's concurrency feature to ensure only one instance runs at a time
    """
    logger = get_run_logger()
    
    # Use concurrency to ensure only one flow runs at a time
    async with concurrency("email-monitoring", occupy=1):
        try:
            logger.info("Starting email monitoring flow")
            
            # Step 1: Authenticate
            graph_client = await authenticate_graph_api(client_id, client_secret, tenant_id)
            
            # Step 2: Fetch new emails
            messages = await fetch_new_emails(graph_client, email_groups)
            
            if not messages:
                logger.info("No messages to process")
                return {"status": "success", "messages_processed": 0}
            
            # Step 3: Process each message's attachments sequentially
            processed_results = []
            
            for message in messages:
                result = await process_message_attachments(
                    graph_client, 
                    message, 
                    attachments_dir,
                    file_types
                )
                processed_results.append(result)
            
            # Create summary artifact
            total_processed = sum(r.get("attachments_processed", 0) for r in processed_results)
            successful = len([r for r in processed_results if r.get("status") == "success"])
            
            summary_markdown = f"""
# Email Processing Summary

- **Messages Processed**: {len(messages)}
- **Successful**: {successful}
- **Total Attachments**: {total_processed}
- **Processing Time**: {datetime.now().isoformat()}

## Results by Message

| Message ID | Subject | Attachments | Status |
|------------|---------|-------------|--------|
"""
            
            for i, (message, result) in enumerate(zip(messages, processed_results)):
                subject = message.get("subject", "No Subject")[:50]
                summary_markdown += f"| {result['message_id'][:8]} | {subject} | {result.get('attachments_processed', 0)} | {result.get('status', 'unknown')} |\n"
            
            await create_markdown_artifact(
                markdown=summary_markdown,
                description="Email processing summary"
            )
            
            logger.info(f"Completed processing {len(messages)} messages with {total_processed} attachments")
            
            return {
                "status": "success",
                "messages_processed": len(messages),
                "attachments_processed": total_processed,
                "results": processed_results
            }
            
        except Exception as e:
            logger.error(f"Flow error: {str(e)}")
            return {"status": "error", "error": str(e)}


def create_deployment():
    """Create and apply Prefect deployment for 24/7 monitoring"""
    
    # Create deployment with interval schedule
    deployment = Deployment.build_from_flow(
        flow=email_monitoring_flow,
        name="email-monitoring-24x7",
        schedule=IntervalSchedule(interval=timedelta(minutes=5)),  # Run every 5 minutes
        parameters={
            "client_id": "your-client-id",  # Replace with actual values or use Prefect Blocks
            "client_secret": "your-client-secret",
            "tenant_id": "your-tenant-id",
            "email_groups": ["support@company.com", "billing@company.com"],
            "attachments_dir": "email_attachments",
            "file_types": [".pdf", ".docx", ".xlsx"]
        },
        tags=["email", "monitoring", "24x7"],
        description="Continuous email monitoring with attachment processing"
    )
    
    return deployment


def main():
    """Main function to setup and deploy the flow"""
    
    # Create concurrency limit to ensure only one instance runs
    from prefect.concurrency import create_concurrency_limit
    
    try:
        create_concurrency_limit(
            tag="email-monitoring",
            concurrency_limit=1,
            slot_decay_per_second=0.0  # No decay, strict limit
        )
        print("Created concurrency limit for email monitoring")
    except Exception as e:
        print(f"Concurrency limit may already exist: {e}")
    
    # Create and apply deployment
    deployment = create_deployment()
    deployment.apply()
    
    print("Email monitoring deployment created successfully!")
    print("To start the flow:")
    print("1. Start Prefect server: prefect server start")
    print("2. Start agent: prefect agent start --pool default-agent-pool")
    print("3. The flow will run automatically every 5 minutes")


if __name__ == "__main__":
    main()