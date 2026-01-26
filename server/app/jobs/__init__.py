"""
Job management module for the Timetable Generator Backend.

Uses Redis for persistent job storage when available,
falls back to in-memory storage for development.
"""

from .redis_queue import RedisJobQueue, Job, JobStatus, get_queue
from .worker import execute_solver_job, worker_pool, CancellationToken


# Lazy alias for backward compatibility (use get_queue() instead)
def _get_job_queue():
    """Lazy accessor for job_queue - use get_queue() instead."""
    return get_queue()


__all__ = [
    "RedisJobQueue",
    "Job",
    "JobStatus",
    "get_queue",
    "execute_solver_job",
    "worker_pool",
    "CancellationToken",
]
