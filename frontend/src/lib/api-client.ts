import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';

// ============================================================================
// Types
// ============================================================================

export interface ApiError {
  message: string;
  code?: string;
  status?: number;
  details?: Record<string, unknown>;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

// ============================================================================
// Configuration
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8010';
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API === 'true';

// ============================================================================
// Axios Instance
// ============================================================================

const axiosInstance: AxiosInstance = axios.create({
  baseURL: USE_MOCK_API ? '' : API_BASE_URL,
  timeout: 60000, // 60 seconds for long operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Add request timestamp for debugging
    if (import.meta.env.VITE_DEBUG === 'true') {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.data);
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    if (import.meta.env.VITE_DEBUG === 'true') {
      console.log(`[API] Response ${response.status}`, response.data);
    }
    return response;
  },
  (error: AxiosError) => {
    const apiError = transformError(error);
    if (import.meta.env.VITE_DEBUG === 'true') {
      console.error('[API] Error', apiError);
    }
    return Promise.reject(apiError);
  }
);

// ============================================================================
// Error Handling
// ============================================================================

function transformError(error: AxiosError): ApiError {
  if (error.response) {
    // Server responded with error
    const data = error.response.data as Record<string, unknown>;
    return {
      message: (data?.message as string) || (data?.detail as string) || 'An error occurred',
      code: (data?.code as string) || `HTTP_${error.response.status}`,
      status: error.response.status,
      details: data,
    };
  } else if (error.request) {
    // Request made but no response
    return {
      message: 'Network error - please check your connection',
      code: 'NETWORK_ERROR',
    };
  } else {
    // Request setup error
    return {
      message: error.message || 'An unexpected error occurred',
      code: 'REQUEST_ERROR',
    };
  }
}

// ============================================================================
// HTTP Methods
// ============================================================================

export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await axiosInstance.get<T>(url, config);
  return response.data;
}

export async function post<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await axiosInstance.post<T>(url, data, config);
  return response.data;
}

export async function put<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await axiosInstance.put<T>(url, data, config);
  return response.data;
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await axiosInstance.delete<T>(url, config);
  return response.data;
}

// ============================================================================
// File Upload
// ============================================================================

export interface UploadProgressEvent {
  loaded: number;
  total: number;
  percentage: number;
}

export async function uploadFile<T>(
  url: string,
  file: File,
  additionalData?: Record<string, string>,
  onProgress?: (event: UploadProgressEvent) => void
): Promise<T> {
  const formData = new FormData();
  formData.append('file', file);

  if (additionalData) {
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, value);
    });
  }

  const response = await axiosInstance.post<T>(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percentage = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress({
          loaded: progressEvent.loaded,
          total: progressEvent.total,
          percentage,
        });
      }
    },
  });

  return response.data;
}

// ============================================================================
// Abort Controller Helper
// ============================================================================

export function createAbortController(): AbortController {
  return new AbortController();
}

// ============================================================================
// Export Instance
// ============================================================================

export { axiosInstance as apiClient };
export default axiosInstance;
