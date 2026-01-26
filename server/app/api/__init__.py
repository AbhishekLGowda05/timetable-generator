"""
API endpoints module for the Timetable Generator Backend.
"""

from .solve import router as solve_router
from .status import router as status_router
from .result import router as result_router
from .validate import router as validate_router
from .upload import router as upload_router
from .download import router as download_router

__all__ = [
    "solve_router",
    "status_router",
    "result_router",
    "validate_router",
    "upload_router",
    "download_router",
]
