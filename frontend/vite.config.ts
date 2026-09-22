import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The production build is served by FastAPI (see app/main.py).
// In development, `npm run dev` proxies API calls to the backend on :8080.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    assetsInlineLimit: 0, // never inline assets as data: URIs; keep everything same-origin files
    sourcemap: false,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
