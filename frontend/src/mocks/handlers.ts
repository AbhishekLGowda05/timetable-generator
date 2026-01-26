import { http, HttpResponse, delay } from 'msw';
import { v4 as uuid } from 'uuid';

// Mock data
const mockJobs = new Map<
  string,
  {
    job_id: string;
    status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
    progress: number;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    school_name?: string;
    classes_count?: number;
    teachers_count?: number;
    logs: Array<{ t: string; message: string }>;
    error?: string;
  }
>();

const mockUploads = new Map<
  string,
  {
    upload_id: string;
    filename: string;
    data_type?: string;
    preview: {
      teachers: number;
      classes: number;
      subjects: number;
      resources: number;
    };
    created_at: string;
  }
>();

// Demo school data
const demoSchoolData = {
  school: {
    name: 'Demo Academy',
    academic_year: '2024-2025',
    days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
    periods_per_day: 8,
    period_times: [
      { start: '08:00', end: '08:45' },
      { start: '08:50', end: '09:35' },
      { start: '09:40', end: '10:25' },
      { start: '10:40', end: '11:25' },
      { start: '11:30', end: '12:15' },
      { start: '13:00', end: '13:45' },
      { start: '13:50', end: '14:35' },
      { start: '14:40', end: '15:25' },
    ],
  },
  teachers: [
    { id: 'T001', name: 'John Smith', subjects: ['MATH'], max_periods_per_day: 6 },
    { id: 'T002', name: 'Jane Doe', subjects: ['ENG'], max_periods_per_day: 6 },
    { id: 'T003', name: 'Bob Wilson', subjects: ['SCI'], max_periods_per_day: 5 },
    { id: 'T004', name: 'Alice Brown', subjects: ['HIST'], max_periods_per_day: 6 },
    { id: 'T005', name: 'Charlie Davis', subjects: ['PE'], max_periods_per_day: 8 },
  ],
  classes: [
    { id: 'C001', name: 'Grade 9A', grade: 9, section: 'A' },
    { id: 'C002', name: 'Grade 9B', grade: 9, section: 'B' },
    { id: 'C003', name: 'Grade 10A', grade: 10, section: 'A' },
    { id: 'C004', name: 'Grade 10B', grade: 10, section: 'B' },
  ],
  subjects: [
    { id: 'MATH', name: 'Mathematics', periods_per_week: 5 },
    { id: 'ENG', name: 'English', periods_per_week: 5 },
    { id: 'SCI', name: 'Science', periods_per_week: 4 },
    { id: 'HIST', name: 'History', periods_per_week: 3 },
    { id: 'PE', name: 'Physical Education', periods_per_week: 2 },
  ],
  resources: [
    { id: 'R001', name: 'Science Lab', type: 'lab', capacity: 30 },
    { id: 'R002', name: 'Computer Lab', type: 'lab', capacity: 25 },
    { id: 'R003', name: 'Gymnasium', type: 'sports', capacity: 100 },
  ],
};

// Generate mock timetable schedule
function generateMockSchedule() {
  const days = demoSchoolData.school.days;
  const periodsPerDay = demoSchoolData.school.periods_per_day;
  const classes: Record<string, Array<any>> = {};
  const teachers: Record<string, Array<any>> = {};

  demoSchoolData.classes.forEach((cls) => {
    classes[cls.name] = [];
    days.forEach((day) => {
      for (let period = 1; period <= periodsPerDay; period++) {
        // Skip some periods to simulate breaks
        if (period === 5) continue;

        const subject =
          demoSchoolData.subjects[Math.floor(Math.random() * demoSchoolData.subjects.length)];
        const teacher = demoSchoolData.teachers.find((t) =>
          t.subjects.includes(subject.id)
        ) || demoSchoolData.teachers[0];

        classes[cls.name].push({
          day,
          period,
          subject_id: subject.id,
          subject_name: subject.name,
          teacher_id: teacher.id,
          teacher_name: teacher.name,
          room_name: `Room ${Math.floor(Math.random() * 10) + 100}`,
        });
      }
    });
  });

  demoSchoolData.teachers.forEach((teacher) => {
    teachers[teacher.name] = [];
    days.forEach((day) => {
      for (let period = 1; period <= periodsPerDay; period++) {
        if (period === 5) continue;
        if (Math.random() > 0.6) {
          const cls =
            demoSchoolData.classes[Math.floor(Math.random() * demoSchoolData.classes.length)];
          const subject =
            demoSchoolData.subjects.find((s) => teacher.subjects.includes(s.id)) ||
            demoSchoolData.subjects[0];

          teachers[teacher.name].push({
            day,
            period,
            subject_id: subject.id,
            subject_name: subject.name,
            class_id: cls.id,
            class_name: cls.name,
            room_name: `Room ${Math.floor(Math.random() * 10) + 100}`,
          });
        }
      }
    });
  });

  return { classes, teachers };
}

// Simulate job progress
function simulateJobProgress(jobId: string) {
  const job = mockJobs.get(jobId);
  if (!job || job.status === 'cancelled') return;

  if (job.status === 'queued') {
    job.status = 'running';
    job.started_at = new Date().toISOString();
    job.logs.push({
      t: new Date().toISOString(),
      message: 'Job started, initializing solver...',
    });
  }

  if (job.status === 'running') {
    job.progress = Math.min(100, job.progress + Math.floor(Math.random() * 20) + 10);
    job.logs.push({
      t: new Date().toISOString(),
      message: `Processing... ${job.progress}%`,
    });

    if (job.progress >= 100) {
      job.status = 'completed';
      job.completed_at = new Date().toISOString();
      job.logs.push({
        t: new Date().toISOString(),
        message: 'Optimization complete. Feasible solution found.',
      });
    } else {
      setTimeout(() => simulateJobProgress(jobId), 2000);
    }
  }
}

export const handlers = [
  // Health check
  http.get('/api/health', async () => {
    await delay(100);
    return HttpResponse.json({
      status: 'healthy',
      version: '1.0.0-mock',
    });
  }),

  // Upload endpoint
  http.post('/api/upload', async ({ request: _request }) => {
    await delay(500);

    const uploadId = uuid();
    mockUploads.set(uploadId, {
      upload_id: uploadId,
      filename: 'uploaded_file.xlsx',
      preview: {
        teachers: demoSchoolData.teachers.length,
        classes: demoSchoolData.classes.length,
        subjects: demoSchoolData.subjects.length,
        resources: demoSchoolData.resources.length,
      },
      created_at: new Date().toISOString(),
    });

    return HttpResponse.json({
      upload_id: uploadId,
      filename: 'uploaded_file.xlsx',
      preview: {
        teachers: demoSchoolData.teachers.length,
        classes: demoSchoolData.classes.length,
        subjects: demoSchoolData.subjects.length,
        resources: demoSchoolData.resources.length,
      },
    });
  }),

  // Bulk upload
  http.post('/api/upload/bulk', async () => {
    await delay(800);

    const uploadId = uuid();
    mockUploads.set(uploadId, {
      upload_id: uploadId,
      filename: 'bulk_upload.xlsx',
      preview: {
        teachers: demoSchoolData.teachers.length,
        classes: demoSchoolData.classes.length,
        subjects: demoSchoolData.subjects.length,
        resources: demoSchoolData.resources.length,
      },
      created_at: new Date().toISOString(),
    });

    return HttpResponse.json({
      upload_id: uploadId,
      filename: 'bulk_upload.xlsx',
      preview: {
        teachers: demoSchoolData.teachers.length,
        classes: demoSchoolData.classes.length,
        subjects: demoSchoolData.subjects.length,
        resources: demoSchoolData.resources.length,
      },
    });
  }),

  // Validation endpoint
  http.post('/api/validate', async ({ request: _request }) => {
    await delay(300);
    return HttpResponse.json({
      valid: true,
      errors: [],
      warnings: [
        {
          field: 'teachers[2].max_periods',
          message: 'Teacher has high workload (35 periods/week)',
        },
      ],
    });
  }),

  // Solve endpoint
  http.post('/api/solve', async ({ request: _request }) => {
    await delay(400);

    const jobId = uuid();
    mockJobs.set(jobId, {
      job_id: jobId,
      status: 'queued',
      progress: 0,
      created_at: new Date().toISOString(),
      school_name: demoSchoolData.school.name,
      classes_count: demoSchoolData.classes.length,
      teachers_count: demoSchoolData.teachers.length,
      logs: [
        {
          t: new Date().toISOString(),
          message: 'Job queued, waiting for worker...',
        },
      ],
    });

    // Start simulation
    setTimeout(() => simulateJobProgress(jobId), 1500);

    return HttpResponse.json({
      job_id: jobId,
      status: 'queued',
      position: 1,
    });
  }),

  // Job status endpoint
  http.get('/api/status/:jobId', async ({ params }) => {
    await delay(200);

    const { jobId } = params;
    const job = mockJobs.get(jobId as string);

    if (!job) {
      return HttpResponse.json(
        { error: 'Job not found' },
        { status: 404 }
      );
    }

    return HttpResponse.json({
      job_id: job.job_id,
      status: job.status,
      progress: job.progress,
      created_at: job.created_at,
      started_at: job.started_at,
      completed_at: job.completed_at,
      logs: job.logs,
      error: job.error,
    });
  }),

  // Job result endpoint
  http.get('/api/result/:jobId', async ({ params }) => {
    await delay(300);

    const { jobId } = params;
    const job = mockJobs.get(jobId as string);

    if (!job) {
      return HttpResponse.json(
        { error: 'Job not found' },
        { status: 404 }
      );
    }

    if (job.status !== 'completed') {
      return HttpResponse.json(
        { error: 'Job not complete' },
        { status: 400 }
      );
    }

    const schedule = generateMockSchedule();

    return HttpResponse.json({
      job_id: job.job_id,
      status: 'optimal',
      objective_value: 150,
      solve_time_seconds: 12.5,
      diagnostics: {
        soft_violations: [
          { constraint: 'Teacher preference violations', count: 3, penalty: 15 },
          { constraint: 'Consecutive period limit', count: 1, penalty: 5 },
        ],
        suggestions: [
          'Consider adding another Math teacher to reduce workload',
          'Science lab is overbooked on Wednesdays',
        ],
      },
      schedule,
      metadata: {
        school_name: demoSchoolData.school.name,
        days: demoSchoolData.school.days,
        periods_per_day: demoSchoolData.school.periods_per_day,
        period_times: demoSchoolData.school.period_times,
      },
    });
  }),

  // Download result
  http.get('/api/result/:jobId/download', async ({ params: _params, request }) => {
    await delay(500);

    const url = new URL(request.url);
    const format = url.searchParams.get('format') || 'json';

    // Return a mock blob
    if (format === 'json') {
      const schedule = generateMockSchedule();
      return HttpResponse.json(schedule);
    }

    // For other formats, return a placeholder
    return new HttpResponse('Mock file content', {
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': `attachment; filename="timetable.${format}"`,
      },
    });
  }),

  // Jobs list
  http.get('/api/jobs', async () => {
    await delay(200);

    const jobs = Array.from(mockJobs.values()).map((job) => ({
      job_id: job.job_id,
      status: job.status,
      created_at: job.created_at,
      started_at: job.started_at,
      completed_at: job.completed_at,
      school_name: job.school_name,
      classes_count: job.classes_count,
      teachers_count: job.teachers_count,
    }));

    return HttpResponse.json({ jobs });
  }),

  // Cancel job
  http.post('/api/cancel/:jobId', async ({ params }) => {
    await delay(200);

    const { jobId } = params;
    const job = mockJobs.get(jobId as string);

    if (!job) {
      return HttpResponse.json(
        { error: 'Job not found' },
        { status: 404 }
      );
    }

    job.status = 'cancelled';
    job.completed_at = new Date().toISOString();

    return HttpResponse.json({ ok: true });
  }),

  // Rerun job
  http.post('/api/rerun/:jobId', async ({ params: _params }) => {
    await delay(300);

    const newJobId = uuid();
    mockJobs.set(newJobId, {
      job_id: newJobId,
      status: 'queued',
      progress: 0,
      created_at: new Date().toISOString(),
      school_name: demoSchoolData.school.name,
      classes_count: demoSchoolData.classes.length,
      teachers_count: demoSchoolData.teachers.length,
      logs: [
        {
          t: new Date().toISOString(),
          message: 'Job requeued...',
        },
      ],
    });

    setTimeout(() => simulateJobProgress(newJobId), 1500);

    return HttpResponse.json({
      job_id: newJobId,
      status: 'queued',
      position: 1,
    });
  }),

  // Templates
  http.get('/api/templates/:type', async ({ params }) => {
    await delay(200);
    return new HttpResponse('Template file content', {
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': `attachment; filename="template_${params.type}.xlsx"`,
      },
    });
  }),
];
