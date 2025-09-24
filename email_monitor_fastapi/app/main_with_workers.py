#!/usr/bin/env python3
"""
Email Monitor FastAPI with Workers Integration

Extended version of main.py that includes worker management in the FastAPI lifecycle.
This demonstrates how to integrate the attachment workers with the existing email
monitoring service.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the existing email monitor components
from app.main import EmailMonitor, monitor, scheduler
from worker_runner import FastAPIWorkerManager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Setup logging
logger = logging.getLogger(__name__)

# Create worker manager
worker_manager = FastAPIWorkerManager(
    num_workers=int(os.getenv('MAX_CONCURRENT_WORKERS', '2'))
)

@asynccontextmanager
async def lifespan_with_workers(app):
    """
    FastAPI lifespan manager that includes worker startup/shutdown
    """
    logger.info("Starting Email Monitor with Workers...")
    
    try:
        # Start attachment workers
        await worker_manager.startup()
        logger.info("✅ Attachment workers started")
        
        # Start email monitoring scheduler
        from apscheduler.triggers.interval import IntervalTrigger
        scheduler.add_job(
            func=lambda: asyncio.create_task(monitor.process_emails()),
            trigger=IntervalTrigger(minutes=5),
            id='email_monitor_job',
            name='Email Monitor',
            replace_existing=True
        )
        scheduler.start()
        logger.info("✅ Email monitoring started - checking every 5 minutes")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Shutdown workers
        logger.info("Shutting down workers...")
        await worker_manager.shutdown()
        
        # Shutdown scheduler
        scheduler.shutdown(wait=False)
        logger.info("✅ Shutdown complete")


# Create new FastAPI app with worker integration
app = FastAPI(
    title="Email Monitor Dashboard with Workers", 
    description="24/7 Email Monitoring with Web Interface and Attachment Workers",
    version="1.1.0",
    lifespan=lifespan_with_workers
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# === Existing Email Monitor Routes ===

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/status")
async def get_status():
    """Enhanced status API with worker information"""
    base_status = {
        "status": "running",
        "stats": monitor.stats,
        "config": {
            "email_groups": monitor.email_groups,
            "attachments_dir": str(monitor.attachments_dir),
            "file_types": monitor.file_types,
            "redis_queue_enabled": monitor.use_redis_queue
        },
        "idempotency_info": {
            "email_deduplication": "Graph API delta queries",
            "attachment_deduplication": "Directory-based file overwriting",
            "delta_link_stored": monitor.graph_client.delta_link is not None if monitor.graph_client else False
        }
    }
    
    # Add Redis queue information if enabled
    if monitor.use_redis_queue and monitor.redis_queue:
        try:
            queue_info = monitor.redis_queue.get_queue_info()
            base_status["redis_queue"] = queue_info
        except Exception as e:
            base_status["redis_queue"] = {"error": str(e)}
    
    # Add worker information
    try:
        worker_health = await worker_manager.health_check()
        worker_stats = worker_manager.get_stats()
        base_status["attachment_workers"] = {
            "enabled": True,
            "health": worker_health,
            "stats": worker_stats
        }
    except Exception as e:
        base_status["attachment_workers"] = {
            "enabled": False,
            "error": str(e)
        }
    
    return base_status

@app.post("/process-now")
async def process_now(background_tasks: BackgroundTasks):
    """Trigger immediate email processing"""
    background_tasks.add_task(monitor.process_emails)
    return {"message": "Email processing triggered immediately"}

@app.get("/recent-results")
async def get_recent_results():
    """Get recent processing results"""
    results = []
    
    try:
        for message_dir in monitor.attachments_dir.iterdir():
            if message_dir.is_dir():
                summary_file = message_dir / "processing_summary.json"
                if summary_file.exists():
                    with open(summary_file) as f:
                        summary = json.load(f)
                        results.append(summary["email_info"])
        
        # Sort by processed date
        results.sort(key=lambda x: x.get("processed_date", ""), reverse=True)
        return {"recent_results": results[:10]}
        
    except Exception as e:
        return {"error": str(e), "recent_results": []}

@app.get("/email-details/{message_id}")
async def get_email_details(message_id: str):
    """Get detailed information about a processed email"""
    import json
    try:
        # Find the message directory
        message_dir = None
        for dir_path in monitor.attachments_dir.iterdir():
            if dir_path.is_dir() and dir_path.name.startswith(message_id[:8]):
                message_dir = dir_path
                break
        
        if not message_dir:
            raise HTTPException(status_code=404, detail="Email not found")
        
        summary_file = message_dir / "processing_summary.json"
        if not summary_file.exists():
            raise HTTPException(status_code=404, detail="Processing summary not found")
        
        with open(summary_file) as f:
            summary = json.load(f)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Redis Queue Management Routes ===

@app.get("/redis-queue/status")
async def get_redis_queue_status():
    """Get Redis queue status and information"""
    if not monitor.use_redis_queue:
        return {"error": "Redis queue not enabled"}
    
    if not monitor.redis_queue:
        return {"error": "Redis queue not initialized"}
    
    try:
        return monitor.redis_queue.get_queue_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/redis-queue/stats")
async def get_redis_queue_stats():
    """Get detailed Redis queue statistics"""
    if not monitor.use_redis_queue or not monitor.redis_queue:
        raise HTTPException(status_code=400, detail="Redis queue not available")
    
    try:
        return monitor.redis_queue.get_queue_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/redis-queue/peek")
async def peek_redis_queue(count: int = 5):
    """Peek at items in Redis queue without removing them"""
    if not monitor.use_redis_queue or not monitor.redis_queue:
        raise HTTPException(status_code=400, detail="Redis queue not available")
    
    if count <= 0 or count > 50:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 50")
    
    try:
        return {
            "queue_peek": monitor.redis_queue.peek_queue(count),
            "peek_count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/redis-queue/clear")
async def clear_redis_queue():
    """Clear all items from Redis queue"""
    if not monitor.use_redis_queue or not monitor.redis_queue:
        raise HTTPException(status_code=400, detail="Redis queue not available")
    
    try:
        removed_count = monitor.redis_queue.clear_queue()
        return {
            "message": f"Cleared {removed_count} items from queue",
            "removed_count": removed_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Worker Management Routes ===

@app.get("/worker-stats")
async def get_worker_stats():
    """Get attachment worker statistics"""
    return worker_manager.get_stats()

@app.get("/worker-health")
async def get_worker_health():
    """Get attachment worker health status"""
    return await worker_manager.health_check()

@app.post("/worker-restart")
async def restart_workers():
    """Restart all attachment workers"""
    try:
        await worker_manager.shutdown()
        await worker_manager.startup()
        return {"message": "Workers restarted successfully"}
    except Exception as e:
        logger.error(f"Failed to restart workers: {e}")
        return {"error": f"Failed to restart workers: {str(e)}"}

@app.get("/system-overview")
async def get_system_overview():
    """Get comprehensive system overview including email monitoring and workers"""
    
    # Get email monitor status
    email_status = {
        "status": "running",
        "stats": monitor.stats,
        "config": {
            "email_groups": monitor.email_groups,
            "attachments_dir": str(monitor.attachments_dir),
            "file_types": monitor.file_types,
            "redis_queue_enabled": monitor.use_redis_queue
        }
    }
    
    # Add Redis queue info if enabled
    if monitor.use_redis_queue and monitor.redis_queue:
        try:
            queue_info = monitor.redis_queue.get_queue_info()
            email_status["redis_queue"] = queue_info
        except Exception as e:
            email_status["redis_queue"] = {"error": str(e)}
    
    # Get worker status
    worker_status = await worker_manager.health_check()
    worker_stats = worker_manager.get_stats()
    
    return {
        "email_monitor": email_status,
        "attachment_workers": {
            "health": worker_status,
            "statistics": worker_stats
        },
        "system_info": {
            "total_components": 2,
            "healthy_components": 1 + (1 if worker_status["workers_running"] > 0 else 0),
            "redis_queue_enabled": monitor.use_redis_queue,
            "integrated_workers": True
        }
    }


def main():
    """Run the enhanced FastAPI server with workers"""
    import uvicorn
    
    print("🚀 Email Monitor Dashboard with Attachment Workers")
    print("=" * 60)
    print("Features:")
    print("• Web dashboard at http://localhost:8000")
    print("• Real-time monitoring and stats")
    print("• JSON processing results viewer")
    print("• Email and attachment details")
    print("• Manual processing trigger")
    print("• Redis queue for attachment processing")
    print("• Queue monitoring and management APIs")
    print("• Attachment worker processes")
    print("• Worker health monitoring and auto-restart")
    print()
    print("Environment variables required:")
    print("• AZURE_CLIENT_ID")
    print("• AZURE_CLIENT_SECRET")
    print("• AZURE_TENANT_ID")
    print("• EMAIL_GROUPS (comma-separated)")
    print()
    print("Environment variables optional (Redis & Workers):")
    print("• USE_REDIS_QUEUE=true (enable Redis queue)")
    print("• REDIS_HOST=localhost")
    print("• REDIS_PORT=6379")
    print("• REDIS_DB=0")
    print("• REDIS_PASSWORD (if required)")
    print("• EMAIL_QUEUE_NAME=email_attachments")
    print("• MAX_QUEUE_SIZE=1000")
    print("• MAX_ATTACHMENT_SIZE=52428800 (50MB)")
    print("• MAX_CONCURRENT_WORKERS=2")
    print()
    print("New Worker APIs:")
    print("• GET /worker-stats - Worker statistics")
    print("• GET /worker-health - Worker health status")
    print("• POST /worker-restart - Restart all workers")
    print("• GET /system-overview - Complete system status")
    print("=" * 60)
    
    # Run FastAPI server
    uvicorn.run(
        "app.main_with_workers:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()