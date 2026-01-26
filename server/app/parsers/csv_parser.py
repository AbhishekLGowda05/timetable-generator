"""
CSV parser for timetable data files.

Handles parsing of:
- Teachers CSV
- Classes CSV
- Subjects CSV
- Resources CSV

Each parser transforms raw CSV data into JSON-schema compliant dictionaries.
"""

import csv
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def parse_csv(file_path: Union[str, Path], data_type: str) -> list[dict]:
    """
    Parse a CSV file based on its data type.
    
    Args:
        file_path: Path to the CSV file
        data_type: Type of data ('teachers', 'classes', 'subjects', 'resources')
    
    Returns:
        List of parsed dictionaries
    
    Raises:
        ValueError: If data_type is not recognized
    """
    parsers = {
        "teachers": parse_teachers_csv,
        "teacher": parse_teachers_csv,
        "classes": parse_classes_csv,
        "class": parse_classes_csv,
        "subjects": parse_subjects_csv,
        "subject": parse_subjects_csv,
        "resources": parse_resources_csv,
        "resource": parse_resources_csv,
    }
    
    parser = parsers.get(data_type.lower())
    if not parser:
        raise ValueError(f"Unknown data type: {data_type}. Supported: {list(parsers.keys())}")
    
    return parser(Path(file_path))


def parse_teachers_csv(file_path: Path) -> list[dict]:
    """
    Parse teachers.csv into list of teacher objects.
    
    Expected CSV format:
    teacher_id,name,subjects,min_day,max_day,max_consecutive,min_week,max_week,class_teacher_of
    T001,Priya Sharma,"MATH;PHYSICS",2,6,3,10,30,8A
    
    Args:
        file_path: Path to the CSV file
    
    Returns:
        List of teacher dictionaries matching teacher.schema.json
    """
    teachers = []
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            teacher = {
                "teacher_id": row.get("teacher_id", "").strip(),
                "name": row.get("name", "").strip(),
                "subjects_can_teach": _parse_list(row.get("subjects", "")),
                "min_periods_day": _parse_int(row.get("min_day"), 0),
                "max_periods_day": _parse_int(row.get("max_day"), 8),
            }
            
            # Optional fields
            if row.get("max_consecutive"):
                teacher["max_consecutive_periods"] = _parse_int(row.get("max_consecutive"), 3)
            
            if row.get("min_week"):
                teacher["min_periods_week"] = _parse_int(row.get("min_week"), 0)
            
            if row.get("max_week"):
                teacher["max_periods_week"] = _parse_int(row.get("max_week"), 40)
            
            if row.get("class_teacher_of"):
                teacher["is_class_teacher_of"] = row.get("class_teacher_of").strip()
            
            if row.get("sections"):
                teacher["sections_assigned"] = _parse_list(row.get("sections", ""))
            
            # Parse availability if columns exist
            availability = _parse_teacher_availability(row)
            if availability:
                teacher["availability"] = availability
            
            # Validate required fields
            if teacher["teacher_id"] and teacher["name"]:
                teachers.append(teacher)
            else:
                logger.warning(f"Skipping invalid teacher row: {row}")
    
    logger.info(f"Parsed {len(teachers)} teachers from {file_path}")
    return teachers


def parse_classes_csv(file_path: Path) -> list[dict]:
    """
    Parse classes.csv into list of class/section objects.
    
    Expected CSV format:
    section_id,grade,section_name,class_teacher_id,subjects
    8A,8,A,T001,"MATH:T001;PHYSICS:T002;KANNADA:T003"
    
    Args:
        file_path: Path to the CSV file
    
    Returns:
        List of class dictionaries matching class.schema.json
    """
    classes = []
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            cls = {
                "section_id": row.get("section_id", "").strip(),
                "grade": _parse_int(row.get("grade"), 1),
                "subject_teacher_map": _parse_subject_teacher_map(row.get("subjects", "")),
            }
            
            # Optional fields
            if row.get("section_name"):
                cls["section_name"] = row.get("section_name").strip()
            
            if row.get("class_teacher_id"):
                cls["class_teacher_id"] = row.get("class_teacher_id").strip()
            
            if row.get("language_block"):
                cls["language_block_enabled"] = _parse_bool(row.get("language_block"))
            
            if row.get("language_subjects"):
                cls["language_subjects"] = _parse_list(row.get("language_subjects", ""))
            
            if row.get("language_teachers"):
                cls["language_teachers"] = _parse_list(row.get("language_teachers", ""))
            
            # Validate required fields
            if cls["section_id"] and cls["subject_teacher_map"]:
                classes.append(cls)
            else:
                logger.warning(f"Skipping invalid class row: {row}")
    
    logger.info(f"Parsed {len(classes)} classes from {file_path}")
    return classes


def parse_subjects_csv(file_path: Path) -> list[dict]:
    """
    Parse subjects.csv into list of subject objects.
    
    Expected CSV format:
    subject_id,name,category,min_week,max_week,requires_block,block_length,resource_type
    MATH,Mathematics,core,6,7,false,0,
    PHYSICS_LAB,Physics Lab,lab,2,2,true,2,Physics Lab
    
    Args:
        file_path: Path to the CSV file
    
    Returns:
        List of subject dictionaries matching subject.schema.json
    """
    subjects = []
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            subject = {
                "subject_id": row.get("subject_id", "").strip(),
                "name": row.get("name", "").strip(),
                "category": _normalize_category(row.get("category", "core")),
                "min_per_week": _parse_int(row.get("min_week"), 1),
                "max_per_week": _parse_int(row.get("max_week"), 10),
            }
            
            # Block period settings
            requires_block = _parse_bool(row.get("requires_block"))
            if requires_block:
                subject["requires_block"] = True
                subject["block_length"] = _parse_int(row.get("block_length"), 2)
            
            # Resource settings
            if row.get("resource_type") and row.get("resource_type").strip():
                subject["requires_resource"] = True
                subject["resource_type"] = row.get("resource_type").strip()
            
            # Scheduling preferences
            if row.get("prefer_morning"):
                subject["prefer_morning"] = _parse_bool(row.get("prefer_morning"))
            
            if row.get("avoid_after_lunch"):
                subject["avoid_after_lunch"] = _parse_bool(row.get("avoid_after_lunch"))
            
            # Validate required fields
            if subject["subject_id"] and subject["name"]:
                subjects.append(subject)
            else:
                logger.warning(f"Skipping invalid subject row: {row}")
    
    logger.info(f"Parsed {len(subjects)} subjects from {file_path}")
    return subjects


def parse_resources_csv(file_path: Path) -> list[dict]:
    """
    Parse resources.csv into list of resource objects.
    
    Expected CSV format:
    resource_id,resource_type,name,capacity
    RES001,Computer Lab,Main Computer Lab,2
    
    Args:
        file_path: Path to the CSV file
    
    Returns:
        List of resource dictionaries matching resource.schema.json
    """
    resources = []
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            resource = {
                "resource_id": row.get("resource_id", "").strip(),
                "resource_type": row.get("resource_type", "").strip(),
                "max_simultaneous_capacity": _parse_int(row.get("capacity"), 1),
            }
            
            # Optional fields
            if row.get("name"):
                resource["name"] = row.get("name").strip()
            
            # Validate required fields
            if resource["resource_id"] and resource["resource_type"]:
                resources.append(resource)
            else:
                logger.warning(f"Skipping invalid resource row: {row}")
    
    logger.info(f"Parsed {len(resources)} resources from {file_path}")
    return resources


# =============================================================================
# Helper Functions
# =============================================================================

def _parse_list(value: str, delimiter: str = ";") -> list[str]:
    """
    Parse a delimited string into a list.
    
    Args:
        value: String value to parse
        delimiter: Delimiter character
    
    Returns:
        List of trimmed strings
    """
    if not value or not value.strip():
        return []
    
    return [item.strip() for item in value.split(delimiter) if item.strip()]


def _parse_subject_teacher_map(value: str) -> dict[str, str]:
    """
    Parse subject:teacher mappings from a string.
    
    Format: "SUBJECT1:TEACHER1;SUBJECT2:TEACHER2"
    
    Args:
        value: String with subject:teacher mappings
    
    Returns:
        Dictionary mapping subject_id to teacher_id
    """
    result = {}
    
    if not value or not value.strip():
        return result
    
    pairs = value.split(";")
    for pair in pairs:
        pair = pair.strip()
        if ":" in pair:
            parts = pair.split(":", 1)
            subject_id = parts[0].strip()
            teacher_id = parts[1].strip()
            if subject_id and teacher_id:
                result[subject_id] = teacher_id
    
    return result


def _parse_int(value: str, default: int = 0) -> int:
    """
    Parse an integer from a string.
    
    Args:
        value: String value to parse
        default: Default value if parsing fails
    
    Returns:
        Parsed integer or default
    """
    if not value:
        return default
    
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def _parse_bool(value: str) -> bool:
    """
    Parse a boolean from a string.
    
    Args:
        value: String value to parse
    
    Returns:
        Boolean value
    """
    if not value:
        return False
    
    return str(value).strip().lower() in ("true", "yes", "1", "on")


def _normalize_category(value: str) -> str:
    """
    Normalize subject category to valid enum value.
    
    Args:
        value: Raw category string
    
    Returns:
        Normalized category (core, language, leisure, or lab)
    """
    value = str(value).strip().lower()
    
    valid_categories = {"core", "language", "leisure", "lab"}
    
    if value in valid_categories:
        return value
    
    # Map common alternatives
    category_map = {
        "main": "core",
        "primary": "core",
        "lang": "language",
        "foreign": "language",
        "fun": "leisure",
        "extracurricular": "leisure",
        "sports": "leisure",
        "pe": "leisure",
        "practical": "lab",
        "laboratory": "lab",
    }
    
    return category_map.get(value, "core")


def _parse_teacher_availability(row: dict) -> dict:
    """
    Parse teacher availability from CSV columns.
    
    Expected columns: available_mon, available_tue, etc.
    Or: blocked_mon, blocked_tue, etc.
    
    Args:
        row: CSV row dictionary
    
    Returns:
        Availability dictionary or empty dict
    """
    availability = {}
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    
    for day in days:
        day_lower = day.lower()
        
        # Check for available_xxx columns
        if f"available_{day_lower}" in row:
            is_available = _parse_bool(row.get(f"available_{day_lower}"))
            availability[day] = {"available": is_available}
        
        # Check for blocked_xxx columns (period numbers)
        if f"blocked_{day_lower}" in row:
            blocked_str = row.get(f"blocked_{day_lower}", "")
            if blocked_str:
                blocked_periods = [
                    int(p.strip()) for p in blocked_str.split(",")
                    if p.strip().isdigit()
                ]
                if day not in availability:
                    availability[day] = {}
                availability[day]["blocked_periods"] = blocked_periods
        
        # Check for time range columns
        if f"from_{day_lower}" in row and f"to_{day_lower}" in row:
            from_time = row.get(f"from_{day_lower}", "").strip()
            to_time = row.get(f"to_{day_lower}", "").strip()
            if from_time and to_time:
                if day not in availability:
                    availability[day] = {}
                availability[day]["from_time"] = from_time
                availability[day]["to_time"] = to_time
    
    return availability
