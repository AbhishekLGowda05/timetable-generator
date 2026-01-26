"""
Validate endpoint - Validate manual timetable changes.

POST /validate - Validate a proposed swap or modification
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..jobs.redis_queue import get_queue

logger = logging.getLogger(__name__)

router = APIRouter()


class SwapRequest(BaseModel):
    """Request to validate a period swap."""
    job_id: str
    section_id: str
    day: str
    period_from: int
    period_to: int


class ValidationResult(BaseModel):
    """Result of swap validation."""
    valid: bool
    violations: Optional[list[dict]] = None
    message: Optional[str] = None


@router.post("/validate", response_model=ValidationResult)
async def validate_swap(request: SwapRequest) -> ValidationResult:
    """
    Validate a proposed period swap.
    
    Checks hard constraints without re-running the solver.
    
    Args:
        request: Swap details including job_id, section, day, and periods
    
    Returns:
        Validation result with any constraint violations
    """
    queue = get_queue()
    job = queue.get_job(request.job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Job not found: {request.job_id}"}
        )
    
    if not job.result:
        raise HTTPException(
            status_code=400,
            detail={"message": "Job has no result to validate against"}
        )
    
    timetable = job.result.get("timetable", {})
    
    if request.section_id not in timetable:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Section not found: {request.section_id}"}
        )
    
    section_timetable = timetable[request.section_id]
    
    if request.day not in section_timetable:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Day not found: {request.day}"}
        )
    
    day_schedule = section_timetable[request.day]
    
    # Find periods to swap
    period_from_entry = None
    period_to_entry = None
    
    for entry in day_schedule:
        if entry["period"] == request.period_from:
            period_from_entry = entry
        if entry["period"] == request.period_to:
            period_to_entry = entry
    
    if not period_from_entry:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Period {request.period_from} not found"}
        )
    
    if not period_to_entry:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Period {request.period_to} not found"}
        )
    
    # Check hard constraints for the swap
    violations = check_swap_constraints(
        job.solver_input,
        job.result,
        request.section_id,
        request.day,
        period_from_entry,
        period_to_entry,
    )
    
    if violations:
        return ValidationResult(
            valid=False,
            violations=violations,
            message="Swap would violate constraints",
        )
    
    return ValidationResult(
        valid=True,
        message="Swap is valid",
    )


def check_swap_constraints(
    solver_input: dict,
    result: dict,
    section_id: str,
    day: str,
    entry_from: dict,
    entry_to: dict,
) -> list[dict]:
    """
    Check if swapping two periods would violate hard constraints.
    
    Args:
        solver_input: Original solver input
        result: Solver result
        section_id: Section being modified
        day: Day of the swap
        entry_from: First period entry
        entry_to: Second period entry
    
    Returns:
        List of constraint violations
    """
    violations = []
    
    teacher_from = entry_from.get("teacher_id")
    teacher_to = entry_to.get("teacher_id")
    subject_from = entry_from.get("subject_id")
    subject_to = entry_to.get("subject_id")
    period_from = entry_from.get("period")
    period_to = entry_to.get("period")
    
    # Skip if both are free periods
    if subject_from == "FREE" and subject_to == "FREE":
        return violations
    
    # Build teacher schedules for this day
    teacher_schedules = result.get("teacher_schedules", {})
    
    # Check 1: Teacher conflict
    # After swap, teacher_from would be at period_to, teacher_to at period_from
    if teacher_from and teacher_from != "FREE":
        teacher_from_schedule = teacher_schedules.get(teacher_from, {}).get(day, [])
        
        # Check if teacher_from is already teaching at period_to in another section
        for assignment in teacher_from_schedule:
            if assignment.get("period") == period_to:
                if assignment.get("section_id") != section_id:
                    violations.append({
                        "type": "teacher_conflict",
                        "message": f"Teacher {teacher_from} is already teaching at period {period_to} in section {assignment.get('section_id')}",
                        "affected_entities": [teacher_from, section_id, assignment.get("section_id")],
                    })
    
    if teacher_to and teacher_to != "FREE":
        teacher_to_schedule = teacher_schedules.get(teacher_to, {}).get(day, [])
        
        for assignment in teacher_to_schedule:
            if assignment.get("period") == period_from:
                if assignment.get("section_id") != section_id:
                    violations.append({
                        "type": "teacher_conflict",
                        "message": f"Teacher {teacher_to} is already teaching at period {period_from} in section {assignment.get('section_id')}",
                        "affected_entities": [teacher_to, section_id, assignment.get("section_id")],
                    })
    
    # Check 2: Block period integrity
    if entry_from.get("is_block_continuation"):
        violations.append({
            "type": "block_integrity",
            "message": f"Cannot swap period {period_from} - it's a continuation of a block period",
            "affected_entities": [section_id, subject_from],
        })
    
    if entry_to.get("is_block_continuation"):
        violations.append({
            "type": "block_integrity",
            "message": f"Cannot swap period {period_to} - it's a continuation of a block period",
            "affected_entities": [section_id, subject_to],
        })
    
    if entry_from.get("is_block_start"):
        violations.append({
            "type": "block_integrity",
            "message": f"Cannot swap period {period_from} - it's the start of a block period",
            "affected_entities": [section_id, subject_from],
        })
    
    if entry_to.get("is_block_start"):
        violations.append({
            "type": "block_integrity",
            "message": f"Cannot swap period {period_to} - it's the start of a block period",
            "affected_entities": [section_id, subject_to],
        })
    
    # Check 3: Teacher availability
    teachers = solver_input.get("teachers", [])
    teacher_map = {t["teacher_id"]: t for t in teachers}
    
    if teacher_from:
        teacher_data = teacher_map.get(teacher_from)
        if teacher_data:
            availability = teacher_data.get("availability", {}).get(day, {})
            blocked_periods = availability.get("blocked_periods", [])
            if period_to in blocked_periods:
                violations.append({
                    "type": "teacher_unavailable",
                    "message": f"Teacher {teacher_from} is not available at period {period_to}",
                    "affected_entities": [teacher_from],
                })
    
    if teacher_to:
        teacher_data = teacher_map.get(teacher_to)
        if teacher_data:
            availability = teacher_data.get("availability", {}).get(day, {})
            blocked_periods = availability.get("blocked_periods", [])
            if period_from in blocked_periods:
                violations.append({
                    "type": "teacher_unavailable",
                    "message": f"Teacher {teacher_to} is not available at period {period_from}",
                    "affected_entities": [teacher_to],
                })
    
    return violations


class ModificationRequest(BaseModel):
    """Request to validate a manual modification."""
    job_id: str
    section_id: str
    day: str
    period: int
    new_subject_id: str
    new_teacher_id: str


@router.post("/validate/modification", response_model=ValidationResult)
async def validate_modification(request: ModificationRequest) -> ValidationResult:
    """
    Validate a manual modification to a period.
    
    Args:
        request: Modification details
    
    Returns:
        Validation result with any constraint violations
    """
    queue = get_queue()
    job = queue.get_job(request.job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Job not found: {request.job_id}"}
        )
    
    if not job.result:
        raise HTTPException(
            status_code=400,
            detail={"message": "Job has no result to validate against"}
        )
    
    violations = []
    
    # Check teacher conflict
    teacher_schedules = job.result.get("teacher_schedules", {})
    teacher_schedule = teacher_schedules.get(request.new_teacher_id, {}).get(request.day, [])
    
    for assignment in teacher_schedule:
        if assignment.get("period") == request.period:
            if assignment.get("section_id") != request.section_id:
                violations.append({
                    "type": "teacher_conflict",
                    "message": f"Teacher {request.new_teacher_id} is already teaching at period {request.period}",
                    "affected_entities": [request.new_teacher_id, request.section_id],
                })
    
    # Check subject-teacher mapping
    classes = job.solver_input.get("classes", [])
    section = next((c for c in classes if c["section_id"] == request.section_id), None)
    
    if section:
        subject_teacher_map = section.get("subject_teacher_map", {})
        expected_teacher = subject_teacher_map.get(request.new_subject_id)
        
        if expected_teacher and expected_teacher != request.new_teacher_id:
            violations.append({
                "type": "teacher_assignment",
                "message": f"Subject {request.new_subject_id} should be taught by {expected_teacher}, not {request.new_teacher_id}",
                "affected_entities": [request.new_subject_id, request.new_teacher_id, expected_teacher],
            })
    
    if violations:
        return ValidationResult(
            valid=False,
            violations=violations,
            message="Modification would violate constraints",
        )
    
    return ValidationResult(
        valid=True,
        message="Modification is valid",
    )
