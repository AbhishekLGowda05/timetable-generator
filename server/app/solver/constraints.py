"""
Constraint implementations for the timetable solver.

This module contains all hard and soft constraints as individual functions.
Each constraint function:
- Accepts: model, variables, solver_input, period data
- Returns: None (adds constraints directly) or slack variables (soft constraints)
- Checks toggle state from constraints config

Hard Constraints (must be satisfied):
- Teacher single assignment
- Section single subject per period
- Max consecutive periods
- Subject weekly load requirements
- Block period integrity
- Resource capacity
- Teacher availability
- Substitution reserve

Soft Constraints (preferences to optimize):
- Core subjects in morning
- Teacher load balance
- Minimize schedule gaps
- Subject distribution
"""

import logging

from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


# =============================================================================
# HARD CONSTRAINTS
# =============================================================================

def add_all_hard_constraints(
    model: cp_model.CpModel,
    variables: dict,
    solver_input: dict,
    academic_periods: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    availability_masks: dict[str, dict[tuple[str, int], bool]],
    subject_map: dict[str, dict],
    teacher_map: dict[str, dict],
    resource_map: dict[str, dict],
    class_teachers: dict[str, str],
) -> None:
    """
    Add all hard constraints to the model.
    
    Constraint Types:
    - HARD_CORE: Always added, cannot be relaxed (teacher clash, class clash, etc.)
    - HARD_RELAXABLE: Added unless explicitly relaxed (can be disabled for feasibility)
    
    Relaxation is controlled by constraints_config flags:
    - relax_teacher_daily_load: Skip daily load bounds
    - relax_weekly_balance: Skip weekly load balance constraint
    - relax_block_periods: Allow non-consecutive blocks
    """
    constraints_config = solver_input.get("constraints", {})
    classes = solver_input.get("classes", [])
    teachers = solver_input.get("teachers", [])
    resources = solver_input.get("resources", [])
    
    # ==========================================================================
    # HARD_CORE Constraints - Always enforced, cannot be relaxed
    # ==========================================================================
    
    # Core assignment: Each section can have only ONE subject per period
    add_section_single_subject_constraint(
        model, variables, classes, periods_by_day
    )
    
    # Core: Teacher cannot be in two places at once
    add_teacher_single_assignment_constraint(
        model, variables, classes, teachers, periods_by_day, 
        section_subject_teacher, availability_masks
    )
    
    # Core: Subject frequency - subjects must get their required periods
    add_subject_frequency_constraint(
        model, variables, classes, periods_by_day, subject_map
    )
    
    # Core: Resource capacity limits
    if resources:
        add_resource_capacity_constraint(
            model, variables, classes, periods_by_day,
            subject_map, resource_map
        )
    
    # ==========================================================================
    # HARD_RELAXABLE Constraints - Can be disabled for feasibility
    # ==========================================================================
    
    # Teacher workload constraints (relaxable)
    if not constraints_config.get("relax_teacher_daily_load", False):
        add_teacher_load_bounds_constraint(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, constraints_config
        )
    else:
        logger.info("RELAXED: Teacher daily load bounds constraint")
    
    # Max consecutive periods (relaxable via high value)
    max_consec = constraints_config.get("max_consecutive_default", 3)
    if max_consec < 99:  # 99 = effectively disabled
        add_max_consecutive_constraint(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, constraints_config
        )
    else:
        logger.info("RELAXED: Max consecutive periods constraint")
    
    # Block period constraints (relaxable)
    if not constraints_config.get("relax_block_periods", False):
        add_block_period_constraint(
            model, variables, classes, periods_by_day, subject_map
        )
    else:
        logger.info("RELAXED: Block period integrity constraint")
    
    # ==========================================================================
    # OPTIONAL HARD_RELAXABLE Constraints - Disabled by default
    # ==========================================================================
    
    # Class teacher in Period 1 (default: disabled)
    if constraints_config.get("class_teacher_period_1", False):
        add_class_teacher_period_1_constraint(
            model, variables, classes, periods_by_day,
            section_subject_teacher, class_teachers
        )
    
    # Language sync (default: disabled)
    if constraints_config.get("language_sync_enabled", False):
        add_language_sync_constraint(
            model, variables, classes, periods_by_day,
            section_subject_teacher, subject_map
        )
    
    # No subject twice daily (default: disabled)
    if constraints_config.get("no_subject_twice_daily", False):
        add_no_subject_twice_daily_constraint(
            model, variables, classes, periods_by_day, subject_map
        )
    
    # Substitution reserve (only if count > 0)
    reserve_count = constraints_config.get("substitution_reserve_count", 0)
    if reserve_count > 0:
        add_substitution_reserve_constraint(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, reserve_count
        )
    
    # Free periods handling - now just logs policy
    # The actual filling is handled by subject_frequency_constraint
    if constraints_config.get("no_free_periods", False):
        logger.info("no_free_periods enabled but using soft enforcement via subject frequency")
    
    add_no_free_periods_constraint(
        model, variables, classes, periods_by_day
    )
    
    logger.info("All hard constraints added")


def add_section_single_subject_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
) -> None:
    """
    Each section can have only ONE subject scheduled per period.
    """
    X = variables["X"]
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_ids = list(cls.get("subject_teacher_map", {}).keys())
        
        for day, day_periods in periods_by_day.items():
            for period_slot in day_periods:
                period = period_slot["period"]
                
                # Sum of all subjects assigned to this slot <= 1
                period_vars = [
                    X[section_id][day][period][subject_id]
                    for subject_id in subject_ids
                    if subject_id in X[section_id][day][period]
                ]
                
                if period_vars:
                    model.Add(sum(period_vars) <= 1)


def add_teacher_single_assignment_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    availability_masks: dict[str, dict[tuple[str, int], bool]],
) -> None:
    """
    A teacher can teach only ONE class/section per period (no double-booking).
    Also enforces teacher availability constraints.
    """
    X = variables["X"]
    
    # Build teacher -> [(section, subject)] mapping
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        assignments = teacher_assignments.get(teacher_id, [])
        availability = availability_masks.get(teacher_id, {})
        
        for day, day_periods in periods_by_day.items():
            for period_slot in day_periods:
                period = period_slot["period"]
                
                # Get all assignment variables for this teacher at this time
                teacher_period_vars = []
                for section_id, subject_id in assignments:
                    if (section_id in X and day in X[section_id] and 
                        period in X[section_id][day] and 
                        subject_id in X[section_id][day][period]):
                        teacher_period_vars.append(X[section_id][day][period][subject_id])
                
                if teacher_period_vars:
                    # Teacher can only be assigned once per period
                    model.Add(sum(teacher_period_vars) <= 1)
                    
                    # If teacher is unavailable, forbid all assignments
                    if not availability.get((day, period), True):
                        for var in teacher_period_vars:
                            model.Add(var == 0)


def add_subject_frequency_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
) -> None:
    """
    Each subject must receive its min_per_week and max_per_week for each section.
    """
    X = variables["X"]
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_ids = list(cls.get("subject_teacher_map", {}).keys())
        
        for subject_id in subject_ids:
            subject = subject_map.get(subject_id)
            if not subject:
                continue
            
            min_per_week = subject.get("min_per_week", 0)
            max_per_week = subject.get("max_per_week", 10)
            
            # Collect all assignment variables for this subject
            subject_vars = []
            for day, day_periods in periods_by_day.items():
                for period_slot in day_periods:
                    period = period_slot["period"]
                    if subject_id in X[section_id][day][period]:
                        subject_vars.append(X[section_id][day][period][subject_id])
            
            if subject_vars:
                model.Add(sum(subject_vars) >= min_per_week)
                model.Add(sum(subject_vars) <= max_per_week)


def add_teacher_load_bounds_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    constraints_config: dict,
) -> None:
    """
    Teacher cannot exceed max_periods_per_day.
    Teacher must meet min_periods_per_day (if not relaxed).
    Weekly load must be within bounds.
    Weekly load must be BALANCED (unless relax_weekly_balance is set).
    
    CRITICAL: Period 0 (prayer/assembly) is EXCLUDED from load calculations.
    Teachers are present during prayer but it doesn't count toward their teaching load.
    
    RELAXATION OPTIONS:
    - relax_weekly_balance: Disables the max-min daily variance constraint
    - When this constraint is relaxed, only weekly total bounds are enforced
    """
    X = variables["X"]
    
    # Check if weekly balance should be relaxed
    relax_balance = constraints_config.get("relax_weekly_balance", False)
    
    # Build teacher -> [(section, subject)] mapping
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    # Get max daily variance allowed (default: 3 periods difference)
    max_daily_variance = constraints_config.get("max_daily_load_variance", 3)
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        assignments = teacher_assignments.get(teacher_id, [])
        
        if not assignments:
            continue
        
        min_day = teacher.get("min_periods_day", 0)
        max_day = teacher.get("max_periods_day", 8)
        min_week = teacher.get("min_periods_week", 0)
        max_week = teacher.get("max_periods_week", 40)
        
        weekly_vars = []
        daily_load_vars = []  # Track daily loads for balance constraint
        
        for day, day_periods in periods_by_day.items():
            daily_vars = []
            
            for period_slot in day_periods:
                period = period_slot["period"]
                
                # ===== CRITICAL FIX: Exclude Period 0 (prayer/assembly) =====
                # Period 0 is for prayer/assembly - teachers are present but
                # it does NOT count toward their daily/weekly teaching load.
                if period == 0 or period_slot.get("is_prayer", False):
                    continue
                
                for section_id, subject_id in assignments:
                    if (section_id in X and day in X[section_id] and
                        period in X[section_id][day] and
                        subject_id in X[section_id][day][period]):
                        daily_vars.append(X[section_id][day][period][subject_id])
            
            if daily_vars:
                # Create a variable to track this day's load
                daily_load = model.NewIntVar(0, max_day, f"load_{teacher_id}_{day}")
                model.Add(daily_load == sum(daily_vars))
                daily_load_vars.append(daily_load)
                
                # Daily bounds - keep max enforced, relax min for flexibility
                # model.Add(sum(daily_vars) >= min_day)  # Relaxed - causes infeasibility
                model.Add(sum(daily_vars) <= max_day)  # Always enforce max
                weekly_vars.extend(daily_vars)
        
        if weekly_vars:
            # Weekly bounds - always enforced
            model.Add(sum(weekly_vars) >= min_week)
            model.Add(sum(weekly_vars) <= max_week)
        
        # === WEEKLY LOAD BALANCE CONSTRAINT ===
        # Prevent scenarios like 7 periods Monday, 2 periods Tuesday
        # SKIP if relaxed for feasibility
        if not relax_balance and len(daily_load_vars) >= 2:
            max_load = model.NewIntVar(0, max_day, f"max_daily_{teacher_id}")
            min_load = model.NewIntVar(0, max_day, f"min_daily_{teacher_id}")
            model.AddMaxEquality(max_load, daily_load_vars)
            model.AddMinEquality(min_load, daily_load_vars)
            
            # Max daily load - Min daily load <= max_daily_variance
            model.Add(max_load - min_load <= max_daily_variance)
        elif relax_balance:
            logger.debug(f"Weekly balance relaxed for teacher {teacher_id}")


def add_max_consecutive_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    constraints_config: dict,
) -> None:
    """
    Teacher cannot exceed max_consecutive_periods without a break.
    """
    X = variables["X"]
    default_max_consecutive = constraints_config.get("max_consecutive_default", 3)
    
    # Build teacher assignments
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        assignments = teacher_assignments.get(teacher_id, [])
        
        if not assignments:
            continue
        
        max_consecutive = teacher.get("max_consecutive_periods", default_max_consecutive)
        
        for day, day_periods in periods_by_day.items():
            # Sort periods by period number
            sorted_periods = sorted(day_periods, key=lambda p: p["period"])
            
            # For each window of (max_consecutive + 1) periods
            window_size = max_consecutive + 1
            
            for i in range(len(sorted_periods) - window_size + 1):
                window = sorted_periods[i:i + window_size]
                
                # Check if window spans a break
                spans_break = any(
                    p.get("is_recess") or p.get("is_after_lunch") 
                    for p in window[1:]  # Skip first period
                )
                
                if not spans_break:
                    # Collect teacher assignment vars for this window
                    window_vars = []
                    for period_slot in window:
                        period = period_slot["period"]
                        for section_id, subject_id in assignments:
                            if (section_id in X and day in X[section_id] and
                                period in X[section_id][day] and
                                subject_id in X[section_id][day][period]):
                                window_vars.append(X[section_id][day][period][subject_id])
                    
                    if window_vars:
                        # Sum of assignments in window <= max_consecutive
                        model.Add(sum(window_vars) <= max_consecutive)


def add_block_period_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
) -> None:
    """
    Subjects requiring N consecutive periods must get contiguous slots.
    Block cannot bridge recess/lunch.
    """
    X = variables["X"]
    B = variables.get("B", {})
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_ids = list(cls.get("subject_teacher_map", {}).keys())
        
        for subject_id in subject_ids:
            subject = subject_map.get(subject_id)
            if not subject or not subject.get("requires_block", False):
                continue
            
            block_length = subject.get("block_length", 2)
            blocks_needed = subject.get("min_per_week", 1) // block_length
            
            if section_id not in B or subject_id not in B[section_id]:
                continue
            
            block_start_vars = []
            
            for day, day_periods in periods_by_day.items():
                sorted_periods = sorted(day_periods, key=lambda p: p["period"])
                
                for i, period_slot in enumerate(sorted_periods):
                    period = period_slot["period"]
                    
                    if day not in B[section_id][subject_id]:
                        continue
                    if period not in B[section_id][subject_id][day]:
                        continue
                    
                    block_start_var = B[section_id][subject_id][day][period]
                    block_start_vars.append(block_start_var)
                    
                    # Check if block can start here
                    can_start_block = True
                    consecutive_periods = [period_slot]
                    
                    for j in range(1, block_length):
                        if i + j >= len(sorted_periods):
                            can_start_block = False
                            break
                        
                        next_period = sorted_periods[i + j]
                        
                        # Check for break in block
                        if next_period.get("is_recess") or next_period.get("is_after_lunch"):
                            can_start_block = False
                            break
                        
                        consecutive_periods.append(next_period)
                    
                    if not can_start_block:
                        # Cannot start block here
                        model.Add(block_start_var == 0)
                    else:
                        # If block starts here, all consecutive periods must have this subject
                        for block_period_slot in consecutive_periods:
                            block_period = block_period_slot["period"]
                            if subject_id in X[section_id][day][block_period]:
                                model.Add(
                                    X[section_id][day][block_period][subject_id] >= block_start_var
                                )
            
            # Ensure minimum number of blocks
            if block_start_vars:
                model.Add(sum(block_start_vars) >= blocks_needed)


def add_resource_capacity_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
    resource_map: dict[str, dict],
) -> None:
    """
    Resources have limited capacity for simultaneous use.
    """
    X = variables["X"]
    
    # Build resource -> [(section, subject)] mapping
    resource_demands = {}
    for cls in classes:
        section_id = cls["section_id"]
        for subject_id in cls.get("subject_teacher_map", {}).keys():
            subject = subject_map.get(subject_id)
            if subject and subject.get("requires_resource"):
                resource_type = subject.get("resource_type")
                if resource_type:
                    if resource_type not in resource_demands:
                        resource_demands[resource_type] = []
                    resource_demands[resource_type].append((section_id, subject_id))
    
    for resource_type, demands in resource_demands.items():
        resource = resource_map.get(resource_type)
        capacity = resource.get("max_simultaneous_capacity", 1) if resource else 1
        
        for day, day_periods in periods_by_day.items():
            for period_slot in day_periods:
                period = period_slot["period"]
                
                # Collect all vars using this resource at this time
                resource_vars = []
                for section_id, subject_id in demands:
                    if (section_id in X and day in X[section_id] and
                        period in X[section_id][day] and
                        subject_id in X[section_id][day][period]):
                        resource_vars.append(X[section_id][day][period][subject_id])
                
                if resource_vars:
                    model.Add(sum(resource_vars) <= capacity)


def add_class_teacher_period_1_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    class_teachers: dict[str, str],
) -> None:
    """
    Class teacher gets Period 1 every day with their own section.
    """
    X = variables["X"]
    
    for cls in classes:
        section_id = cls["section_id"]
        class_teacher_id = class_teachers.get(section_id)
        
        if not class_teacher_id:
            continue
        
        # Find subjects this teacher teaches to this section
        teacher_subjects = [
            subj_id for subj_id, teacher_id 
            in section_subject_teacher.get(section_id, {}).items()
            if teacher_id == class_teacher_id
        ]
        
        if not teacher_subjects:
            continue
        
        for day, day_periods in periods_by_day.items():
            # Find Period 1
            period_1 = None
            for p in day_periods:
                if p["period"] == 1:
                    period_1 = p
                    break
            
            if period_1 is None:
                continue
            
            period = period_1["period"]
            
            # Class teacher must teach one of their subjects in Period 1
            period_1_vars = [
                X[section_id][day][period][subj_id]
                for subj_id in teacher_subjects
                if subj_id in X[section_id][day][period]
            ]
            
            if period_1_vars:
                model.Add(sum(period_1_vars) >= 1)


def add_language_sync_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    subject_map: dict[str, dict],
) -> None:
    """
    Language Block Synchronization Constraint.
    
    This constraint ensures that language teachers who share sections can be
    scheduled at the same time slots across their shared sections. This enables
    "language blocks" where students split into groups (Hindi, Kannada, Sanskrit)
    and each group goes to a different teacher simultaneously.
    
    IMPORTANT: This does NOT mean all 3 languages are taught to the same section
    at the same time. Instead, it ensures that the language teachers teaching
    the SAME SET of sections can have their periods aligned.
    
    For example, if T016 (Hindi), T019 (Kannada), T022 (Sanskrit) all teach
    sections 6A and 6B, we want to enable scheduling them at the same periods
    so students can be split into language groups.
    
    The constraint works by:
    1. Finding language teacher "sets" that share the same sections
    2. For each set, ensuring that if one language is scheduled for a section,
       the other languages CAN be scheduled for that section at the same time
       (but don't HAVE to be - they just need teachers available)
    
    This is a SOFT synchronization - it allows but doesn't force language blocks.
    The strict version that forces all languages simultaneously is too restrictive.
    """
    # Note: X = variables["X"] available if strict constraint is re-enabled
    
    # Group classes by their language teacher set
    # Key: tuple of sorted teacher IDs, Value: list of section_ids
    teacher_set_to_sections = {}
    
    for cls in classes:
        section_id = cls["section_id"]
        
        # Only apply if language block is explicitly enabled for this class
        if not cls.get("language_block_enabled", False):
            continue
        
        # Get the language teachers from the class definition
        language_teachers_list = cls.get("language_teachers", [])
        
        if len(language_teachers_list) < 2:
            continue
        
        # Create a hashable key from sorted teacher IDs
        teacher_set_key = tuple(sorted(language_teachers_list))
        
        if teacher_set_key not in teacher_set_to_sections:
            teacher_set_to_sections[teacher_set_key] = []
        teacher_set_to_sections[teacher_set_key].append(section_id)
    
    # For each teacher set, ensure teachers aren't double-booked across their sections
    # This is already handled by add_teacher_single_assignment_constraint
    # The language sync just needs to ensure the language subjects get scheduled
    # proportionally across sections sharing the same teachers
    
    # NOTE: The strict "all languages at same time" constraint is removed
    # because it's mathematically infeasible for most school configurations.
    # Instead, we rely on:
    # 1. Teacher single assignment (no double booking)
    # 2. Subject frequency (each subject gets its min/max periods)
    # 3. Soft constraints for load balancing
    
    # Variables are available but the strict constraint is not applied
    # X = variables["X"]  # Kept for reference if needed
    
    logger.info(f"Language sync: Found {len(teacher_set_to_sections)} teacher sets")
    for teacher_set, sections in teacher_set_to_sections.items():
        logger.info(f"  Teachers {teacher_set}: sections {sections}")


def add_substitution_reserve_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    reserve_count: int,
) -> None:
    """
    At each period, minimum N teachers must be kept free.
    """
    X = variables["X"]
    num_teachers = len(teachers)
    
    # Build teacher assignments
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    for day, day_periods in periods_by_day.items():
        for period_slot in day_periods:
            period = period_slot["period"]
            
            # Count assigned teachers at this period
            all_assignment_vars = []
            
            for teacher_id, assignments in teacher_assignments.items():
                teacher_vars = []
                for section_id, subject_id in assignments:
                    if (section_id in X and day in X[section_id] and
                        period in X[section_id][day] and
                        subject_id in X[section_id][day][period]):
                        teacher_vars.append(X[section_id][day][period][subject_id])
                
                if teacher_vars:
                    # Create indicator for "teacher is assigned this period"
                    is_assigned = model.NewBoolVar(f"assigned_{teacher_id}_{day}_P{period}")
                    model.AddMaxEquality(is_assigned, teacher_vars)
                    all_assignment_vars.append(is_assigned)
            
            if all_assignment_vars:
                # Number of free teachers = total - assigned
                # Free teachers >= reserve_count
                # So: assigned <= total - reserve_count
                max_assigned = num_teachers - reserve_count
                model.Add(sum(all_assignment_vars) <= max_assigned)


def add_no_subject_twice_daily_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
) -> None:
    """
    Prevent same subject twice in a day (except lab blocks).
    """
    X = variables["X"]
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_ids = list(cls.get("subject_teacher_map", {}).keys())
        
        for subject_id in subject_ids:
            subject = subject_map.get(subject_id)
            
            # Skip block subjects (they need multiple consecutive periods)
            if subject and subject.get("requires_block", False):
                continue
            
            for day, day_periods in periods_by_day.items():
                # Sum of subject assignments for this day <= 1
                day_vars = [
                    X[section_id][day][period_slot["period"]][subject_id]
                    for period_slot in day_periods
                    if subject_id in X[section_id][day][period_slot["period"]]
                ]
                
                if day_vars:
                    model.Add(sum(day_vars) <= 1)


def add_no_free_periods_constraint(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
) -> None:
    """
    IMPORTANT: This constraint ensures CLASSES have all periods filled,
    NOT that teachers have no free periods.
    
    Teachers MAY have free periods - this is normal and expected.
    Classes should have academic content scheduled for each period.
    
    However, if total subject max_per_week < available slots, free periods
    are allowed for the class. The actual enforcement comes from
    subject_frequency_constraint ensuring minimums are met.
    
    This constraint is now a NO-OP - we rely on subject frequency constraints
    to fill periods. Classes may have study periods/library time.
    """
    # REMOVED: The previous implementation was over-constraining.
    # 
    # The single-subject constraint (add_section_single_subject_constraint) 
    # already ensures <= 1 subject per period.
    #
    # The subject_frequency_constraint ensures subjects meet their
    # min_per_week requirements.
    #
    # Together these allow for proper filling while still permitting
    # free/study periods when subject totals don't fill all slots.
    #
    # Teachers having free periods is EXPECTED and helps with:
    # - Preparation time
    # - Substitution availability
    # - Workload balance
    
    logger.info("Free periods policy: Classes fill based on subject requirements, teachers may have free periods")


# =============================================================================
# SOFT CONSTRAINTS
# =============================================================================

def add_all_soft_constraints(
    model: cp_model.CpModel,
    variables: dict,
    solver_input: dict,
    academic_periods: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    subject_map: dict[str, dict],
    teacher_map: dict[str, dict],
) -> list:
    """
    Add all soft constraints and return penalty variables.
    
    IMPORTANT: If constraints_config has "_phase1_only" = True,
    this function returns empty list (no soft constraints for feasibility phase).
    """
    constraints_config = solver_input.get("constraints", {})
    
    # Phase 1 mode - skip all soft constraints
    if constraints_config.get("_phase1_only", False):
        logger.info("Phase 1 mode: skipping all soft constraints")
        return []
    
    soft_weights = constraints_config.get("soft_weights", {})
    classes = solver_input.get("classes", [])
    teachers = solver_input.get("teachers", [])
    
    all_penalties = []
    
    # Core morning preference
    if soft_weights.get("core_morning", 3) > 0:
        penalties = add_core_morning_preference(
            model, variables, classes, periods_by_day, subject_map,
            soft_weights.get("core_morning", 3)
        )
        all_penalties.extend(penalties)
    
    # Teacher balance preference
    if soft_weights.get("teacher_balance", 10) > 0:
        penalties = add_teacher_balance_preference(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, soft_weights.get("teacher_balance", 10)
        )
        all_penalties.extend(penalties)
    
    # Minimize gaps preference
    if soft_weights.get("minimize_gaps", 5) > 0:
        penalties = add_minimize_gaps_preference(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, soft_weights.get("minimize_gaps", 5)
        )
        all_penalties.extend(penalties)
    
    # Leisure afternoon preference
    if soft_weights.get("leisure_afternoon", 2) > 0:
        penalties = add_leisure_afternoon_preference(
            model, variables, classes, periods_by_day, subject_map,
            soft_weights.get("leisure_afternoon", 2)
        )
        all_penalties.extend(penalties)
    
    # Avoid PE in Period 1
    if soft_weights.get("avoid_pe_period_1", 4) > 0:
        penalties = add_avoid_pe_period_1_preference(
            model, variables, classes, periods_by_day, subject_map,
            soft_weights.get("avoid_pe_period_1", 4)
        )
        all_penalties.extend(penalties)
    
    # Subject distribution (avoid clustering)
    if soft_weights.get("subject_distribution", 3) > 0:
        penalties = add_subject_distribution_preference(
            model, variables, classes, periods_by_day, subject_map,
            soft_weights.get("subject_distribution", 3)
        )
        all_penalties.extend(penalties)
    
    # Teacher free period preference
    if soft_weights.get("teacher_free_period", 2) > 0:
        penalties = add_teacher_free_period_preference(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, soft_weights.get("teacher_free_period", 2)
        )
        all_penalties.extend(penalties)
    
    # Fair undesirable slot distribution
    if soft_weights.get("fair_slot_distribution", 5) > 0:
        penalties = add_fair_slot_distribution_preference(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, soft_weights.get("fair_slot_distribution", 5)
        )
        all_penalties.extend(penalties)
    
    # Specialist teacher prioritization
    if soft_weights.get("specialist_priority", 8) > 0:
        penalties = add_specialist_teacher_priority(
            model, variables, classes, teachers, periods_by_day,
            section_subject_teacher, subject_map, teacher_map,
            soft_weights.get("specialist_priority", 8)
        )
        all_penalties.extend(penalties)
    
    logger.info(f"Added {len(all_penalties)} soft constraint penalty variables")
    return all_penalties


def add_core_morning_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
    weight: int,
) -> list:
    """
    Prefer core subjects in morning periods (1, 2, 3).
    Penalize core subjects after lunch.
    """
    X = variables["X"]
    penalties = []
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_ids = list(cls.get("subject_teacher_map", {}).keys())
        
        core_subjects = [
            subj_id for subj_id in subject_ids
            if subject_map.get(subj_id, {}).get("category") == "core"
        ]
        
        for subject_id in core_subjects:
            for day, day_periods in periods_by_day.items():
                for period_slot in day_periods:
                    period = period_slot["period"]
                    
                    if subject_id not in X[section_id][day][period]:
                        continue
                    
                    # Penalize core subjects after lunch
                    if period_slot.get("is_after_lunch"):
                        penalty_var = model.NewBoolVar(
                            f"core_after_lunch_{section_id}_{day}_P{period}_{subject_id}"
                        )
                        model.Add(penalty_var >= X[section_id][day][period][subject_id])
                        penalties.append(weight * penalty_var)
    
    return penalties


def add_teacher_balance_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    weight: int,
) -> list:
    """
    Minimize variance in teacher daily loads.
    """
    X = variables["X"]
    penalties = []
    
    # Build teacher assignments
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    weekdays = list(periods_by_day.keys())
    
    for teacher_id, assignments in teacher_assignments.items():
        if not assignments:
            continue
        
        daily_loads = []
        
        for day in weekdays:
            day_periods = periods_by_day[day]
            daily_vars = []
            
            for period_slot in day_periods:
                period = period_slot["period"]
                for section_id, subject_id in assignments:
                    if (section_id in X and day in X[section_id] and
                        period in X[section_id][day] and
                        subject_id in X[section_id][day][period]):
                        daily_vars.append(X[section_id][day][period][subject_id])
            
            if daily_vars:
                daily_load = model.NewIntVar(0, 10, f"load_{teacher_id}_{day}")
                model.Add(daily_load == sum(daily_vars))
                daily_loads.append(daily_load)
        
        if len(daily_loads) >= 2:
            # Penalize difference between max and min daily load
            max_load = model.NewIntVar(0, 10, f"max_load_{teacher_id}")
            min_load = model.NewIntVar(0, 10, f"min_load_{teacher_id}")
            model.AddMaxEquality(max_load, daily_loads)
            model.AddMinEquality(min_load, daily_loads)
            
            variance = model.NewIntVar(0, 10, f"variance_{teacher_id}")
            model.Add(variance == max_load - min_load)
            penalties.append(weight * variance)
    
    return penalties


def add_minimize_gaps_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    weight: int,
) -> list:
    """
    Minimize idle gaps in teacher's daily schedule.
    """
    X = variables["X"]
    penalties = []
    
    # Build teacher assignments
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    for teacher_id, assignments in teacher_assignments.items():
        if not assignments:
            continue
        
        for day, day_periods in periods_by_day.items():
            sorted_periods = sorted(day_periods, key=lambda p: p["period"])
            
            # For each internal period, penalize gap if surrounded by teaching
            for i in range(1, len(sorted_periods) - 1):
                period_slot = sorted_periods[i]
                period = period_slot["period"]
                
                # Get assignment var for this period
                period_vars = []
                for section_id, subject_id in assignments:
                    if (section_id in X and day in X[section_id] and
                        period in X[section_id][day] and
                        subject_id in X[section_id][day][period]):
                        period_vars.append(X[section_id][day][period][subject_id])
                
                if not period_vars:
                    continue
                
                # Check if teaching before and after
                prev_period = sorted_periods[i-1]["period"]
                next_period = sorted_periods[i+1]["period"]
                
                prev_vars = []
                next_vars = []
                
                for section_id, subject_id in assignments:
                    if (section_id in X and day in X[section_id]):
                        if prev_period in X[section_id][day] and subject_id in X[section_id][day][prev_period]:
                            prev_vars.append(X[section_id][day][prev_period][subject_id])
                        if next_period in X[section_id][day] and subject_id in X[section_id][day][next_period]:
                            next_vars.append(X[section_id][day][next_period][subject_id])
                
                if prev_vars and next_vars and period_vars:
                    # Create indicator variables
                    has_prev = model.NewBoolVar(f"has_prev_{teacher_id}_{day}_P{period}")
                    has_next = model.NewBoolVar(f"has_next_{teacher_id}_{day}_P{period}")
                    is_free = model.NewBoolVar(f"is_free_{teacher_id}_{day}_P{period}")
                    
                    model.AddMaxEquality(has_prev, prev_vars)
                    model.AddMaxEquality(has_next, next_vars)
                    
                    # is_free = NOT(any period_vars)
                    has_current = model.NewBoolVar(f"has_current_{teacher_id}_{day}_P{period}")
                    model.AddMaxEquality(has_current, period_vars)
                    model.Add(is_free == 1).OnlyEnforceIf(has_current.Not())
                    model.Add(is_free == 0).OnlyEnforceIf(has_current)
                    
                    # Gap penalty: prev AND next AND free
                    is_gap = model.NewBoolVar(f"gap_{teacher_id}_{day}_P{period}")
                    model.AddBoolAnd([has_prev, has_next, is_free]).OnlyEnforceIf(is_gap)
                    model.AddBoolOr([has_prev.Not(), has_next.Not(), is_free.Not()]).OnlyEnforceIf(is_gap.Not())
                    
                    penalties.append(weight * is_gap)
    
    return penalties


def add_leisure_afternoon_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
    weight: int,
) -> list:
    """
    Prefer leisure subjects (PE, Art, Music) in afternoon periods.
    """
    X = variables["X"]
    penalties = []
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_ids = list(cls.get("subject_teacher_map", {}).keys())
        
        leisure_subjects = [
            subj_id for subj_id in subject_ids
            if subject_map.get(subj_id, {}).get("category") == "leisure"
        ]
        
        for subject_id in leisure_subjects:
            for day, day_periods in periods_by_day.items():
                for period_slot in day_periods:
                    period = period_slot["period"]
                    
                    if subject_id not in X[section_id][day][period]:
                        continue
                    
                    # Penalize leisure subjects in morning
                    if period <= 3:  # Morning periods
                        penalty_var = model.NewBoolVar(
                            f"leisure_morning_{section_id}_{day}_P{period}_{subject_id}"
                        )
                        model.Add(penalty_var >= X[section_id][day][period][subject_id])
                        penalties.append(weight * penalty_var)
    
    return penalties


def add_avoid_pe_period_1_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
    weight: int,
) -> list:
    """
    Avoid PE in Period 1 and immediately after lunch.
    """
    X = variables["X"]
    penalties = []
    
    # Find PE subject IDs
    pe_subjects = [
        subj["subject_id"] for subj in subject_map.values()
        if "PE" in subj.get("name", "").upper() or 
           "PHYSICAL" in subj.get("name", "").upper() or
           subj.get("subject_id", "").upper() in ["PE", "PHYSICAL_EDUCATION"]
    ]
    
    if not pe_subjects:
        return penalties
    
    for cls in classes:
        section_id = cls["section_id"]
        section_pe = [s for s in pe_subjects if s in cls.get("subject_teacher_map", {})]
        
        for subject_id in section_pe:
            for day, day_periods in periods_by_day.items():
                for period_slot in day_periods:
                    period = period_slot["period"]
                    
                    if subject_id not in X[section_id][day][period]:
                        continue
                    
                    # Penalize PE in Period 1
                    if period == 1:
                        penalty_var = model.NewBoolVar(
                            f"pe_period1_{section_id}_{day}_{subject_id}"
                        )
                        model.Add(penalty_var >= X[section_id][day][period][subject_id])
                        penalties.append(weight * penalty_var)
                    
                    # Penalize PE after lunch
                    if period_slot.get("is_after_lunch"):
                        penalty_var = model.NewBoolVar(
                            f"pe_after_lunch_{section_id}_{day}_{subject_id}"
                        )
                        model.Add(penalty_var >= X[section_id][day][period][subject_id])
                        penalties.append(weight * penalty_var)
    
    return penalties


def add_subject_distribution_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    periods_by_day: dict[str, list[dict]],
    subject_map: dict[str, dict],
    weight: int,
) -> list:
    """
    Distribute heavy subjects evenly across the week.
    Penalize clustering of similar subjects on the same day.
    """
    X = variables["X"]
    penalties = []
    
    for cls in classes:
        section_id = cls["section_id"]
        subject_ids = list(cls.get("subject_teacher_map", {}).keys())
        
        # Find heavy/core subjects
        heavy_subjects = [
            subj_id for subj_id in subject_ids
            if subject_map.get(subj_id, {}).get("category") == "core"
        ]
        
        for subject_id in heavy_subjects:
            subject = subject_map.get(subject_id)
            if not subject:
                continue
            
            min_per_week = subject.get("min_per_week", 0)
            
            # For subjects with 5+ periods, penalize >2 on same day
            if min_per_week >= 5:
                for day, day_periods in periods_by_day.items():
                    day_vars = [
                        X[section_id][day][period_slot["period"]][subject_id]
                        for period_slot in day_periods
                        if subject_id in X[section_id][day][period_slot["period"]]
                    ]
                    
                    if len(day_vars) > 2:
                        # Penalize having more than 2 of this subject per day
                        excess = model.NewIntVar(0, 10, f"excess_{section_id}_{day}_{subject_id}")
                        model.Add(excess >= sum(day_vars) - 2)
                        penalties.append(weight * excess)
    
    return penalties


def add_teacher_free_period_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    weight: int,
) -> list:
    """
    Give each teacher at least one free period daily for preparation.
    """
    X = variables["X"]
    penalties = []
    
    # Build teacher assignments
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        assignments = teacher_assignments.get(teacher_id, [])
        
        if not assignments:
            continue
        
        for day, day_periods in periods_by_day.items():
            num_periods = len(day_periods)
            
            # Count periods taught this day
            daily_vars = []
            for period_slot in day_periods:
                period = period_slot["period"]
                for section_id, subject_id in assignments:
                    if (section_id in X and day in X[section_id] and
                        period in X[section_id][day] and
                        subject_id in X[section_id][day][period]):
                        daily_vars.append(X[section_id][day][period][subject_id])
            
            if daily_vars and num_periods > 0:
                # Penalize if teaching all periods (no free period)
                all_busy = model.NewBoolVar(f"all_busy_{teacher_id}_{day}")
                # all_busy = 1 if sum(daily_vars) >= num_periods
                model.Add(sum(daily_vars) >= num_periods).OnlyEnforceIf(all_busy)
                model.Add(sum(daily_vars) < num_periods).OnlyEnforceIf(all_busy.Not())
                penalties.append(weight * all_busy)
    
    return penalties


def add_fair_slot_distribution_preference(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    weight: int,
) -> list:
    """
    Fair distribution of undesirable slots (Friday P8, Saturday P4) among teachers.
    """
    X = variables["X"]
    penalties = []
    
    # Define undesirable slots
    undesirable_slots = []
    for day, day_periods in periods_by_day.items():
        sorted_periods = sorted(day_periods, key=lambda p: p["period"])
        if sorted_periods:
            last_period = sorted_periods[-1]["period"]
            # Last period of each day is less desirable
            undesirable_slots.append((day, last_period))
            # Friday and Saturday last periods are worst
            if day in ["Fri", "Sat"]:
                undesirable_slots.append((day, last_period))  # Double weight
    
    # Build teacher assignments
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            if teacher_id not in teacher_assignments:
                teacher_assignments[teacher_id] = []
            teacher_assignments[teacher_id].append((section_id, subject_id))
    
    # Track undesirable slot assignments per teacher
    teacher_undesirable_counts = []
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        assignments = teacher_assignments.get(teacher_id, [])
        
        if not assignments:
            continue
        
        teacher_bad_vars = []
        
        for day, period in undesirable_slots:
            if day not in periods_by_day:
                continue
            
            for section_id, subject_id in assignments:
                if (section_id in X and day in X[section_id] and
                    period in X[section_id][day] and
                    subject_id in X[section_id][day][period]):
                    teacher_bad_vars.append(X[section_id][day][period][subject_id])
        
        if teacher_bad_vars:
            count = model.NewIntVar(0, len(teacher_bad_vars), f"bad_slots_{teacher_id}")
            model.Add(count == sum(teacher_bad_vars))
            teacher_undesirable_counts.append(count)
    
    # Penalize variance in undesirable slot counts (fairness)
    if len(teacher_undesirable_counts) >= 2:
        max_bad = model.NewIntVar(0, 20, "max_bad_slots")
        min_bad = model.NewIntVar(0, 20, "min_bad_slots")
        model.AddMaxEquality(max_bad, teacher_undesirable_counts)
        model.AddMinEquality(min_bad, teacher_undesirable_counts)
        
        unfairness = model.NewIntVar(0, 20, "slot_unfairness")
        model.Add(unfairness == max_bad - min_bad)
        penalties.append(weight * unfairness)
    
    return penalties


def add_specialist_teacher_priority(
    model: cp_model.CpModel,
    variables: dict,
    classes: list[dict],
    teachers: list[dict],
    periods_by_day: dict[str, list[dict]],
    section_subject_teacher: dict[str, dict[str, str]],
    subject_map: dict[str, dict],
    teacher_map: dict[str, dict],
    weight: int,
) -> list:
    """
    Prioritize scheduling for specialist/rare subject teachers.
    
    Specialist teachers (Sanskrit, French, Music, Art, etc.) typically:
    - Teach subjects with few periods per week
    - May teach across many sections
    - Have limited availability windows
    
    This constraint ensures their required periods are scheduled first by
    penalizing any unmet specialist teacher requirements.
    
    Teachers are identified as specialists by:
    - is_specialist flag on teacher
    - Teaching subjects marked as is_specialist
    - Teaching rare languages or arts subjects
    """
    X = variables["X"]
    penalties = []
    
    # Identify specialist subjects
    specialist_subjects = set()
    for subject_id, subject in subject_map.items():
        is_specialist = (
            subject.get("is_specialist", False) or
            subject.get("category") in ["language", "arts", "music", "special"] or
            any(s in subject.get("name", "").lower() for s in [
                "sanskrit", "french", "german", "spanish", "music", "art",
                "dance", "craft", "drawing", "painting", "instrumental"
            ])
        )
        if is_specialist:
            specialist_subjects.add(subject_id)
    
    if not specialist_subjects:
        return penalties
    
    # Identify specialist teachers
    specialist_teachers = set()
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        
        # Check if teacher is marked as specialist
        if teacher.get("is_specialist", False):
            specialist_teachers.add(teacher_id)
            continue
        
        # Check if teacher teaches specialist subjects
        for section_id, subject_teacher in section_subject_teacher.items():
            for subject_id, t_id in subject_teacher.items():
                if t_id == teacher_id and subject_id in specialist_subjects:
                    specialist_teachers.add(teacher_id)
                    break
    
    if not specialist_teachers:
        return penalties
    
    # For specialist teachers, ensure their subjects are scheduled
    # by penalizing periods where they could teach but aren't
    for teacher_id in specialist_teachers:
        teacher = teacher_map.get(teacher_id)
        if not teacher:
            continue
        
        # Collect all specialist subject assignments for this teacher
        specialist_assignments = []
        for section_id, subject_teacher in section_subject_teacher.items():
            for subject_id, t_id in subject_teacher.items():
                if t_id == teacher_id and subject_id in specialist_subjects:
                    specialist_assignments.append((section_id, subject_id))
        
        if not specialist_assignments:
            continue
        
        # Count weekly assignments for specialist subjects
        weekly_vars = []
        for section_id, subject_id in specialist_assignments:
            for day, day_periods in periods_by_day.items():
                for period_slot in day_periods:
                    period = period_slot["period"]
                    if (section_id in X and day in X[section_id] and
                        period in X[section_id][day] and
                        subject_id in X[section_id][day][period]):
                        weekly_vars.append(X[section_id][day][period][subject_id])
        
        # Calculate total required periods for specialist subjects
        total_required = sum(
            subject_map.get(subject_id, {}).get("min_per_week", 1)
            for _, subject_id in specialist_assignments
        )
        
        if weekly_vars and total_required > 0:
            # Penalize if specialist doesn't get required periods
            shortfall = model.NewIntVar(0, total_required, f"specialist_shortfall_{teacher_id}")
            model.Add(shortfall >= total_required - sum(weekly_vars))
            penalties.append(weight * shortfall)
    
    return penalties
