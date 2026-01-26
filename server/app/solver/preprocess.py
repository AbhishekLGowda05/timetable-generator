"""
Preprocessing utilities for the timetable solver.

Transforms solver_input into CP-SAT-ready structures including:
- Period grid generation
- Teacher capability matrices
- Availability masks
- Feasibility validation
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def generate_period_grid(school: dict) -> list[dict]:
    """
    Generate the complete period grid for the school week.
    
    Returns a list of period slots with:
    - day: Day name (Mon, Tue, etc.)
    - period: Period number (0 = prayer/assembly, 1+ = academic)
    - start_time: Period start time
    - end_time: Period end time
    - is_prayer: Whether this is Period 0
    - is_recess: Whether this follows a recess
    - is_after_lunch: Whether this is immediately after lunch
    
    LUNCH BREAK STRUCTURE:
    - lunch_after_period: N means lunch break occurs AFTER Period N, BEFORE Period N+1
    - Lunch is NOT a period itself - it's a time gap between academic periods
    - Example: lunch_after_period=4 → Period 4 ends → 30min lunch → Period 5 starts
    
    RECESS STRUCTURE:
    - recess_period_indices: List of period numbers AFTER which recess occurs
    - Alternatively, use recess_after_every_n_periods for automatic placement
    
    Args:
        school: School configuration dictionary
    
    Returns:
        List of period slot dictionaries
    """
    grid = []
    
    weekdays = school.get("weekdays", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
    periods_per_weekday = school.get("periods_per_weekday", 8)
    saturday_periods = school.get("saturday_periods", 4)
    prayer_enabled = school.get("prayer_enabled", True)
    
    start_time_str = school.get("start_time", "08:00")
    period_duration = school.get("period_duration_minutes", 40)
    prayer_duration = school.get("prayer_duration_minutes", 15)
    
    # Support both field names for backward compatibility
    lunch_after_period = school.get("lunch_after_period") or school.get("lunch_period_index", 4)
    lunch_duration = school.get("lunch_duration_minutes", 30)
    
    # Recess configuration - support both explicit indices and automatic placement
    recess_indices = set(school.get("recess_period_indices", []))
    recess_every_n = school.get("recess_after_every_n_periods")
    recess_duration = school.get("recess_duration_minutes", 15)
    
    # Parse start time
    base_time = datetime.strptime(start_time_str, "%H:%M")
    
    for day in weekdays:
        current_time = base_time
        num_periods = saturday_periods if day == "Sat" else periods_per_weekday
        
        # Calculate automatic recess positions if configured
        day_recess_indices = set(recess_indices)
        if recess_every_n and recess_every_n > 0:
            # Add recess after every N periods (excluding lunch period)
            for i in range(recess_every_n, num_periods, recess_every_n):
                if i != lunch_after_period:  # Don't double-break at lunch
                    day_recess_indices.add(i)
        
        # Period 0 (prayer/assembly) if enabled
        if prayer_enabled:
            grid.append({
                "day": day,
                "period": 0,
                "start_time": current_time.strftime("%H:%M"),
                "end_time": (current_time + timedelta(minutes=prayer_duration)).strftime("%H:%M"),
                "is_prayer": True,
                "is_recess": False,
                "is_after_lunch": False,
                "is_break": True,  # Not for academic scheduling
            })
            current_time += timedelta(minutes=prayer_duration)
        
        # Academic periods
        for period_num in range(1, num_periods + 1):
            # Check if this period comes after a recess (previous period was followed by recess)
            is_after_recess = (period_num - 1) in day_recess_indices
            
            # Check if this period comes after lunch
            # lunch_after_period=4 means lunch is AFTER Period 4, so Period 5 is_after_lunch=True
            is_after_lunch = period_num == lunch_after_period + 1
            
            grid.append({
                "day": day,
                "period": period_num,
                "start_time": current_time.strftime("%H:%M"),
                "end_time": (current_time + timedelta(minutes=period_duration)).strftime("%H:%M"),
                "is_prayer": False,
                "is_recess": is_after_recess,
                "is_after_lunch": is_after_lunch,
                "is_break": False,
            })
            
            current_time += timedelta(minutes=period_duration)
            
            # Add breaks AFTER this period (not AS this period)
            # Recess break
            if period_num in day_recess_indices:
                current_time += timedelta(minutes=recess_duration)
            
            # Lunch break - occurs AFTER lunch_after_period, not AS a period
            if period_num == lunch_after_period:
                current_time += timedelta(minutes=lunch_duration)
    
    return grid


def get_academic_periods(period_grid: list[dict]) -> list[dict]:
    """
    Filter period grid to only academic periods (non-prayer, non-break).
    
    Args:
        period_grid: Full period grid
    
    Returns:
        List of academic period slots only
    """
    return [p for p in period_grid if not p.get("is_break", False) and not p.get("is_prayer", False)]


def get_periods_by_day(period_grid: list[dict]) -> dict[str, list[dict]]:
    """
    Group periods by day.
    
    Args:
        period_grid: Full period grid
    
    Returns:
        Dictionary mapping day names to their periods
    """
    by_day = {}
    for period in period_grid:
        day = period["day"]
        if day not in by_day:
            by_day[day] = []
        by_day[day].append(period)
    return by_day


def build_teacher_capability_matrix(
    teachers: list[dict], 
    subjects: list[dict]
) -> dict[str, set[str]]:
    """
    Build a matrix of what subjects each teacher can teach.
    
    Args:
        teachers: List of teacher dictionaries
        subjects: List of subject dictionaries
    
    Returns:
        Dictionary mapping teacher_id to set of subject_ids they can teach
    """
    subject_ids = {s["subject_id"] for s in subjects}
    matrix = {}
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        can_teach = set(teacher.get("subjects_can_teach", []))
        # Validate that subjects exist
        valid_subjects = can_teach.intersection(subject_ids)
        matrix[teacher_id] = valid_subjects
        
        if can_teach != valid_subjects:
            invalid = can_teach - valid_subjects
            logger.warning(
                f"Teacher {teacher_id} references non-existent subjects: {invalid}"
            )
    
    return matrix


def build_availability_mask(
    teacher: dict, 
    period_grid: list[dict]
) -> dict[tuple[str, int], bool]:
    """
    Build availability mask for a teacher across all periods.
    
    Args:
        teacher: Teacher dictionary
        period_grid: Full period grid
    
    Returns:
        Dictionary mapping (day, period) to availability boolean
    """
    availability = teacher.get("availability", {})
    mask = {}
    
    for slot in period_grid:
        day = slot["day"]
        period = slot["period"]
        
        # Default: available for all non-prayer periods
        is_available = not slot.get("is_prayer", False)
        
        # Check day-specific availability
        day_availability = availability.get(day, {})
        
        if not day_availability.get("available", True):
            is_available = False
        elif "blocked_periods" in day_availability:
            if period in day_availability["blocked_periods"]:
                is_available = False
        elif "from_time" in day_availability and "to_time" in day_availability:
            # Time-based availability
            slot_start = slot["start_time"]
            from_time = day_availability["from_time"]
            to_time = day_availability["to_time"]
            
            if slot_start < from_time or slot_start >= to_time:
                is_available = False
        
        mask[(day, period)] = is_available
    
    return mask


def build_all_availability_masks(
    teachers: list[dict],
    period_grid: list[dict]
) -> dict[str, dict[tuple[str, int], bool]]:
    """
    Build availability masks for all teachers.
    
    Args:
        teachers: List of teacher dictionaries
        period_grid: Full period grid
    
    Returns:
        Dictionary mapping teacher_id to their availability mask
    """
    return {
        teacher["teacher_id"]: build_availability_mask(teacher, period_grid)
        for teacher in teachers
    }


def calculate_total_available_slots(
    school: dict,
    period_grid: Optional[list[dict]] = None
) -> int:
    """
    Calculate total number of academic slots per week per section.
    
    Args:
        school: School configuration
        period_grid: Optional pre-generated period grid
    
    Returns:
        Total academic slots per week
    """
    if period_grid is None:
        period_grid = generate_period_grid(school)
    
    return len(get_academic_periods(period_grid))


def validate_feasibility(solver_input: dict) -> tuple[bool, list[str], list[dict]]:
    """
    Pre-flight feasibility checks before running the solver.
    
    Validates that the input data represents a potentially solvable problem:
    - Total required periods don't exceed available slots
    - Teachers have capacity for assigned subjects
    - Block periods can fit in the grid
    - Resources have sufficient capacity
    - Teacher availability is sufficient for their assignments
    
    Args:
        solver_input: Complete solver input dictionary
    
    Returns:
        Tuple of (is_feasible, warning_messages, diagnostic_details)
        diagnostic_details is a list of structured diagnostic objects
    """
    warnings = []
    diagnostics = []
    is_feasible = True
    
    school = solver_input.get("school", {})
    classes = solver_input.get("classes", [])
    teachers = solver_input.get("teachers", [])
    subjects = solver_input.get("subjects", [])
    resources = solver_input.get("resources", [])
    constraints = solver_input.get("constraints", {})
    
    # Generate period grid
    period_grid = generate_period_grid(school)
    academic_periods = get_academic_periods(period_grid)
    periods_by_day = get_periods_by_day(academic_periods)
    
    total_slots_per_section = len(academic_periods)
    weekdays = list(periods_by_day.keys())
    num_days = len(weekdays)
    
    # Build lookup maps
    subject_map = {s["subject_id"]: s for s in subjects}
    teacher_map = {t["teacher_id"]: t for t in teachers}
    
    # Build availability masks
    availability_masks = build_all_availability_masks(teachers, period_grid)
    
    # === Check 1: Total required periods vs available slots ===
    for cls in classes:
        section_id = cls["section_id"]
        subject_teacher_map = cls.get("subject_teacher_map", {})
        
        min_required = 0
        max_required = 0
        
        for subject_id in subject_teacher_map.keys():
            subject = subject_map.get(subject_id)
            if subject:
                min_required += subject.get("min_per_week", 0)
                max_required += subject.get("max_per_week", 0)
        
        if min_required > total_slots_per_section:
            msg = (
                f"Section '{section_id}': minimum required periods ({min_required}) "
                f"exceeds available slots ({total_slots_per_section})"
            )
            warnings.append(msg)
            diagnostics.append({
                "type": "slot_overflow",
                "severity": "critical",
                "category": "Capacity",
                "entity": section_id,
                "message": msg,
                "details": {
                    "required": min_required,
                    "available": total_slots_per_section,
                    "deficit": min_required - total_slots_per_section,
                },
                "suggestions": [
                    f"Reduce subject periods by at least {min_required - total_slots_per_section}",
                    "Increase the number of periods per day",
                    "Remove some subjects from this section",
                ],
            })
            is_feasible = False
        elif max_required < total_slots_per_section:
            warnings.append(
                f"Section '{section_id}': maximum periods ({max_required}) is less than "
                f"available slots ({total_slots_per_section}) - some slots will be empty"
            )
    
    # === Check 2: Teacher capacity ===
    teacher_assignments = {t["teacher_id"]: [] for t in teachers}
    
    for cls in classes:
        section_id = cls["section_id"]
        for subject_id, teacher_id in cls.get("subject_teacher_map", {}).items():
            if teacher_id in teacher_assignments:
                subject = subject_map.get(subject_id)
                if subject:
                    teacher_assignments[teacher_id].append({
                        "section_id": section_id,
                        "subject_id": subject_id,
                        "min_per_week": subject.get("min_per_week", 0),
                        "max_per_week": subject.get("max_per_week", 0),
                    })
    
    for teacher_id, assignments in teacher_assignments.items():
        teacher = teacher_map.get(teacher_id)
        if not teacher:
            continue
        
        total_min = sum(a["min_per_week"] for a in assignments)
        
        # Check weekly limits
        teacher_max_week = teacher.get("max_periods_week", 40)
        
        if total_min > teacher_max_week:
            msg = (
                f"Teacher '{teacher_id}': minimum required ({total_min}) exceeds "
                f"max_periods_week ({teacher_max_week})"
            )
            warnings.append(msg)
            diagnostics.append({
                "type": "teacher_overload",
                "severity": "critical",
                "category": "Teacher Capacity",
                "entity": teacher_id,
                "message": msg,
                "details": {
                    "required": total_min,
                    "max_week": teacher_max_week,
                    "assignments": assignments,
                },
                "suggestions": [
                    f"Increase teacher's max_periods_week to at least {total_min}",
                    "Redistribute some sections to other qualified teachers",
                    "Reduce period requirements for assigned subjects",
                ],
            })
            is_feasible = False
        
        # Check daily limits
        max_per_day = teacher.get("max_periods_day", 8)
        min_daily_requirement = total_min / num_days
        
        if min_daily_requirement > max_per_day:
            warnings.append(
                f"Teacher '{teacher_id}': average daily requirement ({min_daily_requirement:.1f}) "
                f"may exceed max_periods_day ({max_per_day})"
            )
        
        # === Check 2b: Teacher availability vs assignments ===
        # Calculate how many slots the teacher is actually available
        mask = availability_masks.get(teacher_id, {})
        available_slots = sum(1 for (day, period), avail in mask.items() if avail and period > 0)
        
        if total_min > available_slots:
            msg = (
                f"Teacher '{teacher_id}': requires {total_min} periods but only "
                f"available for {available_slots} slots based on their availability"
            )
            warnings.append(msg)
            diagnostics.append({
                "type": "availability_conflict",
                "severity": "critical",
                "category": "Teacher Availability",
                "entity": teacher_id,
                "message": msg,
                "details": {
                    "required": total_min,
                    "available_slots": available_slots,
                    "deficit": total_min - available_slots,
                },
                "suggestions": [
                    "Extend teacher's available hours",
                    "Reduce their teaching load",
                    "Assign some classes to other teachers",
                ],
            })
            is_feasible = False
    
    # === Check 3: Block periods fit in grid ===
    for subject in subjects:
        if subject.get("requires_block", False):
            block_length = subject.get("block_length", 2)
            subject_id = subject["subject_id"]
            
            # Check if any day has enough consecutive periods
            can_fit = False
            for day, day_periods in periods_by_day.items():
                # Check for consecutive slots not crossing lunch/recess
                consecutive = 0
                for period in day_periods:
                    if period.get("is_after_lunch") or period.get("is_recess"):
                        consecutive = 1  # Reset after break
                    else:
                        consecutive += 1
                    
                    if consecutive >= block_length:
                        can_fit = True
                        break
                
                if can_fit:
                    break
            
            if not can_fit:
                msg = (
                    f"Subject '{subject_id}' requires {block_length} consecutive periods "
                    f"but no day has sufficient unbroken slots"
                )
                warnings.append(msg)
                diagnostics.append({
                    "type": "block_impossible",
                    "severity": "critical",
                    "category": "Block Scheduling",
                    "entity": subject_id,
                    "message": msg,
                    "details": {
                        "block_length": block_length,
                    },
                    "suggestions": [
                        "Reduce block length",
                        "Adjust lunch/recess breaks to allow longer consecutive periods",
                        "Disable block requirement for this subject",
                    ],
                })
                is_feasible = False
    
    # === Check 4: Resource capacity ===
    resource_demand = {}
    for cls in classes:
        for subject_id in cls.get("subject_teacher_map", {}).keys():
            subject = subject_map.get(subject_id)
            if subject and subject.get("requires_resource"):
                resource_type = subject.get("resource_type")
                if resource_type:
                    if resource_type not in resource_demand:
                        resource_demand[resource_type] = 0
                    resource_demand[resource_type] += subject.get("min_per_week", 0)
    
    resource_capacity = {}
    for resource in resources:
        resource_type = resource["resource_type"]
        capacity = resource.get("max_simultaneous_capacity", 1)
        # Total capacity per week = capacity * total_slots
        resource_capacity[resource_type] = capacity * total_slots_per_section
    
    for resource_type, demand in resource_demand.items():
        if resource_type in resource_capacity:
            if demand > resource_capacity[resource_type]:
                warnings.append(
                    f"Resource '{resource_type}': total demand ({demand}) may exceed "
                    f"weekly capacity ({resource_capacity[resource_type]})"
                )
    
    # === Check 5: Substitution reserve feasibility ===
    reserve_count = constraints.get("substitution_reserve_count", 3)
    if reserve_count > len(teachers):
        warnings.append(
            f"Substitution reserve ({reserve_count}) exceeds total teachers ({len(teachers)})"
        )
        is_feasible = False
    
    # === Check 6: Class teacher assignments ===
    if constraints.get("class_teacher_period_1", True):
        for cls in classes:
            class_teacher_id = cls.get("class_teacher_id")
            if class_teacher_id and class_teacher_id not in teacher_map:
                warnings.append(
                    f"Section '{cls['section_id']}': class_teacher_id '{class_teacher_id}' "
                    f"not found in teachers list"
                )
    
    # === Check 7: Subject-Teacher Lock-in Validation ===
    # Ensures each subject-section pair has exactly ONE teacher who teaches ALL periods
    for cls in classes:
        section_id = cls["section_id"]
        subject_teacher_map = cls.get("subject_teacher_map", {})
        
        for subject_id, teacher_id in subject_teacher_map.items():
            # Validate teacher exists
            if teacher_id not in teacher_map:
                msg = (
                    f"Section '{section_id}', Subject '{subject_id}': "
                    f"Teacher '{teacher_id}' not found in teachers list"
                )
                warnings.append(msg)
                diagnostics.append({
                    "type": "missing_teacher",
                    "severity": "critical",
                    "category": "Configuration",
                    "entity": teacher_id,
                    "message": msg,
                    "suggestions": [
                        f"Add teacher '{teacher_id}' to the teachers list",
                        "Assign a different existing teacher to this subject",
                    ],
                })
                is_feasible = False
                continue
            
            # Validate teacher can teach this subject
            teacher = teacher_map[teacher_id]
            subjects_can_teach = set(teacher.get("subjects_can_teach", []))
            
            if subjects_can_teach and subject_id not in subjects_can_teach:
                msg = (
                    f"Section '{section_id}', Subject '{subject_id}': "
                    f"Teacher '{teacher_id}' is not qualified to teach this subject. "
                    f"Teacher can teach: {subjects_can_teach}"
                )
                warnings.append(msg)
                diagnostics.append({
                    "type": "unqualified_teacher",
                    "severity": "critical",
                    "category": "Configuration",
                    "entity": teacher_id,
                    "message": msg,
                    "details": {
                        "section_id": section_id,
                        "subject_id": subject_id,
                        "can_teach": list(subjects_can_teach),
                    },
                    "suggestions": [
                        f"Add '{subject_id}' to teacher's subjects_can_teach list",
                        "Assign a different qualified teacher",
                    ],
                })
                is_feasible = False
    
    return is_feasible, warnings, diagnostics


def build_section_subject_teacher_map(classes: list[dict]) -> dict[str, dict[str, str]]:
    """
    Build a mapping of section -> subject -> teacher.
    
    Args:
        classes: List of class dictionaries
    
    Returns:
        Nested dictionary: section_id -> subject_id -> teacher_id
    """
    result = {}
    for cls in classes:
        section_id = cls["section_id"]
        result[section_id] = dict(cls.get("subject_teacher_map", {}))
    return result


def get_class_teachers(classes: list[dict]) -> dict[str, str]:
    """
    Build a mapping of section to class teacher.
    
    Args:
        classes: List of class dictionaries
    
    Returns:
        Dictionary mapping section_id to class_teacher_id
    """
    return {
        cls["section_id"]: cls.get("class_teacher_id")
        for cls in classes
        if cls.get("class_teacher_id")
    }
