# Email Monitor with Redis Queue Integration

A robust email monitoring service that processes Microsoft Graph email attachments and enqueues them to Redis for distributed processing.

## 🚀 Features

### Core Email Monitoring
- **Microsoft Graph Integration**: Connects to Office 365/Exchange via Azure AD
- **Delta Query Support**: Processes only new emails (idempotent)
- **Attachment Filtering**: Configurable file type filtering (.pdf, .docx, .xlsx, etc.)
- **Web Dashboard**: Real-time monitoring at http://localhost:8000

### Redis Queue Integration
- **Attachment Enqueueing**: Sends email content, attachments, and MIME types to Redis
- **Batch Processing**: Efficient bulk enqueuing of multiple attachments
- **Queue Management**: Full queue monitoring and management APIs
- **Error Handling**: Robust error handling with retry logic
- **Health Monitoring**: Queue health checks and statistics

## 📋 Prerequisites

1. **Microsoft Azure AD App Registration**
   - Client ID, Client Secret, and Tenant ID
   - Microsoft Graph API permissions

2. **Redis Server**
   - Redis 6.0+ recommended
   - Local or remote Redis instance

3. **Python 3.8+**
   - See `requirements.txt` for dependencies

## 🔧 Installation

1. **Clone and Setup**
   ```bash
   git clone <your-repo>
   cd email_monitor_fastapi
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start Redis Server** (if local)
   ```bash
   redis-server
   ```

4. **Run the Application**
   ```bash
   python -m app.main
   ```

## 🏗️ Architecture

### Email Processing Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Microsoft     │    │   EmailMonitor   │    │   Redis Queue   │
│   Graph API     │────│   (FastAPI)      │────│                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        │ 1. Fetch new emails    │                        │
        │                        │                        │
        │ 2. Download            │ 3. Enqueue            │
        │    attachments         │    attachments        │
        │                        │                        │
        │                        │                        │
        v                        v                        v
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Delta Query   │    │   Attachment     │    │   Queue Items   │
│   (Idempotent)  │    │   Processing     │    │   (JSON)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Queue Data Structure

Each queued item contains:
```json
{
  "task_id": "abc123_def456_xyz789",
  "email_id": "email_message_id", 
  "email_subject": "Email subject line",
  "email_sender": "John Doe",
  "email_sender_email": "john.doe@company.com",
  "email_content": "Full email body/content text...",
  "email_received_date": "2025-01-19T10:30:00Z",
  "attachment_id": "attachment_graph_id",
  "attachment_filename": "document.pdf",
  "attachment_content_b64": "base64_encoded_content",
  "attachment_mime_type": "application/pdf",
  "attachment_size": 2048576,
  "created_at": "2025-01-19T10:35:00Z"
}
```

## ⚙️ Configuration

### Environment Variables

#### Required (Azure AD)
```bash
AZURE_CLIENT_ID=your_azure_app_client_id
AZURE_CLIENT_SECRET=your_azure_app_client_secret  
AZURE_TENANT_ID=your_azure_tenant_id
```

#### Email Monitoring
```bash
EMAIL_GROUPS=company.com,partner.org          # Domains/groups to monitor
FILE_TYPES=.pdf,.docx,.xlsx,.csv               # File types to process
ATTACHMENTS_DIR=email_attachments              # Local storage directory
```

#### Redis Queue (Optional)
```bash
USE_REDIS_QUEUE=true                           # Enable Redis queue
REDIS_HOST=localhost                           # Redis server host
REDIS_PORT=6379                                # Redis server port
REDIS_DB=0                                     # Redis database number
REDIS_PASSWORD=                                # Redis password (if required)
EMAIL_QUEUE_NAME=email_attachments             # Queue name
MAX_QUEUE_SIZE=1000                            # Maximum queue size
MAX_ATTACHMENT_SIZE=52428800                   # Max file size (50MB)
```

## 🔗 API Endpoints

### Core Monitoring
- `GET /` - Web dashboard
- `GET /status` - System status and statistics
- `POST /process-now` - Trigger immediate email processing

### Redis Queue Management
- `GET /redis-queue/status` - Queue status and connection info
- `GET /redis-queue/stats` - Detailed queue statistics
- `GET /redis-queue/peek?count=5` - Preview queue items (non-destructive)
- `POST /redis-queue/clear` - Clear all queue items
- `GET /redis-queue/health` - Redis connection health check

### Email Data
- `GET /recent-results` - Recent processing results
- `GET /email-details/{message_id}` - Email details
- `GET /email-json/{message_id}` - Complete email JSON data

## 🛠️ Usage Examples

### Basic Setup (No Redis)
```bash
# Set required Azure AD variables
export AZURE_CLIENT_ID="your_client_id"
export AZURE_CLIENT_SECRET="your_client_secret"
export AZURE_TENANT_ID="your_tenant_id"
export EMAIL_GROUPS="company.com"

# Run with direct processing (no Redis)
python -m app.main
```

### Redis Queue Setup
```bash
# Enable Redis queue
export USE_REDIS_QUEUE=true
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Start Redis server (if local)
redis-server &

# Run the application
python -m app.main
```

### Queue Monitoring
```bash
# Check queue status
curl http://localhost:8000/redis-queue/status

# Get queue statistics  
curl http://localhost:8000/redis-queue/stats

# Preview queue items
curl http://localhost:8000/redis-queue/peek?count=10

# Clear queue (be careful!)
curl -X POST http://localhost:8000/redis-queue/clear
```

### Consuming Queue Items (External Worker)
```python
import redis
import json
import base64

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Pop item from queue (FIFO)
queue_item = r.rpop('email_attachments')

if queue_item:
    # Parse JSON data
    data = json.loads(queue_item.decode('utf-8'))
    
    # Get attachment content
    content = base64.b64decode(data['attachment_content_b64'])
    
    # Process attachment with full email context
    print(f"Email from: {data['email_sender']} ({data['email_sender_email']})")
    print(f"Email subject: {data['email_subject']}")
    print(f"Email content preview: {data['email_content'][:100]}...")
    print(f"Processing: {data['attachment_filename']}")
    print(f"MIME Type: {data['attachment_mime_type']}")
    print(f"Size: {data['attachment_size']} bytes")
    
    # Your processing logic here...
```

## 📊 Monitoring

### Key Metrics to Monitor

1. **Queue Length**: Monitor via `/redis-queue/stats`
2. **Processing Rate**: Attachments processed per minute
3. **Error Rate**: Failed enqueue/processing operations  
4. **Memory Usage**: Redis memory consumption
5. **Email Processing Latency**: Time from email arrival to queue

### Health Checks
```bash
# Application health
curl http://localhost:8000/status

# Redis queue health  
curl http://localhost:8000/redis-queue/health
```

### Logging
The application logs to both console and `email_monitor.log`:
- Email processing events
- Queue operations
- Errors and warnings
- Performance metrics

## 🚨 Error Handling

### Retry Logic
- Failed queue operations are logged but don't stop processing
- Configurable retry attempts for Redis connections
- Graceful degradation when Redis is unavailable

### Fallback Behavior
- When Redis is unavailable, reverts to direct processing
- Continues monitoring emails even with queue failures
- Health checks report Redis status

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify REDIS_HOST and REDIS_PORT
   - Check firewall/network connectivity

2. **Queue Full**
   - Increase MAX_QUEUE_SIZE
   - Implement queue consumers
   - Monitor queue length

3. **Large Attachments**
   - Adjust MAX_ATTACHMENT_SIZE
   - Consider Redis memory limits
   - Filter file types appropriately

## 🔒 Security Considerations

### Azure AD
- Store credentials securely (environment variables, key vault)
- Use least-privilege permissions
- Rotate credentials regularly

### Redis Security
- Enable Redis AUTH in production
- Use Redis SSL/TLS for network connections
- Restrict Redis access with firewall rules
- Consider Redis ACLs for fine-grained permissions

### Data Privacy
- Attachment content is stored temporarily in Redis
- Implement data retention policies
- Consider encryption for sensitive attachments
- Monitor access to queue data

## 🚀 Production Deployment

### Docker Setup
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "-m", "app.main"]
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  email-monitor:
    build: .
    ports:
      - "8000:8000"
    environment:
      - USE_REDIS_QUEUE=true
      - REDIS_HOST=redis
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

### Environment-Specific Configuration

#### Development
- Local Redis instance
- Verbose logging
- Smaller queue limits

#### Production  
- Redis cluster or managed service
- SSL/TLS encryption
- Monitoring and alerting
- Backup strategies
- Load balancing

## 📈 Performance Tuning

### Redis Configuration
```conf
# redis.conf optimizations
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
appendonly yes
tcp-keepalive 300
```

### Application Tuning
- Adjust MAX_QUEUE_SIZE based on memory
- Tune MAX_ATTACHMENT_SIZE for your files
- Configure WORKER_TIMEOUT appropriately
- Use connection pooling for high volume

### Monitoring Tools
- Redis monitoring: redis-cli, RedisInsight
- Application metrics: Prometheus, Grafana
- Log aggregation: ELK stack, Splunk
- Health checks: pingdom, datadog

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/redis-enhancement`)
3. Commit changes (`git commit -am 'Add Redis feature'`)
4. Push to branch (`git push origin feature/redis-enhancement`)
5. Create Pull Request

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

## 🆘 Support

- Check logs in `email_monitor.log`
- Use health check endpoints for diagnostics
- Monitor Redis with `redis-cli info`
- Review queue statistics for bottlenecks

For additional support, please open an issue with:
- Environment configuration
- Error logs
- Steps to reproduce
- Expected vs actual behavior