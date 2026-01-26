import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type {
  School,
  Teacher,
  Subject,
  ClassSection,
  Resource,
  Constraints,
  UploadResponse,
  SolverInput,
} from '@/lib/schemas';

// ============================================================================
// Upload Store
// ============================================================================

interface UploadState {
  file: File | null;
  uploadId: string | null;
  preview: UploadResponse['preview'] | null;
  sampleRows: UploadResponse['sample_rows'] | null;
  validationErrors: UploadResponse['validation_errors'];
  isUploading: boolean;
  uploadProgress: number;
  
  // Parsed data
  school: School | null;
  teachers: Teacher[];
  subjects: Subject[];
  classes: ClassSection[];
  resources: Resource[];
  
  // Actions
  setFile: (file: File | null) => void;
  setUploadId: (id: string | null) => void;
  setPreview: (preview: UploadResponse['preview'] | null) => void;
  setSampleRows: (rows: UploadResponse['sample_rows'] | null) => void;
  setValidationErrors: (errors: UploadResponse['validation_errors']) => void;
  setIsUploading: (isUploading: boolean) => void;
  setUploadProgress: (progress: number) => void;
  setSchool: (school: School | null) => void;
  setTeachers: (teachers: Teacher[]) => void;
  setSubjects: (subjects: Subject[]) => void;
  setClasses: (classes: ClassSection[]) => void;
  setResources: (resources: Resource[]) => void;
  reset: () => void;
}

const initialUploadState = {
  file: null,
  uploadId: null,
  preview: null,
  sampleRows: null,
  validationErrors: [],
  isUploading: false,
  uploadProgress: 0,
  school: null,
  teachers: [],
  subjects: [],
  classes: [],
  resources: [],
};

export const useUploadStore = create<UploadState>()((set) => ({
  ...initialUploadState,
  
  setFile: (file) => set({ file }),
  setUploadId: (uploadId) => set({ uploadId }),
  setPreview: (preview) => set({ preview }),
  setSampleRows: (sampleRows) => set({ sampleRows }),
  setValidationErrors: (validationErrors) => set({ validationErrors }),
  setIsUploading: (isUploading) => set({ isUploading }),
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),
  setSchool: (school) => set({ school }),
  setTeachers: (teachers) => set({ teachers }),
  setSubjects: (subjects) => set({ subjects }),
  setClasses: (classes) => set({ classes }),
  setResources: (resources) => set({ resources }),
  reset: () => set(initialUploadState),
}));

// ============================================================================
// Constraints Store (persisted to localStorage)
// ============================================================================

interface ConstraintsState {
  constraints: Constraints;
  teacherOverrides: Record<string, Partial<Teacher>>;
  classOverrides: Record<string, Partial<ClassSection>>;
  isDirty: boolean;
  
  // Actions
  setConstraints: (constraints: Partial<Constraints>) => void;
  resetConstraints: () => void;
  setTeacherOverride: (teacherId: string, override: Partial<Teacher>) => void;
  removeTeacherOverride: (teacherId: string) => void;
  setClassOverride: (classId: string, override: Partial<ClassSection>) => void;
  removeClassOverride: (classId: string) => void;
  markClean: () => void;
}

const defaultConstraints: Constraints = {
  // School Timing Settings
  school_start_time: '08:00',
  school_end_time: '15:30',
  periods_per_weekday: 8,
  period_duration_minutes: 45,
  saturday_periods: 4,
  
  // Assembly/Prayer
  prayer_enabled: true,
  prayer_duration_minutes: 30,
  
  // Breaks
  recess_after_period: 2,
  recess_duration_minutes: 20,
  lunch_after_period: 5,
  lunch_duration_minutes: 40,
  
  // Hard Constraints - Set sensible defaults that won't cause infeasibility
  language_sync_enabled: false,  // Disabled by default - causes conflicts with many sections
  class_teacher_period_1: false, // Disabled by default - can conflict with teacher availability  
  no_subject_twice_daily: false,
  core_morning_only: false,      // This is a preference, not a hard requirement
  subject_frequency_enabled: true,
  teacher_load_bounds_enabled: true,
  block_period_integrity: true,
  resource_capacity_enabled: true,
  
  // Numeric constraints - Relaxed defaults
  substitution_reserve_count: 0, // Reduced to prevent over-constraining
  max_consecutive_default: 4,    // Slightly relaxed from 3
  max_daily_load_variance: 4,    // Slightly relaxed from 3
  
  // Soft weights
  soft_weights: {
    teacher_balance: 10,
    minimize_gaps: 5,
    core_morning: 3,
    leisure_afternoon: 2,
    avoid_pe_period_1: 4,
    avoid_pe_after_lunch: 3,
    subject_distribution: 5,
    teacher_free_period: 2,
    fair_slot_distribution: 5,
    specialist_priority: 8,
    thinking_break_math: 3,
    language_spread: 3,
    saturday_monday_balance: 3,
  },
};

export const useConstraintsStore = create<ConstraintsState>()(
  persist(
    (set) => ({
      constraints: defaultConstraints,
      teacherOverrides: {},
      classOverrides: {},
      isDirty: false,
      
      setConstraints: (newConstraints) =>
        set((state) => ({
          constraints: { ...state.constraints, ...newConstraints },
          isDirty: true,
        })),
        
      resetConstraints: () =>
        set({
          constraints: defaultConstraints,
          teacherOverrides: {},
          classOverrides: {},
          isDirty: false,
        }),
        
      setTeacherOverride: (teacherId, override) =>
        set((state) => ({
          teacherOverrides: {
            ...state.teacherOverrides,
            [teacherId]: { ...state.teacherOverrides[teacherId], ...override },
          },
          isDirty: true,
        })),
        
      removeTeacherOverride: (teacherId) =>
        set((state) => {
          const { [teacherId]: _, ...rest } = state.teacherOverrides;
          return { teacherOverrides: rest, isDirty: true };
        }),
        
      setClassOverride: (classId, override) =>
        set((state) => ({
          classOverrides: {
            ...state.classOverrides,
            [classId]: { ...state.classOverrides[classId], ...override },
          },
          isDirty: true,
        })),
        
      removeClassOverride: (classId) =>
        set((state) => {
          const { [classId]: _, ...rest } = state.classOverrides;
          return { classOverrides: rest, isDirty: true };
        }),
        
      markClean: () => set({ isDirty: false }),
    }),
    {
      name: 'timetable-constraints',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        constraints: state.constraints,
        teacherOverrides: state.teacherOverrides,
        classOverrides: state.classOverrides,
      }),
    }
  )
);

// ============================================================================
// Job Store
// ============================================================================

export type JobStatus = 'queued' | 'running' | 'diagnostics' | 'completed' | 'failed' | 'cancelled';

interface JobLog {
  t: string;
  message: string;
}

interface JobState {
  currentJobId: string | null;
  status: JobStatus | null;
  progress: number;
  logs: JobLog[];
  error: string | null;
  createdAt: string | null;
  startedAt: string | null;
  completedAt: string | null;
  
  // Actions
  setCurrentJob: (jobId: string | null) => void;
  setStatus: (status: JobStatus | null) => void;
  setProgress: (progress: number) => void;
  addLog: (log: JobLog) => void;
  setLogs: (logs: JobLog[]) => void;
  setError: (error: string | null) => void;
  setTimestamps: (timestamps: { createdAt?: string; startedAt?: string; completedAt?: string }) => void;
  reset: () => void;
}

const initialJobState = {
  currentJobId: null,
  status: null,
  progress: 0,
  logs: [],
  error: null,
  createdAt: null,
  startedAt: null,
  completedAt: null,
};

export const useJobStore = create<JobState>()(
  persist(
    (set) => ({
      ...initialJobState,
      
      setCurrentJob: (currentJobId) => set({ currentJobId }),
      setStatus: (status) => set({ status }),
      setProgress: (progress) => set({ progress }),
      addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
      setLogs: (logs) => set({ logs }),
      setError: (error) => set({ error }),
      setTimestamps: (timestamps) =>
        set((state) => ({
          createdAt: timestamps.createdAt ?? state.createdAt,
          startedAt: timestamps.startedAt ?? state.startedAt,
          completedAt: timestamps.completedAt ?? state.completedAt,
        })),
      reset: () => set(initialJobState),
    }),
    {
      name: 'timetable-current-job',
      storage: createJSONStorage(() => localStorage),
      // Persist everything except logs to keep storage size reasonable
      partialize: (state) => ({
        currentJobId: state.currentJobId,
        status: state.status,
        progress: state.progress,
        error: state.error,
        createdAt: state.createdAt,
        startedAt: state.startedAt,
        completedAt: state.completedAt,
        // Only keep the last 50 logs
        logs: state.logs.slice(-50),
      }),
    }
  )
);

// ============================================================================
// Result Store
// ============================================================================

interface ResultState {
  jobId: string | null;
  solverInput: SolverInput | null;
  result: Record<string, unknown> | null;
  teacherViews: Record<string, unknown> | null;
  classViews: Record<string, unknown> | null;
  resourceViews: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  diagnostics: Array<Record<string, unknown>> | null;
  
  // Actions
  setResult: (result: {
    jobId: string;
    solverInput?: SolverInput;
    result: Record<string, unknown>;
    teacherViews?: Record<string, unknown>;
    classViews?: Record<string, unknown>;
    resourceViews?: Record<string, unknown>;
    metrics?: Record<string, unknown>;
    diagnostics?: Array<Record<string, unknown>>;
  }) => void;
  reset: () => void;
}

const initialResultState = {
  jobId: null,
  solverInput: null,
  result: null,
  teacherViews: null,
  classViews: null,
  resourceViews: null,
  metrics: null,
  diagnostics: null,
};

export const useResultStore = create<ResultState>()(
  persist(
    (set) => ({
      ...initialResultState,
      
      setResult: (result) =>
        set({
          jobId: result.jobId,
          solverInput: result.solverInput ?? null,
          result: result.result,
          teacherViews: result.teacherViews ?? null,
          classViews: result.classViews ?? null,
          resourceViews: result.resourceViews ?? null,
          metrics: result.metrics ?? null,
          diagnostics: result.diagnostics ?? null,
        }),
        
      reset: () => set(initialResultState),
    }),
    {
      name: 'timetable-result',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        jobId: state.jobId,
        // Don't persist solverInput as it can be large
        result: state.result,
        teacherViews: state.teacherViews,
        classViews: state.classViews,
        resourceViews: state.resourceViews,
        metrics: state.metrics,
        diagnostics: state.diagnostics,
      }),
    }
  )
);

// ============================================================================
// UI Store (for global UI state)
// ============================================================================

interface UIState {
  sidebarOpen: boolean;
  currentStep: number;
  isOffline: boolean;
  
  // Actions
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setCurrentStep: (step: number) => void;
  setIsOffline: (offline: boolean) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  currentStep: 0,
  isOffline: false,
  
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setCurrentStep: (currentStep) => set({ currentStep }),
  setIsOffline: (isOffline) => set({ isOffline }),
}));
