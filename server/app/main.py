"""
Timetable Generator Backend - FastAPI Application

Production-grade constraint-based timetable generator using Google OR-Tools CP-SAT.
"""

import logging
import json
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import SERVER_HOST, SERVER_PORT, DATA_DIR, GENERATED_DIR, PARSED_DIR, RAW_UPLOADS_DIR
from .utils.path_helper import ensure_dir_exists
from .api import solve_router, status_router, result_router, validate_router, upload_router, download_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    
    Sets up required directories on startup and performs cleanup on shutdown.
    """
    # Startup
    logger.info("Starting Timetable Generator Backend...")
    
    # Ensure required directories exist
    ensure_dir_exists(DATA_DIR)
    ensure_dir_exists(RAW_UPLOADS_DIR)
    ensure_dir_exists(PARSED_DIR)
    ensure_dir_exists(GENERATED_DIR)
    
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info(f"Server running at http://{SERVER_HOST}:{SERVER_PORT}")
    
    # Initialize job queue and log its configuration
    from .jobs.redis_queue import get_queue
    queue = get_queue()
    logger.info(f"Job queue initialized: Redis={'connected' if queue.is_redis_available else 'not available (using in-memory)'}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Timetable Generator Backend...")


# Create FastAPI app
app = FastAPI(
    title="Timetable Generator API",
    description="""
    Production-grade timetable generator using Google OR-Tools CP-SAT.
    
    ## Features
    - One global solve (all classes together)
    - Relocatable design (no hardcoded paths)
    - Schema-first validation
    - Async job execution
    - Infeasibility diagnostics
    - Manual swap validation
    
    ## Endpoints
    - **POST /api/v1/timetable/solve** - Submit generation job
    - **GET /api/v1/timetable/status/{job_id}** - Check job status
    - **GET /api/v1/timetable/result/{job_id}** - Get generated timetable
    - **POST /api/v1/timetable/validate** - Validate manual swap
    - **POST /api/v1/timetable/upload** - Upload demo data
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "detail": exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)},
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "detail": {"message": "Internal server error"},
            "status_code": 500,
        },
    )


# Include API routers
API_PREFIX = "/api/v1/timetable"

app.include_router(solve_router, prefix=API_PREFIX, tags=["solve"])
app.include_router(status_router, prefix=API_PREFIX, tags=["status"])
app.include_router(result_router, prefix=API_PREFIX, tags=["result"])
app.include_router(validate_router, prefix=API_PREFIX, tags=["validate"])
app.include_router(upload_router, prefix=API_PREFIX, tags=["upload"])
app.include_router(download_router, prefix=API_PREFIX, tags=["download"])


# Root endpoints
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Timetable Generator API",
        "version": "1.0.0",
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "endpoints": {
            "solve": f"{API_PREFIX}/solve",
            "status": f"{API_PREFIX}/status/{{job_id}}",
            "result": f"{API_PREFIX}/result/{{job_id}}",
            "validate": f"{API_PREFIX}/validate",
            "upload": f"{API_PREFIX}/upload",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get(f"{API_PREFIX}/config")
async def get_solver_config():
    """
    Get current solver configuration.
    
    Returns time limits, demo mode settings, and other solver parameters
    that can help the frontend provide better UX.
    """
    from .config import (
        SOLVER_TIMEOUT_SECONDS,
        DEMO_MODE,
        DEMO_SOLVE_TIME_SEC,
        DEFAULT_SOLVE_TIME_SEC,
        MAX_SOLVE_TIME_SEC,
        CP_SAT_SEARCH_WORKERS,
        MAX_CONCURRENT_JOBS,
    )
    
    return {
        "solver": {
            "timeout_seconds": SOLVER_TIMEOUT_SECONDS,
            "demo_mode": DEMO_MODE,
            "demo_time_seconds": DEMO_SOLVE_TIME_SEC,
            "default_time_seconds": DEFAULT_SOLVE_TIME_SEC,
            "max_time_seconds": MAX_SOLVE_TIME_SEC,
            "search_workers": CP_SAT_SEARCH_WORKERS,
        },
        "queue": {
            "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
        },
        "features": {
            "deadline_scheduling": True,
            "force_fresh_solve": True,
        },
        "recommendations": {
            "demo_time_limit": DEMO_SOLVE_TIME_SEC,
            "production_time_limit": DEFAULT_SOLVE_TIME_SEC,
            "complex_constraints_time_limit": min(MAX_SOLVE_TIME_SEC, 300),
        },
    }


# Run with uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        log_level="info",
    )
