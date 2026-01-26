"""
Schema validation utilities using JSON Schema.

Provides runtime validation against the JSON schemas defined in shared/schemas/.
"""

import json
import logging

import jsonschema
from jsonschema import Draft7Validator, RefResolver

from ..config import SCHEMAS_DIR

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


# Cache for loaded schemas
_schema_cache: dict[str, dict] = {}


def _load_schema(schema_name: str) -> dict:
    """
    Load and cache a JSON schema.
    
    Args:
        schema_name: Name of the schema (e.g., 'school', 'teacher')
    
    Returns:
        The loaded schema as a dictionary
    """
    if schema_name in _schema_cache:
        return _schema_cache[schema_name]
    
    # Build schema filename
    if not schema_name.endswith(".schema.json"):
        schema_file = f"{schema_name}.schema.json"
    else:
        schema_file = schema_name
    
    schema_path = SCHEMAS_DIR / schema_file
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    
    _schema_cache[schema_name] = schema
    return schema


def _get_resolver() -> RefResolver:
    """
    Create a JSON Schema resolver that can resolve $ref references.
    """
    # Load all schemas into a store for reference resolution
    schema_store = {}
    
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        with open(schema_file, "r", encoding="utf-8") as f:
            schema = json.load(f)
            schema_id = schema.get("$id", schema_file.name)
            schema_store[schema_id] = schema
    
    # Use solver_input as the base schema for resolution
    base_uri = f"file://{SCHEMAS_DIR}/"
    return RefResolver(base_uri, {}, store=schema_store)


def _format_validation_error(error: jsonschema.ValidationError) -> str:
    """
    Format a validation error into a human-readable message.
    """
    path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
    return f"Field '{path}': {error.message}"


def _validate_against_schema(data: dict, schema_name: str) -> tuple[bool, list[str]]:
    """
    Validate data against a named schema.
    
    Args:
        data: Dictionary to validate
        schema_name: Name of the schema to validate against
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    try:
        schema = _load_schema(schema_name)
        resolver = _get_resolver()
        
        validator = Draft7Validator(schema, resolver=resolver)
        errors = list(validator.iter_errors(data))
        
        if errors:
            error_messages = [_format_validation_error(e) for e in errors]
            return False, error_messages
        
        return True, []
    
    except FileNotFoundError as e:
        return False, [str(e)]
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON in schema: {e}"]
    except Exception as e:
        logger.exception("Unexpected error during validation")
        return False, [f"Validation error: {str(e)}"]


def validate_solver_input(data: dict) -> tuple[bool, list[str]]:
    """
    Validate complete solver input data.
    
    Args:
        data: Solver input dictionary
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Validate overall structure
    is_valid, schema_errors = _validate_against_schema(data, "solver_input")
    if not is_valid:
        errors.extend(schema_errors)
    
    # Additional business logic validation
    if is_valid:
        business_errors = _validate_solver_input_business_rules(data)
        errors.extend(business_errors)
    
    return len(errors) == 0, errors


def _validate_solver_input_business_rules(data: dict) -> list[str]:
    """
    Validate business rules that can't be expressed in JSON Schema.
    """
    errors = []
    
    # Build lookup maps
    teacher_ids = {t["teacher_id"] for t in data.get("teachers", [])}
    subject_ids = {s["subject_id"] for s in data.get("subjects", [])}
    section_ids = {c["section_id"] for c in data.get("classes", [])}
    resource_types = {r["resource_type"] for r in data.get("resources", [])}
    
    # Validate class references
    for cls in data.get("classes", []):
        # Check class teacher exists
        if cls.get("class_teacher_id") and cls["class_teacher_id"] not in teacher_ids:
            errors.append(
                f"Section '{cls['section_id']}': class_teacher_id '{cls['class_teacher_id']}' not found in teachers"
            )
        
        # Check subject-teacher map references
        for subject_id, teacher_id in cls.get("subject_teacher_map", {}).items():
            if subject_id not in subject_ids:
                errors.append(
                    f"Section '{cls['section_id']}': subject '{subject_id}' not found in subjects"
                )
            if teacher_id not in teacher_ids:
                errors.append(
                    f"Section '{cls['section_id']}': teacher '{teacher_id}' not found in teachers"
                )
        
        # Check language teachers exist
        for teacher_id in cls.get("language_teachers", []):
            if teacher_id not in teacher_ids:
                errors.append(
                    f"Section '{cls['section_id']}': language teacher '{teacher_id}' not found in teachers"
                )
    
    # Validate teacher references
    for teacher in data.get("teachers", []):
        # Check subjects can teach exist
        for subject_id in teacher.get("subjects_can_teach", []):
            if subject_id not in subject_ids:
                errors.append(
                    f"Teacher '{teacher['teacher_id']}': subject '{subject_id}' not found in subjects"
                )
        
        # Check class teacher assignment
        if teacher.get("is_class_teacher_of"):
            if teacher["is_class_teacher_of"] not in section_ids:
                errors.append(
                    f"Teacher '{teacher['teacher_id']}': is_class_teacher_of '{teacher['is_class_teacher_of']}' not found in classes"
                )
    
    # Validate subject resource references
    for subject in data.get("subjects", []):
        if subject.get("requires_resource") and subject.get("resource_type"):
            if subject["resource_type"] not in resource_types and data.get("resources"):
                errors.append(
                    f"Subject '{subject['subject_id']}': resource_type '{subject['resource_type']}' not found in resources"
                )
    
    # Validate min/max consistency
    for subject in data.get("subjects", []):
        if subject["min_per_week"] > subject["max_per_week"]:
            errors.append(
                f"Subject '{subject['subject_id']}': min_per_week ({subject['min_per_week']}) > max_per_week ({subject['max_per_week']})"
            )
    
    for teacher in data.get("teachers", []):
        if teacher["min_periods_day"] > teacher["max_periods_day"]:
            errors.append(
                f"Teacher '{teacher['teacher_id']}': min_periods_day ({teacher['min_periods_day']}) > max_periods_day ({teacher['max_periods_day']})"
            )
        if teacher.get("min_periods_week", 0) > teacher.get("max_periods_week", 40):
            errors.append(
                f"Teacher '{teacher['teacher_id']}': min_periods_week > max_periods_week"
            )
    
    return errors


def validate_solver_output(data: dict) -> tuple[bool, list[str]]:
    """
    Validate solver output data.
    
    Args:
        data: Solver output dictionary
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    return _validate_against_schema(data, "solver_output")


def validate_school(data: dict) -> tuple[bool, list[str]]:
    """Validate school configuration data."""
    return _validate_against_schema(data, "school")


def validate_teacher(data: dict) -> tuple[bool, list[str]]:
    """Validate teacher data."""
    return _validate_against_schema(data, "teacher")


def validate_class(data: dict) -> tuple[bool, list[str]]:
    """Validate class/section data."""
    return _validate_against_schema(data, "class")


def validate_subject(data: dict) -> tuple[bool, list[str]]:
    """Validate subject data."""
    return _validate_against_schema(data, "subject")


def validate_resource(data: dict) -> tuple[bool, list[str]]:
    """Validate resource data."""
    return _validate_against_schema(data, "resource")


def validate_constraints(data: dict) -> tuple[bool, list[str]]:
    """Validate constraints configuration."""
    return _validate_against_schema(data, "constraints")


def get_validator(data_type: str):
    """
    Get the appropriate validator function for a data type.
    
    Args:
        data_type: Type of data ('teachers', 'classes', 'subjects', 'resources')
    
    Returns:
        Validator function
    """
    validators = {
        "teachers": validate_teacher,
        "teacher": validate_teacher,
        "classes": validate_class,
        "class": validate_class,
        "subjects": validate_subject,
        "subject": validate_subject,
        "resources": validate_resource,
        "resource": validate_resource,
        "school": validate_school,
        "constraints": validate_constraints,
    }
    
    return validators.get(data_type, lambda x: (True, []))


def validate_list(data_list: list[dict], data_type: str) -> tuple[bool, list[str]]:
    """
    Validate a list of items against their schema.
    
    Args:
        data_list: List of items to validate
        data_type: Type of items in the list
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    validator = get_validator(data_type)
    all_errors = []
    
    for i, item in enumerate(data_list):
        is_valid, errors = validator(item)
        if not is_valid:
            for error in errors:
                all_errors.append(f"Item {i}: {error}")
    
    return len(all_errors) == 0, all_errors
