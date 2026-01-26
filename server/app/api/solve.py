"""
Solve endpoint - Submit timetable generation job.

POST /solve - Submit a new timetable generation request
Supports both:
- Direct solver input (school, teachers, classes, subjects)
- Upload ID reference (from /upload endpoint or sample-data)
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..jobs.redis_queue import get_queue
from ..jobs.worker import worker_pool
from ..utils.validators import validate_solver_input
from ..solver.preprocess import validate_feasibility

logger = logging.getLogger(__name__)

router = APIRouter()


class SchoolConfig(BaseModel):
    """School configuration."""
    school_id: int
    name: str
    start_time: str
    end_time: str
    weekdays: list[str]
    periods_per_weekday: int
    saturday_periods: Optional[int] = 4
    period_duration_minutes: Optional[int] = 40
    prayer_enabled: Optional[bool] = True
    prayer_duration_minutes: Optional[int] = 15
    lunch_period_index: Optional[int] = 4
    lunch_duration_minutes: Optional[int] = 30
    recess_period_indices: Optional[list[int]] = []
    recess_duration_minutes: Optional[int] = 15


class TeacherConfig(BaseModel):
    """Teacher configuration."""
    teacher_id: str
    name: str
    subjects_can_teach: list[str]
    min_periods_day: int
    max_periods_day: int
    min_periods_week: Optional[int] = 0
    max_periods_week: Optional[int] = 40
    max_consecutive_periods: Optional[int] = 3
    is_class_teacher_of: Optional[str] = None
    sections_assigned: Optional[list[str]] = []
    availability: Optional[dict] = None


class ClassConfig(BaseModel):
    """Class/Section configuration."""
    section_id: str
    grade: int
    subject_teacher_map: dict[str, str]
    section_name: Optional[str] = None
    class_teacher_id: Optional[str] = None
    language_block_enabled: Optional[bool] = True
    language_subjects: Optional[list[str]] = []
    language_teachers: Optional[list[str]] = []


class SubjectConfig(BaseModel):
    """Subject configuration."""
    subject_id: str
    name: str
    category: str
    min_per_week: int
    max_per_week: int
    requires_block: Optional[bool] = False
    block_length: Optional[int] = 2
    requires_resource: Optional[bool] = False
    resource_type: Optional[str] = None


class ResourceConfig(BaseModel):
    """Resource configuration."""
    resource_id: str
    resource_type: str
    max_simultaneous_capacity: int
    name: Optional[str] = None


class ConstraintsConfig(BaseModel):
    """Constraints configuration."""
    prayer_enabled: Optional[bool] = True
    language_sync_enabled: Optional[bool] = True
    class_teacher_period_1: Optional[bool] = True
    no_subject_twice_daily: Optional[bool] = False
    core_morning_only: Optional[bool] = True
    substitution_reserve_count: Optional[int] = 3
    max_consecutive_default: Optional[int] = 3
    soft_weights: Optional[dict] = None


class SolveOptions(BaseModel):
    """Optional solve parameters."""
    # Time limit in seconds - supports slider values
    # 30 = fast, 60 = normal, 120 = deep, 300 = exhaustive, 900 = maximum
    time_limit_seconds: Optional[int] = Field(
        default=120, 
        ge=10, 
        le=1800,
        description="Solver time limit: 30=fast, 60=normal, 120=deep, 300=exhaustive"
    )
    
    # Demo mode: immediate allocation with higher time limit, no queueing
    demo_mode: Optional[bool] = Field(default=None, description="Enable demo mode for single-request scenario")
    
    # Deadline-based scheduling: specify by when you need results
    # The system will optimize time allocation based on queue and availability
    deadline: Optional[str] = Field(
        default=None, 
        description="ISO 8601 datetime by when results are needed (e.g., '2026-01-25T15:00:00')"
    )
    
    # Force fresh solve: bypass any caching, always run solver fresh
    # Use this when constraints have changed but getting cached results
    force_fresh: Optional[bool] = Field(
        default=True,  # Default to always fresh to avoid stale results
        description="Force fresh solve, ignore cached results"
    )
    
    # Solver strategy: balance between feasibility and optimization
    # "feasibility" - fast, find any solution
    # "balanced" - default two-phase approach  
    # "optimize" - spend more time on optimization
    strategy: Optional[str] = Field(
        default="balanced",
        description="Solver strategy: feasibility, balanced, or optimize"
    )


class SolveRequest(BaseModel):
    """
    Complete solve request - supports two modes:
    
    1. Direct mode: Provide full solver input directly
       {school, teachers, classes, subjects, constraints, ...}
    
    2. Reference mode: Provide upload_id to use previously uploaded/sample data
       {upload_id: "sample-data-vidya-mandir", constraints: {...}, options: {...}}
    """
    # Reference mode fields
    upload_id: Optional[str] = None
    
    # Direct mode fields
    school: Optional[SchoolConfig] = None
    classes: Optional[list[ClassConfig]] = None
    teachers: Optional[list[TeacherConfig]] = None
    subjects: Optional[list[SubjectConfig]] = None
    resources: Optional[list[ResourceConfig]] = []
    
    # Shared fields
    constraints: Optional[ConstraintsConfig] = None
    options: Optional[SolveOptions] = None
    time_limit_seconds: Optional[int] = Field(default=60, ge=5, le=600)
    
    @model_validator(mode='after')
    def validate_input_mode(self):
        """Validate that either upload_id or direct input is provided."""
        has_upload_id = self.upload_id is not None
        has_direct_input = self.school is not None and self.classes is not None
        
        if not has_upload_id and not has_direct_input:
            raise ValueError(
                "Either 'upload_id' or direct input (school, classes, teachers, subjects) must be provided"
            )
        
        return self


class SolveResponse(BaseModel):
    """Response for solve request."""
    job_id: str
    status: str
    message: Optional[str] = None
    warnings: Optional[list[str]] = None
    time_allocated_seconds: Optional[int] = None  # Actual time allocated for solving
    estimated_completion: Optional[str] = None     # Estimated completion time


def _build_solver_input_from_sample_data() -> dict:
    """
    Build a complete solver input from the sample data.
    This is used when upload_id is 'sample-data-vidya-mandir'.
    """
    # Import sample data from download module
    from .download import (
        SAMPLE_SCHOOL, SAMPLE_TEACHERS, SAMPLE_SUBJECTS, SAMPLE_CLASSES,
        SAMPLE_RESOURCES, SAMPLE_MAPPINGS, SAMPLE_LANGUAGE_GROUPS, SAMPLE_CONSTRAINTS_CONFIG
    )
    
    # Transform teachers
    teachers = []
    for t in SAMPLE_TEACHERS:
        teachers.append({
            "teacher_id": t["teacher_id"],
            "name": t["name"],
            "subjects_can_teach": t["subjects_can_teach"],
            "min_periods_day": t["min_periods_day"],
            "max_periods_day": t["max_periods_day"],
            "min_periods_week": t["min_periods_week"],
            "max_periods_week": t["max_periods_week"],
            "max_consecutive_periods": t["max_consecutive_periods"],
            "sections_assigned": [],
            "is_class_teacher_of": None,
        })
    
    # Update class teacher info from SAMPLE_CLASSES
    for c in SAMPLE_CLASSES:
        for t in teachers:
            if t["teacher_id"] == c["class_teacher_id"]:
                t["is_class_teacher_of"] = c["section_id"]
                break
    
    # Update sections assigned based on mappings
    for m in SAMPLE_MAPPINGS:
        for t in teachers:
            if t["teacher_id"] == m["teacher_id"]:
                if m["section_id"] not in t["sections_assigned"]:
                    t["sections_assigned"].append(m["section_id"])
                break
    
    # Transform subjects
    subjects = []
    for s in SAMPLE_SUBJECTS:
        subjects.append({
            "subject_id": s["subject_code"],
            "name": s["name"],
            "category": s["category"],
            "min_per_week": s["min_weekly"],
            "max_per_week": s["max_weekly"],
            "requires_block": s["block_required"],
            "block_length": s["block_length"] if s["block_required"] else 2,
            "requires_resource": s["resource_type"] is not None,
            "resource_type": s["resource_type"],
        })
    
    # Transform classes
    classes = []
    for c in SAMPLE_CLASSES:
        subject_teacher_map = {}
        language_subjects = []
        language_teachers = []
        
        for m in SAMPLE_MAPPINGS:
            if m["section_id"] == c["section_id"]:
                subject_teacher_map[m["subject_code"]] = m["teacher_id"]
        
        # Get language block info
        for lg in SAMPLE_LANGUAGE_GROUPS:
            if lg["section_id"] == c["section_id"]:
                language_subjects = ["HINDI", "KANNADA", "SANSKRIT"]
                language_teachers = [lg["hindi_teacher"], lg["kannada_teacher"], lg["sanskrit_teacher"]]
                break
        
        classes.append({
            "section_id": c["section_id"],
            "grade": c["grade"],
            "section_name": c["section"],
            "class_teacher_id": c["class_teacher_id"],
            "subject_teacher_map": subject_teacher_map,
            "language_block_enabled": c["language_block_enabled"],
            "language_subjects": language_subjects,
            "language_teachers": language_teachers,
        })
    
    # Transform resources
    resources = []
    for r in SAMPLE_RESOURCES:
        resources.append({
            "resource_id": r["resource_id"],
            "resource_type": r["resource_type"],
            "name": r["resource_type"],
            "max_simultaneous_capacity": r["max_simultaneous_capacity"],
        })
    
    # Build school config
    school = {
        "school_id": SAMPLE_SCHOOL["school_id"],
        "name": SAMPLE_SCHOOL["name"],
        "start_time": SAMPLE_SCHOOL["start_time"],
        "end_time": SAMPLE_SCHOOL["end_time"],
        "weekdays": SAMPLE_SCHOOL["weekdays"],
        "periods_per_weekday": SAMPLE_SCHOOL["periods_per_weekday"],
        "saturday_periods": SAMPLE_SCHOOL["saturday_periods"],
        "period_duration_minutes": SAMPLE_SCHOOL["period_duration_minutes"],
        "prayer_enabled": SAMPLE_SCHOOL["prayer_enabled"],
        "prayer_duration_minutes": SAMPLE_SCHOOL["prayer_duration_minutes"],
        "lunch_period_index": SAMPLE_SCHOOL["lunch_period_index"],
        "lunch_duration_minutes": SAMPLE_SCHOOL["lunch_duration_minutes"],
        "recess_period_indices": SAMPLE_SCHOOL["recess_period_indices"],
        "recess_duration_minutes": SAMPLE_SCHOOL["recess_duration_minutes"],
    }
    
    # Build constraints config
    constraints = {
        "prayer_enabled": SAMPLE_CONSTRAINTS_CONFIG.get("prayer_enabled", True),
        "language_sync_enabled": SAMPLE_CONSTRAINTS_CONFIG.get("language_sync_enabled", True),
        "class_teacher_period_1": SAMPLE_CONSTRAINTS_CONFIG.get("class_teacher_period_1", True),
        "no_subject_twice_daily": SAMPLE_CONSTRAINTS_CONFIG.get("no_subject_twice_daily", False),
        "core_morning_only": SAMPLE_CONSTRAINTS_CONFIG.get("core_morning_only", True),
        "substitution_reserve_count": SAMPLE_CONSTRAINTS_CONFIG.get("substitution_reserve_count", 3),
        "max_consecutive_default": SAMPLE_CONSTRAINTS_CONFIG.get("max_consecutive_default", 3),
    }
    
    return {
        "school": school,
        "teachers": teachers,
        "subjects": subjects,
        "classes": classes,
        "resources": resources,
        "constraints": constraints,
    }


@router.post("/solve", response_model=SolveResponse)
async def solve_timetable(request: SolveRequest) -> SolveResponse:
    """
    Submit a timetable generation job.
    
    Supports two modes:
    1. Reference mode: Provide upload_id (e.g., 'sample-data-vidya-mandir')
    2. Direct mode: Provide full solver input (school, teachers, classes, subjects)
    
    The job will be processed asynchronously. Use the returned job_id
    to check status and retrieve results.
    
    Args:
        request: Complete solver input data or upload_id reference
    
    Returns:
        Job ID and initial status
    
    Raises:
        HTTPException: If input validation fails
    """
    # Determine input mode and build solver_input
    if request.upload_id:
        # Reference mode - load data from upload_id
        logger.info(f"Solving with upload_id: {request.upload_id}")
        
        if request.upload_id.startswith("sample-data"):
            # Use sample data
            solver_input = _build_solver_input_from_sample_data()
        else:
            # TODO: Load from parsed upload files
            # For now, we only support sample data
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Upload ID not found: {request.upload_id}",
                    "suggestion": "Use 'sample-data-vidya-mandir' or upload data first",
                }
            )
        
        # Override constraints if provided
        if request.constraints:
            solver_input["constraints"] = {
                **solver_input.get("constraints", {}),
                **request.constraints.model_dump(exclude_none=True),
            }
    else:
        # Direct mode - use provided data
        solver_input = request.model_dump(exclude_none=True)
        # Remove non-solver fields
        solver_input.pop("upload_id", None)
        solver_input.pop("options", None)
    
    # Import config for time limits
    from ..config import DEMO_MODE, DEMO_SOLVE_TIME_SEC, DEFAULT_SOLVE_TIME_SEC, MAX_SOLVE_TIME_SEC
    
    # Calculate effective time limit based on options and mode
    time_limit = _calculate_time_limit(
        request_time_limit=request.time_limit_seconds,
        options=request.options,
        demo_mode_config=DEMO_MODE,
        demo_time=DEMO_SOLVE_TIME_SEC,
        default_time=DEFAULT_SOLVE_TIME_SEC,
        max_time=MAX_SOLVE_TIME_SEC,
    )
    solver_input["time_limit_seconds"] = time_limit
    
    # Check for force_fresh option - default to True to always run fresh
    force_fresh = True
    if request.options and request.options.force_fresh is not None:
        force_fresh = request.options.force_fresh
    solver_input["force_fresh"] = force_fresh
    
    logger.info(f"Time limit: {time_limit}s, Force fresh: {force_fresh}")
    
    # Validate solver input (skip schema validation if using sample data)
    # The sample data is pre-validated, so we can skip strict schema checks
    if not request.upload_id or not request.upload_id.startswith("sample-data"):
        is_valid, schema_errors = validate_solver_input(solver_input)
        if not is_valid:
            logger.warning(f"Schema validation failed: {schema_errors}")
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Input validation failed",
                    "errors": schema_errors,
                }
            )
    
    # Pre-flight feasibility check (lightweight)
    is_feasible, warnings, diagnostics = validate_feasibility(solver_input)
    
    if not is_feasible:
        logger.warning(f"Feasibility check failed: {warnings}")
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Input is not feasible - constraints cannot be satisfied",
                "errors": warnings,
                "diagnostics": diagnostics,
                "suggestion": "Review the diagnostics and adjust input data",
            }
        )
    
    # Get job queue
    queue = get_queue()
    
    # Log queue state for debugging
    logger.info(f"Queue state: Redis available={queue.is_redis_available}")
    
    # Check if worker pool has capacity
    active_count = worker_pool.get_active_count()
    max_workers = worker_pool.get_max_workers()
    
    if active_count >= max_workers:
        # Still create the job but queue it
        logger.info(f"Worker pool full ({active_count}/{max_workers}), job will be queued")
    
    # Create job in the queue
    job_id = str(uuid.uuid4())
    job = queue.create_job(solver_input, job_id=job_id)
    
    # Verify job was created successfully
    if not job:
        logger.error(f"Failed to create job: {job_id}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to create job in queue"}
        )
    
    # Double-check job is accessible before returning
    verify_job = queue.get_job(job_id)
    if not verify_job:
        logger.error(f"Job created but not retrievable: {job_id}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Job created but not accessible - internal queue error"}
        )
    
    logger.info(f"Job {job_id} created and verified in queue with time_limit={time_limit}s")
    
    # Try to start worker immediately
    submitted = worker_pool.submit(job_id, solver_input)
    
    if not submitted:
        logger.info(f"Job {job_id} queued, waiting for worker availability")
    
    logger.info(f"Created solver job: {job_id}")
    
    # Calculate estimated completion time
    from datetime import datetime, timedelta
    estimated_completion = (datetime.utcnow() + timedelta(seconds=time_limit + 5)).isoformat()
    
    return SolveResponse(
        job_id=job_id,
        status="queued",
        message="Timetable generation started" if submitted else "Job queued, waiting for worker",
        warnings=warnings if warnings else None,
        time_allocated_seconds=time_limit,
        estimated_completion=estimated_completion,
    )


def _calculate_time_limit(
    request_time_limit: int | None,
    options: SolveOptions | None,
    demo_mode_config: bool,
    demo_time: int,
    default_time: int,
    max_time: int,
) -> int:
    """
    Calculate the effective time limit for the solver.
    
    Priority:
    1. If deadline is specified, calculate time available until deadline
    2. If demo_mode is explicitly set in options, use demo_time
    3. If global DEMO_MODE is enabled (single-tenant), use demo_time
    4. If time_limit_seconds is specified in options or request, use it
    5. Otherwise, use default_time
    
    Args:
        request_time_limit: Time limit from request body
        options: SolveOptions from request
        demo_mode_config: Global DEMO_MODE from config
        demo_time: Time limit for demo mode
        default_time: Default time limit
        max_time: Maximum allowed time limit
    
    Returns:
        Calculated time limit in seconds
    """
    from datetime import datetime
    
    # Priority 1: Deadline-based calculation
    if options and options.deadline:
        try:
            deadline = datetime.fromisoformat(options.deadline.replace('Z', '+00:00'))
            now = datetime.utcnow()
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=None)
            else:
                now = now.replace(tzinfo=deadline.tzinfo)
            
            available_seconds = (deadline - now).total_seconds()
            
            # Reserve some buffer time for processing
            buffer_seconds = 30
            solver_time = int(available_seconds - buffer_seconds)
            
            if solver_time < 30:
                # Not enough time, use minimum
                return 30
            elif solver_time > max_time:
                return max_time
            else:
                return solver_time
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid deadline format: {options.deadline}, error: {e}")
            # Fall through to other options
    
    # Priority 2: Explicit demo_mode in request options
    if options and options.demo_mode is True:
        return demo_time
    
    # Priority 3: Global DEMO_MODE config (single-tenant scenario)
    if demo_mode_config:
        # In demo mode, use the demo time unless explicitly overridden
        if options and options.time_limit_seconds:
            return min(options.time_limit_seconds, max_time)
        if request_time_limit:
            return min(request_time_limit, max_time)
        return demo_time
    
    # Priority 4: Explicit time_limit from options or request
    if options and options.time_limit_seconds:
        return min(options.time_limit_seconds, max_time)
    if request_time_limit:
        return min(request_time_limit, max_time)
    
    # Priority 5: Default
    return default_time
