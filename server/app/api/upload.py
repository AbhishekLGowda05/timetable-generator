"""
Upload endpoint - Upload demo data files.

POST /upload - Upload CSV or XLSX files for parsing
"""

import json
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from ..config import RAW_UPLOADS_DIR, PARSED_DIR
from ..utils.path_helper import ensure_dir_exists
from ..utils.validators import get_validator
from ..parsers import parse_csv, parse_excel

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload")
async def upload_demo_data(
    file: UploadFile = File(...),
    data_type: str = Form(..., description="Data type: teachers, classes, subjects, resources"),
):
    """
    Upload and parse demo data files.
    
    Supports CSV and XLSX formats.
    
    Args:
        file: Uploaded file (CSV or XLSX)
        data_type: Type of data in the file
    
    Returns:
        Parsed data and file information
    """
    # Validate data type
    valid_types = ["teachers", "classes", "subjects", "resources", "school"]
    if data_type.lower() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Invalid data_type: {data_type}",
                "valid_types": valid_types,
            }
        )
    
    # Validate file extension
    filename = file.filename or "unknown"
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in [".csv", ".xlsx"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unsupported file format: {file_ext}",
                "supported_formats": [".csv", ".xlsx"],
            }
        )
    
    # Generate file ID
    file_id = str(uuid.uuid4())
    
    # Save raw file
    ensure_dir_exists(RAW_UPLOADS_DIR)
    raw_path = RAW_UPLOADS_DIR / f"{file_id}_{filename}"
    
    try:
        content = await file.read()
        with open(raw_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved raw upload: {raw_path}")
    except Exception as e:
        logger.error(f"Failed to save upload: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": f"Failed to save file: {str(e)}"}
        )
    
    # Parse file
    try:
        if file_ext == ".csv":
            parsed = parse_csv(raw_path, data_type)
        else:  # .xlsx
            parsed = parse_excel(raw_path, data_type)
    except Exception as e:
        logger.error(f"Failed to parse file: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Failed to parse file: {str(e)}",
                "suggestion": "Check file format matches expected columns",
            }
        )
    
    # Validate parsed data
    validator = get_validator(data_type)
    validation_errors = []
    
    for i, item in enumerate(parsed):
        is_valid, errors = validator(item)
        if not is_valid:
            for error in errors:
                validation_errors.append(f"Row {i+1}: {error}")
    
    if validation_errors:
        # Return partial success with validation warnings
        logger.warning(f"Validation errors in upload: {validation_errors}")
    
    # Save parsed data
    ensure_dir_exists(PARSED_DIR)
    parsed_path = PARSED_DIR / f"{file_id}_{data_type}.json"
    
    try:
        with open(parsed_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved parsed data: {parsed_path}")
    except Exception as e:
        logger.error(f"Failed to save parsed data: {e}")
    
    return {
        "file_id": file_id,
        "data_type": data_type,
        "records_count": len(parsed),
        "data": parsed,
        "validation_errors": validation_errors if validation_errors else None,
        "raw_path": str(raw_path.relative_to(RAW_UPLOADS_DIR.parent.parent)),
        "parsed_path": str(parsed_path.relative_to(PARSED_DIR.parent.parent)),
    }


@router.get("/templates/{data_type}")
async def get_csv_template(data_type: str):
    """
    Get CSV template headers for a data type.
    
    Args:
        data_type: Type of data
    
    Returns:
        CSV headers and example row
    """
    templates = {
        "teachers": {
            "headers": ["teacher_id", "name", "subjects", "min_day", "max_day", "max_consecutive", "min_week", "max_week", "class_teacher_of"],
            "example": ["T001", "Priya Sharma", "MATH;PHYSICS", "2", "6", "3", "10", "30", "8A"],
            "description": "subjects: semicolon-separated subject IDs",
        },
        "classes": {
            "headers": ["section_id", "grade", "section_name", "class_teacher_id", "subjects"],
            "example": ["8A", "8", "A", "T001", "MATH:T001;PHYSICS:T002;ENGLISH:T003"],
            "description": "subjects: SUBJECT_ID:TEACHER_ID pairs separated by semicolons",
        },
        "subjects": {
            "headers": ["subject_id", "name", "category", "min_week", "max_week", "requires_block", "block_length", "resource_type"],
            "example": ["MATH", "Mathematics", "core", "6", "7", "false", "0", ""],
            "description": "category: core, language, leisure, or lab",
        },
        "resources": {
            "headers": ["resource_id", "resource_type", "name", "capacity"],
            "example": ["LAB01", "Computer Lab", "Main Computer Lab", "2"],
            "description": "capacity: max simultaneous sections",
        },
    }
    
    if data_type.lower() not in templates:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Unknown data type: {data_type}",
                "valid_types": list(templates.keys()),
            }
        )
    
    template = templates[data_type.lower()]
    
    # Generate CSV content
    csv_content = ",".join(template["headers"]) + "\n"
    csv_content += ",".join(f'"{v}"' if ";" in v or ":" in v else v for v in template["example"])
    
    return {
        "data_type": data_type,
        "headers": template["headers"],
        "example": template["example"],
        "description": template["description"],
        "csv_template": csv_content,
    }
