# Email Monitor FastAPI Service

A comprehensive email monitoring service with a beautiful web dashboard for Windows VM environments.

## Features

🌐 **Web Dashboard**: Modern, responsive interface for monitoring email processing  
📊 **Real-time Stats**: Live statistics and processing status  
📄 **JSON Viewer**: View processed attachment data and tables  
🔄 **Idempotency**: Graph API delta queries prevent duplicate processing  
⚡ **Fast**: 5-minute automatic intervals with manual trigger option  
💾 **Persistent**: Delta state survives service restarts  

## Quick Start

### 1. Set Environment Variables

```bash
# Windows Command Prompt
set AZURE_CLIENT_ID=your-client-id
set AZURE_CLIENT_SECRET=your-client-secret
set AZURE_TENANT_ID=your-tenant-id
set EMAIL_GROUPS=support@company.com,billing@company.com
set FILE_TYPES=.pdf,.docx,.xlsx
set ATTACHMENTS_DIR=email_attachments
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Service

```bash
cd email_monitor_fastapi
python -m app.main
```

### 4. Open Dashboard

Visit: http://localhost:8000

## Web Interface Features

### Dashboard Overview
- **Service Status**: Real-time monitoring indicator
- **Processing Stats**: Total runs, messages, and attachments processed
- **Configuration Display**: Current email groups, file types, and storage directory
- **Idempotency Status**: Delta sync status and error tracking

### Email Processing Results
- **Recent Results List**: Last 10 processed emails with details
- **Email Details**: Click to view full email information and attachments
- **JSON Viewer**: View processed attachment content, tables, and metadata
- **Manual Processing**: Trigger immediate email check via web interface

### Real-time Features
- **Auto-refresh**: Dashboard updates every 30 seconds
- **Live Stats**: Processing counters update in real-time
- **Toast Notifications**: Success/error messages for user actions
- **Responsive Design**: Works on desktop, tablet, and mobile

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard (HTML) |
| `/status` | GET | Service status and stats (JSON) |
| `/process-now` | POST | Trigger immediate processing |
| `/recent-results` | GET | Recent processing results |
| `/email-details/{id}` | GET | Detailed email information |
| `/email-json/{id}` | GET | Complete JSON data for email |
| `/attachment-json/{id}/{filename}` | GET | Processed attachment JSON |

## File Structure

```
email_monitor_fastapi/
├── app/
│   ├── __init__.py
│   └── main.py              # Main FastAPI application
├── templates/
│   └── index.html           # Dashboard HTML template
├── static/
│   ├── css/
│   │   └── dashboard.css    # Dashboard styles
│   └── js/
│       └── dashboard.js     # Dashboard JavaScript
├── requirements.txt         # Python dependencies
└── README.md               # This file
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

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `AZURE_CLIENT_ID` | Yes | Azure app client ID | `12345678-1234-1234-1234-123456789012` |
| `AZURE_CLIENT_SECRET` | Yes | Azure app client secret | `your-secret-key` |
| `AZURE_TENANT_ID` | Yes | Azure tenant ID | `87654321-4321-4321-4321-210987654321` |
| `EMAIL_GROUPS` | No | Comma-separated email filters | `support@company.com,billing@company.com` |
| `FILE_TYPES` | No | Comma-separated file extensions | `.pdf,.docx,.xlsx` |
| `ATTACHMENTS_DIR` | No | Storage directory | `email_attachments` |

## Performance

- **Memory Usage**: ~50-100MB typical
- **CPU Usage**: Minimal (processes only during 5-minute intervals)
- **Disk Usage**: Depends on attachment volume
- **Network**: Only during Graph API calls (every 5 minutes)

Perfect for Windows VM environments where you need reliable, continuous email monitoring with a modern web interface!