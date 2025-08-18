"""
Custom attachment processors for specialized PDF processing
"""

from file_processor import ExtractedContent, FileProcessor
import fitz  # PyMuPDF
import re
from typing import Dict, Any, List

def invoice_pdf_processor(file_path: str, metadata: Dict[str, Any]) -> ExtractedContent:
    """
    Custom PDF processor for invoice documents
    
    Extracts:
    - Invoice number
    - Date
    - Vendor information
    - Line items as tables
    - Total amounts
    """
    text = ""
    tables = []
    invoice_metadata = metadata.copy()
    
    try:
        doc = fitz.open(file_path)
        full_text = ""
        
        for page in doc:
            page_text = page.get_text()
            full_text += page_text + "\n"
            
            # Extract tables from each page
            try:
                page_tables = page.find_tables()
                for table in page_tables:
                    table_data = table.extract()
                    if table_data:
                        cleaned_table = []
                        for row in table_data:
                            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                            cleaned_table.append(cleaned_row)
                        if cleaned_table:
                            tables.append(cleaned_table)
            except:
                pass
        
        doc.close()
        
        # Extract invoice-specific information
        invoice_info = extract_invoice_info(full_text)
        invoice_metadata.update(invoice_info)
        
        # Format text with extracted info
        text = f"INVOICE ANALYSIS\n"
        text += f"================\n\n"
        if invoice_info.get('invoice_number'):
            text += f"Invoice Number: {invoice_info['invoice_number']}\n"
        if invoice_info.get('invoice_date'):
            text += f"Invoice Date: {invoice_info['invoice_date']}\n"
        if invoice_info.get('vendor'):
            text += f"Vendor: {invoice_info['vendor']}\n"
        if invoice_info.get('total_amount'):
            text += f"Total Amount: {invoice_info['total_amount']}\n"
        text += f"\nFull Text:\n{full_text}"
        
    except Exception as e:
        text = f"Error processing invoice PDF: {str(e)}"
        invoice_metadata["processing_error"] = str(e)
    
    return ExtractedContent(
        text=text,
        tables=tables,
        metadata=invoice_metadata,
        file_type="invoice_pdf"
    )

def extract_invoice_info(text: str) -> Dict[str, str]:
    """Extract structured information from invoice text"""
    info = {}
    
    # Invoice number patterns
    invoice_patterns = [
        r'Invoice\s*#?\s*:?\s*([A-Z0-9\-]+)',
        r'Invoice\s*Number\s*:?\s*([A-Z0-9\-]+)',
        r'INV\s*#?\s*:?\s*([A-Z0-9\-]+)'
    ]
    
    for pattern in invoice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['invoice_number'] = match.group(1)
            break
    
    # Date patterns
    date_patterns = [
        r'Date\s*:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'Invoice\s*Date\s*:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['invoice_date'] = match.group(1)
            break
    
    # Total amount patterns
    total_patterns = [
        r'Total\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
        r'Amount\s*Due\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
        r'Grand\s*Total\s*:?\s*\$?([0-9,]+\.?\d{0,2})'
    ]
    
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['total_amount'] = match.group(1)
            break
    
    # Basic vendor extraction (first few lines usually contain vendor info)
    lines = text.split('\n')[:10]
    for line in lines:
        if len(line.strip()) > 5 and not re.search(r'invoice|date|total', line, re.IGNORECASE):
            if not info.get('vendor'):
                info['vendor'] = line.strip()
                break
    
    return info

def financial_report_processor(file_path: str, metadata: Dict[str, Any]) -> ExtractedContent:
    """
    Custom processor for financial reports
    
    Focuses on:
    - Balance sheets
    - Income statements
    - Financial ratios
    - Key metrics extraction
    """
    text = ""
    tables = []
    financial_metadata = metadata.copy()
    
    try:
        doc = fitz.open(file_path)
        full_text = ""
        
        for page in doc:
            page_text = page.get_text()
            full_text += page_text + "\n"
            
            # Enhanced table extraction for financial data
            try:
                page_tables = page.find_tables()
                for table in page_tables:
                    table_data = table.extract()
                    if table_data and is_financial_table(table_data):
                        cleaned_table = []
                        for row in table_data:
                            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                            cleaned_table.append(cleaned_row)
                        if cleaned_table:
                            tables.append(cleaned_table)
            except:
                pass
        
        doc.close()
        
        # Extract financial metrics
        financial_info = extract_financial_metrics(full_text)
        financial_metadata.update(financial_info)
        
        # Format text with financial analysis
        text = f"FINANCIAL REPORT ANALYSIS\n"
        text += f"========================\n\n"
        if financial_info.get('revenue'):
            text += f"Revenue: {financial_info['revenue']}\n"
        if financial_info.get('net_income'):
            text += f"Net Income: {financial_info['net_income']}\n"
        if financial_info.get('assets'):
            text += f"Total Assets: {financial_info['assets']}\n"
        text += f"\nFull Text:\n{full_text}"
        
    except Exception as e:
        text = f"Error processing financial report: {str(e)}"
        financial_metadata["processing_error"] = str(e)
    
    return ExtractedContent(
        text=text,
        tables=tables,
        metadata=financial_metadata,
        file_type="financial_report_pdf"
    )

def is_financial_table(table_data: List[List]) -> bool:
    """Check if table contains financial data"""
    if not table_data or len(table_data) < 2:
        return False
    
    financial_keywords = ['revenue', 'income', 'expense', 'asset', 'liability', 'equity', '$', 'total']
    text_content = ' '.join([' '.join(row) for row in table_data]).lower()
    
    return any(keyword in text_content for keyword in financial_keywords)

def extract_financial_metrics(text: str) -> Dict[str, str]:
    """Extract key financial metrics from text"""
    metrics = {}
    
    # Revenue patterns
    revenue_patterns = [
        r'Revenue\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
        r'Total\s*Revenue\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
        r'Sales\s*:?\s*\$?([0-9,]+\.?\d{0,2})'
    ]
    
    for pattern in revenue_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metrics['revenue'] = match.group(1)
            break
    
    # Net income patterns
    income_patterns = [
        r'Net\s*Income\s*:?\s*\$?([0-9,\-]+\.?\d{0,2})',
        r'Net\s*Profit\s*:?\s*\$?([0-9,\-]+\.?\d{0,2})',
        r'Profit\s*:?\s*\$?([0-9,\-]+\.?\d{0,2})'
    ]
    
    for pattern in income_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metrics['net_income'] = match.group(1)
            break
    
    # Assets patterns
    assets_patterns = [
        r'Total\s*Assets\s*:?\s*\$?([0-9,]+\.?\d{0,2})',
        r'Assets\s*:?\s*\$?([0-9,]+\.?\d{0,2})'
    ]
    
    for pattern in assets_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metrics['assets'] = match.group(1)
            break
    
    return metrics

def contract_pdf_processor(file_path: str, metadata: Dict[str, Any]) -> ExtractedContent:
    """
    Custom processor for contract documents
    
    Extracts:
    - Contract parties
    - Effective dates
    - Key terms and conditions
    - Signature information
    """
    text = ""
    tables = []
    contract_metadata = metadata.copy()
    
    try:
        doc = fitz.open(file_path)
        full_text = ""
        
        for page in doc:
            page_text = page.get_text()
            full_text += page_text + "\n"
        
        doc.close()
        
        # Extract contract-specific information
        contract_info = extract_contract_info(full_text)
        contract_metadata.update(contract_info)
        
        # Format text with contract analysis
        text = f"CONTRACT ANALYSIS\n"
        text += f"================\n\n"
        if contract_info.get('parties'):
            text += f"Parties: {', '.join(contract_info['parties'])}\n"
        if contract_info.get('effective_date'):
            text += f"Effective Date: {contract_info['effective_date']}\n"
        if contract_info.get('termination_date'):
            text += f"Termination Date: {contract_info['termination_date']}\n"
        text += f"\nFull Text:\n{full_text}"
        
    except Exception as e:
        text = f"Error processing contract PDF: {str(e)}"
        contract_metadata["processing_error"] = str(e)
    
    return ExtractedContent(
        text=text,
        tables=tables,
        metadata=contract_metadata,
        file_type="contract_pdf"
    )

def extract_contract_info(text: str) -> Dict[str, Any]:
    """Extract structured information from contract text"""
    info = {}
    
    # Extract parties (simplified approach)
    parties = []
    party_patterns = [
        r'between\s+([^,\n]+)\s+and\s+([^,\n]+)',
        r'party\s+of\s+the\s+first\s+part[:\s]+([^,\n]+)',
        r'party\s+of\s+the\s+second\s+part[:\s]+([^,\n]+)'
    ]
    
    for pattern in party_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                parties.extend([party.strip() for party in match])
            else:
                parties.append(match.strip())
    
    if parties:
        info['parties'] = list(set(parties))  # Remove duplicates
    
    # Extract dates
    date_patterns = [
        r'effective\s+date[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'commencing\s+on[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'termination\s+date[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if 'effective' in pattern:
                info['effective_date'] = match.group(1)
            elif 'termination' in pattern:
                info['termination_date'] = match.group(1)
    
    return info

# Example usage functions
def setup_custom_processors(file_processor: FileProcessor):
    """
    Set up custom processors for different PDF types
    """
    # Register custom processors
    file_processor.register_custom_attachment_processor('.pdf', invoice_pdf_processor)
    
    # Or use specific processors for different scenarios
    # file_processor.register_custom_attachment_processor('.pdf', financial_report_processor)
    # file_processor.register_custom_attachment_processor('.pdf', contract_pdf_processor)

def process_email_with_custom_pdf_handler(file_processor: FileProcessor, msg_file: str, email_groups: List[str]):
    """
    Example of processing emails with custom PDF handlers
    """
    # Set up custom PDF processor for invoices
    file_processor.register_custom_attachment_processor('.pdf', invoice_pdf_processor)
    
    # Process attachments
    result = file_processor.read_attachments_from_msg(
        file_path=msg_file,
        email_groups=email_groups,
        file_types=['.pdf']  # Only process PDFs
    )
    
    return result