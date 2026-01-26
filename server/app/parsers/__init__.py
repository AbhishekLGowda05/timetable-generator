"""
Data parsers for the Timetable Generator Backend.
"""

from .csv_parser import (
    parse_csv,
    parse_teachers_csv,
    parse_classes_csv,
    parse_subjects_csv,
    parse_resources_csv,
)

from .excel_parser import (
    parse_excel,
)

__all__ = [
    "parse_csv",
    "parse_teachers_csv",
    "parse_classes_csv",
    "parse_subjects_csv",
    "parse_resources_csv",
    "parse_excel",
]
