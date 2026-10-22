/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// One .env at the repo root serves the API, the web app and Docker Compose.
const envDir = "../..";

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, envDir, ""), ...process.env };

  return {
    envDir,
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": env.API_PROXY_TARGET ?? "http://localhost:8000",
      },
    },
    build: {
      // MapLibre alone is ~1 MB minified; don't warn about it.
      chunkSizeWarningLimit: 1500,
    },
    test: {
      environment: "jsdom",
    },
  };
});
