# Email Monitor FastAPI Service

A comprehensive email monitoring service with a beautiful web dashboard, Redis queue integration, and distributed attachment workers.

## Features

🌐 **Web Dashboard**: Modern, responsive interface for monitoring email processing  
📊 **Real-time Stats**: Live statistics and processing status  
📄 **JSON Viewer**: View processed attachment data and tables  
🔄 **Idempotency**: Graph API delta queries prevent duplicate processing  
⚡ **Fast**: 5-minute automatic intervals with manual trigger option  
💾 **Persistent**: Delta state survives service restarts  
🚀 **Redis Queue**: Distributed attachment processing with worker management  
👷 **Worker Processes**: Auto-scaling attachment workers with health monitoring  
📁 **File Upload Monitoring**: Automatic processing of files dropped in upload directory  
🔌 **Direct Upload API**: Web API for uploading files directly for processing  
🤖 **AI Pipeline**: Multi-agent PDF processing integration  
🧪 **Comprehensive Testing**: Full test suite with coverage reporting

## Quick Start

### 1. Set Environment Variables

```bash
# Copy and modify environment file
cp .env.example .env
# Edit .env with your configuration

# Required (Azure AD)
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
EMAIL_GROUPS=support@company.com,billing@company.com

# Optional (Redis Queue, Workers, and File Upload)
USE_REDIS_QUEUE=true
UPLOAD_DIR=file_uploads
REDIS_HOST=localhost
MAX_CONCURRENT_WORKERS=2
```

### 2. Install Dependencies

```bash
# Basic installation
pip install -r requirements.txt

# Development installation (includes testing tools)
pip install -r requirements_dev.txt
```

### 3. Start Redis (if using queue)

```bash
redis-server
```

### 4. Run Service

```bash
# Basic service
python -m app.main

# Service with integrated workers
python -m app.main_with_workers

# Local testing mode
python -m app.main_local
```

### 5. Start Workers (if running separately)

```bash
# Single worker
python attachment_worker.py

# Multiple workers with management
python worker_runner.py --standalone
```

### 6. Open Dashboard

Visit: http://localhost:8000

## Web Interface Features

### Dashboard Overview
- **Service Status**: Real-time monitoring indicator
- **Processing Stats**: Total runs, messages, and attachments processed
- **Configuration Display**: Current email groups, file types, and storage directory
- **Idempotency Status**: Delta sync status and error tracking
- **Worker Status**: Live worker health and statistics
- **Queue Metrics**: Redis queue length and processing rates

### Email Processing Results
- **Recent Results List**: Last 10 processed emails with details
- **Email Details**: Click to view full email information and attachments
- **JSON Viewer**: View processed attachment content, tables, and metadata
- **Manual Processing**: Trigger immediate email check via web interface
- **Queue Management**: View, peek, and clear Redis queue items

### Worker Management
- **Worker Health**: Monitor worker processes and restart capabilities
- **Performance Metrics**: Processing rates, success/error counts
- **Queue Monitoring**: Real-time queue status and item previews
- **Auto-scaling**: Automatic worker restart on failures

### Real-time Features
- **Auto-refresh**: Dashboard updates every 30 seconds
- **Live Stats**: Processing counters update in real-time
- **Toast Notifications**: Success/error messages for user actions
- **Responsive Design**: Works on desktop, tablet, and mobile

### File Upload Monitoring
- **Folder Watching**: Automatically detects files placed in upload directory
- **Direct Web Upload**: Upload files directly through web API
- **Automatic Queuing**: Files are automatically queued in Redis for processing
- **Archive Management**: Processed files moved to archive folder
- **Same Worker System**: Uses existing worker processes for consistent processing
- **Generic Email Context**: Uploaded files get placeholder email metadata

## API Endpoints

### Core Email Monitoring
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard (HTML) |
| `/status` | GET | Enhanced service status with worker info |
| `/process-now` | POST | Trigger immediate processing |
| `/recent-results` | GET | Recent processing results |
| `/email-details/{id}` | GET | Detailed email information |
| `/email-json/{id}` | GET | Complete JSON data for email |
| `/attachment-json/{id}/{filename}` | GET | Processed attachment JSON |

### Redis Queue Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/redis-queue/status` | GET | Queue status and connection info |
| `/redis-queue/stats` | GET | Detailed queue statistics |
| `/redis-queue/peek?count=5` | GET | Preview queue items (non-destructive) |
| `/redis-queue/clear` | POST | Clear all queue items |
| `/redis-queue/health` | GET | Redis connection health check |

### Worker Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/worker-stats` | GET | Worker processing statistics |
| `/worker-health` | GET | Worker health and status |
| `/worker-restart` | POST | Restart all workers |
| `/system-overview` | GET | Complete system status |

### File Upload Monitoring
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload-file` | POST | Upload a file for processing |
| `/upload-status` | GET | Upload monitoring status and statistics |

## File Structure

```
email_monitor_fastapi/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Basic FastAPI application  
│   ├── main_with_workers.py       # Enhanced version with workers
│   ├── main_local.py              # Local testing version
│   ├── redis_queue.py             # Redis queue management
│   ├── pdf_multiagent_system.py   # AI PDF processing system
│   ├── queue_models.py            # Data models for queuing
│   └── integration_example.py     # Pipeline integration examples
├── templates/
│   └── index.html                 # Dashboard HTML template
├── static/                        # (created at runtime)
│   ├── css/
│   └── js/
├── tests/
│   └── test_email_monitor.py      # Comprehensive test suite
├── attachment_worker.py           # Individual attachment worker
├── worker_runner.py               # Worker process manager
├── run_tests.py                   # Test runner with multiple modes
├── requirements.txt               # Basic Python dependencies
├── requirements_dev.txt           # Development and testing dependencies
├── requirements_test.txt          # Legacy test dependencies
├── .env.example                   # Environment configuration template
├── .env.worker                    # Worker-specific configuration
├── .env.uploads                   # File upload configuration template
├── UPLOAD_GUIDE.md                # File upload monitoring guide
├── test_upload.py                 # File upload testing script
├── pytest.ini                    # Test configuration
├── WARP.md                        # Warp AI assistant guidance
└── README.md                      # This file
```

## How Idempotency Works

### Email Idempotency
- Uses Microsoft Graph API delta queries
- First run: Processes all emails, stores delta link in `delta_link.txt`
- Subsequent runs: Only processes NEW emails since last delta link
- **Result**: Zero duplicate email processing, even across restarts

### Attachment Idempotency
- Each email gets unique directory: `{message_id}_{subject}`
- Same email = same directory = files overwritten (idempotent)
- Different emails = different directories = no conflicts
- **Result**: No duplicate attachment storage

## Output Structure

```
email_attachments/
├── a1b2c3d4_Invoice_March/
│   ├── invoice.pdf                    # Original attachment
│   ├── invoice.pdf.processed.json    # Processed content
│   ├── terms.docx                    # Another attachment
│   ├── terms.docx.processed.json    # Processed content
│   └── processing_summary.json       # Email summary
└── e5f6g7h8_Weekly_Report/
    ├── data.xlsx
    ├── data.xlsx.processed.json
    └── processing_summary.json

file_uploads/                          # File upload monitoring
├── processed/                         # Processed files archive
│   ├── 20241212_143022_document.pdf  # Archived processed files
│   └── 20241212_150033_report.docx   # With timestamp prefixes
└── (temporary files)                  # Files being processed
```

## Running as Windows Service

### Option 1: Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: When computer starts
4. Action: Start a program
5. Program: `python.exe`
6. Arguments: `-m app.main`
7. Start in: `C:\path\to\email_monitor_fastapi`

### Option 2: NSSM (Recommended)
```bash
# Download NSSM (Non-Sucking Service Manager)
nssm install EmailMonitor
# Set Application path to python.exe
# Set Arguments to -m app.main
# Set Startup directory to your project path
nssm start EmailMonitor
```

## Monitoring and Debugging

### Web Dashboard
- Access real-time stats at http://localhost:8000
- View processing errors and success rates
- Monitor idempotency status and delta sync state
- Trigger manual processing for testing

### Log Files
- Application logs: `email_monitor.log`
- Uvicorn server logs: Console output
- Processing errors: Visible in dashboard and logs

### Troubleshooting
1. **Service won't start**: Check environment variables
2. **No emails found**: Verify email groups and Graph API permissions
3. **Authentication errors**: Check Azure app registration credentials
4. **Dashboard not loading**: Ensure port 8000 is available

## Environment Variables

### Required (Azure AD)
| Variable | Description | Example |
|----------|-------------|--------|
| `AZURE_CLIENT_ID` | Azure app client ID | `12345678-1234-1234-1234-123456789012` |
| `AZURE_CLIENT_SECRET` | Azure app client secret | `your-secret-key` |
| `AZURE_TENANT_ID` | Azure tenant ID | `87654321-4321-4321-4321-210987654321` |

### Email Processing
| Variable | Description | Default | Example |
|----------|-------------|---------|--------|
| `EMAIL_GROUPS` | Comma-separated email filters | `""` | `support@company.com,billing@company.com` |
| `FILE_TYPES` | Comma-separated file extensions | `.pdf,.docx,.xlsx` | `.pdf,.docx,.xlsx,.csv` |
| `ATTACHMENTS_DIR` | Storage directory | `email_attachments` | `email_attachments` |
| `UPLOAD_DIR` | File upload monitoring directory | `file_uploads` | `file_uploads` |

### Redis Queue & Workers
| Variable | Description | Default | Example |
|----------|-------------|---------|--------|
| `USE_REDIS_QUEUE` | Enable Redis queue processing | `false` | `true` |
| `REDIS_HOST` | Redis server host | `localhost` | `redis.example.com` |
| `REDIS_PORT` | Redis server port | `6379` | `6379` |
| `REDIS_DB` | Redis database number | `0` | `0` |
| `REDIS_PASSWORD` | Redis password (if required) | `""` | `your-redis-password` |
| `EMAIL_QUEUE_NAME` | Queue name | `email_attachments` | `email_attachments` |
| `MAX_QUEUE_SIZE` | Maximum queue size | `1000` | `2000` |
| `MAX_ATTACHMENT_SIZE` | Max file size (bytes) | `52428800` | `104857600` |
| `MAX_CONCURRENT_WORKERS` | Number of worker processes | `1` | `4` |

### Pipeline Configuration
| Variable | Description | Default | Example |
|----------|-------------|---------|--------|
| `PIPELINE_APP_NAME` | Application name for pipeline | `EMAIL_PROCESSOR` | `CUSTOM_PROCESSOR` |
| `PIPELINE_USER_ID` | User ID for pipeline | `worker_001` | `production_worker` |
| `MAX_PIPELINE_RETRIES` | Maximum retry attempts | `3` | `5` |
| `WORKER_POLL_INTERVAL` | Queue polling interval (seconds) | `5` | `10` |
| `PROCESSING_TIMEOUT` | Max processing time (seconds) | `300` | `600` |

## Performance

- **Memory Usage**: ~50-100MB typical
- **CPU Usage**: Minimal (processes only during 5-minute intervals)
- **Disk Usage**: Depends on attachment volume
- **Network**: Only during Graph API calls (every 5 minutes)

## Worker System Architecture

### Processing Modes
1. **Direct Processing**: Attachments processed immediately when emails are received
2. **Queue Processing**: Attachments enqueued to Redis for distributed worker processing

### Worker Features
- **Distributed Processing**: Multiple workers can process attachments in parallel
- **Auto-restart**: Failed workers automatically restart
- **Health Monitoring**: Real-time worker status and performance metrics
- **Pipeline Integration**: Each attachment processed with full email context
- **MIME Type Handling**: Proper MIME type detection and processing
- **Retry Logic**: Configurable retry attempts with exponential backoff

### Queue Data Structure
Each queued item contains:
- Email metadata (ID, subject, sender, content, date)
- Attachment data (filename, content, MIME type, size)
- Processing metadata (task ID, timestamps, worker info)

## Testing

### Quick Testing
```bash
# Run all tests
python run_tests.py --all

# Run fast tests only
python run_tests.py --fast

# Run specific test categories
python run_tests.py --unit
python run_tests.py --integration
python run_tests.py --worker
python run_tests.py --api

# Run with coverage
python run_tests.py --all
```

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **API Tests**: FastAPI endpoint testing
- **Worker Tests**: Attachment worker functionality
- **Redis Tests**: Queue operations and reliability

### Code Quality
```bash
# Lint code
python run_tests.py --lint

# Format code automatically
python run_tests.py --format

# Type checking
python run_tests.py --type-check

# Security checks
python run_tests.py --security

# Full CI pipeline
python run_tests.py --ci
```

## Deployment Options

### Basic Deployment
```bash
# Single process with direct processing
ENV_FILE=.env python -m app.main
```

### Distributed Deployment
```bash
# Service with integrated workers
ENV_FILE=.env python -m app.main_with_workers

# Or run components separately:
# Terminal 1: Main service
ENV_FILE=.env python -m app.main

# Terminal 2: Worker manager
ENV_FILE=.env python worker_runner.py --standalone
```

### Docker Deployment
```dockerfile
# See included docker-compose example in README_REDIS_QUEUE.md
docker-compose up -d
```

## Monitoring and Troubleshooting

### Health Checks
```bash
# Application health
curl http://localhost:8000/status

# Worker health
curl http://localhost:8000/worker-health

# Redis queue health
curl http://localhost:8000/redis-queue/health

# File upload monitoring status
curl http://localhost:8000/upload-status

# Complete system overview
curl http://localhost:8000/system-overview
```

### Log Files
- `email_monitor.log` - Main application logs
- `attachment_worker.log` - Worker process logs
- Console output - Real-time service logs

### Common Issues
1. **Redis Connection**: Check Redis server status and connection settings
2. **Worker Failures**: Review worker logs and health endpoints
3. **Queue Backlogs**: Monitor queue length and worker processing rates
4. **Azure AD Auth**: Verify credentials and API permissions

## Integration with Your Pipeline

To integrate the worker with your existing AI pipeline:

1. **Replace Placeholder Code**: Update `_execute_pipeline_placeholder()` in `attachment_worker.py`
2. **Import Your Modules**: Add your pipeline imports at the top of the worker file
3. **Configure Processing**: Set pipeline-specific environment variables
4. **Handle MIME Types**: Implement MIME type-specific processing logic
5. **Process Results**: Save pipeline results to your preferred storage

Example integration structure:
```python
# In attachment_worker.py, replace placeholder with:
from your_pipeline import Runner, types, main_pipeline_agent

# Process with email context + attachment
result = await your_pipeline.process(
    email_text=pipeline_input['email_context']['content'],
    attachment_bytes=pipeline_input['attachment']['content_bytes'],
    mime_type=pipeline_input['attachment']['mime_type']
)
```

Perfect for production environments requiring reliable, scalable email monitoring with distributed attachment processing and comprehensive monitoring capabilities!
