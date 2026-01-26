# 🎓 Timetable Generator

> A production-grade, constraint-based school timetable generator powered by Google OR-Tools CP-SAT solver.

---

## 📑 Table of Contents

1. [Overview](#-overview)
2. [Quick Start](#-quick-start)
3. [Frontend Architecture](#-frontend-architecture)
4. [Backend Infrastructure](#-backend-infrastructure)
5. [How It Works - The Big Picture](#-how-it-works---the-big-picture)
6. [Understanding Constraint Programming](#-understanding-constraint-programming)
7. [Architecture Deep Dive](#-architecture-deep-dive)
8. [The Brain: CP-SAT Solver](#-the-brain-cp-sat-solver)
9. [File-by-File Implementation Guide](#-file-by-file-implementation-guide)
10. [Constraint Implementation Details](#-constraint-implementation-details)
11. [Data Flow: From Input to Timetable](#-data-flow-from-input-to-timetable)
12. [API Reference](#-api-reference)
13. [JSON Schemas Explained](#-json-schemas-explained)
14. [Configuration Options](#-configuration-options)
15. [Error Handling & Diagnostics](#-error-handling--diagnostics)
16. [Production Deployment](#-production-deployment)
17. [Testing Strategy](#-testing-strategy)
18. [Troubleshooting](#-troubleshooting)
19. [Performance & Optimization](#-performance--optimization)
20. [Constraint Mapping Summary](#-constraint-mapping-summary)

---

## 🌟 Overview

### What is this?

This is a **school timetable generator** that automatically creates conflict-free schedules for all classes, teachers, and resources. Think of it as an incredibly smart puzzle solver that:

- Assigns **subjects to time slots** for every class
- Ensures **teachers aren't double-booked**
- Respects **lab and resource constraints**
- Balances **workload fairly** among teachers
- Follows **educational best practices** (core subjects in morning, etc.)

### Why is this hard?

Creating a timetable manually is tedious. Creating an **optimal** one is nearly impossible because:

- A school with 20 classes, 50 teachers, 15 subjects, and 40 periods/week has **billions** of possible combinations
- Every constraint you add (teacher availability, lab capacity, etc.) eliminates millions of options
- Finding the "best" solution among valid ones requires evaluating countless possibilities

This is where **Constraint Programming** comes in - it's a mathematical approach that can explore this massive space intelligently.

### Key Features

| Feature | Description |
|---------|-------------|
| **Global Solve** | All classes solved together in one model (not per-class) |
| **Relocatable Design** | No hardcoded paths - works from any directory |
| **Schema-First** | JSON Schema validation for all input/output |
| **Async Execution** | Non-blocking API with job queue |
| **Infeasibility Diagnostics** | Explains WHY constraints can't be satisfied |
| **Manual Swap Validation** | Check if manual edits violate constraints |
| **Configurable Constraints** | Toggle hard constraints, tune soft weights |
| **Production-Ready Backend** | Supabase + R2 + Redis for scalability |
| **Modern React Frontend** | TypeScript, Vite, TanStack Query, Radix UI |
| **Comprehensive Testing** | Unit tests (Vitest), E2E tests (Playwright) |
| **API Mocking** | MSW for frontend development without backend |
| **Multi-Tenant Support** | Tenant isolation with distributed semaphores |
| **Audit Trail** | Complete job history tracking in PostgreSQL |

---

## 🚀 Quick Start

### Backend Setup

```bash
# 1. Navigate to server directory
cd server

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
python -m app.main

# 5. Access API
# API Docs: http://localhost:8010/docs
# Health Check: http://localhost:8010/health
```

### Frontend Setup

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Run development server
npm run dev

# 4. Access UI
# Frontend: http://localhost:3000
# (Proxies API requests to http://localhost:8010)
```

### Quick Test

```bash
# Test backend API directly
curl -X POST http://localhost:8010/api/v1/timetable/solve \
  -H "Content-Type: application/json" \
  -d '{"school": {...}, "teachers": [...], ...}'

# Or use the frontend UI at http://localhost:3000
```

---

## � Frontend Architecture

### Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 18.3.1 | UI framework with concurrent features |
| **TypeScript** | 5.6.2 | Type-safe development |
| **Vite** | 5.4.21 | Lightning-fast build tool & dev server |
| **TanStack Query** | 5.59.0 | Server state management & caching |
| **React Router** | 6.26.2 | Client-side routing |
| **Radix UI** | Latest | Accessible UI primitives |
| **Tailwind CSS** | 3.x | Utility-first styling |
| **Zod** | 3.23.8 | Runtime type validation |
| **Zustand** | 5.0.0 | Lightweight state management |
| **Axios** | 1.7.7 | HTTP client |
| **Vitest** | 2.1.9 | Unit testing framework |
| **Playwright** | 1.58.0 | E2E testing |
| **MSW** | 2.4.9 | API mocking for development |

### Frontend Features

#### 1. **Landing Page** (`LandingPage.tsx`)
- Hero section with feature highlights
- Three-step workflow visualization:
  - 📤 Upload Your Data
  - ⚙️ Configure Constraints
  - 🚀 Generate Timetable
- Quick start button leading to upload flow

#### 2. **Upload Page** (`UploadPage.tsx`)
- Drag-and-drop file upload
- Supports CSV and Excel (.xlsx) formats
- Real-time upload progress tracking
- File validation and preview
- Integrated with backend `/api/upload` endpoint

#### 3. **Constraints Configuration** (`ConstraintsPage.tsx`)
- Interactive constraint toggles
- Soft constraint weight sliders (0-10)
- Hard constraint enable/disable switches:
  - Class Teacher Period 1
  - Language Synchronization
  - No Subject Twice Daily
- Real-time validation feedback
- Saves configuration to Zustand store

#### 4. **Generate Page** (`GeneratePage.tsx`)
- Job submission interface
- Real-time progress monitoring (0-100%)
- Status updates: `queued` → `running` → `completed`/`failed`
- Polling mechanism using TanStack Query
- Cancel job functionality
- Automatic redirect to results on completion

#### 5. **Results Page** (`ResultsPage.tsx`)
- Interactive timetable grid visualization
- Multi-view support:
  - Section-wise timetables
  - Teacher schedules
  - Room allocation
- Export functionality (JSON/CSV)
- Solver metadata display:
  - Solve time
  - Objective value
  - Constraint violations
  - Variables & constraints count
- Re-run job option with same parameters

#### 6. **Recent Jobs Page** (`RecentJobsPage.tsx`)
- Job history table with filtering
- Status badges with color coding
- Job details: creation time, duration, status
- Quick actions:
  - View results
  - Re-run job
  - Cancel running job
  - Delete old jobs
- Pagination and sorting

### Component Library

#### UI Components (`src/components/ui/`)

**Radix UI Primitives** (fully accessible, keyboard navigable):
- `Button` - Multiple variants (default, outline, ghost, destructive)
- `Dialog` - Modal dialogs with overlay
- `Select` - Dropdown selection with search
- `Table` - Sortable data tables
- `Toast` - Notification system
- `Tabs` - Tab navigation
- `Switch` - Toggle switches
- `Checkbox` - Checkboxes with labels
- `Input` - Form inputs with validation
- `Label` - Accessible form labels
- `Progress` - Progress bars
- `Slider` - Range sliders for weights
- `Tooltip` - Contextual help
- `Alert` - Alert messages
- `Card` - Content containers

**Custom Components**:
- `TimetableGrid.tsx` - Specialized grid for timetable display
  - Day-period matrix
  - Cell hover effects
  - Subject color coding
  - Teacher name display

### State Management

#### TanStack Query (React Query)

**Query Keys Structure**:
```typescript
['jobs']                    // All jobs
['job', jobId]             // Specific job status
['result', jobId]          // Job result data
['upload', uploadId]       // Upload status
```

**Query Configuration**:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,    // 5 minutes
      retry: 3,
      refetchOnWindowFocus: false,
    },
  },
});
```

**Polling for Job Status**:
```typescript
const { data: status } = useQuery({
  queryKey: ['job', jobId],
  queryFn: () => getJobStatus(jobId),
  refetchInterval: (data) => 
    data?.status === 'running' ? 2000 : false, // Poll every 2s
});
```

#### Zustand Stores

**Upload Store** (future implementation):
```typescript
interface UploadStore {
  files: File[];
  uploadProgress: Record<string, number>;
  addFile: (file: File) => void;
  removeFile: (fileId: string) => void;
  updateProgress: (fileId: string, progress: number) => void;
}
```

**Constraints Store**:
```typescript
interface ConstraintsStore {
  softWeights: Record<string, number>;
  hardToggles: Record<string, boolean>;
  updateWeight: (key: string, value: number) => void;
  toggleHard: (key: string) => void;
  reset: () => void;
}
```

### API Integration

#### Type-Safe API Client (`lib/api.ts`)

**Full TypeScript Coverage**:
```typescript
// All request/response types from schemas.ts
export async function createSolveJob(
  request: SolveRequest
): Promise<SolveResponse> {
  return post<SolveResponse>('/api/solve', request);
}

export async function getJobStatus(
  jobId: string
): Promise<JobStatusResponse> {
  return get<JobStatusResponse>(`/api/status/${jobId}`);
}

export async function getJobResult(
  jobId: string
): Promise<JobResultResponse> {
  return get<JobResultResponse>(`/api/result/${jobId}`);
}
```

**Axios Configuration** (`lib/api-client.ts`):
- Base URL: `/api` (proxied to `http://localhost:8010` in dev)
- Automatic JSON serialization
- Error handling with typed responses
- Upload progress callbacks
- Request/response interceptors

### Routing

**React Router v6 Setup**:
```typescript
<Routes>
  <Route path="/" element={<AppLayout />}>
    <Route index element={<LandingPage />} />
    <Route path="upload" element={<UploadPage />} />
    <Route path="constraints" element={<ConstraintsPage />} />
    <Route path="generate" element={<GeneratePage />} />
    <Route path="results/:jobId" element={<ResultsPage />} />
    <Route path="jobs" element={<RecentJobsPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route>
</Routes>
```

### Styling System

#### Tailwind CSS + CVA

**Utility-First Approach**:
```tsx
<div className="flex items-center justify-between p-4 border rounded-lg">
  <h3 className="text-lg font-semibold">Timetable</h3>
  <Button variant="outline" size="sm">Export</Button>
</div>
```

**Class Variance Authority (CVA)** for component variants:
```typescript
const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        outline: "border border-input bg-background hover:bg-accent",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        destructive: "bg-destructive text-destructive-foreground",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
      },
    },
  }
);
```

### Development Tools

#### API Mocking with MSW

**Mock Handlers** (`src/mocks/handlers.ts`):
```typescript
export const handlers = [
  http.post('/api/solve', async () => {
    return HttpResponse.json({
      job_id: uuid(),
      status: 'queued',
      message: 'Job created successfully',
    });
  }),
  
  http.get('/api/status/:jobId', async ({ params }) => {
    return HttpResponse.json({
      job_id: params.jobId,
      status: 'completed',
      progress: 100,
    });
  }),
];
```

**Browser Setup** (`src/mocks/browser.ts`):
```typescript
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
```

**Conditional Activation** (`main.tsx`):
```typescript
if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_MSW === 'true') {
  worker.start();
}
```

### Testing Strategy

#### Unit Tests (Vitest)

**Component Testing** (`test/LandingPage.test.tsx`):
```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LandingPage } from '../pages/LandingPage';

describe('LandingPage', () => {
  it('renders the welcome heading', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/Timetable Generator/i)).toBeInTheDocument();
  });

  it('renders feature cards', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    expect(screen.getAllByText(/Upload Your Data/i).length).toBeGreaterThan(0);
  });
});
```

**Test Commands**:
```bash
npm run test        # Run once
npm run test:watch  # Watch mode
```

#### E2E Tests (Playwright)

**End-to-End Scenarios** (`e2e/app.spec.ts`):
```typescript
import { test, expect } from '@playwright/test';

test('complete timetable generation flow', async ({ page }) => {
  await page.goto('/');
  await page.click('text=Get Started');
  
  // Upload file
  await page.setInputFiles('input[type="file"]', 'test-data.csv');
  await expect(page.locator('text=Upload successful')).toBeVisible();
  
  // Configure constraints
  await page.click('text=Next: Constraints');
  await page.fill('input[name="core_morning_weight"]', '5');
  
  // Generate timetable
  await page.click('text=Generate Timetable');
  await expect(page.locator('text=Completed')).toBeVisible({ timeout: 60000 });
});
```

**Run E2E Tests**:
```bash
npx playwright test
npx playwright test --ui      # Interactive mode
npx playwright test --debug   # Debug mode
```

### Build & Deployment

#### Development
```bash
npm run dev          # Start dev server at http://localhost:3000
npm run lint         # ESLint check
npm run type-check   # TypeScript validation
```

#### Production Build
```bash
npm run build        # TypeScript compile + Vite build
npm run preview      # Preview production build
```

**Build Output** (`dist/`):
```
dist/
├── index.html                    # Entry HTML
├── assets/
│   ├── index-[hash].js          # Main bundle (~318KB)
│   ├── vendor-[hash].js         # React, Router, etc (~164KB)
│   ├── ui-[hash].js             # Radix UI components (~95KB)
│   ├── query-[hash].js          # TanStack Query (~42KB)
│   ├── browser-[hash].js        # MSW (dev only, ~248KB)
│   └── index-[hash].css         # Styles (~38KB)
```

**Code Splitting Strategy**:
- Vendor chunk: React, React DOM, Router
- UI chunk: All Radix UI components
- Query chunk: TanStack Query
- Main chunk: App code

**Optimization**:
- Tree-shaking enabled
- Minification with terser
- CSS purging with Tailwind
- Asset optimization (images, fonts)

---

## 🏗 Backend Infrastructure

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TIMETABLE GENERATION FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐│
│  │  CLIENT  │    │   API    │    │   JOB    │    │  SOLVER  │    │ OUTPUT ││
│  │          │───▶│  LAYER   │───▶│  QUEUE   │───▶│  (BRAIN) │───▶│        ││
│  │ POST     │    │          │    │          │    │          │    │ JSON   ││
│  │ /solve   │    │ Validate │    │ Background│   │ CP-SAT   │    │ Result ││
│  │          │    │ Create   │    │ Thread   │    │ Model    │    │        ││
│  │          │◀───│ Job ID   │    │          │    │          │    │        ││
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └────────┘│
│       │                                                              │      │
│       │              GET /status/{job_id} - Poll for progress        │      │
│       │◀─────────────────────────────────────────────────────────────│      │
│       │              GET /result/{job_id} - Retrieve timetable       │      │
│       │◀─────────────────────────────────────────────────────────────│      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗 Backend Infrastructure

### Production Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Database** | Supabase (PostgreSQL) | Job storage, audit trail, multi-tenancy |
| **Object Storage** | Cloudflare R2 | Large payload & result storage |
| **Cache/Queue** | Redis (Upstash) | Distributed semaphores, rate limiting |
| **Backend** | FastAPI + OR-Tools | Constraint solver API |
| **Observability** | Sentry | Error tracking & performance monitoring |

### Multi-Tenant Architecture

#### Tenant Isolation

**Database Level** (`jobs` table):
```sql
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,  -- Tenant isolation
    payload_hash VARCHAR(64) NOT NULL,
    payload_pointer TEXT NOT NULL,    -- R2 or local path
    status job_status NOT NULL,
    -- ... other fields
);

CREATE INDEX idx_jobs_tenant_status ON jobs(tenant_id, status);
CREATE INDEX idx_jobs_tenant_payload_hash ON jobs(tenant_id, payload_hash);
```

**Row-Level Security** (Supabase):
```sql
-- Only allow users to see their tenant's jobs
CREATE POLICY tenant_isolation ON jobs
    FOR ALL USING (tenant_id = current_setting('app.current_tenant'));
```

#### Concurrency Control

**Redis Distributed Semaphores** (`utils/redis_semaphore.py`):

**Global Limits**:
```python
MAX_GLOBAL_ACTIVE_SOLVES = 10  # System-wide concurrent solves
```

**Per-Tenant Limits**:
```python
MAX_PER_TENANT_ACTIVE = 3  # Prevents single tenant monopolizing
```

**Atomic Acquire/Release** (Lua script):
```lua
-- Atomic check-and-increment
local current = redis.call('SCARD', key)
if current < max_count then
    redis.call('SADD', key, worker_id)
    redis.call('EXPIRE', key, ttl)  -- Auto-cleanup on worker death
    return 1
else
    return 0
end
```

### Supabase Integration

#### Job Management (`utils/supabase_client.py`)

**Idempotency with Payload Hashing**:
```python
def compute_payload_hash(solver_input: dict) -> str:
    """SHA256 of canonical JSON for idempotency."""
    canonical = json.dumps(solver_input, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()

def find_job_by_payload_hash(tenant_id: str, payload_hash: str):
    """Check for existing job with same input."""
    response = (
        client.table("jobs")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("payload_hash", payload_hash)
        .in_("status", ["QUEUED", "RUNNING", "COMPLETED"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None
```

### Cloudflare R2 Storage

#### Client Operations (`utils/r2_client.py`)

**Upload Solver Input**:
```python
def upload_solver_input(self, job_id: str, tenant_id: str, 
                        solver_input: dict) -> str:
    """Upload input JSON to R2."""
    object_key = f"inputs/{tenant_id}/{job_id}/solver_input.json"
    data = json.dumps(solver_input, indent=2).encode()
    
    self.s3_client.put_object(
        Bucket=self.bucket,
        Key=object_key,
        Body=data,
        ContentType='application/json'
    )
    
    return f"r2://{self.bucket}/{object_key}"
```

**Presigned URLs** (for direct browser downloads):
```python
def generate_download_url(self, r2_url: str, 
                          expires_in: int = 3600) -> str:
    """Generate presigned URL for browser download."""
    match = re.match(r'r2://([^/]+)/(.+)', r2_url)
    bucket, key = match.groups()
    
    url = self.s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=expires_in
    )
    return url
```

### Database Schema

#### Jobs Table with Audit Trail

```sql
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,      -- SHA256 for idempotency
    payload_pointer TEXT NOT NULL,          -- R2 path or local path
    status job_status NOT NULL DEFAULT 'QUEUED',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Worker metadata
    worker_id VARCHAR(255),
    schema_version VARCHAR(50) NOT NULL DEFAULT '1.0',
    solver_version VARCHAR(50) NOT NULL DEFAULT '1.0',
    time_limit_sec INTEGER NOT NULL DEFAULT 25,
    requested_by VARCHAR(255),
    
    -- Results
    r2_url TEXT,                            -- Result location
    solve_metrics JSONB,                    -- Solver stats
    diagnostics JSONB,                      -- Infeasibility diagnostics
    
    -- Progress tracking
    progress FLOAT DEFAULT 0.0 CHECK (progress >= 0.0 AND progress <= 1.0),
    error_message TEXT
);

CREATE TABLE job_history (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    status job_status NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(255),
    details JSONB
);

-- Automatic status change tracking
CREATE TRIGGER trigger_track_job_status_change
AFTER INSERT OR UPDATE OF status ON jobs
FOR EACH ROW
EXECUTE FUNCTION track_job_status_change();
```

### Observability

#### Sentry Integration

**Error Tracking**:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=SENTRY_DSN,
    environment="production",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% performance monitoring
)
```

**Custom Context**:
```python
with sentry_sdk.push_scope() as scope:
    scope.set_context("job", {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "status": status,
    })
    sentry_sdk.capture_exception(e)
```

#### Structured JSON Logging

```python
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "job_id": getattr(record, 'job_id', None),
            "tenant_id": getattr(record, 'tenant_id', None),
        }
        return json.dumps(log_data)
```

### Production Environment Variables

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJxxx...

# Cloudflare R2
R2_ENDPOINT_URL=https://xxx.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET=timetable-storage

# Redis (Upstash)
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

# Concurrency Limits
MAX_GLOBAL_ACTIVE_SOLVES=10
MAX_PER_TENANT_ACTIVE=3

# Observability
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
LOG_LEVEL=INFO
```

---

## 🎯 How It Works - The Big Picture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TIMETABLE GENERATION FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐│
│  │  FRONTEND│    │   API    │    │SUPABASE/ │    │  SOLVER  │    │   R2   ││
│  │  (React) │───▶│  LAYER   │───▶│  REDIS   │───▶│  (BRAIN) │───▶│ STORAGE││
│  │          │    │          │    │          │    │          │    │        ││
│  │ POST     │    │ Validate │    │ Job Queue│    │ CP-SAT   │    │ Result ││
│  │ /solve   │    │ Create   │    │ Acquire  │    │ Model    │    │  JSON  ││
│  │          │    │ Job ID   │    │Semaphore │    │          │    │        ││
│  │          │◀───│          │    │          │    │          │    │        ││
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └────────┘│
│       │                                                              │      │
│       │  GET /status/{job_id} - Poll for progress (TanStack Query)  │      │
│       │◀─────────────────────────────────────────────────────────────│      │
│       │  GET /result/{job_id} - Retrieve from R2                     │      │
│       │◀─────────────────────────────────────────────────────────────│      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Step-by-Step Process

#### Step 1: Input Submission
```
Client sends POST /solve with:
├── school: Configuration (times, periods, breaks)
├── teachers: List with availability, subjects they teach
├── classes: Sections with subject-teacher mappings
├── subjects: Definitions with weekly requirements
├── resources: Labs, rooms with capacity
└── constraints: Toggles and soft weights
```

#### Step 2: Validation Layer
```
API Layer performs:
├── Pydantic validation (type checking)
├── JSON Schema validation (structure)
└── Pre-flight feasibility check:
    ├── Total periods vs available slots
    ├── Teacher capacity vs requirements
    ├── Resource demand vs supply
    └── Block period feasibility
```

#### Step 3: Job Creation
```
If valid:
├── Generate unique job_id (UUID)
├── Store job in memory queue (QUEUED status)
├── Return job_id to client immediately
└── Start background worker thread
```

#### Step 4: Preprocessing
```
Worker thread runs preprocessing:
├── Generate period grid (all time slots)
├── Build teacher availability masks
├── Create section → subject → teacher mappings
└── Calculate academic vs break periods
```

#### Step 5: Model Building
```
CP-SAT Model Construction:
├── Create X[section][day][period][subject] variables
├── Create B[section][subject][day][period] for blocks
├── Add hard constraints (MUST satisfy)
├── Add soft constraints (preferences)
└── Set objective: minimize(sum(penalties))
```

#### Step 6: Solving
```
CP-SAT Solver runs:
├── Use 4 parallel workers
├── Apply constraint propagation
├── Search for valid assignments
├── Optimize objective function
└── Stop when: optimal/timeout/infeasible
```

#### Step 7: Solution Extraction
```
If solution found:
├── Extract timetable by section
├── Extract teacher schedules
├── Calculate statistics
└── Format as JSON
```

#### Step 8: Result Storage
```
Store in job queue:
├── Update status: COMPLETED/FAILED
├── Store result JSON
├── Record completion time
└── Client can now GET /result/{job_id}
```

---

## 🧠 Understanding Constraint Programming

### What is Constraint Programming (CP)?

Imagine you're solving a Sudoku puzzle. You don't try every possible number combination - instead, you use **rules** to eliminate impossibilities:

- "This row already has a 5, so this cell can't be 5"
- "Only one cell in this column can hold 9"

**Constraint Programming** works the same way, but for much larger problems. It:

1. Defines **variables** (decisions to make)
2. Defines **constraints** (rules that limit valid combinations)
3. Uses smart algorithms to **prune impossible options**
4. Finds solutions that satisfy ALL constraints

### Why NOT Use Brute Force?

Let's calculate the search space for a small school:

```
Variables:
- 10 sections × 6 days × 8 periods × 10 subjects = 4,800 binary variables
- Each variable can be 0 or 1

Brute force combinations: 2^4800 ≈ 10^1445

That's more than atoms in the observable universe (10^80)!
```

CP-SAT uses **intelligent search**:
- **Propagation**: If X=1, then Y must be 0 (reduces search space)
- **Learning**: If combination A,B,C always fails, never try it again
- **Branching**: Make smart choices about which variable to try next

### CP-SAT Solver Explained

CP-SAT stands for **Constraint Programming with SAT (Boolean Satisfiability)**. It combines:

| Technique | What It Does |
|-----------|--------------|
| **Domain Propagation** | Reduces variable domains based on constraints |
| **SAT Solving** | Converts problem to Boolean logic, uses clause learning |
| **Linear Programming** | Handles numerical constraints efficiently |
| **Parallel Search** | Uses multiple CPU cores simultaneously |
| **Lazy Clause Generation** | Generates conflict clauses on-the-fly |

#### How CP-SAT Explores Solutions

```
                        ┌───────────────────────┐
                        │   Start: Empty Slate   │
                        │   All variables = ?    │
                        └───────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │ Try X=1   │   │ Try X=2   │   │ Try X=3   │
            │ Propagate │   │ Propagate │   │ Propagate │
            └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
                  │               │               │
            ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
            │ Conflict! │   │ Continue  │   │ Conflict! │
            │ Backtrack │   │ exploring │   │ Backtrack │
            │ Learn why │   └─────┬─────┘   │ Learn why │
            └───────────┘         │         └───────────┘
                                  │
                            More decisions...
                                  │
                                  ▼
                        ┌───────────────────┐
                        │  Solution Found!   │
                        │  Objective: 23     │
                        │  Keep searching... │
                        └─────────┬─────────┘
                                  │
                                  ▼
                        ┌───────────────────┐
                        │  Better Solution!  │
                        │  Objective: 18     │
                        │  Update best...    │
                        └─────────┬─────────┘
                                  │
                              (repeat)
                                  │
                                  ▼
                        ┌───────────────────┐
                        │  OPTIMAL Found!    │
                        │  Objective: 12     │
                        │  Cannot improve    │
                        └───────────────────┘
```

---

## 🏗 Architecture Deep Dive

### Complete Project Structure

```
Timetable/
│
├── 📁 shared/                          # Shared schemas (used by frontend too)
│   ├── 📁 schemas/
│   │   ├── school.schema.json         # School configuration schema
│   │   ├── teacher.schema.json        # Teacher data schema
│   │   ├── class.schema.json          # Class/section schema
│   │   ├── subject.schema.json        # Subject definition schema
│   │   ├── resource.schema.json       # Resource (labs, rooms) schema
│   │   ├── constraints.schema.json    # Constraint toggles schema
│   │   ├── solver_input.schema.json   # Complete input (combines above)
│   │   └── solver_output.schema.json  # Generated timetable schema
│   └── readme.txt
│
├── 📁 server/                          # Backend application
│   ├── requirements.txt               # Python dependencies
│   └── 📁 app/
│       ├── __init__.py               # Package marker with version
│       ├── main.py                   # FastAPI app entry point
│       ├── config.py                 # Configuration management
│       │
│       ├── 📁 api/                   # REST API endpoints
│       │   ├── __init__.py          # Router exports
│       │   ├── solve.py             # POST /solve endpoint
│       │   ├── status.py            # GET /status/{job_id}
│       │   ├── result.py            # GET /result/{job_id}
│       │   ├── validate.py          # POST /validate (swap check)
│       │   └── upload.py            # POST /upload (file import)
│       │
│       ├── 📁 solver/               # THE BRAIN 🧠
│       │   ├── __init__.py          # Solver exports
│       │   ├── model.py             # TimetableSolver class
│       │   ├── constraints.py       # All constraint implementations
│       │   ├── preprocess.py        # Data transformation
│       │   └── diagnostics.py       # Infeasibility analysis
│       │
│       ├── 📁 jobs/                 # Background job processing
│       │   ├── __init__.py          # Job queue exports
│       │   ├── queue.py             # In-memory job registry
│       │   └── worker.py            # Background thread execution
│       │
│       ├── 📁 parsers/              # File parsing
│       │   ├── __init__.py
│       │   ├── csv_parser.py        # CSV file parsing
│       │   └── excel_parser.py      # Excel file parsing
│       │
│       └── 📁 utils/                # Utilities
│           ├── __init__.py
│           ├── path_helper.py       # Relocatable path management
│           └── validators.py        # JSON Schema validation
│
├── 📁 data/                          # Data storage
│   ├── 📁 raw_uploads/              # Uploaded CSV/Excel files
│   ├── 📁 parsed/                   # Parsed JSON data
│   └── 📁 generated/                # Generated timetable results
│
├── 📁 frontend/                      # React + TypeScript Web UI
│   ├── package.json                 # Dependencies (React 18, Vite, TanStack Query)
│   ├── vite.config.ts               # Vite build configuration
│   ├── tailwind.config.js           # Tailwind CSS styling
│   ├── playwright.config.ts         # E2E testing setup
│   ├── vitest.config.ts             # Unit testing configuration
│   │
│   ├── 📁 public/
│   │   ├── demo-data.json           # Sample data for development
│   │   └── mockServiceWorker.js    # MSW for API mocking
│   │
│   ├── 📁 src/
│   │   ├── main.tsx                 # Application entry point
│   │   ├── App.tsx                  # Root component with routing
│   │   │
│   │   ├── 📁 pages/                # Page components
│   │   │   ├── LandingPage.tsx      # Welcome/home page
│   │   │   ├── UploadPage.tsx       # CSV/Excel file upload
│   │   │   ├── ConstraintsPage.tsx  # Constraint configuration
│   │   │   ├── GeneratePage.tsx     # Job submission & monitoring
│   │   │   ├── ResultsPage.tsx      # Timetable visualization
│   │   │   └── RecentJobsPage.tsx   # Job history & management
│   │   │
│   │   ├── 📁 components/           # Reusable components
│   │   │   ├── TimetableGrid.tsx    # Timetable display grid
│   │   │   └── 📁 ui/               # Radix UI primitives
│   │   │       ├── button.tsx       # Button with variants
│   │   │       ├── dialog.tsx       # Modal dialogs
│   │   │       ├── select.tsx       # Dropdown select
│   │   │       ├── table.tsx        # Data tables
│   │   │       ├── toast.tsx        # Notifications
│   │   │       └── ... (15+ components)
│   │   │
│   │   ├── 📁 lib/                  # Core utilities
│   │   │   ├── api.ts               # API client functions
│   │   │   ├── api-client.ts        # Axios HTTP client
│   │   │   ├── schemas.ts           # Zod validation schemas
│   │   │   └── utils.ts             # Helper functions
│   │   │
│   │   ├── 📁 mocks/                # MSW API mocking
│   │   │   ├── handlers.ts          # Mock API handlers
│   │   │   └── browser.ts           # Browser mock setup
│   │   │
│   │   ├── 📁 layouts/              # Page layouts
│   │   │   └── AppLayout.tsx        # Main app layout
│   │   │
│   │   ├── 📁 stores/               # Zustand state management
│   │   │   └── (future stores)
│   │   │
│   │   └── 📁 test/                 # Unit tests
│   │       ├── setup.ts             # Test configuration
│   │       └── *.test.tsx           # Component tests
│   │
│   └── 📁 e2e/                      # Playwright E2E tests
│       └── app.spec.ts              # End-to-end scenarios
│
├── 📁 migrations/                    # Database migrations (Supabase)
│   └── 001_create_jobs_tables.sql  # Jobs & audit trail schema
│
├── constraints.txt                   # Constraint requirements document
├── prompt.txt                        # Original project specification
├── PRODUCTION_HARDENING_GUIDE.md    # Production deployment guide
└── README.md                         # This file
```

### Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Application                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                              main.py                                     ││
│  │  • App initialization          • CORS middleware                        ││
│  │  • Router registration         • Exception handlers                     ││
│  │  • Lifespan management         • Directory setup                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                     │                                        │
│                    ┌────────────────┼────────────────┐                      │
│                    ▼                ▼                ▼                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│  │   api/solve.py   │ │  api/status.py   │ │  api/result.py   │            │
│  │                  │ │                  │ │                  │            │
│  │ • Input parsing  │ │ • Job lookup     │ │ • Result fetch   │            │
│  │ • Validation     │ │ • Progress calc  │ │ • Format output  │            │
│  │ • Job creation   │ │                  │ │                  │            │
│  └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘            │
│           │                    │                    │                       │
│           ▼                    ▼                    ▼                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         jobs/queue.py                                 │  │
│  │                                                                       │  │
│  │  JobQueue: Thread-safe in-memory registry                            │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │  _jobs: Dict[job_id, Job]                                       │ │  │
│  │  │  _lock: threading.Lock                                          │ │  │
│  │  │                                                                 │ │  │
│  │  │  Job:                                                           │ │  │
│  │  │    • job_id: str                • solver_input: dict            │ │  │
│  │  │    • status: JobStatus          • result: dict                  │ │  │
│  │  │    • progress: 0-100            • error: str                    │ │  │
│  │  │    • created_at, started_at, completed_at                       │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         jobs/worker.py                                │  │
│  │                                                                       │  │
│  │  start_solver_job(job_id, solver_input):                             │  │
│  │    Thread(target=execute_solver_job).start()                         │  │
│  │                                                                       │  │
│  │  execute_solver_job():                                               │  │
│  │    1. Update status → RUNNING                                        │  │
│  │    2. validate_feasibility()                                         │  │
│  │    3. TimetableSolver(input).solve()                                 │  │
│  │    4. analyze_infeasibility() if needed                              │  │
│  │    5. store_result() or store_error()                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     solver/model.py (THE BRAIN)                       │  │
│  │                                                                       │  │
│  │  TimetableSolver:                                                    │  │
│  │    __init__(solver_input):                                           │  │
│  │      • Store input data                                              │  │
│  │      • generate_period_grid()                                        │  │
│  │      • build_all_availability_masks()                                │  │
│  │      • build_section_subject_teacher_map()                           │  │
│  │                                                                       │  │
│  │    build_model():                                                    │  │
│  │      • Create cp_model.CpModel()                                     │  │
│  │      • _create_variables() → X and B variables                       │  │
│  │      • add_all_hard_constraints()                                    │  │
│  │      • add_all_soft_constraints() → penalties                        │  │
│  │      • model.Minimize(sum(penalties))                                │  │
│  │                                                                       │  │
│  │    solve(time_limit, callback):                                      │  │
│  │      • Create CpSolver with parameters                               │  │
│  │      • solver.Solve(model)                                           │  │
│  │      • _extract_timetable()                                          │  │
│  │      • _extract_teacher_schedules()                                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    solver/constraints.py                              │  │
│  │                                                                       │  │
│  │  HARD CONSTRAINTS (11 types):                                        │  │
│  │    add_section_single_subject_constraint()                           │  │
│  │    add_teacher_single_assignment_constraint()                        │  │
│  │    add_subject_frequency_constraint()                                │  │
│  │    add_teacher_load_bounds_constraint()     ← includes balance       │  │
│  │    add_max_consecutive_constraint()                                  │  │
│  │    add_block_period_constraint()                                     │  │
│  │    add_resource_capacity_constraint()                                │  │
│  │    add_class_teacher_period_1_constraint()  ← toggleable             │  │
│  │    add_language_sync_constraint()           ← toggleable             │  │
│  │    add_substitution_reserve_constraint()                             │  │
│  │    add_no_subject_twice_daily_constraint()  ← toggleable             │  │
│  │                                                                       │  │
│  │  SOFT CONSTRAINTS (8 types) → return penalty variables:              │  │
│  │    add_core_morning_preference()                                     │  │
│  │    add_teacher_balance_preference()                                  │  │
│  │    add_minimize_gaps_preference()                                    │  │
│  │    add_leisure_afternoon_preference()                                │  │
│  │    add_avoid_pe_period_1_preference()                                │  │
│  │    add_subject_distribution_preference()                             │  │
│  │    add_teacher_free_period_preference()                              │  │
│  │    add_fair_slot_distribution_preference()                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 File-by-File Implementation Guide

### Core Files Explained

#### 1. `config.py` - Configuration Management

**Purpose:** Centralized configuration with relocatable paths.

**Key Features:**
- **Dynamic project root detection**: Walks up directory tree looking for `shared/` and `data/` markers
- **Environment variable overrides**: All settings can be overridden via `.env` file
- **No hardcoded paths**: Uses `pathlib.Path` for cross-platform compatibility

```python
# How project root is found:
def _find_project_root():
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "shared").is_dir() and (parent / "data").is_dir():
            return parent
    return Path(__file__).parent.parent.parent  # Fallback

# All paths are relative to PROJECT_ROOT:
PROJECT_ROOT = _find_project_root()
DATA_DIR = PROJECT_ROOT / "data"
SCHEMAS_DIR = PROJECT_ROOT / "shared" / "schemas"
```

**Configuration Options:**
| Variable | Default | Environment Override |
|----------|---------|---------------------|
| `SERVER_HOST` | `0.0.0.0` | `SERVER_HOST` |
| `SERVER_PORT` | `8010` | `SERVER_PORT` |
| `SOLVER_TIMEOUT_SECONDS` | `30` | `SOLVER_TIMEOUT` |
| `SOLVER_NUM_WORKERS` | `4` | `SOLVER_NUM_WORKERS` |
| `MAX_CONCURRENT_JOBS` | `5` | `MAX_CONCURRENT_JOBS` |
| `LOG_LEVEL` | `INFO` | `LOG_LEVEL` |

---

#### 2. `main.py` - FastAPI Application Entry

**Purpose:** Application initialization, middleware, routing.

**Lifespan Management:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("Starting Timetable Generator Backend...")
    ensure_dir_exists(DATA_DIR)
    ensure_dir_exists(RAW_UPLOADS_DIR)
    ensure_dir_exists(PARSED_DIR)
    ensure_dir_exists(GENERATED_DIR)
    
    yield  # Application runs here
    
    # SHUTDOWN
    logger.info("Shutting down...")
```

**Registered Routes:**
```python
app.include_router(solve_router, prefix="/api/v1/timetable", tags=["solve"])
app.include_router(status_router, prefix="/api/v1/timetable", tags=["status"])
app.include_router(result_router, prefix="/api/v1/timetable", tags=["result"])
app.include_router(validate_router, prefix="/api/v1/timetable", tags=["validate"])
app.include_router(upload_router, prefix="/api/v1/timetable", tags=["upload"])
```

---

#### 3. `jobs/queue.py` - Job Queue Management

**Purpose:** Thread-safe in-memory job registry.

**Job States:**
```
QUEUED ──▶ RUNNING ──▶ COMPLETED
                 │
                 └──▶ FAILED
```

**Thread Safety:**
```python
class JobQueue:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()  # Protects _jobs dict
    
    def create_job(self, job_id, solver_input):
        with self._lock:  # Acquire lock
            # Safe to modify _jobs
            job = Job(job_id=job_id, ...)
            self._jobs[job_id] = job
        # Lock automatically released
        return job
```

**Job Data Structure:**
```python
@dataclass
class Job:
    job_id: str
    status: JobStatus = QUEUED
    progress: int = 0          # 0-100
    solver_input: dict = {}    # Input data
    result: dict = None        # Output timetable
    error: str = None          # Error message if failed
    created_at: datetime
    started_at: datetime = None
    completed_at: datetime = None
```

---

#### 4. `jobs/worker.py` - Background Execution

**Purpose:** Run solver in separate thread to avoid blocking API.

**Execution Flow:**
```python
def execute_solver_job(job_id, solver_input):
    try:
        # 1. Mark as running
        job_queue.update_status(job_id, RUNNING, progress=5)
        
        # 2. Pre-flight feasibility check
        is_feasible, warnings = validate_feasibility(solver_input)
        if not is_feasible:
            # Store infeasibility result
            job_queue.store_result(job_id, {"status": "INFEASIBLE", ...})
            return
        
        # 3. Build and solve
        solver = TimetableSolver(solver_input)
        result = solver.solve(time_limit=30, progress_callback=...)
        
        # 4. Handle result
        if result["status"] == "INFEASIBLE":
            diagnostics = analyze_infeasibility(solver_input, result["status"])
            result["diagnostics"] = diagnostics
        
        job_queue.store_result(job_id, result)
        
    except Exception as e:
        job_queue.store_error(job_id, str(e))
```

**Progress Callback:**
```python
def progress_callback(percent):
    # Map solver's 0-100 to our 30-90 range
    # (0-30 is preprocessing, 90-100 is post-processing)
    mapped = 30 + int(percent * 0.6)
    job_queue.update_status(job_id, RUNNING, mapped)
```

---

#### 5. `solver/preprocess.py` - Data Transformation

**Purpose:** Transform input data into solver-ready structures.

**Key Functions:**

**`generate_period_grid(school)`** - Creates all time slots:
```python
# Output structure:
[
    {"day": "Mon", "period": 0, "is_prayer": True, "start_time": "08:00", ...},
    {"day": "Mon", "period": 1, "is_prayer": False, "is_recess": False, ...},
    {"day": "Mon", "period": 2, "is_prayer": False, "is_recess": True, ...},  # After recess
    {"day": "Mon", "period": 5, "is_after_lunch": True, ...},  # After lunch
    ...
]
```

**`build_availability_mask(teacher, period_grid)`** - Teacher availability:
```python
# Output: {(day, period): True/False}
{
    ("Mon", 1): True,   # Available
    ("Mon", 2): True,
    ("Sat", 3): False,  # Blocked
    ("Sat", 4): False,
}
```

**`validate_feasibility(solver_input)`** - Pre-flight checks:
```python
# Checks:
# 1. Total required periods <= available slots per section
# 2. Teacher capacity >= assigned subjects
# 3. Block periods can fit in grid
# 4. Resource capacity >= demand
# 5. Substitution reserve < total teachers
# 6. Class teacher actually teaches their section

# Returns: (is_feasible: bool, warnings: list[str])
```

---

#### 6. `solver/model.py` - The Brain

**Purpose:** Build and solve the CP-SAT model.

**TimetableSolver Class:**

```python
class TimetableSolver:
    def __init__(self, solver_input):
        # Store input
        self.school = solver_input["school"]
        self.classes = solver_input["classes"]
        self.teachers = solver_input["teachers"]
        self.subjects = solver_input["subjects"]
        self.resources = solver_input.get("resources", [])
        
        # Build data structures
        self.period_grid = generate_period_grid(self.school)
        self.academic_periods = get_academic_periods(self.period_grid)
        self.periods_by_day = get_periods_by_day(self.academic_periods)
        
        # Build lookup maps
        self.subject_map = {s["subject_id"]: s for s in self.subjects}
        self.teacher_map = {t["teacher_id"]: t for t in self.teachers}
        
        # Build relationships
        self.section_subject_teacher = build_section_subject_teacher_map(self.classes)
        self.availability_masks = build_all_availability_masks(self.teachers, self.period_grid)
```

**Variable Creation:**

```python
def _create_variables(self):
    X = {}  # Primary: X[section][day][period][subject] = BoolVar
    B = {}  # Block: B[section][subject][day][period] = BoolVar
    
    for cls in self.classes:
        section_id = cls["section_id"]
        subjects = cls["subject_teacher_map"].keys()
        
        X[section_id] = {}
        for day in self.weekdays:
            X[section_id][day] = {}
            for period_slot in self.periods_by_day[day]:
                period = period_slot["period"]
                X[section_id][day][period] = {}
                for subject_id in subjects:
                    # Create boolean variable
                    var_name = f"X_{section_id}_{day}_P{period}_{subject_id}"
                    X[section_id][day][period][subject_id] = self.model.NewBoolVar(var_name)
```

**Model Building:**

```python
def build_model(self):
    self.model = cp_model.CpModel()
    
    # 1. Create variables
    self._create_variables()
    
    # 2. Add hard constraints
    add_all_hard_constraints(
        self.model, self.variables, self.solver_input,
        self.academic_periods, self.periods_by_day,
        self.section_subject_teacher, self.availability_masks,
        self.subject_map, self.teacher_map, self.resource_map,
        self.class_teachers,
    )
    
    # 3. Add soft constraints (returns penalty vars)
    self.soft_penalties = add_all_soft_constraints(
        self.model, self.variables, self.solver_input,
        self.academic_periods, self.periods_by_day,
        self.section_subject_teacher, self.subject_map, self.teacher_map,
    )
    
    # 4. Set objective: minimize penalties
    if self.soft_penalties:
        self.model.Minimize(sum(self.soft_penalties))
```

**Solving:**

```python
def solve(self, time_limit=30, progress_callback=None):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 4  # Parallel cores
    solver.parameters.log_search_progress = True
    
    status = solver.Solve(self.model, SolutionCallback(progress_callback))
    
    # Map status
    status_map = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "TIMEOUT",
    }
    
    result = {
        "status": status_map.get(status, "ERROR"),
        "timetable": {},
        "teacher_schedules": {},
        "meta": {...}
    }
    
    if status in (OPTIMAL, FEASIBLE):
        result["timetable"] = self._extract_timetable(solver)
        result["teacher_schedules"] = self._extract_teacher_schedules(solver)
    
    return result
```

---

#### 7. `solver/constraints.py` - Constraint Implementations

**Purpose:** Define all hard and soft constraints.

**(See [Constraint Implementation Details](#-constraint-implementation-details) section for full documentation)**

---

#### 8. `solver/diagnostics.py` - Infeasibility Analysis

**Purpose:** Generate human-readable explanations when solver fails.

**Diagnostic Functions:**

| Function | What It Checks |
|----------|---------------|
| `detect_overloaded_teachers()` | Teacher capacity vs requirements |
| `detect_resource_bottlenecks()` | Resource demand vs supply |
| `detect_impossible_blocks()` | Block periods fit in grid |
| `detect_scheduling_conflicts()` | Total periods vs slots |
| `detect_constraint_conflicts()` | Conflicting constraint settings |
| `suggest_relaxations()` | Prioritized fix suggestions |

**Diagnostic Output:**
```python
{
    "type": "error",      # or "warning", "suggestion"
    "category": "teacher_overload",
    "message": "Teacher 'John Smith' requires 45 periods/week but max is 40",
    "affected_entities": ["T001", "8A/MATH", "8B/MATH"],
    "suggestion": "Reduce subject min_per_week or increase teacher's max_periods_week"
}
```

---

#### 9. `utils/validators.py` - Schema Validation

**Purpose:** Validate input against JSON schemas.

**How It Works:**
```python
def validate_solver_input(data):
    # 1. Load solver_input.schema.json
    schema = _load_schema("solver_input")
    
    # 2. Create resolver for $ref references
    resolver = _get_resolver()  # Loads all schemas into store
    
    # 3. Validate
    validator = Draft7Validator(schema, resolver=resolver)
    errors = list(validator.iter_errors(data))
    
    # 4. Format errors
    error_messages = [_format_validation_error(e) for e in errors]
    
    return (len(errors) == 0, error_messages)
```

---

## 🧪 The Brain: CP-SAT Solver

### Decision Variables

The solver needs to make decisions. Each decision is represented by a **variable**.

#### Primary Variables: X[section][day][period][subject]

These are **boolean** (0 or 1) variables. If `X["8A"]["Mon"][3]["MATH"] = 1`, it means:

> "Class 8A has Mathematics scheduled on Monday, Period 3"

```python
# Variable naming convention:
# X_{section}_{day}_P{period}_{subject}
# Example: X_8A_Mon_P3_MATH

# Total variables for one class:
# subjects × days × periods = 10 × 6 × 8 = 480 variables
```

**Variable Count Example:**
| School Size | Sections | Subjects | Days | Periods | Total X Variables |
|-------------|----------|----------|------|---------|-------------------|
| Small | 10 | 10 | 6 | 8 | 4,800 |
| Medium | 30 | 12 | 6 | 8 | 17,280 |
| Large | 60 | 15 | 6 | 8 | 43,200 |

#### Block Variables: B[section][subject][day][period]

For subjects needing consecutive periods (like labs):

```python
# B = 1 means "block STARTS at this period"
# If B["8A"]["PHY_LAB"]["Mon"][3] = 1:
#   → X["8A"]["Mon"][3]["PHY_LAB"] = 1
#   → X["8A"]["Mon"][4]["PHY_LAB"] = 1
```

### Constraint Types Explained

#### Hard Constraints vs Soft Constraints

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONSTRAINT COMPARISON                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  HARD CONSTRAINTS                    SOFT CONSTRAINTS                   │
│  ════════════════                    ════════════════                   │
│                                                                          │
│  ✗ MUST be satisfied                 ✓ Preferences only                │
│  ✗ Violation = No solution           ✓ Violation = Higher penalty       │
│                                                                          │
│  Implementation:                     Implementation:                    │
│  model.Add(sum(vars) <= 1)          penalty = model.NewIntVar(0, 10)   │
│                                      model.Add(penalty >= violation)    │
│                                      penalties.append(weight * penalty) │
│                                                                          │
│  Examples:                           Examples:                          │
│  • Teacher can't be in 2 places     • Prefer math in morning           │
│  • Subject frequency limits         • Minimize teacher gaps             │
│  • Resource capacity                • Balance teacher loads             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Objective Function

The solver **minimizes** the sum of all soft constraint penalties:

```python
objective = (
    weight_core_morning × penalty_core_after_lunch +
    weight_teacher_balance × penalty_load_variance +
    weight_minimize_gaps × penalty_gap_count +
    weight_leisure_afternoon × penalty_leisure_morning +
    weight_avoid_pe × penalty_pe_bad_slots +
    weight_subject_distribution × penalty_clustering +
    weight_teacher_free × penalty_no_free_period +
    weight_fair_slots × penalty_unfair_distribution
)

model.Minimize(objective)
```

**Solver Outcomes:**

| Status | Meaning | Objective |
|--------|---------|-----------|
| `OPTIMAL` | Best possible solution found | Proven minimum |
| `FEASIBLE` | Valid solution, maybe not best | Good, but improvable |
| `INFEASIBLE` | No valid solution exists | N/A |
| `TIMEOUT` | Time limit reached | Unknown |

---

## 📋 Constraint Implementation Details

### Hard Constraints (11 Types)

#### 1. Section Single Subject Constraint
**Rule:** Each section can have only ONE subject per period.

**Why Needed:** You can't teach Math AND English simultaneously to the same class.

**Implementation:**
```python
def add_section_single_subject_constraint(model, variables, classes, periods_by_day):
    X = variables["X"]
    
    for cls in classes:
        section_id = cls["section_id"]
        subjects = cls["subject_teacher_map"].keys()
        
        for day, periods in periods_by_day.items():
            for period_slot in periods:
                period = period_slot["period"]
                
                # Sum of all subjects at this slot must be <= 1
                slot_vars = [X[section_id][day][period][subj] for subj in subjects]
                model.Add(sum(slot_vars) <= 1)
```

**Mathematical Form:**
$$\sum_{s \in \text{subjects}} X_{section,day,period,s} \leq 1$$

---

#### 2. Teacher Single Assignment Constraint
**Rule:** A teacher can teach only ONE class per period.

**Why Needed:** Mr. Smith can't be in Room 101 AND Room 205 simultaneously.

**Implementation:**
```python
def add_teacher_single_assignment_constraint(model, variables, ...):
    X = variables["X"]
    
    # Build teacher → [(section, subject)] mapping
    teacher_assignments = {}
    for section_id, subject_teacher in section_subject_teacher.items():
        for subject_id, teacher_id in subject_teacher.items():
            teacher_assignments.setdefault(teacher_id, []).append((section_id, subject_id))
    
    for teacher in teachers:
        teacher_id = teacher["teacher_id"]
        assignments = teacher_assignments.get(teacher_id, [])
        
        for day, periods in periods_by_day.items():
            for period_slot in periods:
                period = period_slot["period"]
                
                # Collect all assignment vars for this teacher at this time
                teacher_vars = [
                    X[section][day][period][subject]
                    for section, subject in assignments
                    if subject in X[section][day][period]
                ]
                
                # Teacher can only be in one place
                model.Add(sum(teacher_vars) <= 1)
                
                # If unavailable, force to 0
                if not availability[teacher_id].get((day, period), True):
                    for var in teacher_vars:
                        model.Add(var == 0)
```

---

#### 3. Subject Frequency Constraint
**Rule:** Each subject must get its required weekly periods.

**Why Needed:** Math needs 6-7 periods/week, not 3 or 10.

```python
def add_subject_frequency_constraint(model, variables, classes, periods_by_day, subject_map):
    X = variables["X"]
    
    for cls in classes:
        section_id = cls["section_id"]
        
        for subject_id in cls["subject_teacher_map"].keys():
            subject = subject_map.get(subject_id)
            min_week = subject.get("min_per_week", 0)
            max_week = subject.get("max_per_week", 10)
            
            # Sum of all assignments for this subject across the week
            all_vars = [
                X[section_id][day][period]["subject_id"]
                for day, periods in periods_by_day.items()
                for period_slot in periods
                if subject_id in X[section_id][day][period_slot["period"]]
            ]
            
            model.Add(sum(all_vars) >= min_week)
            model.Add(sum(all_vars) <= max_week)
```

---

#### 4. Teacher Load Bounds Constraint (with Balance)
**Rule:** Teachers have daily/weekly limits AND load must be balanced.

**Why Needed:** Prevent 7 periods Monday, 2 periods Tuesday.

```python
def add_teacher_load_bounds_constraint(model, variables, ...):
    max_variance = constraints_config.get("max_daily_load_variance", 3)
    
    for teacher in teachers:
        min_day = teacher.get("min_periods_day", 0)
        max_day = teacher.get("max_periods_day", 8)
        
        daily_loads = []
        
        for day, periods in periods_by_day.items():
            daily_vars = [...get assignment vars for this day...]
            
            # Daily bounds
            model.Add(sum(daily_vars) >= min_day)
            model.Add(sum(daily_vars) <= max_day)
            
            # Track daily load for balance
            daily_load = model.NewIntVar(0, max_day, f"load_{teacher_id}_{day}")
            model.Add(daily_load == sum(daily_vars))
            daily_loads.append(daily_load)
        
        # BALANCE CONSTRAINT
        if len(daily_loads) >= 2:
            max_load = model.NewIntVar(0, max_day, f"max_daily_{teacher_id}")
            min_load = model.NewIntVar(0, max_day, f"min_daily_{teacher_id}")
            model.AddMaxEquality(max_load, daily_loads)
            model.AddMinEquality(min_load, daily_loads)
            
            # Max variance allowed
            model.Add(max_load - min_load <= max_variance)
```

---

#### 5. Max Consecutive Constraint
**Rule:** Teachers can't teach more than N consecutive periods without a break.

**Why Needed:** Teachers need rest; prevents fatigue.

```python
def add_max_consecutive_constraint(model, variables, ...):
    max_consecutive = 3  # Default
    
    for teacher in teachers:
        for day, periods in periods_by_day.items():
            sorted_periods = sorted(periods, key=lambda p: p["period"])
            
            # Sliding window of (max_consecutive + 1) periods
            window_size = max_consecutive + 1
            
            for i in range(len(sorted_periods) - window_size + 1):
                window = sorted_periods[i:i + window_size]
                
                # Skip if window crosses a break
                if any(p.get("is_recess") or p.get("is_after_lunch") for p in window[1:]):
                    continue
                
                # Get teacher's assignment vars for this window
                window_vars = [...]
                
                # Sum in window must be <= max_consecutive
                model.Add(sum(window_vars) <= max_consecutive)
```

---

#### 6. Block Period Constraint
**Rule:** Lab subjects needing N consecutive periods must get contiguous slots.

**Why Needed:** Can't split a 2-hour lab into non-adjacent periods.

```python
def add_block_period_constraint(model, variables, ...):
    for cls in classes:
        for subject_id in cls["subject_teacher_map"].keys():
            subject = subject_map.get(subject_id)
            
            if not subject.get("requires_block"):
                continue
            
            block_length = subject.get("block_length", 2)
            
            for day, periods in periods_by_day.items():
                sorted_periods = sorted(periods, key=lambda p: p["period"])
                
                for i, period_slot in enumerate(sorted_periods):
                    period = period_slot["period"]
                    block_start_var = B[section_id][subject_id][day][period]
                    
                    # Check if block can start here
                    can_start = True
                    consecutive = [period_slot]
                    
                    for j in range(1, block_length):
                        if i + j >= len(sorted_periods):
                            can_start = False
                            break
                        next_p = sorted_periods[i + j]
                        if next_p.get("is_recess") or next_p.get("is_after_lunch"):
                            can_start = False  # Can't cross break
                            break
                        consecutive.append(next_p)
                    
                    if not can_start:
                        model.Add(block_start_var == 0)
                    else:
                        # If block starts here, all periods must have this subject
                        for p in consecutive:
                            model.Add(X[section][day][p["period"]][subject] >= block_start_var)
```

---

#### 7. Resource Capacity Constraint
**Rule:** Limited resources can only serve N sections simultaneously.

**Why Needed:** Only 2 computer labs, so max 2 sections can have CS at once.

```python
def add_resource_capacity_constraint(model, variables, ...):
    # Build resource → [(section, subject)] mapping
    resource_demands = {}
    for cls in classes:
        for subject_id in cls["subject_teacher_map"].keys():
            subject = subject_map.get(subject_id)
            if subject.get("requires_resource"):
                resource_type = subject.get("resource_type")
                resource_demands.setdefault(resource_type, []).append((section_id, subject_id))
    
    for resource_type, demands in resource_demands.items():
        capacity = resource_map[resource_type].get("max_simultaneous_capacity", 1)
        
        for day, periods in periods_by_day.items():
            for period_slot in periods:
                period = period_slot["period"]
                
                # All sections using this resource at this time
                resource_vars = [X[s][day][period][subj] for s, subj in demands]
                
                model.Add(sum(resource_vars) <= capacity)
```

---

#### 8. Class Teacher Period 1 Constraint (Toggleable)
**Rule:** Class teacher gets Period 1 every day with their section.

**Toggle:** `constraints.class_teacher_period_1` (default: `true`)

```python
def add_class_teacher_period_1_constraint(model, variables, ...):
    for cls in classes:
        section_id = cls["section_id"]
        class_teacher_id = class_teachers.get(section_id)
        
        if not class_teacher_id:
            continue
        
        # Find subjects this teacher teaches to this section
        teacher_subjects = [
            subj for subj, teacher in section_subject_teacher[section_id].items()
            if teacher == class_teacher_id
        ]
        
        for day, periods in periods_by_day.items():
            # Find Period 1
            period_1 = next((p for p in periods if p["period"] == 1), None)
            if not period_1:
                continue
            
            # Teacher must teach one of their subjects in P1
            p1_vars = [X[section_id][day][1][subj] for subj in teacher_subjects]
            model.Add(sum(p1_vars) >= 1)
```

---

#### 9. Language Sync Constraint (Toggleable)
**Rule:** When language block is scheduled, ALL language teachers must be assigned.

**Toggle:** `constraints.language_sync_enabled` (default: `true`)

**Why Needed:** Students split into Hindi/Kannada/Sanskrit/French groups. All teachers must be free simultaneously.

```python
def add_language_sync_constraint(model, variables, ...):
    for cls in classes:
        section_id = cls["section_id"]
        
        # Find language subjects and teachers
        language_subjects = []
        for subject_id, teacher_id in cls["subject_teacher_map"].items():
            subject = subject_map.get(subject_id)
            if is_language_subject(subject):  # Check name, category, flag
                language_subjects.append((subject_id, teacher_id))
        
        if len(language_subjects) < 2:
            continue  # No sync needed
        
        for day, periods in periods_by_day.items():
            for period_slot in periods:
                period = period_slot["period"]
                
                # If ANY language is taught, ALL must be taught
                lang_vars = [X[section_id][day][period][s] for s, _ in language_subjects]
                
                any_lang = model.NewBoolVar(f"any_lang_{section_id}_{day}_P{period}")
                model.AddMaxEquality(any_lang, lang_vars)
                
                # If any_lang, all languages must be scheduled
                for subject_id, _ in language_subjects:
                    model.Add(X[section_id][day][period][subject_id] >= any_lang)
```

---

#### 10. Substitution Reserve Constraint
**Rule:** At each period, N teachers must be kept free for emergencies.

```python
def add_substitution_reserve_constraint(model, variables, ..., reserve_count):
    num_teachers = len(teachers)
    
    for day, periods in periods_by_day.items():
        for period_slot in periods:
            period = period_slot["period"]
            
            # Count assigned teachers
            assigned_vars = []
            for teacher_id, assignments in teacher_assignments.items():
                teacher_vars = [...]  # Get all this teacher's assignments at this time
                
                if teacher_vars:
                    is_assigned = model.NewBoolVar(f"assigned_{teacher_id}_{day}_P{period}")
                    model.AddMaxEquality(is_assigned, teacher_vars)
                    assigned_vars.append(is_assigned)
            
            # Assigned teachers <= total - reserve
            model.Add(sum(assigned_vars) <= num_teachers - reserve_count)
```

---

#### 11. No Subject Twice Daily (Toggleable)
**Rule:** Same subject can't appear twice in one day (except lab blocks).

**Toggle:** `constraints.no_subject_twice_daily` (default: `false`)

```python
def add_no_subject_twice_daily_constraint(model, variables, ...):
    for cls in classes:
        for subject_id in cls["subject_teacher_map"].keys():
            subject = subject_map.get(subject_id)
            
            # Skip block subjects (they need multiple periods)
            if subject.get("requires_block"):
                continue
            
            for day, periods in periods_by_day.items():
                day_vars = [X[section_id][day][p["period"]][subject_id] for p in periods]
                model.Add(sum(day_vars) <= 1)
```

---

### Soft Constraints (8 Types)

#### 1. Core Morning Preference (Weight: 3)
**Preference:** Schedule Math, Science in morning (P1-3).

```python
def add_core_morning_preference(model, variables, ..., weight):
    penalties = []
    
    for cls in classes:
        core_subjects = [s for s in cls["subjects"] if subject_map[s]["category"] == "core"]
        
        for subject_id in core_subjects:
            for day, periods in periods_by_day.items():
                for period_slot in periods:
                    if period_slot.get("is_after_lunch"):
                        # Penalize core after lunch
                        penalty = model.NewBoolVar(f"core_after_lunch_...")
                        model.Add(penalty >= X[section][day][period][subject_id])
                        penalties.append(weight * penalty)
    
    return penalties
```

---

#### 2. Teacher Balance Preference (Weight: 10)
**Preference:** Minimize variance in daily load across week.

```python
def add_teacher_balance_preference(model, variables, ..., weight):
    penalties = []
    
    for teacher_id, assignments in teacher_assignments.items():
        daily_loads = []
        
        for day in weekdays:
            daily_load = model.NewIntVar(0, 10, f"load_{teacher_id}_{day}")
            daily_vars = [...]  # Count periods this day
            model.Add(daily_load == sum(daily_vars))
            daily_loads.append(daily_load)
        
        # Variance = max - min
        max_load = model.NewIntVar(0, 10, f"max_{teacher_id}")
        min_load = model.NewIntVar(0, 10, f"min_{teacher_id}")
        model.AddMaxEquality(max_load, daily_loads)
        model.AddMinEquality(min_load, daily_loads)
        
        variance = model.NewIntVar(0, 10, f"var_{teacher_id}")
        model.Add(variance == max_load - min_load)
        penalties.append(weight * variance)
    
    return penalties
```

---

#### 3. Minimize Gaps Preference (Weight: 5)
**Preference:** Avoid idle gaps (P1, Free, Free, P4).

```python
def add_minimize_gaps_preference(model, variables, ..., weight):
    penalties = []
    
    for teacher_id, assignments in teacher_assignments.items():
        for day, periods in periods_by_day.items():
            sorted_periods = sorted(periods)
            
            for i in range(1, len(sorted_periods) - 1):
                # Check if: teaching before, free now, teaching after
                has_prev = model.NewBoolVar(...)
                has_next = model.NewBoolVar(...)
                is_free = model.NewBoolVar(...)
                
                # is_gap = has_prev AND has_next AND is_free
                is_gap = model.NewBoolVar(...)
                model.AddBoolAnd([has_prev, has_next, is_free]).OnlyEnforceIf(is_gap)
                
                penalties.append(weight * is_gap)
    
    return penalties
```

---

#### 4-8. Other Soft Constraints

| Constraint | Weight | What It Does |
|------------|--------|--------------|
| Leisure Afternoon | 2 | Penalize PE/Art/Music in morning |
| Avoid PE Period 1 | 4 | Penalize PE in P1 or after lunch |
| Subject Distribution | 3 | Penalize >2 of heavy subject per day |
| Teacher Free Period | 2 | Penalize no free period in day |
| Fair Slot Distribution | 5 | Penalize unfair "bad slot" distribution |

---

## 🔄 Data Flow: From Input to Timetable

### Complete Data Transformation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT (JSON)                                                               │
│  ════════════                                                               │
│  {                                                                          │
│    "school": {                                                              │
│      "start_time": "08:00",                                                 │
│      "periods_per_weekday": 8,                                              │
│      "saturday_periods": 4,                                                 │
│      "lunch_period_index": 4,                                               │
│      "recess_period_indices": [2]                                           │
│    },                                                                       │
│    "teachers": [...],                                                       │
│    "classes": [...],                                                        │
│    "subjects": [...],                                                       │
│    "constraints": {...}                                                     │
│  }                                                                          │
│                                                                              │
│                               ▼                                              │
│                                                                              │
│  PREPROCESSING (preprocess.py)                                              │
│  ═════════════════════════════                                              │
│                                                                              │
│  generate_period_grid() ─────────────────────────────────────────────────▶ │
│  [                                                                          │
│    {day: "Mon", period: 0, is_prayer: true, start: "08:00", end: "08:15"}, │
│    {day: "Mon", period: 1, is_prayer: false, start: "08:15", end: "08:55"},│
│    {day: "Mon", period: 2, is_recess: true, start: "08:55", end: "09:35"}, │
│    ...                                                                      │
│  ]                                                                          │
│                                                                              │
│  build_availability_masks() ─────────────────────────────────────────────▶ │
│  {                                                                          │
│    "T001": {("Mon", 1): true, ("Mon", 2): true, ("Sat", 4): false, ...},   │
│    "T002": {...},                                                           │
│  }                                                                          │
│                                                                              │
│  build_section_subject_teacher_map() ────────────────────────────────────▶ │
│  {                                                                          │
│    "8A": {"MATH": "T001", "ENG": "T002", "SCI": "T003", ...},               │
│    "8B": {"MATH": "T001", "ENG": "T004", ...},                              │
│  }                                                                          │
│                                                                              │
│                               ▼                                              │
│                                                                              │
│  MODEL BUILDING (model.py)                                                  │
│  ═════════════════════════                                                  │
│                                                                              │
│  _create_variables() ────────────────────────────────────────────────────▶ │
│  X["8A"]["Mon"][1]["MATH"] = BoolVar("X_8A_Mon_P1_MATH")                    │
│  X["8A"]["Mon"][1]["ENG"]  = BoolVar("X_8A_Mon_P1_ENG")                     │
│  X["8A"]["Mon"][2]["MATH"] = BoolVar("X_8A_Mon_P2_MATH")                    │
│  ... (thousands of variables)                                               │
│                                                                              │
│  add_all_hard_constraints() ─────────────────────────────────────────────▶ │
│  model.Add(X_8A_Mon_P1_MATH + X_8A_Mon_P1_ENG + ... <= 1)  # Single subj   │
│  model.Add(X_8A_Mon_P1_MATH + X_8B_Mon_P1_MATH <= 1)       # Teacher once  │
│  model.Add(sum(X_8A_*_*_MATH) >= 6)                        # Min frequency │
│  model.Add(sum(X_8A_*_*_MATH) <= 7)                        # Max frequency │
│  ...                                                                        │
│                                                                              │
│  add_all_soft_constraints() ─────────────────────────────────────────────▶ │
│  penalties = [                                                              │
│    3 * penalty_core_after_lunch,                                           │
│    10 * penalty_teacher_variance,                                          │
│    5 * penalty_gap,                                                        │
│    ...                                                                      │
│  ]                                                                          │
│  model.Minimize(sum(penalties))                                             │
│                                                                              │
│                               ▼                                              │
│                                                                              │
│  SOLVING (CP-SAT)                                                           │
│  ════════════════                                                           │
│                                                                              │
│  CpSolver.Solve(model) ──────────────────────────────────────────────────▶ │
│  • Parallel search (4 workers)                                              │
│  • Constraint propagation                                                   │
│  • Conflict learning                                                        │
│  • Objective optimization                                                   │
│                                                                              │
│  Status: OPTIMAL | FEASIBLE | INFEASIBLE | TIMEOUT                         │
│                                                                              │
│                               ▼                                              │
│                                                                              │
│  EXTRACTION                                                                  │
│  ══════════                                                                  │
│                                                                              │
│  _extract_timetable() ───────────────────────────────────────────────────▶ │
│  for each section, day, period:                                             │
│    if solver.Value(X[section][day][period][subject]) == 1:                 │
│      assigned_subject = subject                                             │
│      assigned_teacher = section_subject_teacher[section][subject]          │
│                                                                              │
│                               ▼                                              │
│                                                                              │
│  OUTPUT (JSON)                                                              │
│  ═════════════                                                              │
│  {                                                                          │
│    "status": "OPTIMAL",                                                     │
│    "timetable": {                                                           │
│      "8A": {                                                                │
│        "Mon": [                                                             │
│          {"period": 1, "subject_id": "MATH", "teacher_id": "T001",         │
│           "subject_name": "Mathematics", "teacher_name": "John Smith",     │
│           "start_time": "08:15", "end_time": "08:55"},                     │
│          {"period": 2, "subject_id": "ENG", "teacher_id": "T002", ...},    │
│          ...                                                                │
│        ],                                                                   │
│        "Tue": [...],                                                        │
│      },                                                                     │
│      "8B": {...}                                                            │
│    },                                                                       │
│    "teacher_schedules": {                                                   │
│      "T001": {                                                              │
│        "Mon": [                                                             │
│          {"period": 1, "section_id": "8A", "subject_id": "MATH"},          │
│          {"period": 3, "section_id": "8B", "subject_id": "MATH"},          │
│        ]                                                                    │
│      }                                                                      │
│    },                                                                       │
│    "meta": {                                                                │
│      "solve_time_seconds": 12.5,                                           │
│      "variables_count": 4800,                                              │
│      "constraints_count": 15420,                                           │
│      "objective_value": 23                                                 │
│    }                                                                        │
│  }                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📡 API Reference

### Base URL
```
http://localhost:8010/api/v1/timetable
```

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/solve` | Submit timetable generation job |
| `GET` | `/status/{job_id}` | Check job progress |
| `GET` | `/result/{job_id}` | Get generated timetable |
| `POST` | `/validate` | Validate manual swap |
| `POST` | `/upload` | Upload CSV/Excel data |

---

### POST /solve

Start a new timetable generation job.

**Request:**
```json
{
  "school": {
    "school_id": 1,
    "name": "ABC School",
    "start_time": "08:00",
    "end_time": "15:30",
    "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    "periods_per_weekday": 8,
    "saturday_periods": 4,
    "period_duration_minutes": 40,
    "prayer_enabled": true,
    "prayer_duration_minutes": 15,
    "lunch_period_index": 4,
    "lunch_duration_minutes": 30,
    "recess_period_indices": [2],
    "recess_duration_minutes": 15
  },
  "teachers": [
    {
      "teacher_id": "T001",
      "name": "John Smith",
      "subjects_can_teach": ["MATH", "PHY"],
      "min_periods_day": 3,
      "max_periods_day": 6,
      "min_periods_week": 20,
      "max_periods_week": 30,
      "max_consecutive_periods": 3,
      "availability": {
        "Mon": {"available": true},
        "Sat": {"available": true, "blocked_periods": [3, 4]}
      }
    }
  ],
  "classes": [
    {
      "section_id": "8A",
      "grade": 8,
      "class_teacher_id": "T001",
      "subject_teacher_map": {
        "MATH": "T001",
        "ENG": "T002",
        "SCI": "T003"
      }
    }
  ],
  "subjects": [
    {
      "subject_id": "MATH",
      "name": "Mathematics",
      "category": "core",
      "min_per_week": 6,
      "max_per_week": 7,
      "requires_block": false
    },
    {
      "subject_id": "PHY_LAB",
      "name": "Physics Lab",
      "category": "core",
      "min_per_week": 2,
      "max_per_week": 2,
      "requires_block": true,
      "block_length": 2,
      "requires_resource": true,
      "resource_type": "physics_lab"
    }
  ],
  "resources": [
    {
      "resource_id": "LAB1",
      "resource_type": "physics_lab",
      "name": "Physics Laboratory",
      "max_simultaneous_capacity": 1
    }
  ],
  "constraints": {
    "prayer_enabled": true,
    "language_sync_enabled": true,
    "class_teacher_period_1": true,
    "no_subject_twice_daily": false,
    "substitution_reserve_count": 3,
    "max_consecutive_default": 3,
    "soft_weights": {
      "core_morning": 3,
      "teacher_balance": 10,
      "minimize_gaps": 5,
      "leisure_afternoon": 2,
      "avoid_pe_period_1": 4,
      "subject_distribution": 3,
      "teacher_free_period": 2,
      "fair_slot_distribution": 5
    }
  },
  "time_limit_seconds": 30
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Timetable generation started",
  "warnings": ["Teacher T001 has high load: 28-30 periods/week"]
}
```

**Error Response (400/422):**
```json
{
  "error": true,
  "detail": {
    "message": "Input validation failed",
    "errors": ["Field 'school -> start_time': '25:00' is not a valid time"]
  }
}
```

---

### GET /status/{job_id}

Check job progress.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 65,
  "created_at": "2025-01-24T10:30:00Z",
  "started_at": "2025-01-24T10:30:01Z",
  "completed_at": null,
  "error": null
}
```

**Status Values:**
| Status | Progress | Meaning |
|--------|----------|---------|
| `queued` | 0 | Waiting to start |
| `running` | 5-95 | Solver working |
| `completed` | 100 | Success, result available |
| `failed` | N/A | Error occurred |

---

### GET /result/{job_id}

Get generated timetable (only when completed).

**Response:**
```json
{
  "status": "OPTIMAL",
  "timetable": {
    "8A": {
      "Mon": [
        {
          "period": 1,
          "subject_id": "MATH",
          "subject_name": "Mathematics",
          "teacher_id": "T001",
          "teacher_name": "John Smith",
          "start_time": "08:15",
          "end_time": "08:55",
          "is_block_start": false,
          "is_block_continuation": false
        },
        {
          "period": 2,
          "subject_id": "ENG",
          "subject_name": "English",
          "teacher_id": "T002",
          "teacher_name": "Jane Doe",
          "start_time": "08:55",
          "end_time": "09:35",
          "is_block_start": false,
          "is_block_continuation": false
        }
      ],
      "Tue": [...]
    },
    "8B": {...}
  },
  "teacher_schedules": {
    "T001": {
      "Mon": [
        {"period": 1, "section_id": "8A", "subject_id": "MATH"},
        {"period": 3, "section_id": "8B", "subject_id": "MATH"}
      ],
      "Tue": [...]
    }
  },
  "meta": {
    "solve_time_seconds": 12.5,
    "variables_count": 4800,
    "constraints_count": 15420,
    "objective_value": 23,
    "solver_status_code": 4
  },
  "diagnostics": [],
  "warnings": []
}
```

---

### POST /validate

Validate a manual schedule change.

**Request:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "section_id": "8A",
  "day": "Mon",
  "period_from": 3,
  "period_to": 5
}
```

**Response (Valid):**
```json
{
  "valid": true,
  "message": "Swap is valid"
}
```

**Response (Invalid):**
```json
{
  "valid": false,
  "violations": [
    {
      "type": "teacher_conflict",
      "message": "Teacher T001 is already teaching at period 5 in section 8B",
      "affected_entities": ["T001", "8A", "8B"]
    }
  ],
  "message": "Swap would violate constraints"
}
```

---

## 📊 JSON Schemas Explained

All schemas are in `/shared/schemas/` and use JSON Schema Draft-07.

### Schema Relationships

```
                    solver_input.schema.json
                    ┌────────────────────────┐
                    │     SOLVER INPUT       │
                    │  (Main Entry Point)    │
                    └───────────┬────────────┘
                                │
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐
   │ school  │ │teachers │ │ classes │ │subjects │ │constraints│
   │ .schema │ │ .schema │ │ .schema │ │ .schema │ │  .schema  │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   resource.schema.json  │
                    │      (optional)         │
                    └─────────────────────────┘
```

### Schema Files

| Schema | Description | Key Fields |
|--------|-------------|------------|
| `school.schema.json` | School configuration | `start_time`, `periods_per_weekday`, `lunch_period_index` |
| `teacher.schema.json` | Teacher definitions | `subjects_can_teach`, `availability`, `max_periods_day` |
| `class.schema.json` | Class/section | `subject_teacher_map`, `class_teacher_id` |
| `subject.schema.json` | Subject definitions | `min_per_week`, `requires_block`, `category` |
| `resource.schema.json` | Labs, rooms | `max_simultaneous_capacity` |
| `constraints.schema.json` | Toggles and weights | `soft_weights`, toggle booleans |
| `solver_input.schema.json` | Complete input | Combines all above |
| `solver_output.schema.json` | Generated timetable | `timetable`, `teacher_schedules`, `meta` |

---

## ⚙️ Configuration Options

### Environment Variables

Create a `.env` file in `/server/`:

```bash
# Server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8010

# Solver settings
SOLVER_TIMEOUT=60          # Seconds
SOLVER_NUM_WORKERS=8       # CPU cores

# Job settings
MAX_CONCURRENT_JOBS=10
JOB_RETENTION_HOURS=48

# Logging
LOG_LEVEL=DEBUG
```

### Constraint Configuration

```json
{
  "constraints": {
    // Hard constraint toggles
    "prayer_enabled": true,          // Period 0 for assembly
    "language_sync_enabled": true,   // Sync language teachers
    "class_teacher_period_1": true,  // Class teacher gets P1
    "no_subject_twice_daily": false, // Prevent subject twice/day
    
    // Hard constraint parameters
    "substitution_reserve_count": 3, // Free teachers per period
    "max_consecutive_default": 3,    // Max consecutive for teachers
    "max_daily_load_variance": 3,    // Max daily load difference
    
    // Soft constraint weights (0 = disabled)
    "soft_weights": {
      "core_morning": 3,             // Prefer core in morning
      "teacher_balance": 10,         // Balance daily loads
      "minimize_gaps": 5,            // Minimize idle gaps
      "leisure_afternoon": 2,        // Prefer PE/Art in afternoon
      "avoid_pe_period_1": 4,        // Avoid PE in P1
      "subject_distribution": 3,     // Distribute subjects evenly
      "teacher_free_period": 2,      // Give free period daily
      "fair_slot_distribution": 5    // Fair "bad slot" distribution
    }
  }
}
```

---

## 🩺 Error Handling & Diagnostics

### Infeasibility Diagnostics

When solver returns `INFEASIBLE`, the diagnostics system analyzes why:

```json
{
  "status": "INFEASIBLE",
  "diagnostics": [
    {
      "type": "error",
      "category": "teacher_overload",
      "message": "Teacher 'John Smith' requires minimum 45 periods/week but has max_periods_week of 40",
      "affected_entities": ["T001", "8A/MATH", "8B/MATH", "9A/MATH"],
      "suggestion": "Reduce subject min_per_week or increase teacher's max_periods_week"
    },
    {
      "type": "error",
      "category": "resource_bottleneck",
      "message": "Resource 'computer_lab' demand (60 periods) exceeds weekly capacity (40 = 1 × 40 slots)",
      "affected_entities": ["8A/CS", "8B/CS", "9A/CS"],
      "suggestion": "Increase computer_lab capacity or reduce subject requirements"
    },
    {
      "type": "suggestion",
      "category": "relaxation",
      "message": "Consider reassigning some subjects to other teachers or hiring additional teachers"
    }
  ]
}
```

### Diagnostic Categories

| Category | Type | Cause |
|----------|------|-------|
| `teacher_overload` | error | Teacher capacity < required |
| `teacher_high_load` | warning | Teacher at >80% capacity |
| `resource_bottleneck` | error | Resource demand > supply |
| `resource_tight` | warning | Resource at >90% capacity |
| `impossible_block` | error | Block can't fit in any day |
| `tight_block` | warning | Limited block positions |
| `slot_overflow` | error | Section needs more than available |
| `slot_underflow` | warning | Many empty periods |
| `constraint_conflict` | error | Conflicting constraints |
| `constraint_tight` | warning | Constraints very restrictive |

---

## 🔧 Troubleshooting

### Common Issues

#### "INFEASIBLE" Status

The solver couldn't find any valid solution.

**Check:**
1. Total required periods ≤ available slots per section
2. Teachers have capacity for assigned subjects
3. Resource demand ≤ resource capacity
4. Block periods can fit in grid
5. Substitution reserve < total teachers

**Quick Fix:**
- Review diagnostics in response
- Reduce `min_per_week` values
- Increase teacher `max_periods_week`
- Add more resources or teachers

---

#### "TIMEOUT" Status

Solver ran out of time before finding solution.

**Check:**
1. Time limit (default 30s)
2. Problem size (sections × subjects × periods)
3. Constraint complexity

**Quick Fix:**
- Increase `time_limit_seconds`
- Reduce soft constraint weights
- Simplify problem (fewer sections)

---

#### Import Errors

```bash
ModuleNotFoundError: No module named 'ortools'
```

**Fix:**
```bash
pip install --upgrade ortools openpyxl
```

---

#### Job Not Found

```json
{"detail": {"message": "Job not found: abc-123"}}
```

**Cause:** Job ID expired or never existed.

**Note:** Jobs are stored in-memory and lost on server restart.

---

## 🧪 Testing Strategy

### Frontend Testing

#### Unit Tests (Vitest + Testing Library)

**Test Setup** (`src/test/setup.ts`):
```typescript
import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
```

**Component Tests** (`src/test/LandingPage.test.tsx`):
```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LandingPage } from '../pages/LandingPage';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return ({ children }: { children: React.NodeNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('LandingPage', () => {
  it('renders the welcome heading', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/Timetable Generator/i)).toBeInTheDocument();
  });

  it('renders feature cards', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    expect(screen.getAllByText(/Upload Your Data/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Configure Constraints/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Generate Timetable/i).length).toBeGreaterThan(0);
  });

  it('renders the get started button', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    const link = screen.getByRole('link', { name: /Get Started/i });
    expect(link).toBeInTheDocument();
  });
});
```

**Run Unit Tests**:
```bash
npm run test              # Run once
npm run test:watch        # Watch mode for development
npm run test -- --coverage # Coverage report
```

**Test Coverage Goals**:
- Components: > 80%
- API functions: > 90%
- Utils: > 95%

#### E2E Tests (Playwright)

**Configuration** (`playwright.config.ts`):
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

**E2E Test Example** (`e2e/app.spec.ts`):
```typescript
import { test, expect } from '@playwright/test';

test.describe('Timetable Generation Flow', () => {
  test('complete workflow from upload to results', async ({ page }) => {
    // Navigate to landing page
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('School Timetable Generator');
    
    // Click get started
    await page.click('text=Get Started');
    await expect(page).toHaveURL('/upload');
    
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('test-data/sample-school.csv');
    await expect(page.locator('text=Upload successful')).toBeVisible();
    
    // Navigate to constraints
    await page.click('text=Next: Constraints');
    await expect(page).toHaveURL('/constraints');
    
    // Configure constraints
    await page.fill('input[name="core_morning_weight"]', '5');
    await page.click('input[name="language_sync"]');
    
    // Generate timetable
    await page.click('text=Generate Timetable');
    await expect(page).toHaveURL(/\/generate/);
    
    // Wait for completion (with timeout)
    await expect(page.locator('text=Completed')).toBeVisible({ timeout: 60000 });
    
    // View results
    await page.click('text=View Results');
    await expect(page).toHaveURL(/\/results\/.+/);
    await expect(page.locator('table')).toBeVisible();
    
    // Verify timetable has data
    const cells = page.locator('td');
    await expect(cells).toHaveCount({ minimum: 50 });
  });
  
  test('handles upload error gracefully', async ({ page }) => {
    await page.goto('/upload');
    
    // Try invalid file
    await page.locator('input[type="file"]').setInputFiles('test-data/invalid.txt');
    await expect(page.locator('text=Invalid file format')).toBeVisible();
  });
  
  test('job history page displays jobs', async ({ page }) => {
    await page.goto('/jobs');
    await expect(page.locator('h1')).toContainText('Recent Jobs');
    
    // Should see table or empty state
    const table = page.locator('table');
    const emptyState = page.locator('text=No jobs yet');
    await expect(table.or(emptyState)).toBeVisible();
  });
});
```

**Run E2E Tests**:
```bash
npx playwright test                # Run all tests
npx playwright test --ui           # Interactive UI mode
npx playwright test --debug        # Debug mode
npx playwright test --project=chromium  # Specific browser
npx playwright show-report         # View HTML report
```

### Backend Testing

#### Unit Tests (Pytest)

**Test Structure**:
```
server/tests/
├── __init__.py
├── conftest.py                    # Fixtures
├── test_api/
│   ├── test_solve.py
│   ├── test_status.py
│   ├── test_result.py
│   └── test_upload.py
├── test_solver/
│   ├── test_model.py
│   ├── test_constraints.py
│   └── test_preprocess.py
└── test_utils/
    ├── test_validators.py
    ├── test_supabase_client.py
    └── test_r2_client.py
```

**API Test Example** (`tests/test_api/test_solve.py`):
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_solve_job_success():
    """Test successful job creation."""
    payload = {
        "school": {
            "school_id": 1,
            "name": "Test School",
            "start_time": "08:00",
            "end_time": "14:00",
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "periods_per_weekday": 6,
        },
        "teachers": [
            {
                "teacher_id": "T001",
                "name": "John Doe",
                "subjects_can_teach": ["MATH"],
                "min_periods_day": 3,
                "max_periods_day": 6,
            }
        ],
        "classes": [
            {
                "section_id": "8A",
                "grade": 8,
                "subject_teacher_map": {"MATH": "T001"},
            }
        ],
        "subjects": [
            {
                "subject_id": "MATH",
                "name": "Mathematics",
                "category": "core",
                "min_per_week": 5,
                "max_per_week": 6,
            }
        ],
    }
    
    response = client.post("/api/v1/timetable/solve", json=payload)
    assert response.status_code == 202
    assert "job_id" in response.json()
    assert response.json()["status"] == "queued"

def test_create_solve_job_validation_error():
    """Test validation error handling."""
    payload = {
        "school": {
            "school_id": 1,
            # Missing required fields
        }
    }
    
    response = client.post("/api/v1/timetable/solve", json=payload)
    assert response.status_code == 422
    assert "validation_errors" in response.json()

@pytest.mark.asyncio
async def test_job_status_endpoint():
    """Test job status retrieval."""
    # Create job first
    create_response = client.post("/api/v1/timetable/solve", json=valid_payload)
    job_id = create_response.json()["job_id"]
    
    # Check status
    status_response = client.get(f"/api/v1/timetable/status/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["job_id"] == job_id
```

**Run Backend Tests**:
```bash
cd server
pytest                              # Run all tests
pytest -v                          # Verbose output
pytest --cov=app --cov-report=html # Coverage report
pytest -k test_solve               # Run specific test
pytest -x                          # Stop on first failure
pytest --tb=short                  # Short traceback
```

#### Integration Tests

**Test with Real Database** (`tests/integration/test_supabase.py`):
```python
import pytest
from app.utils.supabase_client import SupabaseClient

@pytest.fixture
def supabase_client():
    return SupabaseClient()

def test_job_creation_and_retrieval(supabase_client):
    """Test full job lifecycle."""
    job_id = "test-job-123"
    tenant_id = "test-tenant"
    payload_hash = "abc123"
    
    # Create job
    job = supabase_client.create_job(
        job_id=job_id,
        tenant_id=tenant_id,
        payload_hash=payload_hash,
        payload_pointer="r2://test/input.json"
    )
    
    assert job["job_id"] == job_id
    assert job["status"] == "QUEUED"
    
    # Update status
    supabase_client.update_job_status(job_id, "RUNNING", progress=0.5)
    
    # Retrieve job
    retrieved = supabase_client.get_job(job_id)
    assert retrieved["status"] == "RUNNING"
    assert retrieved["progress"] == 0.5
    
    # Cleanup
    supabase_client.delete_job(job_id)
```

#### Load Testing (Locust)

**Load Test Script** (`tests/load/locustfile.py`):
```python
from locust import HttpUser, task, between

class TimetableUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup - runs once per user."""
        self.job_ids = []
    
    @task(3)
    def create_job(self):
        """Create timetable job (weight: 3)."""
        response = self.client.post(
            "/api/v1/timetable/solve",
            json=self.get_sample_payload(),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 202:
            job_id = response.json()["job_id"]
            self.job_ids.append(job_id)
    
    @task(10)
    def check_status(self):
        """Check job status (weight: 10)."""
        if self.job_ids:
            job_id = self.job_ids[-1]
            self.client.get(f"/api/v1/timetable/status/{job_id}")
    
    @task(2)
    def get_result(self):
        """Get job result (weight: 2)."""
        if self.job_ids:
            job_id = self.job_ids[0]
            self.client.get(f"/api/v1/timetable/result/{job_id}")
    
    def get_sample_payload(self):
        return {
            "school": {...},
            "teachers": [...],
            "classes": [...],
            "subjects": [...],
        }
```

**Run Load Tests**:
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8010
# Open http://localhost:8089 to configure and start test
```

**Load Test Scenarios**:
- **Smoke Test**: 1 user, 10 requests
- **Normal Load**: 10 users, 1000 requests, ramp-up 30s
- **Stress Test**: 100 users, 10000 requests, ramp-up 2min
- **Spike Test**: 0→50→0 users over 5min

---

## 🚀 Production Deployment

### Deployment Architecture

```
                          ┌─────────────────┐
                          │   Cloudflare    │
                          │      CDN        │
                          └────────┬────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
         ┌──────────▼────┐  ┌──────▼───────┐  ┌──▼────────┐
         │  Frontend      │  │   Backend    │  │    R2     │
         │   (Vercel/     │  │   (Railway/  │  │  Storage  │
         │   Netlify)     │  │    Fly.io)   │  │           │
         └────────────────┘  └──────┬───────┘  └───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
         ┌──────────▼────┐  ┌───────▼──────┐  ┌────▼──────┐
         │   Supabase     │  │   Upstash    │  │  Sentry   │
         │  PostgreSQL    │  │    Redis     │  │           │
         └────────────────┘  └──────────────┘  └───────────┘
```

### Frontend Deployment

#### Vercel (Recommended)

**Install Vercel CLI**:
```bash
npm i -g vercel
```

**Deploy**:
```bash
cd frontend
vercel                    # First time: answer config questions
vercel --prod            # Deploy to production
```

**`vercel.json` Configuration**:
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-backend.fly.io/api/:path*"
    }
  ],
  "headers": [
    {
      "source": "/assets/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    }
  ]
}
```

**Environment Variables** (Vercel Dashboard):
```
VITE_API_BASE_URL=https://your-backend.fly.io
VITE_ENABLE_MSW=false
```

#### Alternative: Netlify

**`netlify.toml`**:
```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/api/*"
  to = "https://your-backend.fly.io/api/:splat"
  status = 200

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### Backend Deployment

#### Fly.io (Recommended)

**Install flyctl**:
```bash
curl -L https://fly.io/install.sh | sh
```

**Create Fly App**:
```bash
cd server
fly launch                # Interactive setup
```

**`fly.toml` Configuration**:
```toml
app = "timetable-solver"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[env]
  SERVER_HOST = "0.0.0.0"
  SERVER_PORT = "8080"
  SOLVER_NUM_WORKERS = "4"
  LOG_LEVEL = "INFO"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1
  max_machines_running = 5

  [[http_service.concurrency]]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

[[vm]]
  cpu_kind = "shared"
  cpus = 2
  memory_mb = 2048
```

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY migrations/ ./migrations/

# Run migrations and start server
CMD python -m app.main
```

**Deploy**:
```bash
fly deploy                # Deploy to Fly.io
fly logs                  # View logs
fly status                # Check status
```

**Set Secrets**:
```bash
fly secrets set SUPABASE_URL=https://xxx.supabase.co
fly secrets set SUPABASE_KEY=eyJxxx...
fly secrets set R2_ACCESS_KEY_ID=xxx
fly secrets set R2_SECRET_ACCESS_KEY=xxx
fly secrets set REDIS_URL=rediss://xxx
fly secrets set SENTRY_DSN=https://xxx
```

#### Alternative: Railway

**Deploy via GitHub**:
1. Connect GitHub repo to Railway
2. Railway auto-detects Python
3. Set environment variables in dashboard
4. Deploy automatically on push

**`railway.toml`**:
```toml
[build]
  builder = "nixpacks"
  buildCommand = "pip install -r requirements.txt"

[deploy]
  startCommand = "python -m app.main"
  restartPolicyType = "ON_FAILURE"
  restartPolicyMaxRetries = 10
```

### Infrastructure Setup

#### 1. Supabase

**Create Project**:
```bash
# Via Supabase Dashboard
1. Create new project
2. Note SUPABASE_URL and SUPABASE_KEY
3. Run migrations in SQL Editor
```

**Apply Migrations**:
```sql
-- Copy contents of migrations/001_create_jobs_tables.sql
-- Run in Supabase SQL Editor
```

**Enable RLS**:
```sql
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON jobs
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true));
```

#### 2. Cloudflare R2

**Create Bucket**:
```bash
# Via Cloudflare Dashboard
1. R2 → Create Bucket → "timetable-storage"
2. Create API Token with read/write permissions
3. Note endpoint URL, access key, secret key
```

**Configure CORS**:
```json
[
  {
    "AllowedOrigins": ["https://your-frontend.vercel.app"],
    "AllowedMethods": ["GET", "PUT", "POST"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

#### 3. Upstash Redis

**Create Database**:
```bash
# Via Upstash Dashboard
1. Create Redis database
2. Select region close to backend
3. Copy REDIS_URL (rediss://...)
```

#### 4. Sentry

**Create Project**:
```bash
# Via Sentry Dashboard
1. Create new project → Python/FastAPI
2. Copy DSN
3. Set SENTRY_DSN environment variable
```

### Health Checks & Monitoring

**Health Check Endpoint** (`/health`):
```python
@app.get("/health")
async def health_check():
    checks = {
        "api": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Check Supabase
    try:
        supabase.client.table("jobs").select("count").limit(1).execute()
        checks["supabase"] = "ok"
    except:
        checks["supabase"] = "error"
    
    # Check Redis
    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except:
        checks["redis"] = "error"
    
    # Check R2
    try:
        r2_client.s3_client.head_bucket(Bucket=R2_BUCKET)
        checks["r2"] = "ok"
    except:
        checks["r2"] = "error"
    
    status_code = 200 if all(v == "ok" for v in checks.values() if isinstance(v, str)) else 503
    return JSONResponse(content=checks, status_code=status_code)
```

**Uptime Monitoring**:
- UptimeRobot: https://uptimerobot.com
- Pingdom: https://www.pingdom.com
- StatusCake: https://www.statuscake.com

Configure to check `/health` endpoint every 5 minutes.

### Backup Strategy

**Database Backups** (Supabase):
- Automatic daily backups (7-day retention)
- Manual snapshots before major changes
- Export critical data weekly

**R2 Backups**:
- Cloudflare R2 has 11 9's durability
- Enable versioning for critical objects
- Regular integrity checks

**Configuration Backups**:
- Store environment variables in 1Password/Vault
- Document all infrastructure in code (IaC)
- Version control all configuration files

### Scaling Considerations

**Horizontal Scaling**:
- Backend: Scale Fly.io machines (1-10 instances)
- Frontend: Vercel auto-scales
- Database: Supabase handles scaling
- Redis: Upstash auto-scales

**Vertical Scaling**:
```toml
# fly.toml - Increase resources
[[vm]]
  cpus = 4           # 2 → 4
  memory_mb = 4096   # 2048 → 4096
```

**Rate Limiting**:
```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.post("/api/v1/timetable/solve", dependencies=[Depends(RateLimiter(times=10, minutes=1))])
async def create_solve_job(...):
    ...
```

**Caching Strategy**:
- TanStack Query caching (frontend)
- Redis caching for frequently accessed jobs
- Cloudflare CDN for static assets

---

## 📈 Performance & Optimization

### Scaling Guidelines

| School Size | Sections | Expected Solve Time |
|-------------|----------|---------------------|
| Small | < 20 | 5-15 seconds |
| Medium | 20-50 | 15-60 seconds |
| Large | 50-100 | 1-5 minutes |
| Very Large | > 100 | 5+ minutes |

### Optimization Tips

1. **Start simple**: Test with 2-3 sections first
2. **Increase timeout**: Large problems need more time
3. **Tune soft weights**: Lower weights = faster solving
4. **Disable unused constraints**: Set weight to 0
5. **Use parallel workers**: Set `SOLVER_NUM_WORKERS` to CPU count
6. **Check feasibility first**: Pre-flight check catches obvious issues

### Memory Usage

- ~1KB per variable
- ~10KB per section
- 100 sections ≈ 10MB memory for model

---

## 🗺 Constraint Mapping Summary

### From Requirements to Implementation

| Requirement | Constraint Type | Implementation |
|-------------|-----------------|----------------|
| Global Time Grid | Preprocessing | `preprocess.py:generate_period_grid()` |
| Period 0 (Prayer) | Config | `school.prayer_enabled` |
| Saturday half-day | Config | `school.saturday_periods` |
| Recess/Lunch fixed | Preprocessing | `recess_period_indices`, `lunch_period_index` |
| Teacher single assignment | Hard | `add_teacher_single_assignment_constraint()` |
| Teacher max/min daily | Hard | `add_teacher_load_bounds_constraint()` |
| Weekly load balanced | Hard | `add_teacher_load_bounds_constraint()` (variance) |
| Max consecutive | Hard | `add_max_consecutive_constraint()` |
| Section single subject | Hard | `add_section_single_subject_constraint()` |
| Subject-teacher lock-in | Data | `class.subject_teacher_map` |
| Class teacher Period 1 | Hard (toggle) | `add_class_teacher_period_1_constraint()` |
| Language sync | Hard (toggle) | `add_language_sync_constraint()` |
| Lab double-block | Hard | `add_block_period_constraint()` |
| Resource capacity | Hard | `add_resource_capacity_constraint()` |
| Subject frequency | Hard | `add_subject_frequency_constraint()` |
| Substitution reserve | Hard | `add_substitution_reserve_constraint()` |
| Teacher availability | Hard | Built into teacher single assignment |
| No subject twice daily | Hard (toggle) | `add_no_subject_twice_daily_constraint()` |
| Core morning | Soft | `add_core_morning_preference()` |
| Subject distribution | Soft | `add_subject_distribution_preference()` |
| Teacher balance | Soft | `add_teacher_balance_preference()` |
| Minimize gaps | Soft | `add_minimize_gaps_preference()` |
| Leisure afternoon | Soft | `add_leisure_afternoon_preference()` |
| Avoid PE Period 1 | Soft | `add_avoid_pe_period_1_preference()` |
| Teacher free period | Soft | `add_teacher_free_period_preference()` |
| Fair slot distribution | Soft | `add_fair_slot_distribution_preference()` |

---

## 📜 License

MIT License

---

## 🙏 Acknowledgments

### Backend
- **Google OR-Tools**: The CP-SAT solver powering this system
- **FastAPI**: Modern, fast web framework for Python APIs
- **Pydantic**: Data validation using Python type hints
- **Supabase**: PostgreSQL database with real-time features
- **Cloudflare R2**: S3-compatible object storage
- **Upstash Redis**: Serverless Redis for distributed systems

### Frontend
- **React Team**: React 18 with concurrent features
- **Vite**: Lightning-fast build tool and dev server
- **TanStack Query**: Powerful server state management
- **Radix UI**: Accessible component primitives
- **Vercel**: Hosting and deployment platform
- **Tailwind CSS**: Utility-first CSS framework

### Development Tools
- **TypeScript**: Type-safe JavaScript
- **Vitest**: Fast unit testing framework
- **Playwright**: Reliable E2E testing
- **MSW**: API mocking for development
- **Sentry**: Error tracking and performance monitoring

---

## 📚 Additional Resources

### Documentation
- [Production Hardening Guide](./PRODUCTION_HARDENING_GUIDE.md) - Production deployment best practices
- [Implementation Status](./IMPLEMENTATION_STATUS.md) - Feature completion tracking
- [Constraint Requirements](./constraints.txt) - Detailed constraint specifications

### External Documentation
- [Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Query (TanStack Query)](https://tanstack.com/query/latest)
- [Radix UI](https://www.radix-ui.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [Cloudflare R2](https://developers.cloudflare.com/r2/)

### Community
- **Issues**: Report bugs or request features on GitHub
- **Discussions**: Ask questions and share ideas
- **Contributing**: See CONTRIBUTING.md for guidelines

---

## 🎓 Learning Resources

### Constraint Programming
- [Handbook of Constraint Programming](https://www.elsevier.com/books/handbook-of-constraint-programming/rossi/978-0-444-52726-4)
- [Constraint Programming Course by Coursera](https://www.coursera.org/learn/discrete-optimization)
- [CP-SAT Primer by Google](https://developers.google.com/optimization/cp/cp_primer)

### React & TypeScript
- [React Official Tutorial](https://react.dev/learn)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [TanStack Query Tutorial](https://tanstack.com/query/latest/docs/react/overview)

### System Design
- [Designing Data-Intensive Applications](https://dataintensive.net/)
- [System Design Primer](https://github.com/donnemartin/system-design-primer)

---

## 📊 Project Stats

- **Lines of Code (Backend)**: ~5,000 (Python)
- **Lines of Code (Frontend)**: ~3,500 (TypeScript/React)
- **API Endpoints**: 6
- **Constraint Types**: 19 (11 hard, 8 soft)
- **UI Components**: 20+
- **Test Coverage**: >80% (both frontend & backend)
- **Dependencies**: 
  - Backend: 25 packages
  - Frontend: 42 packages
- **Supported Browsers**: Chrome, Firefox, Safari, Edge
- **Minimum Node Version**: 18.x
- **Minimum Python Version**: 3.10+

---

## 🚀 Roadmap

### Phase 1: Core Features ✅ COMPLETE
- [x] CP-SAT constraint solver implementation
- [x] All 19 constraints implemented
- [x] Infeasibility diagnostics
- [x] REST API with FastAPI
- [x] Job queue system
- [x] React frontend with TypeScript
- [x] TanStack Query integration
- [x] Radix UI component library
- [x] Unit & E2E testing

### Phase 2: Production Infrastructure ✅ COMPLETE
- [x] Supabase PostgreSQL integration
- [x] Cloudflare R2 storage
- [x] Redis distributed semaphores
- [x] Multi-tenant support
- [x] Audit trail & job history
- [x] Sentry error tracking
- [x] Structured JSON logging
- [x] Health check endpoints

### Phase 3: Advanced Features 🚧 IN PROGRESS
- [ ] Real-time WebSocket updates
- [ ] Manual timetable editing
- [ ] Drag-and-drop schedule adjustments
- [ ] Teacher swap validation
- [ ] Conflict visualization
- [ ] Advanced analytics dashboard
- [ ] Export to PDF/Excel
- [ ] Email notifications
- [ ] Mobile app (React Native)

### Phase 4: Enterprise Features 🔮 PLANNED
- [ ] SSO/SAML authentication
- [ ] Role-based access control (RBAC)
- [ ] Custom branding/white-label
- [ ] API rate limiting tiers
- [ ] Webhook notifications
- [ ] Batch processing
- [ ] Multi-school management
- [ ] Historical data analytics
- [ ] AI-powered constraint suggestions
- [ ] Integration with SIS systems

---

*Built with ❤️ using Google OR-Tools, FastAPI, React, and TypeScript*

**Version**: 1.0.0  
**Last Updated**: January 25, 2026  
**Maintainer**: [Your Name/Organization]