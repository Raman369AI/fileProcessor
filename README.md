# Universal File Processor

A comprehensive, modular Python library for reading and extracting content from various file formats with intelligent table detection, custom PDF processing, and Microsoft Graph API integration. Designed for minimal dependencies and maximum functionality.

## 🚀 Key Features

### **Core Capabilities**
- **Universal File Format Support**: PDF, Images, Word, Excel, CSV, Outlook emails, and text files
- **Advanced PDF Processing**: PyMuPDF with OCR fallback for scanned documents
- **Intelligent Table Extraction**: Pattern-based detection from unstructured data
- **Modular Attachment Reading**: Process email attachments with custom processors
- **Microsoft Graph API Integration**: Delta sync for cloud email processing
- **OCR Capabilities**: Text extraction from images and scanned documents
- **Resource Efficient**: Minimal dependencies with maximum functionality
- **Multiple Output Formats**: Markdown and JSON with rich metadata

### **Email Processing Excellence**
- **MSG File Processing**: Complete Outlook email parsing with metadata
- **Graph API Delta Sync**: Incremental email synchronization from Microsoft 365
- **Email Group Filtering**: Process emails from specific senders/groups
- **Attachment Processing**: In-memory attachment reading without temporary files
- **Custom PDF Processors**: Specialized handling for invoices, reports, contracts

### **Advanced Table Detection**
- **Multi-Pattern Recognition**: Space/tab separated, pipe tables, coordinate-based
- **PDF Native Tables**: Direct table extraction using PyMuPDF
- **Excel Integration**: Complete spreadsheet processing with all sheets
- **Unstructured Data**: Extract tables from plain text and images

## 📁 Supported File Types

| Format | Extension | Library Used | Features | Custom Processing |
|--------|-----------|--------------|----------|-------------------|
| **PDF** | `.pdf` | PyMuPDF | Text extraction, native table detection, OCR fallback | ✅ Invoice, Financial, Contract processors |
| **Images** | `.jpg`, `.png`, `.tiff`, `.bmp` | PIL + Tesseract | OCR text extraction, table detection | ✅ Custom image analysis |
| **Word** | `.docx` | python-docx | Text and table extraction, formatting | ✅ Document structure analysis |
| **Excel** | `.xlsx`, `.xls` | pandas | All sheets, formulas, data types | ✅ Financial data processing |
| **CSV** | `.csv` | Built-in csv | Auto-delimiter detection, encoding | ✅ Data quality analysis |
| **Outlook** | `.msg` | extract-msg | Email metadata, attachment extraction | ✅ Email classification |
| **Text** | `.txt` | Built-in | Encoding detection, table patterns | ✅ Content categorization |
| **Email (Cloud)** | Graph API | msal + requests | Delta sync, attachment download | ✅ Real-time processing |

## 📦 Installation

### Quick Start
```bash
# Clone the repository
git clone https://github.com/Raman369AI/fileProcessor.git
cd fileProcessor

# Install dependencies
pip install -r requirements.txt
```

### Core Dependencies
```bash
# Essential libraries (automatically installed)
pip install PyMuPDF>=1.23.0 Pillow>=9.0.0 pytesseract>=0.3.10
pip install python-docx>=0.8.11 pandas>=1.5.0 extract-msg>=0.45.0
pip install msal>=1.24.0 requests>=2.28.0
```

### System Dependencies

**For OCR functionality, install Tesseract:**

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Add to PATH environment variable

**For enhanced PDF processing (optional):**
```bash
# Ubuntu/Debian
sudo apt-get install poppler-utils

# macOS
brew install poppler

# Then install Python package
pip install pdf2image>=1.16.3
```

## 💡 Usage Examples

### 1. Basic File Processing

```python
from file_processor import FileProcessor

# Initialize processor
processor = FileProcessor()

# Process any supported file
content = processor.process_file("document.pdf")

# Get formatted output
markdown = processor.to_markdown(content)
json_output = processor.to_json(content)

# Access extracted data
print(f"File type: {content.file_type}")
print(f"Text: {content.text}")
print(f"Tables found: {len(content.tables)}")
print(f"Metadata: {content.metadata}")
```

### 2. Modular Attachment Processing

```python
# Read all attachments from MSG file
result = processor.read_attachments_from_msg(
    file_path="email_with_attachments.msg",
    email_groups=["finance@company.com", "reports@company.com"],
    file_types=['.pdf', '.xlsx']  # Only process specific types
)

print(f"Total attachments: {result['summary']['total_attachments']}")
print(f"Processed: {result['summary']['processed_attachments']}")

# Access processed content
for attachment in result['processed_content']:
    content = attachment['processed_content']
    print(f"{attachment['filename']}: {len(content.tables)} tables found")
```

### 3. Custom PDF Processing

```python
from custom_processors import invoice_pdf_processor

# Register custom processor for invoices
processor.register_custom_attachment_processor('.pdf', invoice_pdf_processor)

# Process email with invoice attachments
result = processor.read_attachments_from_msg(
    file_path="invoice_email.msg",
    email_groups=["billing@company.com"],
    file_types=['.pdf']
)

# Access invoice-specific data
for attachment in result['processed_content']:
    if attachment['processing_method'] == 'custom':
        content = attachment['processed_content']
        print(f"Invoice #: {content.metadata.get('invoice_number')}")
        print(f"Amount: ${content.metadata.get('total_amount')}")
        print(f"Vendor: {content.metadata.get('vendor')}")
```

### 4. Microsoft Graph API Integration

```python
# Initialize with Azure credentials
processor = FileProcessor(
    graph_client_id="your-client-id",
    graph_client_secret="your-client-secret",
    graph_tenant_id="your-tenant-id"
)

# Authenticate
if processor.authenticate_graph_api():
    # Process emails with delta sync
    emails = processor.process_emails_from_graph(
        email_groups=["support@company.com", "sales@company.com"]
    )
    
    print(f"Processed {len(emails)} emails")
    
    # Get delta link for next sync
    delta_link = processor.get_graph_delta_link()
    # Next run will only get new/changed emails
```

### 5. Batch Processing

```python
import os

# Process multiple files
files = ["doc1.pdf", "report.xlsx", "image.png", "email.msg"]
results = []

for file_path in files:
    if os.path.exists(file_path):
        content = processor.process_file(file_path)
        results.append({
            'file': file_path,
            'type': content.file_type,
            'tables': len(content.tables),
            'text_length': len(content.text)
        })

# Summary report
for result in results:
    print(f"{result['file']}: {result['tables']} tables, {result['text_length']} chars")
```

### 6. Command Line Usage

```bash
# Basic processing
python file_processor.py

# Or run examples
python example_usage.py
```

## 🏗️ Architecture

### Core Components

```
FileProcessor (Main Orchestrator)
├── AttachmentReader (Modular file processing)
│   ├── Built-in processors (PDF, Word, Excel, etc.)
│   └── Custom processors (Invoice, Financial, Contract)
├── TableExtractor (Pattern-based table detection)
├── OutlookMsgParser (MSG file processing)
├── GraphApiEmailProcessor (Microsoft 365 integration)
└── ExtractedContent (Data container)
```

#### **FileProcessor**
- Main orchestrator class
- Routes files to appropriate processors
- Handles output formatting (Markdown/JSON)
- Manages custom processor registration

#### **AttachmentReader** 
- Modular attachment processing system
- Supports custom processors for specialized file types
- In-memory processing without temporary files
- Extensible architecture for new file formats

#### **GraphApiEmailProcessor**
- Microsoft Graph API integration
- Delta sync for incremental email processing
- Authentication management (MSAL)
- Attachment downloading from cloud

#### **TableExtractor**
- Multi-pattern table detection
- Coordinate-based positioning
- Works with OCR text and structured documents

#### **Custom Processors**
- `invoice_pdf_processor`: Invoice number, amount, vendor extraction
- `financial_report_processor`: Revenue, assets, financial metrics
- `contract_pdf_processor`: Parties, dates, terms extraction

### Design Principles

- **🎯 Single Responsibility**: Each class handles one specific task
- **📦 Minimal Dependencies**: Uses only essential libraries
- **⚡ Resource Efficiency**: Optimized for low memory usage
- **🔧 Modular Design**: Easy to extend with new file types
- **🛡️ Error Handling**: Graceful fallbacks for missing dependencies
- **🔄 Extensibility**: Plugin architecture for custom processors

## Table Detection Features

- **Pattern Recognition**: Multiple space/tab separated values
- **Pipe Tables**: Markdown-style table detection
- **Coordinate-based**: Position-aware table extraction
- **PDF Tables**: Native table detection with PyMuPDF
- **Excel Tables**: Direct spreadsheet processing

## ML Enhancement Opportunities

The codebase is designed with machine learning integration in mind:

- Document classification using transformers
- Layout analysis with computer vision models
- Advanced table detection with deep learning
- Content summarization and entity extraction
- Multi-modal processing capabilities

## Error Handling

- Graceful degradation when optional dependencies are missing
- OCR fallback for text extraction failures
- Multiple parsing strategies for complex file formats
- Comprehensive error reporting in metadata

## Dependencies

### Core Dependencies
- PyMuPDF (PDF processing)
- Pillow (Image handling)
- pytesseract (OCR)
- python-docx (Word documents)
- pandas (Excel files)
- extract-msg (Outlook emails)

### Optional Dependencies
- pdf2image (Enhanced PDF processing)
- EasyOCR (Alternative OCR)
- spacy (NLP capabilities)
- transformers (ML models)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the coding guidelines in CLAUDE.md
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Performance Notes

- **Memory Efficient**: Processes files incrementally
- **Resource Aware**: Minimal library footprint
- **Scalable**: Designed for batch processing
- **Fast**: Optimized extraction algorithms