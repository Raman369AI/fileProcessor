"""
Example usage of the Universal File Processor with enhanced email features
"""

from file_processor import FileProcessor
import os

def basic_file_processing():
    """Basic file processing example"""
    print("=== Basic File Processing ===")
    
    processor = FileProcessor()
    
    # Process any file
    # file_path = "sample.pdf"  # Replace with actual file path
    # content = processor.process_file(file_path)
    # print(f"File type: {content.file_type}")
    # print(f"Tables found: {len(content.tables)}")
    # print(f"Text preview: {content.text[:200]}...")

def modular_attachment_reading():
    """Example of modular attachment reading with custom processors"""
    print("\n=== Modular Attachment Reading ===")
    
    processor = FileProcessor()
    
    # Example 1: Read all attachment types
    msg_file = "email_with_attachments.msg"  # Replace with actual MSG file
    email_groups = ["finance@company.com", "reports@company.com"]
    
    if os.path.exists(msg_file):
        # Read all attachments
        result = processor.read_attachments_from_msg(
            file_path=msg_file,
            email_groups=email_groups
            # file_types=None means process all types
        )
        
        print(f"Email from: {result['email_info']['sender']}")
        print(f"Subject: {result['email_info']['subject']}")
        print(f"Total attachments: {result['summary']['total_attachments']}")
        print(f"Processed: {result['summary']['processed_attachments']}")
        print(f"File types: {result['summary']['file_types_processed']}")
        
        # Show processing results
        for attachment in result['processed_content']:
            print(f"\n{attachment['filename']}: {attachment['processing_method']} processing")
            if attachment['processed_content']:
                content = attachment['processed_content']
                print(f"  Text length: {len(content.text)}")
                print(f"  Tables: {len(content.tables)}")
                print(f"  File type: {content.file_type}")
    else:
        print("MSG file not found for demo")

def custom_pdf_processing():
    """Example of custom PDF processing for specific document types"""
    print("\n=== Custom PDF Processing ===")
    
    from custom_processors import invoice_pdf_processor, financial_report_processor
    
    processor = FileProcessor()
    
    # Register custom PDF processor for invoices
    processor.register_custom_attachment_processor('.pdf', invoice_pdf_processor)
    
    msg_file = "invoice_email.msg"  # Replace with actual MSG file
    
    if os.path.exists(msg_file):
        result = processor.read_attachments_from_msg(
            file_path=msg_file,
            email_groups=["billing@company.com", "invoices@company.com"],
            file_types=['.pdf']  # Only process PDFs
        )
        
        for attachment in result['processed_content']:
            if attachment['processing_method'] == 'custom':
                content = attachment['processed_content']
                print(f"\nInvoice PDF: {attachment['filename']}")
                print(f"Invoice Number: {content.metadata.get('invoice_number', 'Not found')}")
                print(f"Invoice Date: {content.metadata.get('invoice_date', 'Not found')}")
                print(f"Total Amount: {content.metadata.get('total_amount', 'Not found')}")
                print(f"Vendor: {content.metadata.get('vendor', 'Not found')}")
    else:
        print("Invoice email not found for demo")

def selective_file_type_processing():
    """Example of processing only specific file types"""
    print("\n=== Selective File Type Processing ===")
    
    processor = FileProcessor()
    
    msg_file = "mixed_attachments.msg"  # Replace with actual MSG file
    
    if os.path.exists(msg_file):
        # Only process PDFs and Excel files
        result = processor.read_attachments_from_msg(
            file_path=msg_file,
            file_types=['.pdf', '.xlsx', '.xls']
        )
        
        print(f"Total attachments: {result['summary']['total_attachments']}")
        print(f"Processed (PDF/Excel only): {result['summary']['processed_attachments']}")
        
        for attachment in result['processed_content']:
            content = attachment['processed_content']
            print(f"\n{attachment['filename']} ({content.file_type}):")
            print(f"  Processing method: {attachment['processing_method']}")
            print(f"  Tables extracted: {len(content.tables)}")
            
            # Show table preview for Excel files
            if content.file_type in ['excel_attachment'] and content.tables:
                print(f"  First table preview: {content.tables[0][:2] if content.tables[0] else 'Empty'}")
    else:
        print("Mixed attachments email not found for demo")

def graph_api_email_processing():
    """Example of processing emails using Microsoft Graph API"""
    print("\n=== Microsoft Graph API Email Processing ===")
    
    # Initialize with Azure app credentials
    processor = FileProcessor(
        graph_client_id="your-client-id",
        graph_client_secret="your-client-secret",  # Optional for public clients
        graph_tenant_id="your-tenant-id"
    )
    
    try:
        # Authenticate (interactive login)
        if processor.authenticate_graph_api():
            print("Successfully authenticated with Graph API")
            
            # Process emails from specific groups
            email_groups = ["support@company.com", "sales@company.com"]
            emails = processor.process_emails_from_graph(email_groups=email_groups)
            
            print(f"Processed {len(emails)} emails")
            
            for email in emails[:3]:  # Show first 3 emails
                print(f"\nSubject: {email.metadata['subject']}")
                print(f"From: {email.metadata['sender']}")
                print(f"Has attachments: {email.metadata['has_attachments']}")
                print(f"Tables found: {len(email.tables)}")
                
            # Get delta token for next sync
            delta_token = processor.get_graph_delta_token()
            print(f"Delta token for next sync: {delta_token[:50]}...")
            
        else:
            print("Authentication failed")
            
    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def advanced_email_workflow():
    """Advanced workflow combining MSG and Graph API processing"""
    print("\n=== Advanced Email Workflow ===")
    
    # Initialize processor with Graph API credentials
    processor = FileProcessor(
        graph_client_id=os.getenv("GRAPH_CLIENT_ID"),
        graph_client_secret=os.getenv("GRAPH_CLIENT_SECRET"),
        graph_tenant_id=os.getenv("GRAPH_TENANT_ID")
    )
    
    # Step 1: Process local MSG files with PDF attachments
    msg_files = ["email1.msg", "email2.msg"]  # Replace with actual files
    finance_groups = ["finance@company.com", "accounting@company.com"]
    
    for msg_file in msg_files:
        if os.path.exists(msg_file):
            result = processor.extract_pdf_attachments_from_msg(
                file_path=msg_file,
                email_groups=finance_groups
            )
            
            if result['processed_content']:
                print(f"Processed {len(result['processed_content'])} PDFs from {msg_file}")
                
                # Analyze extracted content
                for content in result['processed_content']:
                    pdf_data = content['content']
                    if pdf_data.tables:
                        print(f"  {content['filename']}: {len(pdf_data.tables)} tables extracted")
    
    # Step 2: Sync new emails from Graph API
    if processor.graph_processor:
        try:
            if processor.authenticate_graph_api():
                new_emails = processor.process_emails_from_graph(
                    email_groups=finance_groups
                )
                
                print(f"Synced {len(new_emails)} new emails from Graph API")
                
                # Filter emails with attachments for further processing
                emails_with_attachments = [
                    email for email in new_emails 
                    if email.metadata.get('has_attachments', False)
                ]
                
                print(f"Found {len(emails_with_attachments)} emails with attachments")
                
        except Exception as e:
            print(f"Graph API processing failed: {e}")

def batch_processing_example():
    """Example of batch processing multiple file types"""
    print("\n=== Batch Processing Example ===")
    
    processor = FileProcessor()
    
    # List of files to process
    files = [
        "document.pdf",
        "spreadsheet.xlsx", 
        "image.png",
        "email.msg",
        "data.csv"
    ]
    
    results = []
    
    for file_path in files:
        if os.path.exists(file_path):
            try:
                content = processor.process_file(file_path)
                results.append({
                    'file': file_path,
                    'type': content.file_type,
                    'tables': len(content.tables),
                    'text_length': len(content.text),
                    'metadata': content.metadata
                })
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
    
    # Summary report
    print("\nBatch Processing Summary:")
    for result in results:
        print(f"{result['file']}: {result['type']} - {result['tables']} tables, {result['text_length']} chars")

if __name__ == "__main__":
    print("Universal File Processor - Modular Attachment Reading Demo")
    
    # Run examples
    basic_file_processing()
    modular_attachment_reading()
    custom_pdf_processing()
    selective_file_type_processing()
    graph_api_email_processing()
    advanced_email_workflow()
    batch_processing_example()
    
    print("\nDemo completed!")
    print("\nKey Features:")
    print("1. Modular attachment reading with custom processors")
    print("2. Selective file type processing")
    print("3. Custom PDF processing for invoices, contracts, financial reports")
    print("4. Graph API integration with delta sync")
    print("5. Email group filtering")
    print("6. In-memory attachment processing (no temporary files)")
    print("\nTo get started:")
    print("- Install dependencies: pip install -r requirements.txt")
    print("- For MSG files: ensure extract-msg library is installed")
    print("- For Graph API: register app in Azure AD and set credentials")