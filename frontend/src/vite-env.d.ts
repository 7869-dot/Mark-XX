/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string;
  readonly VITE_API_URL?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_GOOGLE_CLIENT_ID?: string;
  readonly VITE_GMAIL_ENABLED?: string;
  readonly VITE_CALENDAR_ENABLED?: string;
  readonly VITE_A2A_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
