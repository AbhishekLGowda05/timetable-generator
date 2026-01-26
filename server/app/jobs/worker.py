"""
Background worker for executing solver jobs.

Runs solver jobs in separate threads with:
- Timeout handling
- Cancellation support
- Progress reporting
- Result persistence
"""

import logging
import threading
import os
import json
from threading import Thread, Event
from datetime import datetime

from .redis_queue import get_queue, JobStatus

logger = logging.getLogger(__name__)


class CancellationToken:
    """Token for checking if a job has been cancelled."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self._cancelled = Event()
        self._queue = get_queue()
    
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        if self._cancelled.is_set():
            return True
        # Check queue for external cancellation request
        if self._queue.is_cancellation_requested(self.job_id):
            self._cancelled.set()
            return True
        return False
    
    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled.set()
        self._queue.request_cancellation(self.job_id)


def execute_solver_job(
    job_id: str,
    solver_input: dict,
    cancellation_token: CancellationToken,
) -> None:
    """
    Execute a solver job in the background using two-phase solving.
    
    This function uses the TwoPhaseSolver for guaranteed feasibility:
    1. Check cache by input hash
    2. Capacity analysis - pre-flight check
    3. Phase 1 - find feasibility with auto-relaxation
    4. Phase 2 - optimize solution
    5. Cache result by hash
    6. Persist result to data/results/{job_id}.json
    
    Logs emitted: JobQueued, JobStarted, Phase1Start, Phase1Result, 
                  ConstraintsRelaxed, Phase2Start, Phase2End, JobCompleted
    
    Args:
        job_id: The job identifier
        solver_input: The complete solver input data
        cancellation_token: Token for checking/requesting cancellation
    """
    logger.info(f"[JobStarted] job_id={job_id}")
    queue = get_queue()
    
    try:
        # Update status to RUNNING
        queue.update_status(job_id, JobStatus.RUNNING, progress=5)
        queue.add_log(job_id, "[JobStarted] Two-phase solver initialized", "info")
        
        # Import solvers and utilities
        from ..solver.two_phase_solver import TwoPhaseSolver, analyze_capacity, compute_input_hash
        from ..solver.preprocess import validate_feasibility
        from ..solver.diagnostics import analyze_infeasibility
        from ..config import SOLVER_TIMEOUT_SECONDS, GENERATED_DIR, RESULTS_DIR
        
        # Check cancellation
        if cancellation_token.is_cancelled():
            queue.update_status(job_id, JobStatus.CANCELLED)
            queue.add_log(job_id, "[JobCancelled] Cancelled before start", "warning")
            return
        
        # Compute input hash for caching
        input_hash = compute_input_hash(solver_input)
        queue.add_log(job_id, f"Input hash: {input_hash[:16]}...", "info")
        
        # Check for force_fresh - default to True to ensure fresh results
        force_fresh = solver_input.get("force_fresh", True)
        
        # Check cache if not forcing fresh solve
        if not force_fresh:
            cached = queue.get_result_by_hash(input_hash)
            if cached:
                queue.add_log(job_id, f"[CacheHit] Using cached result from job {cached.get('job_id')}", "info")
                result = cached.get("result", {})
                result["meta"] = result.get("meta", {})
                result["meta"]["from_cache"] = True
                result["meta"]["original_job_id"] = cached.get("job_id")
                result["meta"]["cached_at"] = cached.get("cached_at")
                
                _save_result(job_id, input_hash, result, GENERATED_DIR, RESULTS_DIR)
                queue.store_result(job_id, result)
                queue.add_log(job_id, "[JobCompleted] From cache", "info")
                return
        else:
            # Invalidate any existing cache for this input
            queue.invalidate_hash_cache(input_hash)
            queue.add_log(job_id, "[CacheInvalidated] Force fresh enabled", "info")
        
        # Pre-flight capacity analysis
        queue.update_status(job_id, JobStatus.RUNNING, progress=10)
        queue.add_log(job_id, "[CapacityAnalysis] Running capacity check", "info")
        
        capacity = analyze_capacity(solver_input)
        
        if not capacity.is_sufficient:
            queue.add_log(
                job_id, 
                f"[CapacityWarning] Insufficient capacity (ratio: {capacity.capacity_ratio:.2f})", 
                "warning"
            )
            for warning in capacity.warnings:
                queue.add_log(job_id, f"  {warning}", "warning")
        else:
            queue.add_log(
                job_id,
                f"[CapacityOK] {capacity.num_teachers} teachers, {capacity.num_classes} classes (ratio: {capacity.capacity_ratio:.2f})",
                "info"
            )
        
        # Pre-flight feasibility check
        queue.update_status(job_id, JobStatus.RUNNING, progress=15)
        queue.add_log(job_id, "[FeasibilityCheck] Running pre-flight validation", "info")
        
        is_feasible, warnings, diagnostic_details = validate_feasibility(solver_input)
        
        for warning in warnings:
            queue.add_log(job_id, f"  {warning}", "warning")
        
        if not is_feasible:
            queue.add_log(job_id, "[FeasibilityWarning] Issues found, proceeding with two-phase solver", "warning")
        
        # Check cancellation
        if cancellation_token.is_cancelled():
            queue.update_status(job_id, JobStatus.CANCELLED)
            queue.add_log(job_id, "[JobCancelled] During feasibility check", "warning")
            return
        
        # Initialize two-phase solver
        queue.update_status(job_id, JobStatus.RUNNING, progress=20)
        queue.add_log(job_id, "[Phase1Start] Initializing two-phase solver", "info")
        
        solver = TwoPhaseSolver(solver_input)
        
        # Create progress callback with cancellation check
        def progress_callback(percent: int) -> bool:
            # Map solver progress (0-100) to our range (20-90)
            mapped_progress = 20 + int(percent * 0.7)
            queue.update_status(job_id, JobStatus.RUNNING, progress=mapped_progress)
            
            # Return cancellation status to solver
            return cancellation_token.is_cancelled()
        
        # Get time limit from solver_input
        time_limit = solver_input.get("time_limit_seconds", SOLVER_TIMEOUT_SECONDS)
        queue.add_log(job_id, f"Time limit: {time_limit}s", "info")
        
        # Run two-phase solver
        result = solver.solve(
            time_limit=time_limit,
            progress_callback=progress_callback,
        )
        
        # Check cancellation after solve
        if cancellation_token.is_cancelled():
            queue.update_status(job_id, JobStatus.CANCELLED)
            queue.add_log(job_id, "[JobCancelled] During solve", "warning")
            return
        
        # Add warnings to result
        if warnings:
            result["warnings"] = result.get("warnings", []) + warnings
        
        # Log phase results
        relaxed = result.get("relaxation_info", {}).get("relaxed_constraints", [])
        if relaxed:
            queue.add_log(job_id, f"[ConstraintsRelaxed] {', '.join(relaxed)}", "info")
        
        # Log result details
        solve_time = result.get("meta", {}).get("solve_time_seconds", 0)
        phase1_time = result.get("meta", {}).get("phase1_time_seconds", 0)
        phase2_time = result.get("meta", {}).get("phase2_time_seconds", 0)
        
        queue.add_log(job_id, f"[Phase1Result] Completed in {phase1_time:.2f}s, feasible={result['status'] != 'INFEASIBLE'}", "info")
        queue.add_log(job_id, f"[Phase2End] Completed in {phase2_time:.2f}s", "info")
        
        if result["status"] == "INFEASIBLE":
            queue.add_log(job_id, "[SolverResult] INFEASIBLE after all relaxation attempts", "warning")
            diagnostics = analyze_infeasibility(solver_input, result["status"])
            result["diagnostics"] = result.get("diagnostics", []) + diagnostics
        elif result["status"] == "OPTIMAL":
            queue.add_log(job_id, f"[SolverResult] OPTIMAL in {solve_time:.2f}s", "info")
        elif result["status"] == "FEASIBLE":
            queue.add_log(job_id, f"[SolverResult] FEASIBLE in {solve_time:.2f}s", "info")
            if relaxed:
                queue.add_log(job_id, f"  Relaxed constraints: {', '.join(relaxed)}", "info")
        
        # Save result to file (both generated and results directories)
        _save_result(job_id, input_hash, result, GENERATED_DIR, RESULTS_DIR)
        
        # Store result in queue
        queue.update_status(job_id, JobStatus.RUNNING, progress=95)
        queue.store_result(job_id, result)
        
        # Cache successful results by hash
        if result["status"] in ["OPTIMAL", "FEASIBLE"]:
            queue.store_result_by_hash(input_hash, job_id, result)
            queue.add_log(job_id, f"[ResultCached] hash={input_hash[:16]}...", "info")
        
        logger.info(f"[JobCompleted] job_id={job_id}, status={result['status']}")
        queue.add_log(job_id, f"[JobCompleted] status={result['status']}", "info")
        
    except Exception as e:
        error_msg = f"Solver error: {str(e)}"
        logger.exception(f"[JobFailed] job_id={job_id}")
        queue.store_error(job_id, error_msg)
        queue.add_log(job_id, f"[JobFailed] {error_msg}", "error")


def _save_result(job_id: str, input_hash: str, result: dict, generated_dir, results_dir) -> None:
    """
    Save result to JSON files for persistence.
    
    Saves to both:
    - data/generated/result_{job_id}.json (legacy location)
    - data/results/job_{job_id}.json (new persistent location)
    
    Args:
        job_id: The job identifier
        input_hash: The input hash for caching
        result: The solver result
        generated_dir: Generated directory path
        results_dir: Results directory path
    """
    from pathlib import Path
    
    # Build the full result object for persistence
    result_with_meta = {
        "job_id": job_id,
        "input_hash": input_hash,
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
        "_meta": {
            "job_id": job_id,
            "saved_at": datetime.utcnow().isoformat(),
        },
        # Also include full result for backward compatibility
        "full_result": result,
    }
    
    try:
        # Save to generated directory (legacy)
        generated_path = Path(generated_dir)
        generated_path.mkdir(parents=True, exist_ok=True)
        legacy_path = generated_path / f"result_{job_id}.json"
        
        with open(legacy_path, "w") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Saved result to {legacy_path}")
        
        # Save to results directory (new persistent location)
        results_path = Path(results_dir)
        results_path.mkdir(parents=True, exist_ok=True)
        persist_path = results_path / f"job_{job_id}.json"
        
        with open(persist_path, "w") as f:
            json.dump(result_with_meta, f, indent=2)
        
        logger.info(f"Persisted result to {persist_path}")
        
    except Exception as e:
        logger.error(f"Failed to save result file: {e}")


def start_solver_job(job_id: str, solver_input: dict) -> tuple[Thread, CancellationToken]:
    """
    Start a solver job in a background thread.
    
    Args:
        job_id: The job identifier
        solver_input: The complete solver input data
    
    Returns:
        Tuple of (Thread, CancellationToken)
    """
    cancellation_token = CancellationToken(job_id)
    
    thread = Thread(
        target=execute_solver_job,
        args=(job_id, solver_input, cancellation_token),
        name=f"solver-{job_id[:8]}",
        daemon=True  # Thread will be killed when main process exits
    )
    thread.start()
    logger.info(f"Started worker thread for job: {job_id}")
    return thread, cancellation_token


class SolverWorkerPool:
    """
    Worker pool for managing concurrent solver jobs.
    
    Limits the number of concurrent solver executions and
    tracks active jobs for cancellation support.
    """
    
    def __init__(self, max_workers: int = 3):
        """
        Initialize the worker pool.
        
        Args:
            max_workers: Maximum concurrent solver jobs
        """
        self._max_workers = max_workers
        self._active_jobs: dict[str, tuple[Thread, CancellationToken]] = {}
        self._lock = threading.Lock()
    
    def submit(self, job_id: str, solver_input: dict) -> bool:
        """
        Submit a job to the worker pool.
        
        Args:
            job_id: The job identifier
            solver_input: The solver input data
        
        Returns:
            True if job was submitted, False if pool is full
        """
        with self._lock:
            # Clean up finished threads
            self._cleanup_locked()
            
            if len(self._active_jobs) >= self._max_workers:
                logger.warning(f"Worker pool full ({self._max_workers}), cannot submit job: {job_id}")
                return False
            
            thread, token = start_solver_job(job_id, solver_input)
            self._active_jobs[job_id] = (thread, token)
            return True
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Request cancellation of a running job.
        
        Args:
            job_id: The job identifier
        
        Returns:
            True if cancellation was requested
        """
        with self._lock:
            job_info = self._active_jobs.get(job_id)
            if job_info:
                _, token = job_info
                token.cancel()
                logger.info(f"Cancellation requested for job: {job_id}")
                return True
            
            # Also try to cancel via queue (in case job is in different process)
            queue = get_queue()
            return queue.request_cancellation(job_id)
    
    def _cleanup_locked(self) -> None:
        """Remove finished threads from tracking. Must hold _lock."""
        finished = [
            job_id for job_id, (thread, _) in self._active_jobs.items()
            if not thread.is_alive()
        ]
        for job_id in finished:
            del self._active_jobs[job_id]
    
    def get_active_count(self) -> int:
        """Get number of active worker threads."""
        with self._lock:
            self._cleanup_locked()
            return len(self._active_jobs)
    
    def is_job_running(self, job_id: str) -> bool:
        """Check if a specific job is currently running."""
        with self._lock:
            job_info = self._active_jobs.get(job_id)
            if job_info:
                thread, _ = job_info
                return thread.is_alive()
            return False
    
    def get_max_workers(self) -> int:
        """Get the maximum number of concurrent workers."""
        return self._max_workers


# Global worker pool instance
def _create_worker_pool() -> SolverWorkerPool:
    """Create worker pool with configured max workers."""
    from ..config import MAX_CONCURRENT_JOBS
    return SolverWorkerPool(max_workers=MAX_CONCURRENT_JOBS)

worker_pool = _create_worker_pool()
