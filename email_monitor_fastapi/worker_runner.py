#!/usr/bin/env python3
"""
Worker Runner

Manages attachment worker processes for the email monitoring system.
Can be integrated with FastAPI lifespan or run as standalone process.
"""

import os
import sys
import asyncio
import logging
import signal
import multiprocessing as mp
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WorkerManager:
    """
    Manages multiple attachment worker processes
    """
    
    def __init__(self, num_workers: int = None):
        """Initialize the worker manager"""
        self.num_workers = num_workers or int(os.getenv('MAX_CONCURRENT_WORKERS', '1'))
        self.workers: List[mp.Process] = []
        self.running = False
        
        # Statistics
        self.stats = {
            'manager_started_at': datetime.now().isoformat(),
            'workers_started': 0,
            'workers_stopped': 0,
            'restarts': 0
        }
        
        logger.info(f"WorkerManager initialized with {self.num_workers} workers")
    
    async def start_workers(self):
        """Start all worker processes"""
        if self.running:
            logger.warning("Workers already running")
            return
        
        logger.info(f"Starting {self.num_workers} worker processes...")
        
        self.running = True
        
        for i in range(self.num_workers):
            try:
                # Create worker process
                worker = mp.Process(
                    target=self._run_worker_process,
                    args=(f"worker_{i+1}",),
                    name=f"AttachmentWorker_{i+1}"
                )
                
                worker.start()
                self.workers.append(worker)
                self.stats['workers_started'] += 1
                
                logger.info(f"Started worker {i+1}/{self.num_workers} (PID: {worker.pid})")
                
            except Exception as e:
                logger.error(f"Failed to start worker {i+1}: {e}")
        
        logger.info(f"All {len(self.workers)} workers started")
    
    async def stop_workers(self):
        """Stop all worker processes"""
        if not self.running:
            logger.warning("Workers not running")
            return
        
        logger.info("Stopping all workers...")
        self.running = False
        
        # Send termination signal to all workers
        for i, worker in enumerate(self.workers):
            if worker.is_alive():
                logger.info(f"Terminating worker {i+1} (PID: {worker.pid})")
                worker.terminate()
        
        # Wait for graceful shutdown
        shutdown_timeout = 30  # seconds
        for i, worker in enumerate(self.workers):
            try:
                worker.join(timeout=shutdown_timeout)
                if worker.is_alive():
                    logger.warning(f"Force killing worker {i+1} (PID: {worker.pid})")
                    worker.kill()
                    worker.join()
                
                self.stats['workers_stopped'] += 1
                logger.info(f"Worker {i+1} stopped")
                
            except Exception as e:
                logger.error(f"Error stopping worker {i+1}: {e}")
        
        self.workers.clear()
        logger.info("All workers stopped")
    
    def _run_worker_process(self, worker_id: str):
        """
        Target function for worker process
        
        This runs in a separate process and imports the worker module
        to avoid issues with multiprocessing and asyncio.
        """
        try:
            # Set worker-specific environment
            os.environ['PIPELINE_USER_ID'] = worker_id
            
            # Import and run the worker (done in subprocess to avoid import issues)
            from attachment_worker import main
            
            # Run the async main function
            asyncio.run(main())
            
        except Exception as e:
            logger.error(f"Worker process {worker_id} failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def monitor_workers(self):
        """Monitor worker health and restart if needed"""
        while self.running:
            dead_workers = []
            
            for i, worker in enumerate(self.workers):
                if not worker.is_alive():
                    logger.warning(f"Worker {i+1} (PID: {worker.pid}) is dead")
                    dead_workers.append(i)
            
            # Restart dead workers
            for worker_idx in reversed(dead_workers):  # Reverse to maintain indices
                old_worker = self.workers[worker_idx]
                logger.info(f"Restarting worker {worker_idx+1}")
                
                try:
                    # Create new worker
                    new_worker = mp.Process(
                        target=self._run_worker_process,
                        args=(f"worker_{worker_idx+1}",),
                        name=f"AttachmentWorker_{worker_idx+1}"
                    )
                    
                    new_worker.start()
                    self.workers[worker_idx] = new_worker
                    self.stats['restarts'] += 1
                    
                    logger.info(f"Restarted worker {worker_idx+1} (new PID: {new_worker.pid})")
                    
                except Exception as e:
                    logger.error(f"Failed to restart worker {worker_idx+1}: {e}")
            
            # Wait before next check
            await asyncio.sleep(30)  # Check every 30 seconds
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker manager statistics"""
        active_workers = sum(1 for w in self.workers if w.is_alive())
        
        return {
            **self.stats,
            'num_workers_configured': self.num_workers,
            'active_workers': active_workers,
            'total_workers': len(self.workers),
            'running': self.running,
            'worker_pids': [w.pid for w in self.workers if w.is_alive()]
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all workers"""
        health = {
            'manager_running': self.running,
            'workers_configured': self.num_workers,
            'workers_running': 0,
            'workers_healthy': 0,
            'worker_details': []
        }
        
        for i, worker in enumerate(self.workers):
            worker_info = {
                'worker_id': i + 1,
                'pid': worker.pid if worker.is_alive() else None,
                'alive': worker.is_alive(),
                'name': worker.name
            }
            
            if worker.is_alive():
                health['workers_running'] += 1
                health['workers_healthy'] += 1  # Basic health check
            
            health['worker_details'].append(worker_info)
        
        return health


class FastAPIWorkerManager:
    """
    Integration class for FastAPI lifespan management
    """
    
    def __init__(self, num_workers: int = None):
        self.worker_manager = WorkerManager(num_workers)
        self.monitor_task = None
    
    async def startup(self):
        """FastAPI startup event handler"""
        logger.info("Starting workers for FastAPI application")
        
        # Start workers
        await self.worker_manager.start_workers()
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self.worker_manager.monitor_workers())
        
        logger.info("Workers startup completed")
    
    async def shutdown(self):
        """FastAPI shutdown event handler"""
        logger.info("Shutting down workers for FastAPI application")
        
        # Cancel monitoring task
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop workers
        await self.worker_manager.stop_workers()
        
        logger.info("Workers shutdown completed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics for API endpoints"""
        return self.worker_manager.get_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for API endpoints"""
        return await self.worker_manager.health_check()


# Example FastAPI integration
def create_fastapi_with_workers():
    """
    Example of how to integrate the worker manager with FastAPI
    
    Add this to your main.py to include worker management in the FastAPI lifecycle.
    """
    from fastapi import FastAPI
    from contextlib import asynccontextmanager
    
    # Create worker manager
    worker_manager = FastAPIWorkerManager(num_workers=2)
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await worker_manager.startup()
        yield
        # Shutdown
        await worker_manager.shutdown()
    
    # Create FastAPI app with lifespan
    app = FastAPI(title="Email Monitor with Workers", lifespan=lifespan)
    
    @app.get("/worker-stats")
    async def get_worker_stats():
        """Get worker statistics"""
        return worker_manager.get_stats()
    
    @app.get("/worker-health")
    async def get_worker_health():
        """Get worker health status"""
        return await worker_manager.health_check()
    
    return app


async def standalone_runner():
    """Run workers as standalone process"""
    logger.info("Starting standalone worker runner")
    
    # Create worker manager
    manager = WorkerManager()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(manager.stop_workers())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start workers
        await manager.start_workers()
        
        # Run monitoring loop
        await manager.monitor_workers()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Standalone runner failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await manager.stop_workers()


def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--standalone":
        # Run as standalone process
        asyncio.run(standalone_runner())
    else:
        # Show usage
        print("""
Worker Runner Usage:

1. Standalone mode:
   python worker_runner.py --standalone

2. FastAPI integration:
   from worker_runner import FastAPIWorkerManager
   
   worker_manager = FastAPIWorkerManager(num_workers=2)
   
   @app.on_event("startup")
   async def startup_event():
       await worker_manager.startup()
   
   @app.on_event("shutdown") 
   async def shutdown_event():
       await worker_manager.shutdown()

3. Environment variables:
   MAX_CONCURRENT_WORKERS=2  # Number of worker processes
   REDIS_HOST=localhost
   REDIS_PORT=6379
   EMAIL_QUEUE_NAME=email_attachments

Worker Features:
- Automatic restart of failed workers
- Health monitoring and statistics
- Graceful shutdown handling
- Redis queue consumption
- Per-attachment processing with email context
- MIME type handling
- Retry logic with exponential backoff
""")


if __name__ == "__main__":
    main()