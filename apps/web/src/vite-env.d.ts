interface ImportMetaEnv {
  readonly VITE_BASEMAP_STYLE_URL?: string;
  readonly VITE_USE_MOCK_DATA?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
