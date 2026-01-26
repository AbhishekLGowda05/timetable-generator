import { z } from 'zod';

// ============================================================================
// Base Types
// ============================================================================

export const WeekdaySchema = z.enum(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']);
export type Weekday = z.infer<typeof WeekdaySchema>;

export const SubjectCategorySchema = z.enum(['core', 'language', 'leisure', 'lab', 'arts', 'special']);
export type SubjectCategory = z.infer<typeof SubjectCategorySchema>;

export const JobStatusSchema = z.enum(['queued', 'running', 'diagnostics', 'completed', 'failed', 'cancelled']);
export type JobStatus = z.infer<typeof JobStatusSchema>;

export const SolverStatusSchema = z.enum(['OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'TIMEOUT', 'ERROR']);
export type SolverStatus = z.infer<typeof SolverStatusSchema>;

// ============================================================================
// School Schema
// ============================================================================

export const SchoolSchema = z.object({
  school_id: z.number(),
  name: z.string().min(1),
  start_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/),
  end_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/),
  weekdays: z.array(WeekdaySchema).min(1),
  periods_per_weekday: z.number().min(1).max(10),
  saturday_periods: z.number().min(0).max(6).default(4),
  period_duration_minutes: z.number().min(20).max(90).default(40),
  prayer_enabled: z.boolean().default(true),
  prayer_duration_minutes: z.number().min(0).max(30).default(15),
  lunch_period_index: z.number().min(1).optional(),
  lunch_after_period: z.number().min(1).optional(),
  lunch_duration_minutes: z.number().min(20).max(60).default(30),
  recess_period_indices: z.array(z.number().min(1)).default([]),
  recess_after_every_n_periods: z.number().min(2).max(5).optional(),
  recess_duration_minutes: z.number().min(5).max(30).default(15),
});
export type School = z.infer<typeof SchoolSchema>;

// ============================================================================
// Teacher Schema
// ============================================================================

export const TeacherAvailabilitySchema = z.object({
  available: z.boolean().default(true),
  from_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/).optional(),
  to_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/).optional(),
  blocked_periods: z.array(z.number().min(0)).optional(),
});
export type TeacherAvailability = z.infer<typeof TeacherAvailabilitySchema>;

export const TeacherSchema = z.object({
  teacher_id: z.string().regex(/^[A-Za-z0-9_-]+$/),
  name: z.string().min(1),
  subjects_can_teach: z.array(z.string()).min(1),
  sections_assigned: z.array(z.string()).default([]),
  min_periods_day: z.number().min(0).max(10),
  max_periods_day: z.number().min(1).max(10),
  min_periods_week: z.number().min(0).default(0),
  max_periods_week: z.number().min(1).default(40),
  max_consecutive_periods: z.number().min(1).max(5).default(3),
  is_class_teacher_of: z.string().nullable().default(null),
  is_specialist: z.boolean().default(false),
  availability: z.record(z.string(), TeacherAvailabilitySchema).optional(),
});
export type Teacher = z.infer<typeof TeacherSchema>;

// ============================================================================
// Subject Schema
// ============================================================================

export const SubjectTimeRestrictionSchema = z.object({
  allowed_days: z.array(WeekdaySchema).optional(),
  allowed_periods: z.array(z.number().min(1)).optional(),
  blocked_days: z.array(WeekdaySchema).optional(),
  blocked_periods: z.array(z.number().min(1)).optional(),
});
export type SubjectTimeRestriction = z.infer<typeof SubjectTimeRestrictionSchema>;

export const SubjectSchema = z.object({
  subject_id: z.string().regex(/^[A-Za-z0-9_-]+$/),
  name: z.string().min(1),
  category: SubjectCategorySchema,
  min_per_week: z.number().min(0),
  max_per_week: z.number().min(1),
  requires_block: z.boolean().default(false),
  block_length: z.number().min(2).max(4).default(2),
  requires_resource: z.boolean().default(false),
  resource_type: z.string().optional(),
  prefer_morning: z.boolean().default(false),
  avoid_after_lunch: z.boolean().default(false),
  is_specialist: z.boolean().default(false),
  is_language_block: z.boolean().default(false),
  // Time restrictions for scheduling
  time_restriction: SubjectTimeRestrictionSchema.optional(),
});
export type Subject = z.infer<typeof SubjectSchema>;

// ============================================================================
// Class/Section Schema
// ============================================================================

export const ClassSectionSchema = z.object({
  section_id: z.string().regex(/^[A-Za-z0-9_-]+$/),
  grade: z.number().min(1).max(12),
  section_name: z.string().default('A'),
  class_teacher_id: z.string().optional(),
  subject_teacher_map: z.record(z.string(), z.string()).refine((val) => Object.keys(val).length > 0, {
    message: 'At least one subject-teacher mapping is required',
  }),
  language_block_enabled: z.boolean().default(true),
  language_subjects: z.array(z.string()).default([]),
  language_teachers: z.array(z.string()).default([]),
});
export type ClassSection = z.infer<typeof ClassSectionSchema>;

// ============================================================================
// Resource Schema
// ============================================================================

export const ResourceSchema = z.object({
  resource_id: z.string().regex(/^[A-Za-z0-9_-]+$/),
  resource_type: z.string().min(1),
  name: z.string().optional(),
  max_simultaneous_capacity: z.number().min(1),
  available_periods: z.record(z.string(), z.array(z.number().min(0))).optional(),
});
export type Resource = z.infer<typeof ResourceSchema>;

// ============================================================================
// Constraints Schema
// ============================================================================

export const SoftWeightsSchema = z.object({
  teacher_balance: z.number().min(0).default(10),
  minimize_gaps: z.number().min(0).default(5),
  core_morning: z.number().min(0).default(3),
  leisure_afternoon: z.number().min(0).default(2),
  avoid_pe_period_1: z.number().min(0).default(4),
  avoid_pe_after_lunch: z.number().min(0).default(3),
  subject_distribution: z.number().min(0).default(5),
  teacher_free_period: z.number().min(0).default(2),
  fair_slot_distribution: z.number().min(0).default(5),
  specialist_priority: z.number().min(0).default(8),
  // Additional soft constraints from requirements
  thinking_break_math: z.number().min(0).default(3),
  language_spread: z.number().min(0).default(3),
  saturday_monday_balance: z.number().min(0).default(3),
});
export type SoftWeights = z.infer<typeof SoftWeightsSchema>;

export const ConstraintsSchema = z.object({
  // School Timing Settings
  school_start_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/).default('08:00'),
  school_end_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/).default('15:30'),
  periods_per_weekday: z.number().min(4).max(12).default(8),
  period_duration_minutes: z.number().min(20).max(60).default(45),
  saturday_periods: z.number().min(0).max(6).default(4),
  
  // Assembly/Prayer
  prayer_enabled: z.boolean().default(true),
  prayer_duration_minutes: z.number().min(10).max(45).default(30),
  
  // Breaks
  recess_after_period: z.number().min(1).max(5).default(2),
  recess_duration_minutes: z.number().min(10).max(30).default(20),
  lunch_after_period: z.number().min(3).max(7).default(5),
  lunch_duration_minutes: z.number().min(20).max(60).default(40),
  
  // Hard Constraints (toggles) - Sensible defaults to avoid infeasibility
  language_sync_enabled: z.boolean().default(false),  // Disabled by default
  class_teacher_period_1: z.boolean().default(false), // Disabled by default
  no_subject_twice_daily: z.boolean().default(false),
  core_morning_only: z.boolean().default(false),      // Soft preference only
  subject_frequency_enabled: z.boolean().default(true),
  teacher_load_bounds_enabled: z.boolean().default(true),
  block_period_integrity: z.boolean().default(true),
  resource_capacity_enabled: z.boolean().default(true),
  
  // Numeric constraints - Relaxed defaults
  substitution_reserve_count: z.number().min(0).default(0),
  max_consecutive_default: z.number().min(1).max(5).default(4),
  max_daily_load_variance: z.number().min(1).max(5).default(4),
  
  // Soft weights
  soft_weights: SoftWeightsSchema.default({}),
});
export type Constraints = z.infer<typeof ConstraintsSchema>;

// ============================================================================
// Solver Input Schema
// ============================================================================

export const SolverInputSchema = z.object({
  school: SchoolSchema,
  classes: z.array(ClassSectionSchema).min(1),
  teachers: z.array(TeacherSchema).min(1),
  subjects: z.array(SubjectSchema).min(1),
  resources: z.array(ResourceSchema).default([]),
  constraints: ConstraintsSchema,
});
export type SolverInput = z.infer<typeof SolverInputSchema>;

// ============================================================================
// Solver Output Schema
// ============================================================================

export const TimetablePeriodSchema = z.object({
  period: z.number().min(0),
  subject_id: z.string(),
  subject_name: z.string().optional(),
  teacher_id: z.string(),
  teacher_name: z.string().optional(),
  resource_id: z.string().optional(),
  is_block_start: z.boolean().default(false),
  is_block_continuation: z.boolean().default(false),
  start_time: z.string().optional(),
  end_time: z.string().optional(),
});
export type TimetablePeriod = z.infer<typeof TimetablePeriodSchema>;

export const TimetableDaySchema = z.array(TimetablePeriodSchema);
export type TimetableDay = z.infer<typeof TimetableDaySchema>;

export const SectionTimetableSchema = z.record(z.string(), TimetableDaySchema);
export type SectionTimetable = z.infer<typeof SectionTimetableSchema>;

export const DiagnosticSchema = z.object({
  type: z.enum(['error', 'warning', 'suggestion']),
  category: z.string(),
  message: z.string(),
  affected_entities: z.array(z.string()).optional(),
  suggestion: z.string().optional(),
});
export type Diagnostic = z.infer<typeof DiagnosticSchema>;

export const SolverMetaSchema = z.object({
  solve_time_seconds: z.number().optional(),
  variables_count: z.number().optional(),
  constraints_count: z.number().optional(),
  objective_value: z.number().optional(),
  soft_violations: z.record(z.string(), z.number()).optional(),
  solver_status_code: z.number().optional(),
});
export type SolverMeta = z.infer<typeof SolverMetaSchema>;

// Grid configuration for frontend rendering (break positions, periods)
export const GridConfigSchema = z.object({
  weekdays: z.array(z.string()),
  periods_per_weekday: z.number(),
  saturday_periods: z.number().optional(),
  prayer_enabled: z.boolean().optional(),
  prayer_duration_minutes: z.number().optional(),
  recess: z.object({
    after_periods: z.array(z.number()),
    duration_minutes: z.number(),
  }).optional(),
  lunch: z.object({
    after_period: z.number(),
    duration_minutes: z.number(),
  }).optional(),
  period_times: z.array(z.object({
    period: z.number(),
    start_time: z.string(),
    end_time: z.string(),
    is_prayer: z.boolean().optional(),
    is_after_recess: z.boolean().optional(),
    is_after_lunch: z.boolean().optional(),
  })).optional(),
  start_time: z.string().optional(),
  period_duration_minutes: z.number().optional(),
});
export type GridConfig = z.infer<typeof GridConfigSchema>;

export const SolverOutputSchema = z.object({
  status: SolverStatusSchema,
  timetable: z.record(z.string(), SectionTimetableSchema),
  teacher_schedules: z.record(z.string(), z.record(z.string(), z.array(z.object({
    period: z.number(),
    section_id: z.string(),
    subject_id: z.string(),
  })))).optional(),
  resource_views: z.record(z.string(), z.record(z.string(), z.array(z.object({
    period: z.number(),
    section_id: z.string(),
    subject_id: z.string(),
    teacher_id: z.string().optional(),
  })))).optional(),
  meta: SolverMetaSchema.optional(),
  diagnostics: z.array(DiagnosticSchema).optional(),
  warnings: z.array(z.string()).optional(),
  grid_config: GridConfigSchema.optional(),
});
export type SolverOutput = z.infer<typeof SolverOutputSchema>;

// ============================================================================
// API Request/Response Schemas
// ============================================================================

export const UploadResponseSchema = z.object({
  upload_id: z.string(),
  preview: z.object({
    teachers: z.number(),
    classes: z.number(),
    subjects: z.number(),
    resources: z.number(),
  }),
  sample_rows: z.object({
    teachers: z.array(z.record(z.string(), z.unknown())).optional(),
    classes: z.array(z.record(z.string(), z.unknown())).optional(),
    subjects: z.array(z.record(z.string(), z.unknown())).optional(),
    resources: z.array(z.record(z.string(), z.unknown())).optional(),
  }).optional(),
  validation_errors: z.array(z.object({
    row: z.number().optional(),
    field: z.string().optional(),
    message: z.string(),
  })).default([]),
});
export type UploadResponse = z.infer<typeof UploadResponseSchema>;

export const ValidateRequestSchema = z.object({
  upload_id: z.string().optional(),
  solver_input: SolverInputSchema.optional(),
});
export type ValidateRequest = z.infer<typeof ValidateRequestSchema>;

export const ValidateResponseSchema = z.object({
  ok: z.boolean(),
  issues: z.array(z.object({
    type: z.enum(['hard', 'soft']),
    message: z.string(),
    hint: z.string().optional(),
    path: z.string().optional(),
  })).default([]),
});
export type ValidateResponse = z.infer<typeof ValidateResponseSchema>;

export const SolveOptionsSchema = z.object({
  // Time limit in seconds - increased default for better results
  time_limit_seconds: z.number().min(10).max(600).optional(),
  // Demo mode: immediate allocation with higher time limit
  demo_mode: z.boolean().optional(),
  // Deadline: ISO 8601 datetime by when results are needed
  deadline: z.string().optional(),
  // Force fresh solve: bypass any caching (defaults to true on server)
  force_fresh: z.boolean().optional(),
  // Legacy field
  concurrency_group: z.string().optional(),
});
export type SolveOptions = z.infer<typeof SolveOptionsSchema>;

export const SolveRequestSchema = z.object({
  upload_id: z.string().optional(),
  solver_input: SolverInputSchema.optional(),
  constraints: ConstraintsSchema.optional(),
  options: SolveOptionsSchema.optional(),
});
export type SolveRequest = z.infer<typeof SolveRequestSchema>;

export const SolveResponseSchema = z.object({
  job_id: z.string(),
  status: z.string().optional(),
  message: z.string().optional(),
  warnings: z.array(z.string()).optional(),
  time_allocated_seconds: z.number().optional(),
  estimated_completion: z.string().optional(),
  // Legacy field
  estimated_time_seconds: z.number().optional(),
});
export type SolveResponse = z.infer<typeof SolveResponseSchema>;

export const JobLogSchema = z.object({
  t: z.string(),
  message: z.string(),
});
export type JobLog = z.infer<typeof JobLogSchema>;

export const JobStatusResponseSchema = z.object({
  job_id: z.string(),
  status: JobStatusSchema,
  progress: z.number().min(0).max(100),
  logs: z.array(JobLogSchema).optional(),
  diagnostics_summary: z.object({
    violations: z.number(),
    suggestions: z.array(z.string()),
  }).optional(),
  created_at: z.string().optional(),
  started_at: z.string().optional(),
  completed_at: z.string().optional(),
  error: z.string().optional(),
});
export type JobStatusResponse = z.infer<typeof JobStatusResponseSchema>;

export const JobResultResponseSchema = z.object({
  job_id: z.string(),
  timetable_json: SolverOutputSchema,
  teacher_views: z.record(z.string(), z.unknown()).optional(),
  class_views: z.record(z.string(), z.unknown()).optional(),
  resource_views: z.record(z.string(), z.unknown()).optional(),
  metrics: SolverMetaSchema.optional(),
  diagnostics: z.array(DiagnosticSchema).optional(),
});
export type JobResultResponse = z.infer<typeof JobResultResponseSchema>;

export const JobListItemSchema = z.object({
  job_id: z.string(),
  status: JobStatusSchema,
  progress: z.number(),
  created_at: z.string().optional(),
});
export type JobListItem = z.infer<typeof JobListItemSchema>;

export const JobListResponseSchema = z.object({
  jobs: z.array(JobListItemSchema),
  total: z.number(),
});
export type JobListResponse = z.infer<typeof JobListResponseSchema>;

// ============================================================================
// Form State Types
// ============================================================================

export interface UploadFormState {
  file: File | null;
  uploadId: string | null;
  preview: UploadResponse['preview'] | null;
  sampleRows: UploadResponse['sample_rows'] | null;
  validationErrors: UploadResponse['validation_errors'];
  isUploading: boolean;
  uploadProgress: number;
}

export interface ConstraintsFormState {
  school: Partial<School>;
  constraints: Partial<Constraints>;
  teacherOverrides: Record<string, Partial<Teacher>>;
  classOverrides: Record<string, Partial<ClassSection>>;
}

export interface GenerateFormState {
  uploadId: string | null;
  solverInput: SolverInput | null;
  options: {
    time_limit_seconds: number;
    concurrency_group?: string;
  };
}
