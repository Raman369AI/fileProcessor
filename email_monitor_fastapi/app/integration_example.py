"""
Integration example showing how to use the PDF Multi-Agent System
with the existing email monitoring service
"""

from pdf_multiagent_system import create_pdf_multiagent_system
import logging
from pathlib import Path
import json


class PDFProcessorIntegration:
    """Integration class to connect email monitor with PDF multi-agent system"""
    
    def __init__(self):
        self.pdf_system = create_pdf_multiagent_system()
        self.logger = logging.getLogger("pdf_integration")
        
    def process_pdf_attachment(self, file_path: str, email_metadata: dict = None) -> dict:
        """
        Process a PDF attachment using the multi-agent system
        
        Args:
            file_path: Path to the PDF file
            email_metadata: Optional metadata from the email (sender, subject, etc.)
            
        Returns:
            Processing result dictionary
        """
        try:
            self.logger.info(f"Processing PDF with multi-agent system: {file_path}")
            
            # Add email context to the processing
            if email_metadata:
                self.logger.info(f"Email context: {email_metadata.get('subject', 'No subject')}")
            
            # Process through multi-agent system
            result = self.pdf_system.process_pdf(file_path)
            
            # Add email metadata to result
            if email_metadata:
                result['email_context'] = email_metadata
                
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process PDF: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path,
                "email_context": email_metadata
            }
    
    def get_agent_status(self) -> dict:
        """Get status of the multi-agent system"""
        return self.pdf_system.get_system_status()


# Example integration with the email monitor
def integrate_with_email_monitor():
    """
    Example of how to integrate the PDF multi-agent system
    with the existing email monitoring service
    """
    
    # This would be called from main.py in the _process_message method
    pdf_processor = PDFProcessorIntegration()
    
    # Example: Processing a PDF attachment
    sample_file = "/path/to/sample.pdf"
    email_context = {
        "email_id": "sample_123",
        "subject": "Important Document",
        "sender": "sender@example.com",
        "received_date": "2025-09-02"
    }
    
    # Process the PDF
    result = pdf_processor.process_pdf_attachment(sample_file, email_context)
    
    print("Multi-Agent Processing Result:")
    print(json.dumps(result, indent=2))
    
    return result


if __name__ == "__main__":
    # Test the integration
    integrate_with_email_monitor()