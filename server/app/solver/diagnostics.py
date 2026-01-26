"""
Diagnostics and infeasibility analysis for the timetable solver.

Provides human-readable explanations when the solver fails to find
a solution, including:
- Detection of overloaded teachers
- Resource bottleneck identification
- Impossible block period detection
- Relaxation suggestions
"""

import logging
from typing import Optional

from .preprocess import (
    generate_period_grid,
    get_academic_periods,
    get_periods_by_day,
)

logger = logging.getLogger(__name__)


def analyze_infeasibility(solver_input: dict, solver_status: str) -> list[dict]:
    """
    Generate human-readable explanations when solver fails.
    
    Args:
        solver_input: The complete solver input
        solver_status: The solver result status
    
    Returns:
        List of diagnostic messages with type, category, message, and suggestions
    """
    diagnostics = []
    
    # Run all diagnostic checks
    teacher_issues = detect_overloaded_teachers(solver_input)
    diagnostics.extend(teacher_issues)
    
    resource_issues = detect_resource_bottlenecks(solver_input)
    diagnostics.extend(resource_issues)
    
    block_issues = detect_impossible_blocks(solver_input)
    diagnostics.extend(block_issues)
    
    schedule_issues = detect_scheduling_conflicts(solver_input)
    diagnostics.extend(schedule_issues)
    
    constraint_issues = detect_constraint_conflicts(solver_input)
    diagnostics.extend(constraint_issues)
    
    # Add relaxation suggestions
    suggestions = suggest_relaxations(diagnostics)
    for suggestion in suggestions:
        diagnostics.append({
            "type": "suggestion",
            "category": "relaxation",
            "message": suggestion,
            "affected_entities": [],
        })
    
    # If no specific issues found, add a generic message
    if not diagnostics:
        diagnostics.append({
            "type": "warning",
            "category": "unknown",
            "message": f"Solver returned {solver_status} but no specific issue was identified. "
                      "Try relaxing constraints or increasing time limit.",
            "affected_entities": [],
        })
    
    return diagnostics


def detect_overloaded_teachers(solver_input: dict) -> list[dict]:
    """
    Check if required periods exceed teacher capacity.
    
    Args:
        solver_input: The solver input data
    
    Returns:
        List of diagnostic messages about teacher overloading
    """
    diagnostics = []
    
    teachers = solver_input.get("teachers", [])
    classes = solver_input.get("classes", [])
    subjects = solver_input.get("subjects", [])
    school = solver_input.get("school", {})
    
    # Build lookup maps
    subject_map = {s["subject_id"]: s for s in subjects}
    teacher_map = {t["teacher_id"]: t for t in teachers}
    
    # Calculate teacher load requirements
    teacher_loads = {t["teacher_id"]: {"min": 0, "max": 0, "sections": []} for t in teachers}
    
    for cls in classes:
        section_id = cls["section_id"]
        for subject_id, teacher_id in cls.get("subject_teacher_map", {}).items():
            if teacher_id in teacher_loads:
                subject = subject_map.get(subject_id)
                if subject:
                    teacher_loads[teacher_id]["min"] += subject.get("min_per_week", 0)
                    teacher_loads[teacher_id]["max"] += subject.get("max_per_week", 0)
                    teacher_loads[teacher_id]["sections"].append(f"{section_id}/{subject_id}")
    
    # Generate period grid to calculate available slots
    period_grid = generate_period_grid(school)
    academic_periods = get_academic_periods(period_grid)
    periods_by_day = get_periods_by_day(academic_periods)
    num_days = len(periods_by_day)
    
    for teacher_id, load in teacher_loads.items():
        teacher = teacher_map.get(teacher_id)
        if not teacher:
            continue
        
        max_per_day = teacher.get("max_periods_day", 8)
        max_per_week = teacher.get("max_periods_week", 40)
        
        # Check weekly overload
        if load["min"] > max_per_week:
            diagnostics.append({
                "type": "error",
                "category": "teacher_overload",
                "message": f"Teacher '{teacher.get('name', teacher_id)}' requires minimum "
                          f"{load['min']} periods/week but has max_periods_week of {max_per_week}",
                "affected_entities": [teacher_id] + load["sections"],
                "suggestion": "Reduce subject min_per_week or increase teacher's max_periods_week",
            })
        
        # Check daily overload
        min_daily = load["min"] / num_days if num_days > 0 else 0
        if min_daily > max_per_day:
            diagnostics.append({
                "type": "error",
                "category": "teacher_overload",
                "message": f"Teacher '{teacher.get('name', teacher_id)}' needs ~{min_daily:.1f} "
                          f"periods/day on average but max_periods_day is {max_per_day}",
                "affected_entities": [teacher_id],
                "suggestion": "Increase max_periods_day or reassign some subjects",
            })
        
        # Check for teachers with very high load
        if load["min"] > 0.8 * max_per_week:
            diagnostics.append({
                "type": "warning",
                "category": "teacher_high_load",
                "message": f"Teacher '{teacher.get('name', teacher_id)}' has high load: "
                          f"{load['min']}-{load['max']} periods/week (limit: {max_per_week})",
                "affected_entities": [teacher_id],
            })
    
    return diagnostics


def detect_resource_bottlenecks(solver_input: dict) -> list[dict]:
    """
    Check if resource demand exceeds supply.
    
    Args:
        solver_input: The solver input data
    
    Returns:
        List of diagnostic messages about resource bottlenecks
    """
    diagnostics = []
    
    classes = solver_input.get("classes", [])
    subjects = solver_input.get("subjects", [])
    resources = solver_input.get("resources", [])
    school = solver_input.get("school", {})
    
    if not resources:
        return diagnostics
    
    subject_map = {s["subject_id"]: s for s in subjects}
    resource_map = {r["resource_type"]: r for r in resources}
    
    # Calculate resource demand
    resource_demand = {}
    
    for cls in classes:
        section_id = cls["section_id"]
        for subject_id in cls.get("subject_teacher_map", {}).keys():
            subject = subject_map.get(subject_id)
            if subject and subject.get("requires_resource"):
                resource_type = subject.get("resource_type")
                if resource_type:
                    if resource_type not in resource_demand:
                        resource_demand[resource_type] = {"total": 0, "sections": []}
                    resource_demand[resource_type]["total"] += subject.get("min_per_week", 0)
                    resource_demand[resource_type]["sections"].append(
                        f"{section_id}/{subject_id}"
                    )
    
    # Generate period grid
    period_grid = generate_period_grid(school)
    academic_periods = get_academic_periods(period_grid)
    total_slots = len(academic_periods)
    
    for resource_type, demand in resource_demand.items():
        resource = resource_map.get(resource_type)
        if resource:
            capacity = resource.get("max_simultaneous_capacity", 1)
            weekly_capacity = capacity * total_slots
            
            if demand["total"] > weekly_capacity:
                diagnostics.append({
                    "type": "error",
                    "category": "resource_bottleneck",
                    "message": f"Resource '{resource_type}' demand ({demand['total']} periods) "
                              f"exceeds weekly capacity ({weekly_capacity} = {capacity} × {total_slots} slots)",
                    "affected_entities": demand["sections"],
                    "suggestion": f"Increase {resource_type} capacity or reduce subject requirements",
                })
            elif demand["total"] > 0.9 * weekly_capacity:
                diagnostics.append({
                    "type": "warning",
                    "category": "resource_tight",
                    "message": f"Resource '{resource_type}' is near capacity: "
                              f"{demand['total']}/{weekly_capacity} ({100*demand['total']/weekly_capacity:.0f}%)",
                    "affected_entities": demand["sections"],
                })
    
    return diagnostics


def detect_impossible_blocks(solver_input: dict, period_grid: Optional[list] = None) -> list[dict]:
    """
    Check if block periods can fit in the grid.
    
    Args:
        solver_input: The solver input data
        period_grid: Optional pre-generated period grid
    
    Returns:
        List of diagnostic messages about impossible block periods
    """
    diagnostics = []
    
    subjects = solver_input.get("subjects", [])
    school = solver_input.get("school", {})
    
    if period_grid is None:
        period_grid = generate_period_grid(school)
    
    academic_periods = get_academic_periods(period_grid)
    periods_by_day = get_periods_by_day(academic_periods)
    
    for subject in subjects:
        if not subject.get("requires_block", False):
            continue
        
        subject_id = subject["subject_id"]
        block_length = subject.get("block_length", 2)
        
        # Check each day for valid block positions
        valid_positions = 0
        
        for day, day_periods in periods_by_day.items():
            sorted_periods = sorted(day_periods, key=lambda p: p["period"])
            
            # Count consecutive periods not crossing breaks
            consecutive = 0
            for i, period in enumerate(sorted_periods):
                if i > 0 and (period.get("is_recess") or period.get("is_after_lunch")):
                    consecutive = 1
                else:
                    consecutive += 1
                
                if consecutive >= block_length:
                    valid_positions += 1
        
        if valid_positions == 0:
            diagnostics.append({
                "type": "error",
                "category": "impossible_block",
                "message": f"Subject '{subject.get('name', subject_id)}' requires {block_length} "
                          f"consecutive periods but no day has sufficient unbroken slots",
                "affected_entities": [subject_id],
                "suggestion": "Reduce block_length or adjust recess/lunch timing",
            })
        elif valid_positions < subject.get("min_per_week", 0) / block_length:
            diagnostics.append({
                "type": "warning",
                "category": "tight_block",
                "message": f"Subject '{subject.get('name', subject_id)}' has limited block positions: "
                          f"{valid_positions} positions for {subject.get('min_per_week', 0)//block_length} required blocks",
                "affected_entities": [subject_id],
            })
    
    return diagnostics


def detect_scheduling_conflicts(solver_input: dict) -> list[dict]:
    """
    Detect potential scheduling conflicts.
    
    Args:
        solver_input: The solver input data
    
    Returns:
        List of diagnostic messages about scheduling conflicts
    """
    diagnostics = []
    
    classes = solver_input.get("classes", [])
    subjects = solver_input.get("subjects", [])
    school = solver_input.get("school", {})
    
    subject_map = {s["subject_id"]: s for s in subjects}
    
    # Generate period grid
    period_grid = generate_period_grid(school)
    academic_periods = get_academic_periods(period_grid)
    total_slots = len(academic_periods)
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_teacher_map = cls.get("subject_teacher_map", {})
        
        # Calculate total required slots
        min_required = 0
        max_required = 0
        
        for subject_id in subject_teacher_map.keys():
            subject = subject_map.get(subject_id)
            if subject:
                min_required += subject.get("min_per_week", 0)
                max_required += subject.get("max_per_week", 0)
        
        if min_required > total_slots:
            diagnostics.append({
                "type": "error",
                "category": "slot_overflow",
                "message": f"Section '{section_id}' requires minimum {min_required} periods "
                          f"but only {total_slots} slots are available",
                "affected_entities": [section_id],
                "suggestion": "Reduce subject min_per_week or add more periods to the school day",
            })
        elif max_required < total_slots * 0.5:
            diagnostics.append({
                "type": "warning",
                "category": "slot_underflow",
                "message": f"Section '{section_id}' can use max {max_required} periods "
                          f"but {total_slots} slots are available - many free periods",
                "affected_entities": [section_id],
            })
    
    return diagnostics


def detect_constraint_conflicts(solver_input: dict) -> list[dict]:
    """
    Detect conflicting constraint settings.
    
    Args:
        solver_input: The solver input data
    
    Returns:
        List of diagnostic messages about constraint conflicts
    """
    diagnostics = []
    
    constraints = solver_input.get("constraints", {})
    teachers = solver_input.get("teachers", [])
    classes = solver_input.get("classes", [])
    
    # Check substitution reserve vs teacher count
    reserve_count = constraints.get("substitution_reserve_count", 3)
    if reserve_count >= len(teachers):
        diagnostics.append({
            "type": "error",
            "category": "constraint_conflict",
            "message": f"Substitution reserve ({reserve_count}) equals or exceeds "
                      f"total teachers ({len(teachers)})",
            "affected_entities": [],
            "suggestion": "Reduce substitution_reserve_count",
        })
    elif reserve_count > len(teachers) * 0.5:
        diagnostics.append({
            "type": "warning",
            "category": "constraint_tight",
            "message": f"Substitution reserve ({reserve_count}) is more than half "
                      f"of total teachers ({len(teachers)})",
            "affected_entities": [],
        })
    
    # Check class teacher constraint feasibility
    if constraints.get("class_teacher_period_1", True):
        for cls in classes:
            class_teacher_id = cls.get("class_teacher_id")
            if class_teacher_id:
                # Check if class teacher teaches any subject to this section
                subject_teacher_map = cls.get("subject_teacher_map", {})
                teaches_section = class_teacher_id in subject_teacher_map.values()
                
                if not teaches_section:
                    diagnostics.append({
                        "type": "error",
                        "category": "constraint_conflict",
                        "message": f"class_teacher_period_1 enabled but class teacher "
                                  f"'{class_teacher_id}' doesn't teach any subject to "
                                  f"section '{cls['section_id']}'",
                        "affected_entities": [cls["section_id"], class_teacher_id],
                        "suggestion": "Assign at least one subject to the class teacher "
                                    "or disable class_teacher_period_1",
                    })
    
    return diagnostics


def suggest_relaxations(diagnostics: list[dict]) -> list[str]:
    """
    Generate prioritized suggestions for constraint relaxation.
    
    Args:
        diagnostics: List of diagnostic messages
    
    Returns:
        Prioritized list of relaxation suggestions
    """
    suggestions = []
    seen_suggestions = set()
    
    # Analyze diagnostics and generate specific suggestions
    for diag in diagnostics:
        if diag.get("type") != "error":
            continue
        
        category = diag.get("category", "")
        
        if category == "teacher_overload":
            suggestion = "Consider reassigning some subjects to other teachers or hiring additional teachers"
            if suggestion not in seen_suggestions:
                suggestions.append(suggestion)
                seen_suggestions.add(suggestion)
        
        elif category == "resource_bottleneck":
            suggestion = "Increase resource capacity or reduce subject requirements that need resources"
            if suggestion not in seen_suggestions:
                suggestions.append(suggestion)
                seen_suggestions.add(suggestion)
        
        elif category == "impossible_block":
            suggestion = "Reduce block period length or adjust break timings"
            if suggestion not in seen_suggestions:
                suggestions.append(suggestion)
                seen_suggestions.add(suggestion)
        
        elif category == "slot_overflow":
            suggestion = "Reduce subject min_per_week requirements or add more periods to school day"
            if suggestion not in seen_suggestions:
                suggestions.append(suggestion)
                seen_suggestions.add(suggestion)
        
        elif category == "constraint_conflict":
            suggestion = "Review and relax conflicting constraint settings"
            if suggestion not in seen_suggestions:
                suggestions.append(suggestion)
                seen_suggestions.add(suggestion)
    
    # Add generic suggestions if no specific ones
    if not suggestions:
        suggestions = [
            "Try increasing the solver time limit",
            "Consider disabling some soft constraints",
            "Review teacher availability settings",
        ]
    
    return suggestions


def generate_diagnostic_report(solver_input: dict, result: dict) -> str:
    """
    Generate a human-readable diagnostic report.
    
    Args:
        solver_input: The solver input data
        result: The solver result
    
    Returns:
        Formatted diagnostic report string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("TIMETABLE SOLVER DIAGNOSTIC REPORT")
    lines.append("=" * 60)
    lines.append("")
    
    status = result.get("status", "UNKNOWN")
    lines.append(f"Solver Status: {status}")
    lines.append("")
    
    if result.get("diagnostics"):
        lines.append("ISSUES DETECTED:")
        lines.append("-" * 40)
        
        errors = [d for d in result["diagnostics"] if d.get("type") == "error"]
        warnings = [d for d in result["diagnostics"] if d.get("type") == "warning"]
        suggestions = [d for d in result["diagnostics"] if d.get("type") == "suggestion"]
        
        if errors:
            lines.append("\n❌ ERRORS (must fix):")
            for i, error in enumerate(errors, 1):
                lines.append(f"  {i}. [{error.get('category')}] {error.get('message')}")
                if error.get("suggestion"):
                    lines.append(f"     → {error.get('suggestion')}")
        
        if warnings:
            lines.append("\n⚠️ WARNINGS:")
            for i, warning in enumerate(warnings, 1):
                lines.append(f"  {i}. [{warning.get('category')}] {warning.get('message')}")
        
        if suggestions:
            lines.append("\n💡 SUGGESTIONS:")
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"  {i}. {suggestion.get('message')}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)
