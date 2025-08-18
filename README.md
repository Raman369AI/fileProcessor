# Universal File Processor

A modular Python library for reading and extracting content from various file formats with intelligent table detection and minimal dependencies.

## Features

- **Multiple File Format Support**: PDF, Images, Word, Excel, CSV, Outlook emails, and text files
- **Advanced PDF Processing**: Uses PyMuPDF with OCR fallback for scanned documents
- **Table Extraction**: Intelligent pattern-based table detection from unstructured data
- **Email Processing**: Enhanced Outlook MSG file parsing with metadata extraction
- **OCR Capabilities**: Text extraction from images and scanned documents
- **Resource Efficient**: Minimal dependencies with maximum functionality
- **Output Formats**: Both Markdown and JSON output support

## Supported File Types

| Format | Extension | Library Used | Features |
|--------|-----------|--------------|----------|
| PDF | `.pdf` | PyMuPDF | Text extraction, table detection, OCR fallback |
| Images | `.jpg`, `.png`, `.tiff`, `.bmp` | PIL + Tesseract | OCR text extraction, table detection |
| Word | `.docx` | python-docx | Text and table extraction |
| Excel | `.xlsx`, `.xls` | pandas | All sheets, data extraction |
| CSV | `.csv` | Built-in csv | Auto-delimiter detection |
| Outlook | `.msg` | extract-msg | Email metadata, attachments info |
| Text | `.txt` | Built-in | Pattern-based table detection |

## Installation

```bash
pip install -r requirements.txt
```

### System Dependencies

For OCR functionality, install Tesseract:

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

## Usage

### Basic Usage

```python
from file_processor import FileProcessor

# Initialize processor
processor = FileProcessor()

# Process any supported file
content = processor.process_file("document.pdf")

# Get markdown output
markdown = processor.to_markdown(content)
print(markdown)

# Get JSON output
json_output = processor.to_json(content)
print(json_output)
```

### Command Line Usage

```bash
python file_processor.py
# Enter file path when prompted
```

### Programmatic Access

```python
# Access extracted data
print(f"File type: {content.file_type}")
print(f"Text: {content.text}")
print(f"Tables found: {len(content.tables)}")
print(f"Metadata: {content.metadata}")

# Process tables
for i, table in enumerate(content.tables):
    print(f"Table {i+1}:")
    for row in table:
        print(row)
```

## Architecture

### Core Components

- **FileProcessor**: Main orchestrator class
- **TableExtractor**: Pattern-based table detection
- **OutlookMsgParser**: Enhanced email processing
- **ExtractedContent**: Data container with metadata

### Design Principles

- **Single Responsibility**: Each class handles one specific task
- **Minimal Dependencies**: Uses only essential libraries
- **Resource Efficiency**: Optimized for low memory usage
- **Modular Design**: Easy to extend with new file types
- **Error Handling**: Graceful fallbacks for missing dependencies

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