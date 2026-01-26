"""
Constraint Type Classification for the Timetable Solver.

This module defines a tiered constraint classification system that enables:
1. Two-phase solving (feasibility first, then optimization)
2. Automatic relaxation when infeasibility is detected
3. Clear separation of mathematically essential vs preference constraints

Constraint Tiers:
- HARD_CORE: Mathematically essential, cannot be relaxed (e.g., no teacher double-booking)
- HARD_RELAXABLE: Important but can be relaxed in priority order to find feasibility
- SOFT: Preferences that are optimized but never cause infeasibility

Design Philosophy:
- If a feasible solution exists mathematically, the solver MUST find it
- HARD_CORE constraints define "what makes a timetable valid"
- HARD_RELAXABLE constraints define "what makes a timetable good" but can be relaxed
- SOFT constraints define "what makes a timetable optimal"
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List


class ConstraintType(Enum):
    """
    Three-tier constraint classification.
    
    HARD_CORE: Cannot be violated under any circumstances.
        - Teacher cannot be in two places at once
        - Class cannot have two subjects simultaneously
        - Subject weekly minimums must be met
        - Resource capacity limits
        
    HARD_RELAXABLE: Important constraints that can be relaxed to find feasibility.
        - Ordered by priority (lower = relax first)
        - Each constraint has a relaxation cost/priority
        - System attempts solve without relaxation first
        
    SOFT: Optimization preferences that never block feasibility.
        - Implemented via penalty variables in objective function
        - Violation increases cost but doesn't cause infeasibility
    """
    HARD_CORE = auto()
    HARD_RELAXABLE = auto()
    SOFT = auto()


@dataclass
class ConstraintConfig:
    """
    Configuration for a single constraint.
    
    Attributes:
        name: Unique identifier for the constraint
        display_name: Human-readable name
        constraint_type: Classification (HARD_CORE, HARD_RELAXABLE, SOFT)
        default_enabled: Whether constraint is enabled by default
        relaxation_priority: For HARD_RELAXABLE, order of relaxation (lower = relax first)
        soft_weight: For SOFT constraints, weight in objective function
        description: Human-readable description of what the constraint does
        config_key: Key in constraints_config dict to check enabled state
    """
    name: str
    display_name: str
    constraint_type: ConstraintType
    default_enabled: bool = True
    relaxation_priority: int = 0  # Lower = relax first
    soft_weight: int = 1
    description: str = ""
    config_key: Optional[str] = None
    
    def is_enabled(self, constraints_config: dict) -> bool:
        """Check if this constraint is enabled based on config."""
        if self.config_key is None:
            return self.default_enabled
        return constraints_config.get(self.config_key, self.default_enabled)


# =============================================================================
# CONSTRAINT REGISTRY
# =============================================================================

# HARD_CORE Constraints - Never relaxed, mathematically essential
HARD_CORE_CONSTRAINTS = [
    ConstraintConfig(
        name="teacher_single_assignment",
        display_name="Teacher No Double-Booking",
        constraint_type=ConstraintType.HARD_CORE,
        default_enabled=True,
        description="A teacher cannot teach two classes at the same time",
    ),
    ConstraintConfig(
        name="section_single_subject",
        display_name="Class Single Subject per Period",
        constraint_type=ConstraintType.HARD_CORE,
        default_enabled=True,
        description="A class can only have one subject per period",
    ),
    ConstraintConfig(
        name="subject_frequency",
        display_name="Subject Weekly Requirements",
        constraint_type=ConstraintType.HARD_CORE,
        default_enabled=True,
        description="Subjects must receive their minimum weekly periods",
    ),
    ConstraintConfig(
        name="teacher_availability",
        display_name="Teacher Availability",
        constraint_type=ConstraintType.HARD_CORE,
        default_enabled=True,
        description="Teachers can only be assigned when available",
    ),
    ConstraintConfig(
        name="resource_capacity",
        display_name="Resource Capacity",
        constraint_type=ConstraintType.HARD_CORE,
        default_enabled=True,
        description="Resources cannot exceed simultaneous capacity",
    ),
]

# HARD_RELAXABLE Constraints - Can be relaxed in priority order
# Priority: lower number = relax first
HARD_RELAXABLE_CONSTRAINTS = [
    ConstraintConfig(
        name="language_sync",
        display_name="Language Block Synchronization",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=False,  # Off by default to avoid infeasibility
        relaxation_priority=1,  # Relax first
        config_key="language_sync_enabled",
        description="Language teachers teaching same sections should be synchronized",
    ),
    ConstraintConfig(
        name="class_teacher_period_1",
        display_name="Class Teacher in Period 1",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=False,  # Off by default
        relaxation_priority=2,
        config_key="class_teacher_period_1",
        description="Class teacher must teach their class in Period 1",
    ),
    ConstraintConfig(
        name="no_subject_twice_daily",
        display_name="No Subject Twice Daily",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=False,  # Off by default
        relaxation_priority=3,
        config_key="no_subject_twice_daily",
        description="A subject should not appear twice in the same day (except blocks)",
    ),
    ConstraintConfig(
        name="substitution_reserve",
        display_name="Substitution Reserve",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=False,  # Only enable if explicitly set
        relaxation_priority=4,
        config_key="substitution_reserve_count",
        description="Keep N teachers free each period for substitution",
    ),
    ConstraintConfig(
        name="max_consecutive",
        display_name="Max Consecutive Periods",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=True,
        relaxation_priority=5,
        description="Teachers cannot exceed max consecutive periods",
    ),
    ConstraintConfig(
        name="teacher_daily_load",
        display_name="Teacher Daily Load Limits",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=True,
        relaxation_priority=6,
        description="Teachers must stay within daily min/max periods",
    ),
    ConstraintConfig(
        name="teacher_weekly_balance",
        display_name="Teacher Weekly Load Balance",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=True,
        relaxation_priority=7,
        description="Teacher's daily loads should be balanced (not 7 one day, 2 next)",
    ),
    ConstraintConfig(
        name="block_periods",
        display_name="Block Period Integrity",
        constraint_type=ConstraintType.HARD_RELAXABLE,
        default_enabled=True,
        relaxation_priority=8,  # Relax late, important for labs
        description="Subjects requiring blocks must get consecutive periods",
    ),
]

# SOFT Constraints - Preferences, never cause infeasibility
SOFT_CONSTRAINTS = [
    ConstraintConfig(
        name="core_morning",
        display_name="Core Subjects in Morning",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=3,
        config_key="core_morning_only",
        description="Prefer core subjects (Math, Science, etc.) in morning periods",
    ),
    ConstraintConfig(
        name="teacher_balance",
        display_name="Teacher Load Balance",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=10,
        description="Minimize variance in teacher daily loads",
    ),
    ConstraintConfig(
        name="minimize_gaps",
        display_name="Minimize Schedule Gaps",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=5,
        description="Minimize idle gaps in teacher schedules",
    ),
    ConstraintConfig(
        name="leisure_afternoon",
        display_name="Leisure in Afternoon",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=2,
        description="Prefer leisure subjects (PE, Art) in afternoon",
    ),
    ConstraintConfig(
        name="avoid_pe_period_1",
        display_name="Avoid PE in Period 1",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=4,
        description="Avoid scheduling PE in the first period",
    ),
    ConstraintConfig(
        name="subject_distribution",
        display_name="Subject Distribution",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=3,
        description="Distribute subjects evenly across the week",
    ),
    ConstraintConfig(
        name="teacher_free_period",
        display_name="Teacher Free Period Preference",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=2,
        description="Teachers should have some free periods for prep",
    ),
    ConstraintConfig(
        name="fair_slot_distribution",
        display_name="Fair Undesirable Slot Distribution",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=5,
        description="Distribute undesirable slots (last period, Saturday) fairly",
    ),
    ConstraintConfig(
        name="specialist_priority",
        display_name="Specialist Teacher Priority",
        constraint_type=ConstraintType.SOFT,
        default_enabled=True,
        soft_weight=8,
        description="Prioritize specialist teachers for their primary subjects",
    ),
]


# Combined registry for easy lookup
CONSTRAINT_REGISTRY = {
    c.name: c for c in HARD_CORE_CONSTRAINTS + HARD_RELAXABLE_CONSTRAINTS + SOFT_CONSTRAINTS
}


def get_constraint_config(name: str) -> Optional[ConstraintConfig]:
    """Get constraint configuration by name."""
    return CONSTRAINT_REGISTRY.get(name)


def get_constraints_by_type(constraint_type: ConstraintType) -> list[ConstraintConfig]:
    """Get all constraints of a specific type."""
    return [c for c in CONSTRAINT_REGISTRY.values() if c.constraint_type == constraint_type]


def get_relaxation_order() -> list[ConstraintConfig]:
    """
    Get HARD_RELAXABLE constraints in relaxation order (lowest priority first).
    
    Returns:
        List of constraints ordered by relaxation priority (ascending)
    """
    relaxable = get_constraints_by_type(ConstraintType.HARD_RELAXABLE)
    return sorted(relaxable, key=lambda c: c.relaxation_priority)


def get_enabled_relaxable_constraints(constraints_config: dict) -> list[ConstraintConfig]:
    """
    Get enabled HARD_RELAXABLE constraints in relaxation order.
    
    Args:
        constraints_config: The constraints configuration dict
        
    Returns:
        List of enabled constraints ordered by relaxation priority
    """
    relaxable = get_relaxation_order()
    return [c for c in relaxable if c.is_enabled(constraints_config)]


def get_soft_weights(constraints_config: dict) -> dict[str, int]:
    """
    Get soft constraint weights from config with defaults.
    
    Args:
        constraints_config: The constraints configuration dict
        
    Returns:
        Dictionary mapping constraint name to weight
    """
    config_weights = constraints_config.get("soft_weights", {})
    weights = {}
    
    for constraint in SOFT_CONSTRAINTS:
        # Use config weight if provided, otherwise default
        weights[constraint.name] = config_weights.get(constraint.name, constraint.soft_weight)
    
    return weights


# =============================================================================
# PHASE CONFIGURATION
# =============================================================================

class SolvePhase(Enum):
    """
    Solving phase for the two-phase approach.
    
    FEASIBILITY: Phase 1 - Find ANY valid timetable using only HARD_CORE constraints
    OPTIMIZATION: Phase 2 - Improve solution using SOFT constraints with warm start
    """
    FEASIBILITY = "feasibility"
    OPTIMIZATION = "optimization"


@dataclass
class PhaseConfig:
    """
    Configuration for a solving phase.
    
    Attributes:
        phase: The phase type
        include_hard_core: Always True - core constraints always included
        include_hard_relaxable: Whether to include relaxable constraints
        include_soft: Whether to include soft constraints
        relaxed_constraints: List of constraint names that have been relaxed
        time_limit_fraction: Fraction of total time to allocate (0.0-1.0)
    """
    phase: SolvePhase
    include_hard_core: bool = True
    include_hard_relaxable: bool = True
    include_soft: bool = True
    relaxed_constraints: list[str] = None
    time_limit_fraction: float = 1.0
    
    def __post_init__(self):
        if self.relaxed_constraints is None:
            self.relaxed_constraints = []


def get_feasibility_phase_config(relaxed: list[str] = None) -> PhaseConfig:
    """
    Get configuration for Phase 1 (feasibility) solving.
    
    In Phase 1, we:
    - Include all HARD_CORE constraints (always)
    - Include HARD_RELAXABLE constraints (minus any relaxed)
    - Exclude SOFT constraints (no optimization)
    - Goal: find ANY valid timetable
    
    Args:
        relaxed: List of constraint names to exclude (already relaxed)
        
    Returns:
        PhaseConfig for feasibility solving
    """
    return PhaseConfig(
        phase=SolvePhase.FEASIBILITY,
        include_hard_core=True,
        include_hard_relaxable=True,
        include_soft=False,
        relaxed_constraints=relaxed or [],
        time_limit_fraction=0.3,  # 30% of time for feasibility
    )


def get_optimization_phase_config() -> PhaseConfig:
    """
    Get configuration for Phase 2 (optimization) solving.
    
    In Phase 2, we:
    - Include all constraints
    - Use Phase 1 solution as warm start
    - Optimize soft constraint penalties
    - Goal: improve the feasible solution
    
    Returns:
        PhaseConfig for optimization solving
    """
    return PhaseConfig(
        phase=SolvePhase.OPTIMIZATION,
        include_hard_core=True,
        include_hard_relaxable=True,
        include_soft=True,
        relaxed_constraints=[],
        time_limit_fraction=0.7,  # 70% of time for optimization
    )


# =============================================================================
# RELAXATION RESULT
# =============================================================================

@dataclass
class RelaxationResult:
    """
    Result of the automatic relaxation process.
    
    Attributes:
        success: Whether a feasible solution was found
        relaxed_constraints: List of constraints that were relaxed
        iterations: Number of relaxation iterations tried
        final_status: Final solver status
        solution: The solution (if found)
        diagnostics: Diagnostic messages
    """
    success: bool
    relaxed_constraints: list[str]
    iterations: int
    final_status: str
    solution: Optional[dict] = None
    diagnostics: list[dict] = None
    
    def __post_init__(self):
        if self.diagnostics is None:
            self.diagnostics = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "relaxed_constraints": self.relaxed_constraints,
            "relaxed_count": len(self.relaxed_constraints),
            "iterations": self.iterations,
            "final_status": self.final_status,
            "diagnostics": self.diagnostics,
            "relaxation_details": [
                {
                    "name": name,
                    "display_name": CONSTRAINT_REGISTRY[name].display_name 
                        if name in CONSTRAINT_REGISTRY else name,
                    "description": CONSTRAINT_REGISTRY[name].description 
                        if name in CONSTRAINT_REGISTRY else "",
                }
                for name in self.relaxed_constraints
            ]
        }
