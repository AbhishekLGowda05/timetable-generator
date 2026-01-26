"""
In-memory job queue for managing solver jobs.

Thread-safe implementation using locks for concurrent access.
This is suitable for demo purposes; production would use Redis/Celery.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Possible states for a solver job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Represents a timetable solver job."""
    
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0  # 0-100
    solver_input: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert job to dictionary for API responses."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class JobQueue:
    """
    Thread-safe in-memory job registry.
    
    Manages job creation, status updates, and result storage.
    Uses threading.Lock for concurrent access safety.
    """
    
    def __init__(self, max_jobs: int = 100):
        """
        Initialize the job queue.
        
        Args:
            max_jobs: Maximum number of jobs to retain (oldest are removed)
        """
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs
    
    def create_job(self, job_id: str, solver_input: dict) -> Job:
        """
        Create a new job and add it to the queue.
        
        Args:
            job_id: Unique identifier for the job
            solver_input: The solver input data
        
        Returns:
            The created Job object
        """
        with self._lock:
            # Cleanup old jobs if at capacity
            if len(self._jobs) >= self._max_jobs:
                self._cleanup_oldest_jobs()
            
            job = Job(
                job_id=job_id,
                status=JobStatus.QUEUED,
                progress=0,
                solver_input=solver_input,
                created_at=datetime.utcnow(),
            )
            self._jobs[job_id] = job
            logger.info(f"Created job: {job_id}")
            return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve a job by its ID.
        
        Args:
            job_id: The job identifier
        
        Returns:
            The Job object if found, None otherwise
        """
        with self._lock:
            return self._jobs.get(job_id)
    
    def update_status(
        self, 
        job_id: str, 
        status: JobStatus, 
        progress: int = 0
    ) -> bool:
        """
        Update job status and progress.
        
        Args:
            job_id: The job identifier
            status: New job status
            progress: Progress percentage (0-100)
        
        Returns:
            True if job was found and updated, False otherwise
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.warning(f"Job not found for status update: {job_id}")
                return False
            
            job.status = status
            job.progress = min(100, max(0, progress))
            
            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = datetime.utcnow()
            elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.completed_at = datetime.utcnow()
            
            logger.info(f"Job {job_id} status: {status.value}, progress: {progress}%")
            return True
    
    def store_result(self, job_id: str, result: dict) -> bool:
        """
        Store the solver result for a completed job.
        
        Args:
            job_id: The job identifier
            result: The solver result dictionary
        
        Returns:
            True if successful, False if job not found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.warning(f"Job not found for result storage: {job_id}")
                return False
            
            job.result = result
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.utcnow()
            
            logger.info(f"Stored result for job: {job_id}")
            return True
    
    def store_error(self, job_id: str, error: str) -> bool:
        """
        Store an error message for a failed job.
        
        Args:
            job_id: The job identifier
            error: The error message
        
        Returns:
            True if successful, False if job not found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.warning(f"Job not found for error storage: {job_id}")
                return False
            
            job.error = error
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            
            logger.error(f"Job {job_id} failed: {error}")
            return True
    
    def get_all_jobs(self) -> list[Job]:
        """Get all jobs in the queue."""
        with self._lock:
            return list(self._jobs.values())
    
    def get_active_jobs(self) -> list[Job]:
        """Get all jobs that are queued or running."""
        with self._lock:
            return [
                job for job in self._jobs.values()
                if job.status in (JobStatus.QUEUED, JobStatus.RUNNING)
            ]
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from the queue.
        
        Args:
            job_id: The job identifier
        
        Returns:
            True if job was deleted, False if not found
        """
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Deleted job: {job_id}")
                return True
            return False
    
    def _cleanup_oldest_jobs(self, keep_count: int = 50) -> None:
        """
        Remove oldest completed/failed jobs to free up space.
        
        Args:
            keep_count: Number of jobs to keep
        """
        # Get completed/failed jobs sorted by creation time
        completed_jobs = [
            job for job in self._jobs.values()
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED)
        ]
        completed_jobs.sort(key=lambda j: j.created_at)
        
        # Remove oldest jobs
        jobs_to_remove = len(self._jobs) - keep_count
        for job in completed_jobs[:jobs_to_remove]:
            del self._jobs[job.job_id]
            logger.info(f"Cleaned up old job: {job.job_id}")


# Global job queue instance
job_queue = JobQueue()
