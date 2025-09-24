# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a comprehensive email monitoring service built with FastAPI that connects to Microsoft Graph API to process emails and attachments. The system features a web dashboard, Redis queue integration, and multi-agent PDF processing capabilities using Google's Agent Development Kit.

## Core Architecture

### Main Components
- **FastAPI Service** (`app/main.py`): Production email monitoring service with web dashboard
- **Local Testing Service** (`app/main_local.py`): Local development version using mock server
- **Redis Queue System** (`app/redis_queue.py`): Queue-based attachment processing
- **Multi-Agent PDF System** (`app/pdf_multiagent_system.py`): AI-powered PDF processing using Google ADK
- **File Processor** (`../file_processor.py`): Universal file content extraction system
- **Queue Models** (`app/queue_models.py`): Data models and configurations for Redis queuing

### Data Flow
1. **Email Ingestion**: Microsoft Graph API → Delta Query (idempotent) → Email processing
2. **Attachment Handling**: Download → Queue to Redis OR Process directly → Store results
3. **Multi-Agent Processing**: PDF files → Preprocessing Agent → Main Processing → Postprocessing Agent
4. **Web Interface**: Real-time dashboard with processing results and queue management

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables (copy and modify)
cp .env.example .env

# Start Redis server (if using queue)
redis-server
```

### Running the Service
```bash
# Production service (requires Azure AD credentials)
python -m app.main

# Local development with mock server
python -m app.main_local

# Start mock email server for testing
python mock_email_server.py
```

### Testing Commands
```bash
# Install test dependencies
pip install -r requirements_test.txt

# Run comprehensive stress tests
python test_stress_local.py

# Run simple tests (no external dependencies)
python simple_stress_test.py

# Run demo with all components
python demo_run.py
```

### Redis Queue Management
```bash
# Check queue status
curl http://localhost:8000/redis-queue/status

# View queue statistics
curl http://localhost:8000/redis-queue/stats

# Peek at queue items (non-destructive)
curl http://localhost:8000/redis-queue/peek?count=10

# Clear queue (be careful!)
curl -X POST http://localhost:8000/redis-queue/clear
```

## Key Configuration

### Required Environment Variables
```bash
# Microsoft Graph API (Production)
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
AZURE_TENANT_ID=your_tenant_id

# Email Processing
EMAIL_GROUPS=company.com,partner.org  # Comma-separated domains/groups
FILE_TYPES=.pdf,.docx,.xlsx,.csv      # Supported file types
ATTACHMENTS_DIR=email_attachments     # Storage directory
```

### Optional Redis Configuration
```bash
USE_REDIS_QUEUE=true                  # Enable Redis queue
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
EMAIL_QUEUE_NAME=email_attachments
MAX_QUEUE_SIZE=1000
MAX_ATTACHMENT_SIZE=52428800          # 50MB in bytes
```

## Important Architectural Patterns

### Idempotency Design
- **Email Level**: Uses Microsoft Graph API delta queries to process only new emails
- **Attachment Level**: Directory-based file naming prevents duplicate processing
- **Delta State Persistence**: Delta links stored in `delta_link.txt` survive restarts

### Multi-Agent System Integration
The system implements Google's Agent Development Kit for PDF processing:
- **PDFMainAgent**: Coordinates the entire workflow
- **PDFPreProcessingAgent**: Validates and prepares files
- **PDFPostProcessingAgent**: Formats and validates results
- **Tools & Callbacks**: Extensible tool registration and lifecycle management

### Queue-Based Processing
Two processing modes available:
1. **Direct Processing**: Immediate attachment processing and storage
2. **Queue Processing**: Enqueue attachments to Redis for distributed processing

### Error Handling & Recovery
- Graceful degradation when Redis is unavailable
- Comprehensive error logging and dashboard visibility  
- Retry logic with configurable delays
- Health check endpoints for monitoring

## File Structure Insights

### Processing Pipeline
1. `GraphEmailClient` handles Microsoft Graph authentication and delta queries
2. `EmailMonitor` orchestrates the main processing workflow
3. `AttachmentReader` (from parent directory) processes various file types
4. `RedisEmailQueue` manages queue operations and data serialization

### Web Interface
- Dashboard at `http://localhost:8000` with real-time stats
- Modal dialogs for detailed email and attachment viewing
- JSON processing results viewer
- Manual processing triggers

### Testing Infrastructure
- Mock email server simulates Microsoft Graph API responses
- Stress testing with concurrent operations and performance measurement
- Local development mode with reduced polling intervals
- Comprehensive test coverage for authentication, processing, and error scenarios

## Development Notes

### When Adding New File Types
1. Update `FILE_TYPES` environment variable
2. Add processor to `AttachmentReader.supported_types`
3. Implement custom processor using `register_custom_processor()`
4. Test with both direct and queued processing modes

### When Modifying Queue Structure
1. Update `EmailAttachmentData` dataclass in `redis_queue.py`
2. Ensure backward compatibility for serialization
3. Update queue validation in `RedisQueueConfig`
4. Test queue peek and processing functions

### When Adding New Agents
1. Extend from `LlmAgent` in PDF multiagent system
2. Register tools using `Tool` class
3. Set up before/after callbacks for logging and validation
4. Add to `PDFMainAgent.sub_agents` list

### Performance Considerations
- Attachment size limits prevent memory issues
- Queue size limits prevent Redis overload
- Connection pooling and timeouts for Graph API calls
- Background scheduling prevents blocking the web interface

## Integration Points

### External Dependencies
- **Microsoft Graph API**: Email and attachment access
- **Redis**: Queue management and distributed processing
- **Google ADK**: Multi-agent AI processing framework
- **PyMuPDF, PIL, pytesseract**: File content extraction
- **FastAPI/Uvicorn**: Web service and API framework

### Monitoring Endpoints
- `GET /status`: Service health and statistics
- `GET /redis-queue/health`: Redis connection health
- `GET /recent-results`: Processing history
- `POST /process-now`: Manual processing trigger