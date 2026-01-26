"""
Status endpoint - Check job status.

GET /status/{job_id} - Get current status of a timetable generation job
POST /cancel/{job_id} - Cancel a running job
GET /jobs - List all jobs
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..jobs.redis_queue import get_queue
from ..jobs.worker import worker_pool

logger = logging.getLogger(__name__)

router = APIRouter()


class StatusResponse(BaseModel):
    """Response for status request."""
    job_id: str
    status: str
    progress: int
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    queue_position: Optional[int] = None
    logs: Optional[list] = None


class CancelResponse(BaseModel):
    """Response for cancel request."""
    job_id: str
    cancelled: bool
    message: str


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_job_status(job_id: str, include_logs: bool = False) -> StatusResponse:
    """
    Get the current status of a timetable generation job.
    
    Args:
        job_id: The job identifier returned from /solve
        include_logs: Whether to include job logs in response
    
    Returns:
        Current job status including progress percentage
    
    Raises:
        HTTPException: If job not found
    """
    queue = get_queue()
    job = queue.get_job(job_id)
    
    if not job:
        # Check if job result exists in file system (job completed but removed from memory)
        from ..config import GENERATED_DIR
        import os
        import json
        
        result_path = os.path.join(GENERATED_DIR, f"result_{job_id}.json")
        if os.path.exists(result_path):
            logger.info(f"Job {job_id} not in queue but result file exists - returning completed status")
            try:
                with open(result_path, 'r') as f:
                    result_data = json.load(f)
                return StatusResponse(
                    job_id=job_id,
                    status="completed",
                    progress=100,
                    created_at=result_data.get("_meta", {}).get("saved_at"),
                    completed_at=result_data.get("_meta", {}).get("saved_at"),
                )
            except Exception as e:
                logger.error(f"Error reading result file for {job_id}: {e}")
        
        logger.warning(f"Job not found: {job_id} (queue has {queue.get_job_count()} jobs)")
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Job not found: {job_id}",
                "hint": "The job may have expired or the server was restarted. Please create a new job."
            }
        )
    
    # Get queue position if job is pending
    queue_position = None
    if job.status.value == "queued":
        queue_position = queue.get_queue_position(job_id)
    
    return StatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        queue_position=queue_position,
        logs=job.logs if include_logs else None,
    )


@router.post("/cancel/{job_id}", response_model=CancelResponse)
async def cancel_job(job_id: str) -> CancelResponse:
    """
    Request cancellation of a running job.
    
    Args:
        job_id: The job identifier
    
    Returns:
        Cancellation status
    """
    queue = get_queue()
    job = queue.get_job(job_id)
    
    if not job:
        # Check if job might be in worker pool but not visible yet
        if worker_pool.is_job_running(job_id):
            # Try to cancel via worker pool directly
            cancelled = worker_pool.cancel_job(job_id)
            return CancelResponse(
                job_id=job_id,
                cancelled=cancelled,
                message="Cancellation requested (job in worker pool)" if cancelled else "Unable to cancel"
            )
        
        # Job truly not found
        logger.warning(f"Cancel requested for unknown job: {job_id}")
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Job not found: {job_id}",
                "hint": "The job may have already completed, expired, or the server was restarted."
            }
        )
    
    # Can only cancel queued or running jobs
    if job.status.value in ("completed", "failed", "cancelled"):
        return CancelResponse(
            job_id=job_id,
            cancelled=False,
            message=f"Job already {job.status.value}"
        )
    
    # Request cancellation
    cancelled = worker_pool.cancel_job(job_id)
    
    return CancelResponse(
        job_id=job_id,
        cancelled=cancelled,
        message="Cancellation requested" if cancelled else "Unable to cancel"
    )


@router.get("/jobs")
async def list_jobs(limit: int = 50, status: Optional[str] = None):
    """
    List all jobs in the queue.
    
    Args:
        limit: Maximum number of jobs to return
        status: Optional status filter (queued, running, completed, failed, cancelled)
    
    Returns:
        List of all jobs with their status
    """
    queue = get_queue()
    
    # Convert status string to enum if provided
    status_filter = None
    if status:
        from ..jobs.redis_queue import JobStatus
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"message": f"Invalid status: {status}"}
            )
    
    jobs = queue.list_jobs(status=status_filter, limit=limit)
    
    return {
        "jobs": jobs,
        "total": len(jobs),
        "active_workers": worker_pool.get_active_count(),
        "max_workers": worker_pool.get_max_workers(),
    }
