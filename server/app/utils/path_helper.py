"""
Path helper utilities for relocatable path management.

All paths are relative to the project root, ensuring the application
works correctly regardless of its installation location.
"""

from pathlib import Path
from typing import Optional
import logging

from ..config import (
    DATA_DIR,
    RAW_UPLOADS_DIR,
    PARSED_DIR,
    GENERATED_DIR,
    SCHEMAS_DIR,
)

logger = logging.getLogger(__name__)


def resolve_data_path(relative_path: str, base_dir: Optional[Path] = None) -> Path:
    """
    Resolve a relative path to an absolute path within the data directory.
    
    Args:
        relative_path: Path relative to the base directory
        base_dir: Base directory (defaults to DATA_DIR)
    
    Returns:
        Absolute Path object
    
    Raises:
        ValueError: If the resolved path escapes the base directory
    """
    if base_dir is None:
        base_dir = DATA_DIR
    
    # Resolve the path
    resolved = (base_dir / relative_path).resolve()
    
    # Security check: ensure path doesn't escape base directory
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError:
        raise ValueError(
            f"Path '{relative_path}' resolves outside of base directory '{base_dir}'"
        )
    
    return resolved


def ensure_dir_exists(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Path to the directory
    
    Returns:
        The same path (for chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {path}")
    return path


def get_schema_path(schema_name: str) -> Path:
    """
    Get the full path to a JSON schema file.
    
    Args:
        schema_name: Name of the schema file (with or without .json extension)
    
    Returns:
        Path to the schema file
    
    Raises:
        FileNotFoundError: If the schema file doesn't exist
    """
    # Add .json extension if not present
    if not schema_name.endswith(".json"):
        schema_name = f"{schema_name}.json"
    
    # Handle both "school" and "school.schema.json" formats
    if not schema_name.endswith(".schema.json"):
        schema_name = schema_name.replace(".json", ".schema.json")
    
    schema_path = SCHEMAS_DIR / schema_name
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    return schema_path


def get_all_schema_paths() -> dict[str, Path]:
    """
    Get paths to all schema files in the schemas directory.
    
    Returns:
        Dictionary mapping schema names to their paths
    """
    schema_paths = {}
    
    if SCHEMAS_DIR.exists():
        for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
            name = schema_file.stem.replace(".schema", "")
            schema_paths[name] = schema_file
    
    return schema_paths


def get_raw_upload_path(filename: str) -> Path:
    """
    Get the path for a raw uploaded file.
    
    Args:
        filename: Name of the uploaded file
    
    Returns:
        Full path in the raw_uploads directory
    """
    ensure_dir_exists(RAW_UPLOADS_DIR)
    return RAW_UPLOADS_DIR / filename


def get_parsed_path(filename: str) -> Path:
    """
    Get the path for a parsed data file.
    
    Args:
        filename: Name of the parsed file
    
    Returns:
        Full path in the parsed directory
    """
    ensure_dir_exists(PARSED_DIR)
    return PARSED_DIR / filename


def get_generated_path(filename: str) -> Path:
    """
    Get the path for a generated output file.
    
    Args:
        filename: Name of the generated file
    
    Returns:
        Full path in the generated directory
    """
    ensure_dir_exists(GENERATED_DIR)
    return GENERATED_DIR / filename


def cleanup_old_files(directory: Path, max_age_hours: int = 24) -> int:
    """
    Remove files older than max_age_hours from a directory.
    
    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files to keep
    
    Returns:
        Number of files removed
    """
    import time
    
    if not directory.exists():
        return 0
    
    max_age_seconds = max_age_hours * 3600
    current_time = time.time()
    removed_count = 0
    
    for file_path in directory.iterdir():
        if file_path.is_file():
            file_age = current_time - file_path.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    file_path.unlink()
                    removed_count += 1
                    logger.info(f"Removed old file: {file_path}")
                except OSError as e:
                    logger.warning(f"Failed to remove file {file_path}: {e}")
    
    return removed_count
