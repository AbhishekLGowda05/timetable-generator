"""
Result endpoint - Get completed timetable.

GET /result/{job_id} - Get the generated timetable for a completed job
GET /result/{job_id}/diagnostics - Get diagnostics for infeasible jobs
GET /result/{job_id}/section/{section_id} - Get timetable for specific section
GET /result/{job_id}/teacher/{teacher_id} - Get schedule for specific teacher
"""

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..jobs.redis_queue import get_queue, JobStatus
from ..config import GENERATED_DIR, RESULTS_DIR
from ..utils.path_helper import ensure_dir_exists

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_result_from_file(job_id: str) -> dict | None:
    """
    Try to load result from saved files.
    
    Checks both:
    1. data/results/job_{job_id}.json (new persistent location)
    2. data/generated/result_{job_id}.json (legacy location)
    """
    # Try new persistent location first
    persist_path = Path(RESULTS_DIR) / f"job_{job_id}.json"
    if persist_path.exists():
        try:
            with open(persist_path, "r") as f:
                data = json.load(f)
                # Return full_result if available, else the whole structure
                return data.get("full_result", data)
        except Exception as e:
            logger.error(f"Failed to load result from {persist_path}: {e}")
    
    # Fall back to legacy location
    legacy_path = Path(GENERATED_DIR) / f"result_{job_id}.json"
    if legacy_path.exists():
        try:
            with open(legacy_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load result from {legacy_path}: {e}")
    
    return None


def _load_persisted_job_data(job_id: str) -> dict | None:
    """
    Load full persisted job data including metadata.
    
    Returns the complete job record with:
    - job_id, input_hash, status, time_used_seconds
    - relaxed_constraints, diagnostics
    - result (with classes and teachers views)
    - solver_stats
    """
    persist_path = Path(RESULTS_DIR) / f"job_{job_id}.json"
    if persist_path.exists():
        try:
            with open(persist_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load job data from {persist_path}: {e}")
    return None


@router.get("/result/{job_id}")
async def get_result(job_id: str, format: str = "json"):
    """
    Get the generated timetable for a completed job.
    
    Args:
        job_id: The job identifier
        format: Output format ('json' or 'file')
    
    Returns:
        Generated timetable matching solver_output.schema.json
    
    Raises:
        HTTPException: If job not found or not completed
    """
    queue = get_queue()
    job = queue.get_job(job_id)
    
    # If job not in queue, try to load from file
    result = None
    status = None
    progress = 0
    error = None
    
    if job:
        status = job.status
        progress = job.progress
        error = job.error
        result = job.result
    else:
        # Try to load from file
        result = _load_result_from_file(job_id)
        if result:
            status = JobStatus.COMPLETED
            progress = 100
    
    if not status:
        logger.warning(f"Job not found: {job_id}")
        raise HTTPException(
            status_code=404,
            detail={"message": f"Job not found: {job_id}"}
        )
    
    if status == JobStatus.QUEUED:
        raise HTTPException(
            status_code=202,
            detail={
                "message": "Job is still queued",
                "status": status.value,
                "progress": progress,
            }
        )
    
    if status == JobStatus.RUNNING:
        raise HTTPException(
            status_code=202,
            detail={
                "message": "Job is still running",
                "status": status.value,
                "progress": progress,
            }
        )
    
    if status == JobStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Job was cancelled",
                "status": status.value,
            }
        )
    
    if status == JobStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Job failed",
                "error": error,
            }
        )
    
    # Try loading from file if not in memory
    if not result:
        result = _load_result_from_file(job_id)
    
    if not result:
        raise HTTPException(
            status_code=500,
            detail={"message": "Job completed but no result available"}
        )
    
    # If format is 'file', save to disk and return file path
    if format == "file":
        ensure_dir_exists(GENERATED_DIR)
        output_path = GENERATED_DIR / f"{job_id}_timetable.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved timetable to: {output_path}")
        
        return FileResponse(
            path=output_path,
            filename=f"timetable_{job_id[:8]}.json",
            media_type="application/json",
        )
    
    # Return JSON response wrapped in expected format for frontend
    # The frontend expects: { job_id, timetable_json, diagnostics, ... }
    return {
        "job_id": job_id,
        "timetable_json": result,
        "diagnostics": result.get("diagnostics", []),
        "warnings": result.get("warnings", []),
        "relaxed_constraints": result.get("relaxation_info", {}).get("relaxed_constraints", []),
        "solver_stats": result.get("solver_stats", {}),
        "meta": result.get("meta", {}),
    }


@router.get("/result/{job_id}/full")
async def get_full_result(job_id: str):
    """
    Get the full persisted job result including all metadata.
    
    Returns the complete job record matching the persistence schema:
    - job_id, input_hash, status
    - time_used_seconds, time_limit_seconds
    - relaxed_constraints, diagnostics
    - result (with classes and teachers views)
    - solver_stats
    
    Args:
        job_id: The job identifier
    
    Returns:
        Full job result with all metadata
    """
    # Try to load full persisted data
    job_data = _load_persisted_job_data(job_id)
    if job_data:
        return job_data
    
    # Fall back to loading from queue/file
    queue = get_queue()
    job = queue.get_job(job_id)
    
    result = None
    if job:
        if job.status not in [JobStatus.COMPLETED]:
            raise HTTPException(
                status_code=400,
                detail={"message": f"Job not completed. Status: {job.status.value}"}
            )
        result = job.result
    else:
        result = _load_result_from_file(job_id)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Job not found: {job_id}"}
        )
    
    # Build response in the persisted format
    return {
        "job_id": job_id,
        "input_hash": result.get("meta", {}).get("input_hash", ""),
        "status": result.get("status", "unknown"),
        "time_used_seconds": result.get("meta", {}).get("solve_time_seconds", 0),
        "time_limit_seconds": result.get("meta", {}).get("time_limit_seconds", 0),
        "relaxed_constraints": result.get("relaxation_info", {}).get("relaxed_constraints", []),
        "diagnostics": result.get("diagnostics", []),
        "result": {
            "classes": result.get("timetable", {}),
            "teachers": result.get("teacher_schedules", {}),
        },
        "solver_stats": result.get("solver_stats", {}),
    }


@router.get("/result/{job_id}/diagnostics")
async def get_diagnostics(job_id: str):
    """
    Get diagnostics for an infeasible or failed job.
    
    Args:
        job_id: The job identifier
    
    Returns:
        Diagnostic information explaining why the solve failed
    """
    queue = get_queue()
    job = queue.get_job(job_id)
    
    result = None
    if job:
        result = job.result
    else:
        result = _load_result_from_file(job_id)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Job not found or no result: {job_id}"}
        )
    
    return {
        "job_id": job_id,
        "status": result.get("status"),
        "diagnostics": result.get("diagnostics", []),
        "warnings": result.get("warnings", []),
    }


@router.get("/result/{job_id}/section/{section_id}")
async def get_section_timetable(job_id: str, section_id: str):
    """
    Get the timetable for a specific section.
    
    Args:
        job_id: The job identifier
        section_id: The section identifier
    
    Returns:
        Timetable for the specified section
    """
    queue = get_queue()
    job = queue.get_job(job_id)
    
    result = None
    if job:
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail={"message": f"Job not completed. Status: {job.status.value}"}
            )
        result = job.result
    else:
        result = _load_result_from_file(job_id)
    
    if not result:
        raise HTTPException(status_code=404, detail={"message": f"Job not found: {job_id}"})
    
    timetable = result.get("timetable", {})
    
    if section_id not in timetable:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Section not found: {section_id}"}
        )
    
    return {
        "section_id": section_id,
        "timetable": timetable[section_id],
    }


@router.get("/result/{job_id}/teacher/{teacher_id}")
async def get_teacher_schedule(job_id: str, teacher_id: str):
    """
    Get the schedule for a specific teacher.
    
    Args:
        job_id: The job identifier
        teacher_id: The teacher identifier
    
    Returns:
        Schedule for the specified teacher
    """
    queue = get_queue()
    job = queue.get_job(job_id)
    
    result = None
    if job:
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail={"message": f"Job not completed. Status: {job.status.value}"}
            )
        result = job.result
    else:
        result = _load_result_from_file(job_id)
    
    if not result:
        raise HTTPException(status_code=404, detail={"message": f"Job not found: {job_id}"})
    
    teacher_schedules = result.get("teacher_schedules", {})
    
    if teacher_id not in teacher_schedules:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Teacher not found: {teacher_id}"}
        )
    
    return {
        "teacher_id": teacher_id,
        "schedule": teacher_schedules[teacher_id],
    }
