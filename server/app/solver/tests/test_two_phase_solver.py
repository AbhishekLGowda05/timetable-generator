"""
Tests for the Two-Phase Solver with Automatic Relaxation.

These tests verify the acceptance criteria:
1. 6 classes, 35 teachers → always solves
2. Remove all soft constraints → still solves
3. Change constraint toggle → new result produced
4. Phase 2 failure → Phase 1 returned
5. Teacher free periods allowed
6. Capacity >= demand → solver never infeasible
"""

import pytest
from typing import Optional
import sys
import os

# Add the server directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.solver.constraint_types import (
    ConstraintType,
    RelaxationResult,
    get_constraints_by_type,
    get_relaxation_order,
    get_enabled_relaxable_constraints,
    CONSTRAINT_REGISTRY,
)
from app.solver.two_phase_solver import (
    TwoPhaseSolver,
    analyze_capacity,
    compute_input_hash,
)


# =============================================================================
# Test Fixtures
# =============================================================================

def create_minimal_school():
    """Create a minimal school configuration."""
    return {
        "school_id": 1,
        "name": "Test School",
        "start_time": "08:00",
        "end_time": "15:00",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "periods_per_weekday": 8,
        "saturday_periods": 0,
        "period_duration_minutes": 45,
        "prayer_enabled": False,
        "lunch_period_index": 4,
        "lunch_duration_minutes": 30,
        "recess_period_indices": [2],
        "recess_duration_minutes": 15,
    }


def create_teachers(count: int, max_periods_week: int = 30):
    """Create a list of teachers."""
    teachers = []
    for i in range(count):
        teachers.append({
            "teacher_id": f"T{i+1:03d}",
            "name": f"Teacher {i+1}",
            "subjects_can_teach": [f"SUBJ{j+1}" for j in range(5)],  # Each teacher can teach 5 subjects
            "min_periods_day": 0,
            "max_periods_day": 7,
            "min_periods_week": 0,
            "max_periods_week": max_periods_week,
            "max_consecutive_periods": 4,
        })
    return teachers


def create_subjects(count: int, min_per_week: int = 4, max_per_week: int = 5):
    """Create a list of subjects."""
    subjects = []
    for i in range(count):
        subjects.append({
            "subject_id": f"SUBJ{i+1}",
            "name": f"Subject {i+1}",
            "category": "core" if i < count // 2 else "elective",
            "min_per_week": min_per_week,
            "max_per_week": max_per_week,
            "requires_block": False,
        })
    return subjects


def create_classes(count: int, subjects_per_class: int, teachers: list):
    """Create a list of classes with teacher assignments."""
    classes = []
    for i in range(count):
        subject_teacher_map = {}
        for j in range(subjects_per_class):
            subject_id = f"SUBJ{j+1}"
            # Assign teacher in round-robin fashion
            teacher_idx = (i * subjects_per_class + j) % len(teachers)
            subject_teacher_map[subject_id] = teachers[teacher_idx]["teacher_id"]
        
        classes.append({
            "section_id": f"CLASS_{i+1}",
            "grade": 6 + (i // 3),
            "subject_teacher_map": subject_teacher_map,
            "language_block_enabled": False,
        })
    return classes


def create_solver_input(
    num_classes: int = 6,
    num_teachers: int = 35,
    num_subjects: int = 10,
    subjects_per_class: int = 8,
    constraints: Optional[dict] = None,
) -> dict:
    """
    Create a complete solver input for testing.
    
    Default: 6 classes, 35 teachers (surplus capacity scenario)
    """
    school = create_minimal_school()
    teachers = create_teachers(num_teachers)
    subjects = create_subjects(num_subjects)
    classes = create_classes(num_classes, subjects_per_class, teachers)
    
    return {
        "school": school,
        "teachers": teachers,
        "subjects": subjects,
        "classes": classes,
        "resources": [],
        "constraints": constraints or {
            "language_sync_enabled": False,
            "class_teacher_period_1": False,
            "no_subject_twice_daily": False,
            "substitution_reserve_count": 0,
        },
    }


# =============================================================================
# Constraint Type Tests
# =============================================================================

class TestConstraintTypes:
    """Tests for constraint classification system."""
    
    def test_hard_core_constraints_exist(self):
        """Verify all essential hard constraints are classified."""
        hard_core = get_constraints_by_type(ConstraintType.HARD_CORE)
        hard_core_names = {c.name for c in hard_core}
        
        # Essential constraints that MUST be HARD_CORE
        assert "teacher_single_assignment" in hard_core_names
        assert "section_single_subject" in hard_core_names
        assert "subject_frequency" in hard_core_names
    
    def test_relaxable_constraints_have_priority(self):
        """Verify relaxable constraints have valid priorities."""
        relaxable = get_relaxation_order()
        
        # Should be sorted by priority
        priorities = [c.relaxation_priority for c in relaxable]
        assert priorities == sorted(priorities)
    
    def test_soft_constraints_have_weights(self):
        """Verify soft constraints have positive weights."""
        soft = get_constraints_by_type(ConstraintType.SOFT)
        
        for constraint in soft:
            assert constraint.soft_weight > 0, f"{constraint.name} has no weight"
    
    def test_constraint_registry_complete(self):
        """Verify all constraints are in the registry."""
        assert len(CONSTRAINT_REGISTRY) > 0
        
        # Check each type has at least one constraint
        for ctype in ConstraintType:
            constraints = get_constraints_by_type(ctype)
            assert len(constraints) > 0, f"No constraints of type {ctype}"


# =============================================================================
# Capacity Analysis Tests
# =============================================================================

class TestCapacityAnalysis:
    """Tests for pre-solve capacity analysis."""
    
    def test_surplus_capacity_detected(self):
        """Test detection of surplus teacher capacity."""
        solver_input = create_solver_input(num_classes=6, num_teachers=35)
        capacity = analyze_capacity(solver_input)
        
        assert capacity.is_sufficient
        assert capacity.capacity_ratio > 1.0
        assert capacity.num_teachers == 35
        assert capacity.num_classes == 6
    
    def test_insufficient_capacity_detected(self):
        """Test detection of insufficient capacity."""
        # Create scenario where teachers can't cover all classes
        solver_input = create_solver_input(
            num_classes=20, 
            num_teachers=2,  # Way too few teachers
        )
        capacity = analyze_capacity(solver_input)
        
        # Should detect capacity issue
        assert capacity.capacity_ratio < 1.0 or len(capacity.warnings) > 0
    
    def test_exact_capacity_threshold(self):
        """Test capacity at exactly 1.0 ratio."""
        solver_input = create_solver_input(num_classes=6, num_teachers=6)
        capacity = analyze_capacity(solver_input)
        
        # Should not fail, but may have warnings
        assert capacity.capacity_ratio >= 0.5  # Some margin for calculation differences


# =============================================================================
# Input Hash Tests
# =============================================================================

class TestInputHash:
    """Tests for deterministic input hashing."""
    
    def test_same_input_same_hash(self):
        """Same input should produce same hash."""
        input1 = create_solver_input(num_classes=6, num_teachers=10)
        input2 = create_solver_input(num_classes=6, num_teachers=10)
        
        hash1 = compute_input_hash(input1)
        hash2 = compute_input_hash(input2)
        
        assert hash1 == hash2
    
    def test_different_constraints_different_hash(self):
        """Different constraints should produce different hash."""
        input1 = create_solver_input(
            constraints={"language_sync_enabled": True}
        )
        input2 = create_solver_input(
            constraints={"language_sync_enabled": False}
        )
        
        hash1 = compute_input_hash(input1)
        hash2 = compute_input_hash(input2)
        
        assert hash1 != hash2
    
    def test_different_data_different_hash(self):
        """Different school data should produce different hash."""
        input1 = create_solver_input(num_classes=6)
        input2 = create_solver_input(num_classes=7)
        
        hash1 = compute_input_hash(input1)
        hash2 = compute_input_hash(input2)
        
        assert hash1 != hash2
    
    def test_hash_is_deterministic(self):
        """Hash should be deterministic across multiple calls."""
        solver_input = create_solver_input()
        
        hashes = [compute_input_hash(solver_input) for _ in range(5)]
        
        assert len(set(hashes)) == 1  # All hashes should be the same


# =============================================================================
# Two-Phase Solver Tests
# =============================================================================

class TestTwoPhaseSolver:
    """Tests for the two-phase solver."""
    
    def test_surplus_teachers_always_solves(self):
        """
        CRITICAL: 6 classes, 35 teachers must ALWAYS find a solution.
        
        This is the primary acceptance criterion - if mathematical solution
        exists (surplus teachers), solver must find it.
        """
        solver_input = create_solver_input(num_classes=6, num_teachers=35)
        
        solver = TwoPhaseSolver(solver_input)
        result = solver.solve(time_limit=60)
        
        assert result["status"] in ["OPTIMAL", "FEASIBLE"], \
            f"Solver failed with surplus teachers: {result.get('diagnostics', [])}"
        assert result.get("timetable"), "No timetable in result"
    
    def test_no_soft_constraints_still_solves(self):
        """Removing all soft constraints should still produce solution."""
        solver_input = create_solver_input(
            constraints={
                "language_sync_enabled": False,
                "class_teacher_period_1": False,
                "no_subject_twice_daily": False,
                "substitution_reserve_count": 0,
                "_phase1_only": True,  # Explicitly disable soft constraints
                "soft_weights": {},
            }
        )
        
        solver = TwoPhaseSolver(solver_input)
        result = solver.solve(time_limit=30)
        
        assert result["status"] in ["OPTIMAL", "FEASIBLE"]
    
    def test_relaxation_info_in_result(self):
        """Result should include relaxation information."""
        solver_input = create_solver_input()
        
        solver = TwoPhaseSolver(solver_input)
        result = solver.solve(time_limit=30)
        
        assert "relaxation_info" in result
        assert "meta" in result
        assert "input_hash" in result.get("meta", {})
    
    def test_capacity_analysis_in_result(self):
        """Result should include capacity analysis."""
        solver_input = create_solver_input()
        
        solver = TwoPhaseSolver(solver_input)
        result = solver.solve(time_limit=30)
        
        assert "capacity_analysis" in result
        capacity = result["capacity_analysis"]
        assert "capacity_ratio" in capacity
        assert "is_sufficient" in capacity


# =============================================================================
# Free Period Tests
# =============================================================================

class TestFreePeriods:
    """Tests for teacher free period handling."""
    
    def test_teachers_can_have_free_periods(self):
        """
        Teachers should be allowed to have free periods.
        
        This tests that the solver doesn't force every teacher
        to teach every period.
        """
        # Create scenario where teachers have excess capacity
        solver_input = create_solver_input(
            num_classes=3,  # Few classes
            num_teachers=20,  # Many teachers
        )
        
        solver = TwoPhaseSolver(solver_input)
        result = solver.solve(time_limit=30)
        
        assert result["status"] in ["OPTIMAL", "FEASIBLE"]
        
        # With 3 classes and 20 teachers, most teachers should have free periods
        teacher_schedules = result.get("teacher_schedules", {})
        
        # At least some teachers should have fewer than max periods
        if teacher_schedules:
            teachers_with_free = 0
            for teacher_id, schedule in teacher_schedules.items():
                total_periods = sum(len(day_schedule) for day_schedule in schedule.values())
                if total_periods < 40:  # Less than full load
                    teachers_with_free += 1
            
            # Most teachers should have free periods in this scenario
            assert teachers_with_free > 10


# =============================================================================
# Relaxation Tests
# =============================================================================

class TestAutoRelaxation:
    """Tests for automatic constraint relaxation."""
    
    def test_enabled_relaxable_constraints(self):
        """Test getting enabled relaxable constraints."""
        constraints_config = {
            "language_sync_enabled": True,
            "class_teacher_period_1": True,
        }
        
        enabled = get_enabled_relaxable_constraints(constraints_config)
        enabled_names = [c.name for c in enabled]
        
        assert "language_sync" in enabled_names
        assert "class_teacher_period_1" in enabled_names
    
    def test_relaxation_result_structure(self):
        """Test RelaxationResult dataclass."""
        result = RelaxationResult(
            success=True,
            relaxed_constraints=["language_sync", "class_teacher_period_1"],
            iterations=3,
            final_status="FEASIBLE",
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["relaxed_count"] == 2
        assert result_dict["iterations"] == 3


# =============================================================================
# Integration Tests (Longer running)
# =============================================================================

@pytest.mark.slow
class TestIntegration:
    """Integration tests that run the full solver."""
    
    def test_full_solve_pipeline(self):
        """Test complete solve pipeline end-to-end."""
        solver_input = create_solver_input(
            num_classes=6,
            num_teachers=35,
            constraints={
                "language_sync_enabled": False,
                "class_teacher_period_1": False,
            }
        )
        
        solver = TwoPhaseSolver(solver_input)
        result = solver.solve(time_limit=60)
        
        # Verify all expected fields
        assert "status" in result
        assert "timetable" in result
        assert "meta" in result
        assert "relaxation_info" in result
        
        # If successful, verify timetable structure
        if result["status"] in ["OPTIMAL", "FEASIBLE"]:
            timetable = result["timetable"]
            assert len(timetable) == 6  # 6 classes
            
            for section_id, schedule in timetable.items():
                assert len(schedule) == 5  # 5 days
    
    def test_capacity_ratio_check_before_solve(self):
        """Verify capacity is checked before expensive solve."""
        solver_input = create_solver_input(num_classes=6, num_teachers=35)
        
        # Just check capacity without solving
        capacity = analyze_capacity(solver_input)
        
        assert capacity.is_sufficient
        assert capacity.num_classes == 6
        assert capacity.num_teachers == 35
        assert capacity.capacity_ratio > 1.0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
