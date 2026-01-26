"""
Solver module for the Timetable Generator Backend.

Contains the CP-SAT model builder, constraints, and preprocessing utilities.
"""

from .model import TimetableSolver
from .preprocess import (
    generate_period_grid,
    build_teacher_capability_matrix,
    build_availability_mask,
    validate_feasibility,
)
from .constraints import (
    add_all_hard_constraints,
    add_all_soft_constraints,
)
from .diagnostics import (
    analyze_infeasibility,
    detect_overloaded_teachers,
    detect_resource_bottlenecks,
    suggest_relaxations,
)

__all__ = [
    "TimetableSolver",
    "generate_period_grid",
    "build_teacher_capability_matrix",
    "build_availability_mask",
    "validate_feasibility",
    "add_all_hard_constraints",
    "add_all_soft_constraints",
    "analyze_infeasibility",
    "detect_overloaded_teachers",
    "detect_resource_bottlenecks",
    "suggest_relaxations",
]
