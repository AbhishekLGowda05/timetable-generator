"""
CP-SAT Solver Model for Timetable Generation.

This module contains the core constraint programming model that generates
optimal timetables using Google OR-Tools CP-SAT solver.

Design Principles:
1. Global Solve: All classes solved together in one model
2. Variable Naming: Clear prefixes (X_ for assignments, B_ for blocks)
3. Objective Function: Weighted sum of soft constraint penalties
4. Configurable Time Limit
"""

import logging
import time
from typing import Callable, Optional

from ortools.sat.python import cp_model

from .preprocess import (
    generate_period_grid,
    get_academic_periods,
    get_periods_by_day,
    build_all_availability_masks,
    build_section_subject_teacher_map,
    get_class_teachers,
)
from .constraints import add_all_hard_constraints, add_all_soft_constraints

logger = logging.getLogger(__name__)


class TimetableSolver:
    """
    Core timetable solver using CP-SAT.
    
    Builds and solves a constraint programming model that assigns:
    - Subjects to time slots for each section
    - Teachers to their assigned sections/subjects
    - Resources to sections requiring them
    """
    
    def __init__(self, solver_input: dict):
        """
        Initialize the solver with input data.
        
        Args:
            solver_input: Complete solver input dictionary
        """
        self.solver_input = solver_input
        self.school = solver_input["school"]
        self.classes = solver_input["classes"]
        self.teachers = solver_input["teachers"]
        self.subjects = solver_input["subjects"]
        self.resources = solver_input.get("resources", [])
        self.constraints_config = solver_input.get("constraints", {})
        
        # Build data structures
        self.period_grid = generate_period_grid(self.school)
        self.academic_periods = get_academic_periods(self.period_grid)
        self.periods_by_day = get_periods_by_day(self.academic_periods)
        self.weekdays = list(self.periods_by_day.keys())
        
        # Build lookup maps
        self.subject_map = {s["subject_id"]: s for s in self.subjects}
        self.teacher_map = {t["teacher_id"]: t for t in self.teachers}
        self.section_map = {c["section_id"]: c for c in self.classes}
        self.resource_map = {r["resource_type"]: r for r in self.resources}
        
        # Section -> Subject -> Teacher mapping
        self.section_subject_teacher = build_section_subject_teacher_map(self.classes)
        self.class_teachers = get_class_teachers(self.classes)
        
        # Teacher availability
        self.availability_masks = build_all_availability_masks(
            self.teachers, self.period_grid
        )
        
        # CP-SAT model and variables (initialized during build)
        self.model: Optional[cp_model.CpModel] = None
        self.variables: dict = {}
        self.soft_penalties: list = []
        
    def build_model(self) -> None:
        """
        Build the complete CP-SAT model with all variables and constraints.
        """
        logger.info("Building CP-SAT model...")
        start_time = time.time()
        
        self.model = cp_model.CpModel()
        self.variables = {}
        self.soft_penalties = []
        
        # Create decision variables
        self._create_variables()
        
        # Add hard constraints
        add_all_hard_constraints(
            self.model,
            self.variables,
            self.solver_input,
            self.academic_periods,
            self.periods_by_day,
            self.section_subject_teacher,
            self.availability_masks,
            self.subject_map,
            self.teacher_map,
            self.resource_map,
            self.class_teachers,
        )
        
        # Add soft constraints and collect penalties
        self.soft_penalties = add_all_soft_constraints(
            self.model,
            self.variables,
            self.solver_input,
            self.academic_periods,
            self.periods_by_day,
            self.section_subject_teacher,
            self.subject_map,
            self.teacher_map,
        )
        
        # Set objective: minimize soft constraint violations
        if self.soft_penalties:
            self.model.Minimize(sum(self.soft_penalties))
        
        build_time = time.time() - start_time
        logger.info(f"Model built in {build_time:.2f}s")
        logger.info(f"Variables: {len(self.variables.get('X', {}))} assignment vars")
    
    def _create_variables(self) -> None:
        """
        Create all CP-SAT decision variables.
        
        Variables created:
        - X[section][day][period][subject]: Binary, subject assigned to slot
        - B[section][subject][day][period]: Binary, block start indicator
        """
        X = {}  # Assignment variables
        B = {}  # Block start variables
        
        for cls in self.classes:
            section_id = cls["section_id"]
            subject_teacher_map = cls.get("subject_teacher_map", {})
            
            X[section_id] = {}
            B[section_id] = {}
            
            for day in self.weekdays:
                X[section_id][day] = {}
                
                for period_slot in self.periods_by_day[day]:
                    period = period_slot["period"]
                    X[section_id][day][period] = {}
                    
                    for subject_id in subject_teacher_map.keys():
                        var_name = f"X_{section_id}_{day}_P{period}_{subject_id}"
                        X[section_id][day][period][subject_id] = self.model.NewBoolVar(var_name)
            
            # Block start variables for subjects requiring blocks
            for subject_id in subject_teacher_map.keys():
                subject = self.subject_map.get(subject_id)
                if subject and subject.get("requires_block", False):
                    B[section_id][subject_id] = {}
                    
                    for day in self.weekdays:
                        B[section_id][subject_id][day] = {}
                        
                        for period_slot in self.periods_by_day[day]:
                            period = period_slot["period"]
                            var_name = f"B_{section_id}_{subject_id}_{day}_P{period}"
                            B[section_id][subject_id][day][period] = self.model.NewBoolVar(var_name)
        
        self.variables["X"] = X
        self.variables["B"] = B
    
    def solve(
        self, 
        time_limit: int = 30,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> dict:
        """
        Solve the timetable model.
        
        Args:
            time_limit: Maximum solver time in seconds
            progress_callback: Optional callback for progress updates (0-100)
        
        Returns:
            Solver output dictionary matching solver_output.schema.json
        """
        if self.model is None:
            self.build_model()
        
        logger.info(f"Starting solver with time limit: {time_limit}s")
        start_time = time.time()
        
        # Import config for search workers
        try:
            from ..config import CP_SAT_SEARCH_WORKERS
            num_workers = CP_SAT_SEARCH_WORKERS
        except ImportError:
            num_workers = 8  # Default to 8 workers for better optimization
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = num_workers
        solver.parameters.log_search_progress = True
        
        # Additional solver parameters for better results
        # Use more aggressive search strategies for timetabling
        solver.parameters.linearization_level = 2  # More linearization
        solver.parameters.cp_model_presolve = True
        solver.parameters.cp_model_probing_level = 2  # More probing
        
        # Optimization parameters for school timetabling
        # These help the solver find better solutions with the increased time limit
        solver.parameters.use_optional_variables = True
        solver.parameters.optimize_with_core = True
        
        # binary_minimization_algorithm parameter requires enum value in newer versions
        # Using try/except to handle different OR-Tools versions
        try:
            from ortools.sat.python import cp_model as cp
            if hasattr(cp, 'BinaryMinimizationAlgorithm'):
                solver.parameters.binary_minimization_algorithm = cp.BinaryMinimizationAlgorithm.BINARY_SEARCH
            else:
                # Older versions don't have this enum, skip setting
                pass
        except (ImportError, AttributeError):
            # Older OR-Tools versions may not support this parameter
            pass
        
        # If we have more time (> 60s), enable more thorough search
        if time_limit > 60:
            solver.parameters.interleave_search = True
            solver.parameters.diversify_lns_params = True
        
        logger.info(f"Solver config: workers={num_workers}, time_limit={time_limit}s")
        
        # Create solution callback for progress
        callback = SolutionCallback(progress_callback)
        
        status = solver.Solve(self.model, callback)
        solve_time = time.time() - start_time
        
        logger.info(f"Solver finished in {solve_time:.2f}s, status: {solver.StatusName(status)}")
        
        # Map OR-Tools status to our status
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "ERROR",
            cp_model.UNKNOWN: "TIMEOUT",
        }
        
        result_status = status_map.get(status, "ERROR")
        
        # Build result
        result = {
            "status": result_status,
            "timetable": {},
            "teacher_schedules": {},
            "meta": {
                "solve_time_seconds": round(solve_time, 2),
                "variables_count": self._count_variables(),
                "constraints_count": self.model.Proto().constraints.__len__() if self.model else 0,
                "objective_value": solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
                "solver_status_code": status,
                "soft_violations": {},
            },
            "diagnostics": [],
            "warnings": [],
            "grid_config": self._build_grid_config(),  # Include break/period structure
        }
        
        # Extract solution if found
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            result["timetable"] = self._extract_timetable(solver)
            result["teacher_schedules"] = self._extract_teacher_schedules(solver)
            result["resource_views"] = self._extract_resource_views(solver)
        
        return result
    
    def _build_grid_config(self) -> dict:
        """
        Build grid configuration metadata for frontend rendering.
        
        This includes information about:
        - Period structure (Period 0/Assembly, academic periods)
        - Break positions and durations (recess, lunch)
        - Time slots for each period
        - Days configuration
        
        Returns:
            Grid configuration dictionary for frontend
        """
        school = self.school
        
        # Extract break configuration
        recess_after_period = school.get("recess_after_period", 2)
        recess_duration = school.get("recess_duration_minutes", 20)
        lunch_after_period = school.get("lunch_after_period") or school.get("lunch_period_index", 5)
        lunch_duration = school.get("lunch_duration_minutes", 40)
        
        # Handle recess as list (could be multiple recess periods)
        recess_indices = school.get("recess_period_indices", [])
        if not recess_indices and recess_after_period:
            recess_indices = [recess_after_period]
        
        # Build period times from period_grid
        period_times = []
        seen_periods = set()
        for slot in self.period_grid:
            period_num = slot["period"]
            if period_num not in seen_periods:
                seen_periods.add(period_num)
                period_times.append({
                    "period": period_num,
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                    "is_prayer": slot.get("is_prayer", False),
                    "is_after_recess": slot.get("is_recess", False),
                    "is_after_lunch": slot.get("is_after_lunch", False),
                })
        
        return {
            "weekdays": self.weekdays,
            "periods_per_weekday": school.get("periods_per_weekday", 8),
            "saturday_periods": school.get("saturday_periods", 4),
            "prayer_enabled": school.get("prayer_enabled", True),
            "prayer_duration_minutes": school.get("prayer_duration_minutes", 30),
            "recess": {
                "after_periods": recess_indices,
                "duration_minutes": recess_duration,
            },
            "lunch": {
                "after_period": lunch_after_period,
                "duration_minutes": lunch_duration,
            },
            "period_times": sorted(period_times, key=lambda x: x["period"]),
            "start_time": school.get("start_time", "08:00"),
            "period_duration_minutes": school.get("period_duration_minutes", 45),
        }
    
    def _count_variables(self) -> int:
        """Count total decision variables."""
        count = 0
        X = self.variables.get("X", {})
        for section in X.values():
            for day in section.values():
                for period in day.values():
                    count += len(period)
        
        B = self.variables.get("B", {})
        for section in B.values():
            for subject in section.values():
                for day in subject.values():
                    count += len(day)
        
        return count
    
    def _extract_timetable(self, solver: cp_model.CpSolver) -> dict:
        """
        Extract the timetable from the solved model.
        
        Args:
            solver: The solved CP solver
        
        Returns:
            Timetable dictionary by section and day
        """
        timetable = {}
        X = self.variables["X"]
        B = self.variables.get("B", {})
        
        for cls in self.classes:
            section_id = cls["section_id"]
            subject_teacher_map = cls.get("subject_teacher_map", {})
            timetable[section_id] = {}
            
            for day in self.weekdays:
                timetable[section_id][day] = []
                
                for period_slot in self.periods_by_day[day]:
                    period = period_slot["period"]
                    
                    # Find assigned subject
                    assigned_subject = None
                    assigned_teacher = None
                    
                    for subject_id in subject_teacher_map.keys():
                        if solver.Value(X[section_id][day][period][subject_id]) == 1:
                            assigned_subject = subject_id
                            assigned_teacher = subject_teacher_map.get(subject_id)
                            break
                    
                    if assigned_subject:
                        subject = self.subject_map.get(assigned_subject, {})
                        teacher = self.teacher_map.get(assigned_teacher, {})
                        
                        # Check if this is a block period
                        is_block_start = False
                        is_block_continuation = False
                        
                        if subject.get("requires_block", False):
                            section_b = B.get(section_id, {})
                            subject_b = section_b.get(assigned_subject, {})
                            day_b = subject_b.get(day, {})
                            
                            if period in day_b:
                                is_block_start = solver.Value(day_b[period]) == 1
                            
                            # Check if previous period was same subject (continuation)
                            prev_period = period - 1
                            if prev_period in X[section_id][day]:
                                if assigned_subject in X[section_id][day][prev_period]:
                                    if solver.Value(X[section_id][day][prev_period][assigned_subject]) == 1:
                                        is_block_continuation = True
                        
                        # Get resource if applicable
                        resource_id = None
                        if subject.get("requires_resource"):
                            resource_id = subject.get("resource_type")
                        
                        slot_entry = {
                            "period": period,
                            "subject_id": assigned_subject,
                            "subject_name": subject.get("name", assigned_subject),
                            "teacher_id": assigned_teacher,
                            "teacher_name": teacher.get("name", assigned_teacher),
                            "start_time": period_slot.get("start_time"),
                            "end_time": period_slot.get("end_time"),
                            "is_block_start": is_block_start,
                            "is_block_continuation": is_block_continuation,
                        }
                        
                        if resource_id:
                            slot_entry["resource_id"] = resource_id
                        
                        timetable[section_id][day].append(slot_entry)
                    else:
                        # Free period
                        timetable[section_id][day].append({
                            "period": period,
                            "subject_id": "FREE",
                            "subject_name": "Free Period",
                            "teacher_id": None,
                            "teacher_name": None,
                            "start_time": period_slot.get("start_time"),
                            "end_time": period_slot.get("end_time"),
                            "is_block_start": False,
                            "is_block_continuation": False,
                        })
        
        return timetable
    
    def _extract_teacher_schedules(self, solver: cp_model.CpSolver) -> dict:
        """
        Extract teacher-centric view of the timetable.
        
        Args:
            solver: The solved CP solver
        
        Returns:
            Schedule dictionary by teacher and day
        """
        schedules = {t["teacher_id"]: {} for t in self.teachers}
        X = self.variables["X"]
        
        for teacher in self.teachers:
            teacher_id = teacher["teacher_id"]
            
            for day in self.weekdays:
                schedules[teacher_id][day] = []
                
                for period_slot in self.periods_by_day[day]:
                    period = period_slot["period"]
                    
                    # Find which section/subject this teacher is teaching
                    assigned = None
                    
                    for cls in self.classes:
                        section_id = cls["section_id"]
                        subject_teacher_map = cls.get("subject_teacher_map", {})
                        
                        for subject_id, assigned_teacher in subject_teacher_map.items():
                            if assigned_teacher == teacher_id:
                                if solver.Value(X[section_id][day][period][subject_id]) == 1:
                                    assigned = {
                                        "period": period,
                                        "section_id": section_id,
                                        "subject_id": subject_id,
                                    }
                                    break
                        
                        if assigned:
                            break
                    
                    if assigned:
                        schedules[teacher_id][day].append(assigned)
        
        return schedules

    def _extract_resource_views(self, solver: cp_model.CpSolver) -> dict:
        """
        Extract resource-centric view of the timetable.
        Shows which sections are using each resource at each time slot.
        
        Args:
            solver: The solved CP solver
        
        Returns:
            Schedule dictionary by resource_id and day
        """
        resource_views = {}
        X = self.variables["X"]
        
        # Find all resources used
        resources_used = set()
        for subject in self.subjects:
            if subject.get("requires_resource") and subject.get("resource_type"):
                resources_used.add(subject["resource_type"])
        
        # Initialize views
        for resource_id in resources_used:
            resource_views[resource_id] = {}
        
        # Scan timetable for resource usage
        for cls in self.classes:
            section_id = cls["section_id"]
            subject_teacher_map = cls.get("subject_teacher_map", {})
            
            for day in self.weekdays:
                for period_slot in self.periods_by_day[day]:
                    period = period_slot["period"]
                    
                    for subject_id in subject_teacher_map.keys():
                        if solver.Value(X[section_id][day][period][subject_id]) == 1:
                            subject = self.subject_map.get(subject_id, {})
                            
                            if subject.get("requires_resource") and subject.get("resource_type"):
                                resource_id = subject["resource_type"]
                                
                                if resource_id not in resource_views:
                                    resource_views[resource_id] = {}
                                
                                if day not in resource_views[resource_id]:
                                    resource_views[resource_id][day] = []
                                
                                resource_views[resource_id][day].append({
                                    "period": period,
                                    "section_id": section_id,
                                    "subject_id": subject_id,
                                    "teacher_id": subject_teacher_map.get(subject_id),
                                })
        
        return resource_views


class SolutionCallback(cp_model.CpSolverSolutionCallback):
    """
    Callback for tracking solver progress and solutions.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[int], None]] = None):
        super().__init__()
        self._progress_callback = progress_callback
        self._solution_count = 0
        self._start_time = time.time()
    
    def on_solution_callback(self) -> None:
        """Called when a new solution is found."""
        self._solution_count += 1
        elapsed = time.time() - self._start_time
        
        logger.info(
            f"Solution {self._solution_count} found at {elapsed:.1f}s, "
            f"objective: {self.ObjectiveValue()}"
        )
        
        if self._progress_callback:
            # Estimate progress based on solutions found
            progress = min(90, 40 + self._solution_count * 10)
            self._progress_callback(progress)
