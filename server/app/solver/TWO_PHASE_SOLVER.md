# Two-Phase Timetable Solver

## Overview

The Two-Phase Solver is a guaranteed-feasibility solving pipeline that ensures a usable timetable is always returned when mathematically possible.

### Design Philosophy

> **Feasible > Optimal**: Return a usable timetable first, then improve it.

The solver prioritizes finding *any* valid solution over finding the *best* solution. This ensures users get a working timetable even when time limits are tight or constraints are challenging.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Two-Phase Solver Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. CAPACITY ANALYSIS                                           │
│     ├── Calculate teacher:class ratio                          │
│     ├── Detect overloaded teachers                             │
│     └── Warn if capacity insufficient                          │
│                                                                 │
│  2. PHASE 1: FEASIBILITY (40% of time budget)                  │
│     ├── Use only HARD_CORE constraints                         │
│     ├── If INFEASIBLE → trigger auto-relaxation                │
│     │   └── Relax HARD_RELAXABLE in priority order             │
│     └── Output: ANY valid timetable                            │
│                                                                 │
│  3. PHASE 2: OPTIMIZATION (60% of time budget)                 │
│     ├── Use Phase 1 solution as baseline                       │
│     ├── Add SOFT constraint penalties                          │
│     ├── Optimize objective function                            │
│     └── Output: Improved timetable (or Phase 1 if no improve)  │
│                                                                 │
│  4. RESULT & CACHING                                           │
│     ├── Persist to data/results/{job_id}.json                  │
│     ├── Cache by input hash                                    │
│     └── Return with metadata and diagnostics                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## The Problem

Traditional single-pass constraint solving can fail for several reasons:
1. **Over-constrained problems**: Soft preferences conflict with hard requirements
2. **Search space issues**: The solver may time out before finding valid regions
3. **Solver heuristics**: CP-SAT may make early decisions that lead to dead ends

## Constraint Classification

### HARD_CORE (Never Relaxed)

These constraints define what makes a timetable **mathematically valid**:

| Constraint | Description |
|------------|-------------|
| `teacher_single_assignment` | Teacher cannot be in two places at once |
| `section_single_subject` | Class can only have one subject per period |
| `subject_frequency` | Subjects must receive minimum weekly periods |
| `teacher_availability` | Teachers assigned only when available |
| `resource_capacity` | Resources cannot exceed capacity |

### HARD_RELAXABLE (Can Be Relaxed)

These constraints define what makes a timetable **good**, but can be relaxed to find feasibility:

| Priority | Constraint | Description |
|----------|------------|-------------|
| 1 | `language_sync` | Sync language teachers across sections |
| 2 | `class_teacher_period_1` | Class teacher in Period 1 |
| 3 | `no_subject_twice_daily` | Subject appears once per day |
| 4 | `substitution_reserve` | Keep teachers free for substitution |
| 5 | `max_consecutive` | Limit consecutive teaching periods |
| 6 | `teacher_daily_load` | Daily period bounds |
| 7 | `teacher_weekly_balance` | Balance daily loads across week |
| 8 | `block_periods` | Subjects requiring consecutive periods |

**Relaxation Order**: Lower priority = relaxed first (least disruptive first)

### SOFT (Optimization Only)

These are preferences that never cause infeasibility:

- Core subjects in morning
- Teacher load balance
- Minimize schedule gaps
- Leisure subjects in afternoon
- Fair distribution of undesirable slots

## Capacity Analysis

Before solving, the system analyzes **capacity**:

```
Capacity Ratio = (Total Teacher Teaching Slots) / (Total Required Slots)
```

- **Ratio > 1.0**: Surplus capacity - solution should exist
- **Ratio < 1.0**: Insufficient capacity - may be infeasible
- **Ratio ≈ 1.0**: Tight - solution exists but may be hard to find

This catches obvious infeasibility before expensive solving.

## API Usage

### Solve Request

```bash
POST /api/v1/timetable/solve
Content-Type: application/json

{
  "upload_id": "sample-data-vidya-mandir",
  "options": {
    "time_limit_seconds": 120,
    "force_fresh": true,
    "strategy": "balanced"
  }
}
```

### Response

```json
{
  "job_id": "abc123...",
  "status": "queued",
  "time_allocated_seconds": 120,
  "estimated_completion": "2026-01-26T10:02:00"
}
```

### Get Result

```bash
GET /api/v1/timetable/result/{job_id}
```

```json
{
  "job_id": "abc123...",
  "timetable_json": {
    "status": "FEASIBLE",
    "timetable": {...},
    "teacher_schedules": {...},
    "meta": {
      "solve_time_seconds": 45.3,
      "phase1_time_seconds": 18.2,
      "phase2_time_seconds": 27.1,
      "relaxed_constraints": ["language_sync"],
      "input_hash": "a1b2c3...",
      "solver_pipeline": "two_phase"
    },
    "relaxation_info": {
      "success": true,
      "relaxed_constraints": ["language_sync"],
      "iterations": 2
    },
    "capacity_analysis": {
      "num_teachers": 60,
      "num_classes": 40,
      "capacity_ratio": 1.45,
      "is_sufficient": true
    }
  },
  "diagnostics": [...],
  "warnings": ["Solution found after relaxing 1 constraint(s)"]
}
```

## Caching

Results are cached by **input hash**:

```
Hash = SHA256(solver_version + school + teachers + subjects + classes + constraints)
```

- Same input → same hash → cached result returned
- Any change (including constraint toggles) → new hash → fresh solve
- Solver version change → cache invalidated

This fixes the bug where changing constraints returned stale results.

### Persistence

Results are persisted to:
- `data/results/job_{job_id}.json` - Full job record
- `data/results/hash_{hash}.json` - Hash-indexed cache
- `data/generated/result_{job_id}.json` - Legacy format

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `SOLVER_VERSION` | `2.0.0-two-phase` | Solver version (changes invalidate cache) |
| `SOLVER_TIMEOUT` | `120` | Default solver timeout (seconds) |
| `SOLVER_PHASE1_TIME_FRACTION` | 0.4 | Phase 1 time share |
| `SOLVER_PHASE2_TIME_FRACTION` | 0.6 | Phase 2 time share |
| `MIN_PHASE1_TIME_SEC` | 15 | Minimum Phase 1 time |
| `MIN_PHASE2_TIME_SEC` | 15 | Minimum Phase 2 time |
| `SOLVER_MAX_RELAXATION_ITERATIONS` | 10 | Max relaxation attempts |
| `RELAXATION_ATTEMPT_TIME_FRACTION` | 0.3 | Time per relaxation attempt |
| `CP_SAT_SEARCH_WORKERS` | 8 | Parallel search workers |
| `DEADLINE_BUFFER_SEC` | 30 | Buffer before deadline |

## Logging

The solver emits structured log events:

```
[JobStarted] job_id=abc123
[CapacityOK] 60 teachers, 40 classes (ratio: 1.45)
[Phase1Start] Initializing two-phase solver
[Phase1Result] Completed in 18.20s, feasible=True
[ConstraintsRelaxed] language_sync
[Phase2End] Completed in 27.10s
[SolverResult] FEASIBLE in 45.30s
[ResultCached] hash=a1b2c3...
[JobCompleted] status=FEASIBLE
```

## Acceptance Criteria

### Demo Case (6 Classes, 35 Teachers)

The solver must handle the standard demo case with:
- 6 classes, 35 teachers
- 8 periods/day, 6 days/week
- Core + language + lab subjects

**Expected Results:**
- Status: FEASIBLE or OPTIMAL
- Solve time: < 120 seconds
- No HARD_CORE constraint violations
- Result persisted to `data/results/`

### Stale Cache Invalidation

When constraints change:
1. Old cached result should NOT be returned
2. New solve should produce fresh result
3. New result should reflect constraint changes

## File Structure

```
server/app/solver/
├── two_phase_solver.py    # Main solver pipeline
├── constraint_types.py    # Constraint classification
├── constraints.py         # Constraint implementations
├── model.py              # CP-SAT model builder
├── preprocess.py         # Input preprocessing
├── diagnostics.py        # Infeasibility analysis
└── tests/
    └── test_two_phase_solver.py
```

## API Usage (Python)

```python
from app.solver.two_phase_solver import TwoPhaseSolver, analyze_capacity

# Pre-check capacity
capacity = analyze_capacity(solver_input)
if not capacity.is_sufficient:
    print(f"Warning: Capacity ratio {capacity.capacity_ratio:.2f}")

# Solve with two-phase strategy
solver = TwoPhaseSolver(solver_input)
result = solver.solve(time_limit=120)

# Check result
if result["status"] in ["OPTIMAL", "FEASIBLE"]:
    timetable = result["timetable"]
    relaxed = result["relaxation_info"]["relaxed_constraints"]
    if relaxed:
        print(f"Relaxed constraints: {relaxed}")
else:
    print(f"Failed: {result['diagnostics']}")
```

## Result Structure

```json
{
  "status": "FEASIBLE",
  "timetable": { ... },
  "teacher_schedules": { ... },
  "meta": {
    "input_hash": "abc123...",
    "phase1_time_sec": 24.5,
    "phase2_time_sec": 35.2,
    "total_time_sec": 59.7
  },
  "relaxation_info": {
    "success": true,
    "relaxed_constraints": ["language_sync"],
    "relaxed_count": 1,
    "iterations": 2
  },
  "capacity_analysis": {
    "capacity_ratio": 1.85,
    "is_sufficient": true,
    "num_teachers": 35,
    "num_classes": 6
  }
}
```

## Guarantees

The two-phase solver guarantees:

1. ✅ **6 classes, 35 teachers → always solves** (surplus capacity)
2. ✅ **Remove soft constraints → still solves** (HARD_CORE only)
3. ✅ **Change constraint → new result** (hash-based caching)
4. ✅ **Phase 2 fails → Phase 1 returned** (warm start fallback)
5. ✅ **Teachers may have free periods** (not over-constrained)
6. ✅ **Capacity ≥ demand → never infeasible** (capacity analysis)
