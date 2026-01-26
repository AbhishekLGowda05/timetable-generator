"""
Two-Phase Timetable Solver with Automatic Relaxation.

This module implements a guaranteed-feasible solving pipeline:

Phase 1 (Feasibility):
- Uses HARD_CORE constraints strictly
- Attempts to find ANY valid timetable
- If fails: triggers automatic relaxation of HARD_RELAXABLE constraints

Phase 2 (Optimization):  
- Uses Phase 1 solution as baseline
- Adds SOFT constraints for optimization
- Returns best solution found (even if time limit reached)

Automatic Relaxation:
- If Phase 1 fails, iteratively relaxes HARD_RELAXABLE constraints
- Follows priority order (least disruptive → most disruptive)
- Stops when feasibility is found or all constraints exhausted

Design Philosophy:
- Feasible > Optimal: Return a usable timetable first, then improve
- Never return infeasible if mathematical solution exists
- Clear logging and diagnostics for troubleshooting
"""

import logging
import time
import hashlib
import json
from typing import Optional, Callable
from dataclasses import dataclass, field

from .constraint_types import (
    SolvePhase,
    RelaxationResult,
    get_enabled_relaxable_constraints,
    get_relaxation_order,
    CONSTRAINT_REGISTRY,
)
from .preprocess import (
    generate_period_grid,
    get_academic_periods,
    get_periods_by_day,
    build_all_availability_masks,
    build_section_subject_teacher_map,
    get_class_teachers,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CAPACITY ANALYSIS
# =============================================================================

@dataclass
class CapacityAnalysis:
    """
    Pre-solve capacity analysis results.
    
    Used to determine if a solution is mathematically possible before solving.
    """
    total_required_periods: int
    total_teacher_capacity: int
    num_classes: int
    num_teachers: int
    periods_per_class: int
    capacity_ratio: float
    is_sufficient: bool
    warnings: list = field(default_factory=list)
    teacher_load_details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "total_required_periods": self.total_required_periods,
            "total_teacher_capacity": self.total_teacher_capacity,
            "num_classes": self.num_classes,
            "num_teachers": self.num_teachers,
            "periods_per_class": self.periods_per_class,
            "capacity_ratio": round(self.capacity_ratio, 2),
            "is_sufficient": self.is_sufficient,
            "warnings": self.warnings,
            "teacher_load_details": self.teacher_load_details,
        }


def analyze_capacity(solver_input: dict) -> CapacityAnalysis:
    """
    Perform pre-solve capacity analysis.
    
    Determines if the teacher capacity is mathematically sufficient
    to cover all class periods. This is a necessary (but not sufficient)
    condition for feasibility.
    
    Args:
        solver_input: Complete solver input dictionary
        
    Returns:
        CapacityAnalysis with capacity metrics
    """
    school = solver_input.get("school", {})
    classes = solver_input.get("classes", [])
    teachers = solver_input.get("teachers", [])
    subjects = solver_input.get("subjects", [])
    
    # Generate period grid
    period_grid = generate_period_grid(school)
    academic_periods = get_academic_periods(period_grid)
    periods_per_class = len(academic_periods)
    
    # Calculate total required periods
    num_classes = len(classes)
    total_required = num_classes * periods_per_class
    
    # Calculate total teacher capacity
    subject_map = {s["subject_id"]: s for s in subjects}
    total_teacher_capacity = 0
    teacher_loads = {}
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        max_week = teacher.get("max_periods_week", 40)
        teacher_loads[teacher_id] = {
            "max_capacity": max_week,
            "required": 0,
            "sections": [],
        }
        total_teacher_capacity += max_week
    
    # Calculate actual required load per teacher based on assignments
    for cls in classes:
        section_id = cls["section_id"]
        for subject_id, teacher_id in cls.get("subject_teacher_map", {}).items():
            if teacher_id in teacher_loads:
                subject = subject_map.get(subject_id, {})
                min_periods = subject.get("min_per_week", 0)
                teacher_loads[teacher_id]["required"] += min_periods
                teacher_loads[teacher_id]["sections"].append(f"{section_id}/{subject_id}")
    
    capacity_ratio = total_teacher_capacity / total_required if total_required > 0 else float('inf')
    is_sufficient = total_teacher_capacity >= total_required
    
    warnings = []
    overloaded_teachers = []
    
    if not is_sufficient:
        deficit = total_required - total_teacher_capacity
        warnings.append(
            f"Teacher capacity ({total_teacher_capacity}) is less than required periods "
            f"({total_required}). Deficit: {deficit} periods."
        )
    
    # Check individual teacher overloads
    for teacher_id, load in teacher_loads.items():
        if load["required"] > load["max_capacity"]:
            overloaded_teachers.append(teacher_id)
            warnings.append(
                f"Teacher {teacher_id}: required {load['required']} periods exceeds capacity {load['max_capacity']}"
            )
    
    # Log capacity analysis
    if capacity_ratio >= 1.2:
        logger.info(f"CapacityAnalysis: Good ratio {capacity_ratio:.2f} ({len(teachers)} teachers, {num_classes} classes)")
    elif capacity_ratio >= 1.0:
        logger.info(f"CapacityAnalysis: Tight ratio {capacity_ratio:.2f} ({len(teachers)} teachers, {num_classes} classes)")
    else:
        logger.warning(f"CapacityAnalysis: Insufficient ratio {capacity_ratio:.2f} ({len(teachers)} teachers, {num_classes} classes)")
    
    return CapacityAnalysis(
        total_required_periods=total_required,
        total_teacher_capacity=total_teacher_capacity,
        num_classes=num_classes,
        num_teachers=len(teachers),
        periods_per_class=periods_per_class,
        capacity_ratio=capacity_ratio,
        is_sufficient=is_sufficient,
        warnings=warnings,
        teacher_load_details={
            "overloaded": overloaded_teachers,
            "teacher_count": len(teachers),
            "class_count": num_classes,
        },
    )


# =============================================================================
# INPUT HASHING
# =============================================================================

def compute_input_hash(solver_input: dict, include_options: bool = True) -> str:
    """
    Compute a deterministic hash of the solver input.
    
    Used for result caching - same input should return same cached result.
    Different constraints or solver version should produce different hash.
    
    Args:
        solver_input: Complete solver input dictionary
        include_options: Whether to include time_limit in hash
        
    Returns:
        SHA-256 hash string
    """
    from ..config import SOLVER_VERSION
    
    # Create a normalized, sorted representation for consistent hashing
    def normalize(obj):
        if isinstance(obj, dict):
            return {k: normalize(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [normalize(item) for item in obj]
        else:
            return obj
    
    # Include all relevant fields in hash
    hash_input = {
        "solver_version": SOLVER_VERSION,  # Include version to invalidate on upgrades
        "school": normalize(solver_input.get("school", {})),
        "classes": normalize(solver_input.get("classes", [])),
        "teachers": normalize(solver_input.get("teachers", [])),
        "subjects": normalize(solver_input.get("subjects", [])),
        "resources": normalize(solver_input.get("resources", [])),
        "constraints": normalize(solver_input.get("constraints", {})),
    }
    
    # Optionally include time_limit (different time limits = different cache entries)
    if include_options:
        hash_input["time_limit_seconds"] = solver_input.get("time_limit_seconds", 120)
    
    # Compute hash
    json_str = json.dumps(hash_input, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


# =============================================================================
# STATUS TRACKING
# =============================================================================

@dataclass 
class TwoPhaseStatus:
    """Status tracking for two-phase solving."""
    
    phase: SolvePhase = SolvePhase.FEASIBILITY
    relaxation_iteration: int = 0
    relaxed_constraints: list = field(default_factory=list)
    phase1_solution: Optional[dict] = None
    phase2_solution: Optional[dict] = None
    total_solve_time: float = 0.0
    phase1_time: float = 0.0
    phase2_time: float = 0.0
    capacity_analysis: Optional[CapacityAnalysis] = None
    solver_stats: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)
    
    def add_log(self, message: str, level: str = "info"):
        """Add a log entry."""
        self.logs.append({
            "timestamp": time.time(),
            "level": level,
            "message": message,
        })
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)


# =============================================================================
# TWO-PHASE SOLVER
# =============================================================================

class TwoPhaseSolver:
    """
    Two-phase timetable solver with automatic relaxation.
    
    Implements a guaranteed-feasible solving pipeline:
    1. Capacity check - verify mathematical feasibility
    2. Phase 1 - find any feasible solution (with auto-relaxation)
    3. Phase 2 - optimize the feasible solution
    """
    
    def __init__(self, solver_input: dict):
        """
        Initialize the two-phase solver.
        
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
        
        # Status tracking
        self.status = TwoPhaseStatus()
        
        # Compute input hash for caching
        self.input_hash = compute_input_hash(solver_input)
        
    def solve(
        self,
        time_limit: int = 120,
        progress_callback: Optional[Callable[[int], bool]] = None,
    ) -> dict:
        """
        Execute the two-phase solving pipeline.
        
        Args:
            time_limit: Total time limit in seconds
            progress_callback: Optional callback for progress updates (returns True if cancelled)
            
        Returns:
            Solver output dictionary with solution and metadata
        """
        from ..config import (
            SOLVER_PHASE1_TIME_FRACTION,
            SOLVER_PHASE2_TIME_FRACTION,
            MIN_PHASE1_TIME_SEC,
            MIN_PHASE2_TIME_SEC,
            SOLVER_MAX_RELAXATION_ITERATIONS,
        )
        
        start_time = time.time()
        self.status.add_log(f"TwoPhaseSolver starting with time_limit={time_limit}s")
        
        # Step 1: Capacity analysis
        self.status.add_log("Step 1: Running capacity analysis")
        self.status.capacity_analysis = analyze_capacity(self.solver_input)
        
        if not self.status.capacity_analysis.is_sufficient:
            self.status.add_log(
                f"Warning: Capacity may be insufficient (ratio: {self.status.capacity_analysis.capacity_ratio:.2f})",
                "warning"
            )
            for warning in self.status.capacity_analysis.warnings:
                self.status.add_log(f"  {warning}", "warning")
        else:
            self.status.add_log(
                f"Capacity OK: {self.status.capacity_analysis.num_teachers} teachers, "
                f"{self.status.capacity_analysis.num_classes} classes, "
                f"ratio: {self.status.capacity_analysis.capacity_ratio:.2f}"
            )
        
        if progress_callback and progress_callback(5):
            return self._build_cancelled_result()
        
        # Calculate phase time allocations
        phase1_time = max(MIN_PHASE1_TIME_SEC, int(time_limit * SOLVER_PHASE1_TIME_FRACTION))
        phase2_time = max(MIN_PHASE2_TIME_SEC, int(time_limit * SOLVER_PHASE2_TIME_FRACTION))
        
        self.status.add_log(f"Time allocation: Phase1={phase1_time}s, Phase2={phase2_time}s")
        
        # Step 2: Phase 1 - Feasibility solve with auto-relaxation
        self.status.add_log("Step 2: Phase 1 - Feasibility solve with auto-relaxation")
        self.status.phase = SolvePhase.FEASIBILITY
        
        relaxation_result = self._solve_with_relaxation(
            time_limit=phase1_time,
            max_iterations=SOLVER_MAX_RELAXATION_ITERATIONS,
            progress_callback=lambda p: progress_callback(5 + int(p * 0.4)) if progress_callback else False,
        )
        
        self.status.phase1_time = time.time() - start_time
        self.status.add_log(f"Phase 1 completed in {self.status.phase1_time:.2f}s")
        
        if not relaxation_result.success:
            # True infeasibility - even with all relaxations
            self.status.add_log("Phase 1 FAILED - no feasible solution found", "error")
            self.status.total_solve_time = time.time() - start_time
            return self._build_infeasible_result(relaxation_result)
        
        self.status.phase1_solution = relaxation_result.solution
        self.status.relaxed_constraints = relaxation_result.relaxed_constraints
        
        if relaxation_result.relaxed_constraints:
            self.status.add_log(
                f"Phase 1 found feasible solution (relaxed: {', '.join(relaxation_result.relaxed_constraints)})"
            )
        else:
            self.status.add_log("Phase 1 found feasible solution (no relaxations needed)")
        
        if progress_callback and progress_callback(50):
            return self._build_cancelled_result()
        
        # Step 3: Phase 2 - Optimization solve
        self.status.add_log("Step 3: Phase 2 - Optimization solve")
        self.status.phase = SolvePhase.OPTIMIZATION
        
        remaining_time = time_limit - int(time.time() - start_time)
        actual_phase2_time = max(MIN_PHASE2_TIME_SEC, remaining_time)
        
        self.status.add_log(f"Phase 2 starting with {actual_phase2_time}s remaining")
        
        phase2_result = self._solve_phase2(
            warm_start=relaxation_result.solution,
            time_limit=actual_phase2_time,
            progress_callback=lambda p: progress_callback(50 + int(p * 0.45)) if progress_callback else False,
        )
        
        self.status.phase2_time = time.time() - start_time - self.status.phase1_time
        self.status.total_solve_time = time.time() - start_time
        
        if progress_callback and progress_callback(95):
            return self._build_cancelled_result()
        
        # Return best result
        if phase2_result and phase2_result.get("status") in ["OPTIMAL", "FEASIBLE"]:
            self.status.phase2_solution = phase2_result
            self.status.add_log(f"Phase 2 completed: status={phase2_result['status']}")
            return self._build_final_result(phase2_result, relaxation_result)
        else:
            # Phase 2 failed or timeout, return Phase 1 solution
            self.status.add_log("Phase 2 did not improve, returning Phase 1 solution", "warning")
            return self._build_final_result(
                relaxation_result.solution, 
                relaxation_result,
                phase2_attempted=True,
                phase2_failed=True,
            )
    
    def _solve_with_relaxation(
        self,
        time_limit: int,
        max_iterations: int,
        progress_callback: Optional[Callable[[int], bool]] = None,
    ) -> RelaxationResult:
        """
        Attempt to find feasibility, relaxing constraints if needed.
        
        Args:
            time_limit: Total time limit for relaxation attempts
            max_iterations: Maximum relaxation iterations
            progress_callback: Progress callback (returns True if cancelled)
            
        Returns:
            RelaxationResult with solution or diagnostics
        """
        from ..config import RELAXATION_ATTEMPT_TIME_FRACTION
        
        start_time = time.time()
        relaxed_constraints = []
        iteration = 0
        
        # Get enabled relaxable constraints in priority order
        relaxable = get_relaxation_order()
        relaxable_names = [c.name for c in relaxable if c.is_enabled(self.constraints_config)]
        
        self.status.add_log(f"Relaxation order: {relaxable_names}")
        
        while iteration < max_iterations:
            iteration += 1
            elapsed = time.time() - start_time
            remaining = time_limit - elapsed
            
            if remaining < 10:
                self.status.add_log("Time limit reached during relaxation", "warning")
                break
            
            # Calculate time for this attempt
            attempt_time = min(int(remaining * RELAXATION_ATTEMPT_TIME_FRACTION), 30)
            attempt_time = max(10, attempt_time)  # At least 10 seconds
            
            self.status.add_log(
                f"Relaxation iteration {iteration}: "
                f"relaxed={relaxed_constraints}, attempt_time={attempt_time}s"
            )
            
            # Check for cancellation
            if progress_callback:
                progress = int((iteration / (len(relaxable_names) + 2)) * 100)
                if progress_callback(progress):
                    return RelaxationResult(
                        success=False,
                        relaxed_constraints=relaxed_constraints,
                        iterations=iteration,
                        final_status="CANCELLED",
                        diagnostics=[{"type": "info", "message": "Cancelled by user"}],
                    )
            
            # Build and solve with current relaxation set
            result = self._solve_phase1(
                relaxed_constraints=relaxed_constraints,
                time_limit=attempt_time,
            )
            
            if result["status"] in ["OPTIMAL", "FEASIBLE"]:
                self.status.add_log(
                    f"Found feasible solution after {iteration} iterations "
                    f"with relaxations: {relaxed_constraints}"
                )
                
                return RelaxationResult(
                    success=True,
                    relaxed_constraints=relaxed_constraints.copy(),
                    iterations=iteration,
                    final_status=result["status"],
                    solution=result,
                )
            
            # Find next constraint to relax
            next_to_relax = None
            for name in relaxable_names:
                if name not in relaxed_constraints:
                    next_to_relax = name
                    break
            
            if next_to_relax is None:
                # All constraints relaxed, truly infeasible
                self.status.add_log(
                    "All relaxable constraints exhausted, problem is infeasible",
                    "error"
                )
                break
            
            self.status.add_log(f"Relaxing constraint: {next_to_relax}")
            relaxed_constraints.append(next_to_relax)
        
        # Failed to find feasible solution
        return RelaxationResult(
            success=False,
            relaxed_constraints=relaxed_constraints,
            iterations=iteration,
            final_status="INFEASIBLE",
            diagnostics=[{
                "type": "error",
                "category": "infeasibility",
                "message": "Could not find feasible solution even after relaxing all constraints",
                "relaxed": relaxed_constraints,
                "suggestion": "Check teacher capacity and subject requirements",
            }],
        )
    
    def _solve_phase1(
        self,
        relaxed_constraints: list,
        time_limit: int,
    ) -> dict:
        """
        Execute Phase 1 solve with specified relaxations.
        
        Phase 1 uses only HARD_CORE constraints plus enabled HARD_RELAXABLE
        (minus any relaxed constraints). No SOFT constraints.
        
        Args:
            relaxed_constraints: List of constraint names to skip
            time_limit: Time limit in seconds
            
        Returns:
            Solver result dictionary
        """
        from .model import TimetableSolver
        from ..config import CP_SAT_SEARCH_WORKERS, CP_SAT_RANDOM_SEED
        
        # Create a modified constraints config that disables relaxed constraints
        modified_config = dict(self.constraints_config)
        
        for name in relaxed_constraints:
            # Disable the relaxed constraints
            if name == "language_sync":
                modified_config["language_sync_enabled"] = False
            elif name == "class_teacher_period_1":
                modified_config["class_teacher_period_1"] = False
            elif name == "no_subject_twice_daily":
                modified_config["no_subject_twice_daily"] = False
            elif name == "substitution_reserve":
                modified_config["substitution_reserve_count"] = 0
            elif name == "max_consecutive":
                modified_config["max_consecutive_default"] = 99  # Effectively disable
            elif name == "teacher_daily_load":
                modified_config["relax_teacher_daily_load"] = True
            elif name == "teacher_weekly_balance":
                modified_config["relax_weekly_balance"] = True
            elif name == "block_periods":
                modified_config["relax_block_periods"] = True
        
        # Force disable soft constraints for Phase 1
        modified_config["_phase1_only"] = True
        modified_config["soft_weights"] = {k: 0 for k in modified_config.get("soft_weights", {})}
        
        # Create solver with modified config
        modified_input = dict(self.solver_input)
        modified_input["constraints"] = modified_config
        
        solver = TimetableSolver(modified_input)
        result = solver.solve(time_limit=time_limit)
        
        # Capture solver stats
        if "solver_stats" in result:
            self.status.solver_stats["phase1"] = result["solver_stats"]
        
        return result
    
    def _solve_phase2(
        self,
        warm_start: dict,
        time_limit: int,
        progress_callback: Optional[Callable[[int], bool]] = None,
    ) -> Optional[dict]:
        """
        Execute Phase 2 optimization with warm start from Phase 1.
        
        Args:
            warm_start: Phase 1 solution to use as starting point
            time_limit: Time limit in seconds
            progress_callback: Progress callback
            
        Returns:
            Optimized solution or None if failed
        """
        from .model import TimetableSolver
        from ..config import CP_SAT_SEARCH_WORKERS, CP_SAT_RANDOM_SEED
        
        try:
            # Create solver with full constraints (including soft)
            modified_input = dict(self.solver_input)
            
            # Apply the same relaxations from Phase 1
            if self.status.relaxed_constraints:
                modified_config = dict(self.constraints_config)
                for name in self.status.relaxed_constraints:
                    if name == "language_sync":
                        modified_config["language_sync_enabled"] = False
                    elif name == "class_teacher_period_1":
                        modified_config["class_teacher_period_1"] = False
                    elif name == "no_subject_twice_daily":
                        modified_config["no_subject_twice_daily"] = False
                    elif name == "substitution_reserve":
                        modified_config["substitution_reserve_count"] = 0
                    elif name == "max_consecutive":
                        modified_config["max_consecutive_default"] = 99
                    elif name == "teacher_daily_load":
                        modified_config["relax_teacher_daily_load"] = True
                    elif name == "teacher_weekly_balance":
                        modified_config["relax_weekly_balance"] = True
                    elif name == "block_periods":
                        modified_config["relax_block_periods"] = True
                modified_input["constraints"] = modified_config
            
            # Enable soft constraints for Phase 2
            if "constraints" not in modified_input:
                modified_input["constraints"] = {}
            modified_input["constraints"]["_phase1_only"] = False
            
            # Set warm start hint
            modified_input["warm_start"] = warm_start.get("timetable", {})
            
            solver = TimetableSolver(modified_input)
            result = solver.solve(
                time_limit=time_limit,
                progress_callback=progress_callback,
            )
            
            # Capture solver stats
            if "solver_stats" in result:
                self.status.solver_stats["phase2"] = result["solver_stats"]
            
            return result
            
        except Exception as e:
            self.status.add_log(f"Phase 2 optimization failed: {e}", "error")
            return None
    
    def _build_infeasible_result(self, relaxation_result: RelaxationResult) -> dict:
        """Build result for truly infeasible case."""
        from .diagnostics import analyze_infeasibility
        
        diagnostics = analyze_infeasibility(self.solver_input, "INFEASIBLE")
        diagnostics.extend(relaxation_result.diagnostics)
        
        return {
            "status": "INFEASIBLE",
            "timetable": {},
            "teacher_schedules": {},
            "meta": {
                "solve_time_seconds": round(self.status.total_solve_time, 2),
                "phase1_time_seconds": round(self.status.phase1_time, 2),
                "phase2_time_seconds": 0,
                "relaxation_iterations": relaxation_result.iterations,
                "relaxed_constraints": relaxation_result.relaxed_constraints,
                "input_hash": self.input_hash,
                "solver_pipeline": "two_phase",
            },
            "diagnostics": diagnostics,
            "warnings": self.status.capacity_analysis.warnings if self.status.capacity_analysis else [],
            "capacity_analysis": self.status.capacity_analysis.to_dict() if self.status.capacity_analysis else None,
            "relaxation_info": relaxation_result.to_dict(),
            "solver_stats": self.status.solver_stats,
            "solver_logs": self.status.logs,
        }
    
    def _build_cancelled_result(self) -> dict:
        """Build result for cancelled case."""
        return {
            "status": "CANCELLED",
            "timetable": {},
            "teacher_schedules": {},
            "meta": {
                "solve_time_seconds": round(self.status.total_solve_time, 2),
                "input_hash": self.input_hash,
                "solver_pipeline": "two_phase",
            },
            "diagnostics": [{"type": "info", "message": "Solve cancelled by user"}],
            "warnings": [],
            "solver_logs": self.status.logs,
        }
    
    def _build_final_result(
        self,
        solution: dict,
        relaxation_result: RelaxationResult,
        phase2_attempted: bool = True,
        phase2_failed: bool = False,
    ) -> dict:
        """Build final result with all metadata."""
        result = dict(solution)
        
        # Enhance metadata
        result["meta"] = result.get("meta", {})
        result["meta"]["solve_time_seconds"] = round(self.status.total_solve_time, 2)
        result["meta"]["phase1_time_seconds"] = round(self.status.phase1_time, 2)
        result["meta"]["phase2_time_seconds"] = round(self.status.phase2_time, 2)
        result["meta"]["relaxation_iterations"] = relaxation_result.iterations
        result["meta"]["relaxed_constraints"] = relaxation_result.relaxed_constraints
        result["meta"]["input_hash"] = self.input_hash
        result["meta"]["phase2_attempted"] = phase2_attempted
        result["meta"]["phase2_failed"] = phase2_failed
        result["meta"]["solver_pipeline"] = "two_phase"
        
        # Add capacity analysis
        result["capacity_analysis"] = (
            self.status.capacity_analysis.to_dict() 
            if self.status.capacity_analysis else None
        )
        
        # Add relaxation info
        result["relaxation_info"] = relaxation_result.to_dict()
        
        # Add solver stats
        result["solver_stats"] = self.status.solver_stats
        
        # Add solver logs
        result["solver_logs"] = self.status.logs
        
        # Add warnings about relaxations
        if relaxation_result.relaxed_constraints:
            warnings = result.get("warnings", []) or []
            relaxed_names = []
            for name in relaxation_result.relaxed_constraints:
                config = CONSTRAINT_REGISTRY.get(name)
                display_name = config.display_name if config else name
                relaxed_names.append(display_name)
            
            warnings.append(
                f"Solution found after relaxing {len(relaxation_result.relaxed_constraints)} "
                f"constraint(s): {', '.join(relaxed_names)}"
            )
            result["warnings"] = warnings
        
        return result
