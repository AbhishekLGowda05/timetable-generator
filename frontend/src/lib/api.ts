import { get, post, uploadFile, UploadProgressEvent } from './api-client';
import type {
  UploadResponse,
  ValidateRequest,
  ValidateResponse,
  SolveRequest,
  SolveResponse,
  JobStatusResponse,
  JobResultResponse,
  JobListResponse,
  SolverInput,
  Constraints,
  School,
  Teacher,
  Subject,
  ClassSection,
  Resource,
} from './schemas';

// API prefix for the timetable backend
const API_PREFIX = '/api/v1/timetable';

// ============================================================================
// Upload API
// ============================================================================

export async function uploadData(
  file: File,
  dataType?: string,
  onProgress?: (event: UploadProgressEvent) => void
): Promise<UploadResponse> {
  return uploadFile<UploadResponse>(
    `${API_PREFIX}/upload`,
    file,
    dataType ? { data_type: dataType } : undefined,
    onProgress
  );
}

export async function uploadBulkData(
  file: File,
  onProgress?: (event: UploadProgressEvent) => void
): Promise<UploadResponse> {
  return uploadFile<UploadResponse>(
    `${API_PREFIX}/upload/bulk`,
    file,
    undefined,
    onProgress
  );
}

// ============================================================================
// Validation API
// ============================================================================

export async function validateData(request: ValidateRequest): Promise<ValidateResponse> {
  return post<ValidateResponse>(`${API_PREFIX}/validate`, request);
}

export async function validateSolverInput(solverInput: SolverInput): Promise<ValidateResponse> {
  return post<ValidateResponse>(`${API_PREFIX}/validate`, { solver_input: solverInput });
}

// ============================================================================
// Solve API
// ============================================================================

export async function createSolveJob(request: SolveRequest): Promise<SolveResponse> {
  return post<SolveResponse>(`${API_PREFIX}/solve`, request);
}

export async function createJobFromUpload(
  uploadId: string,
  constraints?: Constraints,
  options?: SolveRequest['options']
): Promise<SolveResponse> {
  return post<SolveResponse>(`${API_PREFIX}/solve`, {
    upload_id: uploadId,
    constraints,
    options,
  });
}

export async function createJobFromInput(
  solverInput: SolverInput,
  options?: SolveRequest['options']
): Promise<SolveResponse> {
  return post<SolveResponse>(`${API_PREFIX}/solve`, {
    solver_input: solverInput,
    options,
  });
}

// ============================================================================
// Status API
// ============================================================================

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return get<JobStatusResponse>(`${API_PREFIX}/status/${jobId}`);
}

export async function getJobLogs(jobId: string): Promise<{ logs: Array<{ t: string; message: string }> }> {
  return get<{ logs: Array<{ t: string; message: string }> }>(`${API_PREFIX}/status/${jobId}?include_logs=true`);
}

// ============================================================================
// Result API
// ============================================================================

export async function getJobResult(jobId: string): Promise<JobResultResponse> {
  return get<JobResultResponse>(`${API_PREFIX}/result/${jobId}`);
}

export async function getJobDiagnostics(jobId: string): Promise<{ diagnostics: Array<Record<string, unknown>> }> {
  return get<{ diagnostics: Array<Record<string, unknown>> }>(`${API_PREFIX}/result/${jobId}/diagnostics`);
}

export async function downloadJobResult(jobId: string, _format: 'json' | 'csv' = 'json'): Promise<Blob> {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  const response = await fetch(`${baseUrl}${API_PREFIX}/result/${jobId}?format=file`, {
    method: 'GET',
  });
  if (!response.ok) {
    throw new Error(`Failed to download result: ${response.statusText}`);
  }
  return response.blob();
}

export async function downloadResult(
  jobId: string,
  format: 'xlsx' | 'csv' | 'json' | 'pdf',
  view?: string
): Promise<Blob> {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  const params = new URLSearchParams({ format });
  if (view) params.append('view', view);
  const response = await fetch(`${baseUrl}${API_PREFIX}/result/${jobId}/download?${params}`, {
    method: 'GET',
  });
  if (!response.ok) {
    throw new Error(`Failed to download result: ${response.statusText}`);
  }
  return response.blob();
}

// ============================================================================
// Job Management API
// ============================================================================

export async function listJobs(): Promise<JobListResponse> {
  return get<JobListResponse>(`${API_PREFIX}/jobs`);
}

export async function cancelJob(jobId: string): Promise<{ cancelled: boolean; message: string }> {
  return post<{ cancelled: boolean; message: string }>(`${API_PREFIX}/cancel/${jobId}`);
}

export async function rerunJob(
  jobId: string,
  constraints?: Partial<Constraints>,
  weights?: Record<string, number>
): Promise<SolveResponse> {
  return post<SolveResponse>(`${API_PREFIX}/rerun/${jobId}`, {
    constraints,
    weights,
  });
}

// ============================================================================
// Health Check
// ============================================================================

export async function healthCheck(): Promise<{ status: string; version?: string }> {
  return get<{ status: string; version?: string }>(`${API_PREFIX}/health`);
}

// ============================================================================
// Template Downloads
// ============================================================================

export function getTemplateUrl(type: 'teachers' | 'classes' | 'subjects' | 'resources' | 'full'): string {
  return `${API_PREFIX}/templates/${type}`;
}

export async function downloadTemplate(
  type: 'teachers' | 'classes' | 'subjects' | 'resources' | 'full'
): Promise<Blob> {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  const response = await fetch(`${baseUrl}${getTemplateUrl(type)}`);
  if (!response.ok) {
    throw new Error(`Failed to download template: ${response.statusText}`);
  }
  return response.blob();
}

export async function downloadFullTemplate(): Promise<Blob> {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  const response = await fetch(`${baseUrl}${API_PREFIX}/download-template`);
  if (!response.ok) {
    throw new Error(`Failed to download template: ${response.statusText}`);
  }
  return response.blob();
}

export async function downloadSampleDataset(): Promise<Blob> {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  const response = await fetch(`${baseUrl}${API_PREFIX}/download-sample`);
  if (!response.ok) {
    throw new Error(`Failed to download sample: ${response.statusText}`);
  }
  return response.blob();
}

export async function getSampleData(): Promise<UploadResponse & {
  school: School;
  teachers: Teacher[];
  subjects: Subject[];
  classes: ClassSection[];
  resources: Resource[];
  constraints: Record<string, unknown>;
}> {
  return get('/api/v1/timetable/sample-data');
}
