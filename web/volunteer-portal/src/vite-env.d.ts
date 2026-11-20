/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PI_HOST?: string;
  readonly VITE_PI_PORT?: string;
  readonly VITE_PI_GATEWAY_PORT?: string;
  readonly VITE_PI_USE_SSL?: string;
  readonly VITE_PI_NODE_ID?: string;
  readonly VITE_MOCK_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
