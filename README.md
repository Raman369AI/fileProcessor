# Universal File Processor

A comprehensive, modular Python library for reading and extracting content from various file formats with intelligent table detection, custom PDF processing, and 24/7 email monitoring capabilities. Designed for minimal dependencies and maximum functionality.

## 🚀 Key Features

### **Core Capabilities**
- **Universal File Format Support**: PDF, Images, Word, Excel, CSV, Outlook emails, and text files
- **Advanced PDF Processing**: PyMuPDF with OCR fallback for scanned documents
- **Intelligent Table Extraction**: Pattern-based detection from unstructured data
- **Modular Attachment Reading**: Process email attachments with custom processors
- **24/7 Email Monitoring**: Prefect-based orchestration for continuous email processing
- **OCR Capabilities**: Text extraction from images and scanned documents
- **Resource Efficient**: Minimal dependencies with maximum functionality
- **Multiple Output Formats**: Markdown and JSON with rich metadata

### **Email Processing Excellence**
- **MSG File Processing**: Complete Outlook email parsing with metadata
- **24/7 Email Monitoring**: Continuous monitoring with Prefect orchestration
- **Email Group Filtering**: Process emails from specific senders/groups
- **Multi-Attachment Support**: Handle multiple attachments per email with proper saving
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
| **Email (Cloud)** | Prefect + Graph API | msal + prefect | 24/7 monitoring, delta sync | ✅ Orchestrated processing |

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

### 4. Basic File Processing

```python
# Process any file type
files = ["document.pdf", "spreadsheet.xlsx", "image.png", "email.msg"]

for file_path in files:
    if os.path.exists(file_path):
        content = processor.process_file(file_path)
        print(f"{file_path}: {len(content.tables)} tables, {len(content.text)} chars")
```

### 5. Command Line Usage

```bash
# Basic file processing
python file_processor.py

# Run file processing examples
python example_usage.py

# Run email monitoring examples
python email_monitor_example.py
```

## 📧 24/7 Email Monitoring Service

Two options for continuous email monitoring and attachment processing:

### Option 1: FastAPI Service (Recommended for Windows)
Perfect for Windows VMs - lightweight service with web monitoring interface.

### Option 2: Prefect Orchestration (Advanced workflows)
More robust orchestration platform with enterprise features.

## FastAPI Service (Windows Recommended)

### Features
- **Windows VM Optimized**: No cron dependencies, runs as background service
- **Email Idempotency**: Graph API delta queries prevent duplicate processing
- **Attachment Idempotency**: Directory-based storage prevents duplicate files
- **5-Minute Intervals**: APScheduler handles timing automatically
- **Web Monitoring**: Built-in web interface at http://localhost:8000
- **Persistent**: Delta state survives service restarts

### Installation

```bash
# Install FastAPI dependencies
pip install -r requirements_fastapi.txt
```

### Quick Start

```bash
# Set environment variables
set AZURE_CLIENT_ID=your-client-id
set AZURE_CLIENT_SECRET=your-client-secret
set AZURE_TENANT_ID=your-tenant-id
set EMAIL_GROUPS=support@company.com,billing@company.com

# Start service
python email_monitor_fastapi.py

# Monitor at http://localhost:8000
```

### Idempotency Guarantees

**Email Processing**: Uses Microsoft Graph API delta queries
- First run: Processes all emails, stores delta link
- Subsequent runs: Only processes NEW emails since last delta link
- Result: Zero duplicate email processing

**Attachment Storage**: Directory-based deduplication  
- Each email gets unique directory: `{message_id}_{subject}`
- Same email = same directory = files overwritten (idempotent)
- Different emails = different directories = no conflicts

## Prefect Service (Enterprise Features)

### Features
- **Advanced Orchestration**: Complex workflow management
- **Built-in Retries**: Automatic error handling and recovery
- **Rich UI**: Comprehensive monitoring and debugging
- **Concurrency Control**: Ensures single instance execution

### Installation

```bash
# Install Prefect dependencies
pip install -r requirements_prefect.txt
```

### Quick Start

```bash
# 1. Start Prefect server
prefect server start

# 2. Create deployment (in another terminal)
python email_monitor_prefect.py

# 3. Start agent (in another terminal)
prefect agent start --pool default-agent-pool
```

### Configuration

```bash
# Set environment variables
export AZURE_CLIENT_ID='your-azure-client-id'
export AZURE_CLIENT_SECRET='your-azure-client-secret'
export AZURE_TENANT_ID='your-azure-tenant-id'
```

```python
# Simple usage
import asyncio
from email_monitor_prefect import email_monitoring_flow

# Run once for testing
result = asyncio.run(email_monitoring_flow(
    client_id=os.getenv('AZURE_CLIENT_ID'),
    client_secret=os.getenv('AZURE_CLIENT_SECRET'),
    tenant_id=os.getenv('AZURE_TENANT_ID'),
    email_groups=['support@company.com'],
    attachments_dir='email_attachments',
    file_types=['.pdf', '.docx']
))
```

### Output Structure

```
email_attachments/
├── {message_id}_{subject}/
│   ├── attachment1.pdf
│   ├── attachment1.pdf.processed.json
│   ├── attachment2.xlsx
│   ├── attachment2.xlsx.processed.json
│   └── processing_results.json
```

### Monitoring

- **Prefect UI**: Access at http://localhost:4200 for flow monitoring
- **Logs**: Real-time logging with structured output
- **Artifacts**: Processing summaries with markdown reports
- **Concurrency**: Automatic single-instance enforcement

## 🏗️ Architecture

### Core Components

```
FileProcessor (Core File Processing)
├── AttachmentReader (Modular file processing)
│   ├── Built-in processors (PDF, Word, Excel, etc.)
│   └── Custom processors (Invoice, Financial, Contract)
├── TableExtractor (Pattern-based table detection)
├── OutlookMsgParser (MSG file processing)
└── ExtractedContent (Data container)

Email Monitoring Service (Separate Prefect Service)
├── GraphEmailClient (Microsoft Graph API integration)
├── Prefect Flow (Orchestration and scheduling)
├── Concurrency Control (Single instance enforcement)
└── Attachment Processing (Multi-file handling)
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

#### **Email Monitoring Service**
- 24/7 Prefect-based orchestration
- Microsoft Graph API integration with delta sync
- Single instance concurrency control
- Multi-attachment processing and saving

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