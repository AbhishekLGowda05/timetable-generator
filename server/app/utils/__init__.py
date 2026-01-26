"""
Utility modules for the Timetable Generator Backend.
"""

from .path_helper import (
    resolve_data_path,
    ensure_dir_exists,
    get_schema_path,
    get_all_schema_paths,
)

from .validators import (
    validate_solver_input,
    validate_solver_output,
    validate_school,
    validate_teacher,
    validate_class,
    validate_subject,
    validate_resource,
    validate_constraints,
    ValidationError,
)

__all__ = [
    "resolve_data_path",
    "ensure_dir_exists",
    "get_schema_path",
    "get_all_schema_paths",
    "validate_solver_input",
    "validate_solver_output",
    "validate_school",
    "validate_teacher",
    "validate_class",
    "validate_subject",
    "validate_resource",
    "validate_constraints",
    "ValidationError",
]
