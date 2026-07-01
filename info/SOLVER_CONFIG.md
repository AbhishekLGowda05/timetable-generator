# Solver Configuration Guide

## Overview

The timetable solver now supports configurable time limits and scheduling modes to handle both demo/single-tenant scenarios and production multi-tenant environments.

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLVER_TIMEOUT` | `60` | Default solver timeout in seconds |
| `DEMO_SOLVE_TIME_SEC` | `90` | Time limit for demo mode (single requests) |
| `DEFAULT_SOLVE_TIME_SEC` | `60` | Default time for queued requests |
| `MAX_SOLVE_TIME_SEC` | `600` | Maximum allowed time (10 minutes) |
| `DEMO_MODE` | `true` | Enable demo mode (immediate allocation) |
| `CP_SAT_SEARCH_WORKERS` | `8` | Number of parallel search workers |

### API Request Options

When calling `/api/v1/timetable/solve`, you can specify:

```json
{
  "upload_id": "sample-data-vidya-mandir",
  "constraints": { ... },
  "options": {
    "time_limit_seconds": 120,
    "demo_mode": true,
    "deadline": "2026-01-25T15:00:00",
    "force_fresh": true
  }
}
```

#### Options Explained

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `time_limit_seconds` | int | 60 | Maximum solver time (5-600 seconds) |
| `demo_mode` | bool | null | Override global demo mode setting |
| `deadline` | string | null | ISO 8601 datetime for deadline-based scheduling |
| `force_fresh` | bool | true | Always run solver fresh, ignore cached results |

## Scheduling Modes

### 1. Demo Mode (Default for Development)

When `DEMO_MODE=true`:
- Jobs are allocated immediately
- Time limit defaults to `DEMO_SOLVE_TIME_SEC` (90s)
- Suitable for single-user/demo scenarios

### 2. Production Mode

When `DEMO_MODE=false`:
- Jobs are queued and allocated based on availability
- Time limit defaults to `DEFAULT_SOLVE_TIME_SEC` (60s)
- Supports multi-tenant scenarios

### 3. Deadline-Based Scheduling

Specify a deadline to automatically calculate optimal time allocation:

```json
{
  "options": {
    "deadline": "2026-01-25T15:00:00"
  }
}
```

The system will:
1. Calculate available time until deadline
2. Reserve buffer time (30s) for processing
3. Allocate remaining time to solver (up to `MAX_SOLVE_TIME_SEC`)

**Example Scenario:**
- Request at 9:00 AM
- Deadline at 3:00 PM
- Available: 6 hours = 21,600 seconds
- Allocated: 600 seconds (capped at max)

## Caching Behavior

### Force Fresh Solve

By default, `force_fresh=true` ensures:
- Solver always runs fresh when constraints change
- No stale INFEASIBLE results returned
- Each request with different constraints gets a new solve

### Recommended Settings

| Scenario | Recommended Settings |
|----------|---------------------|
| Demo/Testing | `demo_mode: true`, `time_limit_seconds: 90` |
| Quick Preview | `time_limit_seconds: 30` |
| Production | `time_limit_seconds: 60` |
| Complex Constraints | `time_limit_seconds: 120-300` |
| Overnight Processing | `deadline: "next-morning-time"` |

## Staffing Ratio Reference

Based on CBSE/ICSE school norms:

| Metric | Ratio | Example (40 Sections) |
|--------|-------|----------------------|
| Teacher:Section | 1.5:1 | 60 teachers total |
| Subject Teacher Coverage | 1:3.5 | 1 teacher per 3-4 sections |
| Pupil:Teacher | 30:1 | RTE mandate |

These ratios ensure the solver has realistic constraints to work with.

## API Response

The solve endpoint now returns additional information:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "message": "Timetable generation started",
  "warnings": [],
  "time_allocated_seconds": 90,
  "estimated_completion": "2026-01-25T12:31:30"
}
```

## Configuration Endpoint

Get current solver configuration:

```bash
GET /api/v1/timetable/config
```

Returns:
```json
{
  "solver": {
    "timeout_seconds": 60,
    "demo_mode": true,
    "demo_time_seconds": 90,
    "default_time_seconds": 60,
    "max_time_seconds": 600,
    "search_workers": 8
  },
  "queue": {
    "max_concurrent_jobs": 5
  },
  "features": {
    "deadline_scheduling": true,
    "force_fresh_solve": true
  },
  "recommendations": {
    "demo_time_limit": 90,
    "production_time_limit": 60,
    "complex_constraints_time_limit": 300
  }
}
```

## Troubleshooting

### "INFEASIBLE" Results with All Hard Constraints

If you're getting INFEASIBLE with most hard constraints enabled:

1. **Increase time limit**: Try `time_limit_seconds: 180` or higher
2. **Check constraint conflicts**: 
   - Language Block Sync requires all language teachers free simultaneously
   - Class Teacher Period 1 may conflict with teacher availability
3. **Review staffing ratios**: Ensure you have 1.5 teachers per section

### Cached Results After Constraint Changes

If changing constraints returns old results:

1. Ensure `force_fresh: true` in options
2. Check that constraints are being sent correctly
3. Verify the request is not hitting browser cache

### Solver Timeout

If solver times out without finding a solution:

1. Start with fewer hard constraints
2. Increase `time_limit_seconds`
3. Use deadline-based scheduling for longer runs
