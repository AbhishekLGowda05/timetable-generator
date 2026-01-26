/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_ADK_API_URL?: string;
  readonly VITE_USE_MOCK_API?: string;
  readonly VITE_MAX_UPLOAD_SIZE_MB?: string;
  readonly VITE_DEBUG?: string;
  readonly VITE_SENTRY_DSN?: string;
  readonly VITE_APP_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
