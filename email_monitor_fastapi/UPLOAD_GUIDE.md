# File Upload Monitoring Guide

## Overview

The EmailMonitor system now supports file upload monitoring in addition to email attachment processing. Files can be processed through two methods:

1. **Folder Monitoring**: Drop files into a monitored upload directory
2. **Web API**: Upload files directly through HTTP API endpoints

## Requirements

- Redis queue must be enabled (`USE_REDIS_QUEUE=true`)
- Worker processes must be running to process the uploaded files
- Supported file types: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt`, `.jpg`, `.jpeg`, `.png` (configurable)

## Configuration

### Environment Variables

```bash
# Enable Redis queue (required for upload processing)
USE_REDIS_QUEUE=true

# Upload directory path
UPLOAD_DIR=file_uploads

# Supported file types (comma-separated)
FILE_TYPES=.pdf,.docx,.xlsx,.csv,.txt,.jpg,.jpeg,.png

# Redis connection
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Quick Setup

1. Copy the example configuration:
   ```bash
   cp .env.uploads .env
   ```

2. Update the Azure credentials and other settings in `.env`

3. Install dependencies including watchdog:
   ```bash
   pip install -r requirements.txt
   ```

4. Start Redis server:
   ```bash
   redis-server
   ```

5. Start the FastAPI application:
   ```bash
   python -m app.main
   ```

6. Start worker processes (in separate terminal):
   ```bash
   python attachment_worker.py
   ```

## Usage Methods

### Method 1: Folder Monitoring

1. The system automatically monitors the upload directory (default: `file_uploads/`)
2. Simply copy or move files into this directory
3. Files are automatically:
   - Detected by the file system watcher
   - Queued in Redis for processing
   - Moved to `file_uploads/processed/` after queuing
   - Processed by worker processes

Example:
```bash
# Copy a file to be processed
cp document.pdf file_uploads/
```

### Method 2: Web API Upload

Upload files directly through the HTTP API:

```bash
# Upload a single file
curl -X POST "http://localhost:8000/upload-file" \
     -F "file=@document.pdf"
```

Response:
```json
{
  "message": "File uploaded successfully and queued for processing",
  "filename": "document.pdf",
  "saved_as": "20241212_143022_document.pdf",
  "size": 245760,
  "upload_time": "2024-12-12T14:30:22.123456"
}
```

## Monitoring Upload Status

### Check Upload System Status

```bash
curl http://localhost:8000/upload-status
```

Response:
```json
{
  "upload_dir": "/path/to/file_uploads",
  "upload_monitoring_active": true,
  "redis_queue_enabled": true,
  "supported_file_types": [".pdf", ".docx", ".xlsx"],
  "processed_files_count": 15,
  "processed_files_dir": "/path/to/file_uploads/processed"
}
```

### Check Overall System Status

```bash
curl http://localhost:8000/status
```

The response includes upload monitoring information in the `config` section.

## Processing Workflow

1. **File Detection**: File is placed in upload directory or uploaded via API
2. **Validation**: File type and size are validated
3. **Queuing**: File is queued in Redis with generic email metadata:
   - Email Subject: "File Upload Processing"
   - Email Sender: "File Upload System"
   - Email Content: "Processing uploaded file: {filename}"
4. **Archiving**: Original file is moved to `processed/` subfolder
5. **Worker Processing**: Background workers process the file content
6. **Results**: Processed content is available through existing APIs

## API Endpoints

### Upload APIs

- `POST /upload-file` - Upload a file for processing
  - Accepts multipart/form-data with `file` field
  - Returns upload confirmation and file details

- `GET /upload-status` - Get upload monitoring status
  - Returns upload directory info and monitoring status

### Existing APIs (work with uploaded files)

- `GET /status` - Overall system status
- `GET /redis-queue/status` - Queue status and statistics
- `GET /redis-queue/peek` - Preview queued items
- All other email/attachment APIs work with uploaded files

## File Structure

```
project/
├── file_uploads/           # Upload directory (monitored)
│   ├── processed/          # Processed files archive
│   └── (uploaded files)    # Temporary location before processing
├── email_attachments/      # Email attachment storage
└── (worker results)        # Processing results
```

## Troubleshooting

### Upload monitoring not starting
- Check Redis queue is enabled (`USE_REDIS_QUEUE=true`)
- Verify Redis server is running
- Check logs for connection errors

### Files not being processed
- Ensure worker processes are running
- Check file type is supported (`FILE_TYPES` setting)
- Verify file permissions and directory access
- Check Redis queue status: `GET /redis-queue/status`

### File upload API errors
- Verify file type is allowed
- Check file size limits
- Ensure Redis queue is available

## Integration Notes

- Uploaded files are processed using the same worker system as email attachments
- Results are stored in the same format and accessible through existing APIs
- File uploads create placeholder email metadata for consistency
- The system maintains the same retry and error handling mechanisms