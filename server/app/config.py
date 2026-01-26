"""
Configuration module for the Timetable Generator Backend.

This module provides centralized configuration management with:
- Relocatable paths using pathlib (no hardcoded absolute paths)
- Environment variable support for overrides
- Dynamic project root detection
- Two-phase solver configuration
- Result persistence settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# ============================================================================
# Solver Version (increment when solver logic changes to invalidate cache)
# ============================================================================

SOLVER_VERSION: str = os.getenv("SOLVER_VERSION", "2.0.0")


def _find_project_root() -> Path:
    """
    Dynamically detect project root by walking up from this file.
    Looks for markers like 'shared' directory or 'data' directory.
    """
    current = Path(__file__).resolve()
    
    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        # Check for project markers
        if (parent / "shared").is_dir() and (parent / "data").is_dir():
            return parent
        if (parent / "server").is_dir() and (parent / "shared").is_dir():
            return parent
    
    # Fallback: assume we're in server/app/, go up two levels
    return Path(__file__).resolve().parent.parent.parent


# ============================================================================
# Path Configuration (All Relative - Relocatable Design)
# ============================================================================

PROJECT_ROOT: Path = _find_project_root()

# Data directories
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_UPLOADS_DIR: Path = DATA_DIR / "raw_uploads"
PARSED_DIR: Path = DATA_DIR / "parsed"
GENERATED_DIR: Path = DATA_DIR / "generated"
RESULTS_DIR: Path = DATA_DIR / "results"  # Persisted job results

# Schema directory
SCHEMAS_DIR: Path = PROJECT_ROOT / "shared" / "schemas"

# Server directory
SERVER_DIR: Path = PROJECT_ROOT / "server"

# ============================================================================
# Server Configuration (Environment Variable Overrides)
# ============================================================================

SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8010"))

# ============================================================================
# Solver Configuration
# ============================================================================

# Solver execution
# Default timeout increased to 120 seconds for better results with hard constraints
# This accounts for complex timetables with 40+ sections (teacher:section ratio ~1.5:1)
SOLVER_TIMEOUT_SECONDS: int = int(os.getenv("SOLVER_TIMEOUT", "120"))
SOLVER_NUM_WORKERS: int = int(os.getenv("SOLVER_NUM_WORKERS", "4"))

# Time limits:
# - DEMO_SOLVE_TIME: For demo/single requests - immediate allocation, higher time limit
#   Set to 120 seconds to allow proper optimization even with all hard constraints enabled
# - DEFAULT_SOLVE_TIME: For queued requests in multi-tenant scenarios
# - MAX_SOLVE_TIME: Absolute maximum (for deadline-based scheduling)
# 
# Rationale for increased times:
# - With teacher:section ratio of 1.5:1 and ~40 sections, the model has ~60 teachers
# - Each section has ~40-45 periods/week, teachers handle ~28-30 periods/week
# - The solver needs adequate time to find feasible solutions with all hard constraints
DEMO_SOLVE_TIME_SEC: int = int(os.getenv("DEMO_SOLVE_TIME_SEC", "120"))
DEFAULT_SOLVE_TIME_SEC: int = int(os.getenv("DEFAULT_SOLVE_TIME_SEC", "90"))
MAX_SOLVE_TIME_SEC: int = int(os.getenv("MAX_SOLVE_TIME_SEC", "1800"))  # 30 minutes max for deadline scheduling

# Minimum solve time (for quick feasibility checks)
MIN_SOLVE_TIME_SEC: int = int(os.getenv("MIN_SOLVE_TIME_SEC", "10"))

# Deadline buffer - seconds to reserve before deadline for processing
DEADLINE_BUFFER_SEC: int = int(os.getenv("DEADLINE_BUFFER_SEC", "30"))

# Demo mode: When enabled, jobs get immediate allocation with higher time limits
# In demo mode, there's only one request at a time, so maximize solver time
DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"

# CP-SAT solver parallelism (use more workers for better optimization)
# More workers = better exploration of search space = higher chance of finding optimal solution
CP_SAT_SEARCH_WORKERS: int = int(os.getenv("CP_SAT_SEARCH_WORKERS", "8"))

# Random seed for reproducible debugging (None = random each run)
CP_SAT_RANDOM_SEED: int = int(os.getenv("CP_SAT_RANDOM_SEED", "0")) if os.getenv("CP_SAT_RANDOM_SEED") else None

# Two-phase solver configuration
# Phase 1: Feasibility solve (find ANY valid timetable)
# Phase 2: Optimization solve (improve the solution)
SOLVER_PHASE1_TIME_FRACTION: float = float(os.getenv("SOLVER_PHASE1_TIME_FRACTION", "0.4"))  # 40% for feasibility
SOLVER_PHASE2_TIME_FRACTION: float = float(os.getenv("SOLVER_PHASE2_TIME_FRACTION", "0.6"))  # 60% for optimization

# Minimum time per phase (ensures each phase gets meaningful time)
MIN_PHASE1_TIME_SEC: int = int(os.getenv("MIN_PHASE1_TIME_SEC", "15"))
MIN_PHASE2_TIME_SEC: int = int(os.getenv("MIN_PHASE2_TIME_SEC", "15"))

# Maximum relaxation iterations before giving up
SOLVER_MAX_RELAXATION_ITERATIONS: int = int(os.getenv("SOLVER_MAX_RELAXATION_ITERATIONS", "10"))

# Time budget per relaxation attempt (fraction of remaining phase1 time)
RELAXATION_ATTEMPT_TIME_FRACTION: float = float(os.getenv("RELAXATION_ATTEMPT_TIME_FRACTION", "0.3"))

# Payload hashing
PAYLOAD_HASH_ALGO: str = os.getenv("PAYLOAD_HASH_ALGO", "sha256")

# ============================================================================
# Job Configuration
# ============================================================================

MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "5"))
JOB_RETENTION_HOURS: int = int(os.getenv("JOB_RETENTION_HOURS", "24"))

# Concurrency limits
MAX_GLOBAL_ACTIVE_SOLVES: int = int(os.getenv("MAX_GLOBAL_ACTIVE_SOLVES", "6"))
MAX_PER_TENANT_ACTIVE: int = int(os.getenv("MAX_PER_TENANT_ACTIVE", "1"))
WORKER_POLL_INTERVAL_SEC: float = float(os.getenv("WORKER_POLL_INTERVAL_SEC", "1.0"))
WORKER_SEMAPHORE_TTL_SEC: int = int(os.getenv("WORKER_SEMAPHORE_TTL_SEC", "300"))

# Worker identification
WORKER_ID: str = os.getenv("WORKER_ID", f"worker-{os.getpid()}")

# ============================================================================
# Database Configuration (Supabase)
# ============================================================================

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

# Database connection pool
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))

# ============================================================================
# Redis Configuration (Upstash)
# ============================================================================

REDIS_URL: str = os.getenv("REDIS_URL", "")
UPSTASH_REDIS_URL: str = os.getenv("UPSTASH_REDIS_URL", REDIS_URL)
UPSTASH_REDIS_TOKEN: str = os.getenv("UPSTASH_REDIS_TOKEN", "")

# Redis keys
REDIS_QUEUE_KEY: str = "solver:queue:jobs"
REDIS_QUEUE_DEAD_LETTER: str = "solver:queue:failed"

# ============================================================================
# Storage Configuration (Cloudflare R2)
# ============================================================================

R2_BUCKET: str = os.getenv("R2_BUCKET", "")
R2_ENDPOINT_URL: str = os.getenv("R2_ENDPOINT_URL", "")
R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_PUBLIC_URL: str = os.getenv("R2_PUBLIC_URL", "")  # For public access

# Presigned URL expiration
R2_PRESIGNED_URL_EXPIRATION_SEC: int = int(os.getenv("R2_PRESIGNED_URL_EXPIRATION_SEC", "3600"))

# ============================================================================
# Observability Configuration (Sentry)
# ============================================================================

SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT: str = os.getenv("SENTRY_ENVIRONMENT", "development")
SENTRY_TRACES_SAMPLE_RATE: float = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

# Enable/disable Sentry
SENTRY_ENABLED: bool = os.getenv("SENTRY_ENABLED", "false").lower() == "true" and bool(SENTRY_DSN)

# ============================================================================
# Parser Configuration
# ============================================================================

PARSE_SYNC_MAX_SIZE: int = int(os.getenv("PARSE_SYNC_MAX_SIZE", "1048576"))  # 1MB default

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = os.getenv(
    "LOG_FORMAT", 
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ============================================================================
# API Configuration
# ============================================================================

API_PREFIX: str = "/api/v1/timetable"
API_TITLE: str = "Timetable Generator API"
API_VERSION: str = "1.0.0"
API_DESCRIPTION: str = """
Production-grade constraint-based timetable generator using Google OR-Tools CP-SAT.

## Features
- Global solve (all classes together)
- Relocatable design (no hardcoded paths)
- Schema-first validation
- Async job execution
- Infeasibility diagnostics
- Manual swap validation
"""

# ============================================================================
# CORS Configuration
# ============================================================================

CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS: list = ["*"]
CORS_ALLOW_HEADERS: list = ["*"]

# ============================================================================
# Directory Initialization
# ============================================================================

def ensure_directories() -> None:
    """Create all required directories if they don't exist."""
    directories = [
        DATA_DIR,
        RAW_UPLOADS_DIR,
        PARSED_DIR,
        GENERATED_DIR,
        RESULTS_DIR,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def get_config_summary() -> dict:
    """Return a summary of current configuration for debugging."""
    return {
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "results_dir": str(RESULTS_DIR),
        "schemas_dir": str(SCHEMAS_DIR),
        "server_host": SERVER_HOST,
        "server_port": SERVER_PORT,
        "solver_version": SOLVER_VERSION,
        "solver_timeout": SOLVER_TIMEOUT_SECONDS,
        "default_solve_time": DEFAULT_SOLVE_TIME_SEC,
        "demo_solve_time": DEMO_SOLVE_TIME_SEC,
        "max_solve_time": MAX_SOLVE_TIME_SEC,
        "min_solve_time": MIN_SOLVE_TIME_SEC,
        "deadline_buffer": DEADLINE_BUFFER_SEC,
        "demo_mode": DEMO_MODE,
        "cp_sat_workers": CP_SAT_SEARCH_WORKERS,
        "phase1_fraction": SOLVER_PHASE1_TIME_FRACTION,
        "phase2_fraction": SOLVER_PHASE2_TIME_FRACTION,
        "max_relaxation_iterations": SOLVER_MAX_RELAXATION_ITERATIONS,
        "max_global_active": MAX_GLOBAL_ACTIVE_SOLVES,
        "max_per_tenant_active": MAX_PER_TENANT_ACTIVE,
        "worker_id": WORKER_ID,
        "sentry_enabled": SENTRY_ENABLED,
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
        "redis_configured": bool(REDIS_URL),
        "r2_configured": bool(R2_BUCKET and R2_ENDPOINT_URL),
        "log_level": LOG_LEVEL,
    }


def validate_production_config() -> list[str]:
    """
    Validate that required production configuration is present.
    Returns list of missing/invalid config items.
    """
    issues = []
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        issues.append("SUPABASE_URL and SUPABASE_KEY required for production")
    
    if not REDIS_URL and not UPSTASH_REDIS_URL:
        issues.append("REDIS_URL or UPSTASH_REDIS_URL required for production")
    
    if not R2_BUCKET or not R2_ENDPOINT_URL:
        issues.append("R2_BUCKET and R2_ENDPOINT_URL required for production storage")
    
    if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
        issues.append("R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY required")
    
    if MAX_GLOBAL_ACTIVE_SOLVES < 1:
        issues.append("MAX_GLOBAL_ACTIVE_SOLVES must be >= 1")
    
    if MAX_PER_TENANT_ACTIVE < 1:
        issues.append("MAX_PER_TENANT_ACTIVE must be >= 1")
    
    if SENTRY_ENABLED and not SENTRY_DSN:
        issues.append("SENTRY_DSN required when SENTRY_ENABLED=true")
    
    return issues


# Initialize directories on module load
ensure_directories()
