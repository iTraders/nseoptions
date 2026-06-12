/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional absolute API base (e.g. http://127.0.0.1:8000); empty = same origin. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
