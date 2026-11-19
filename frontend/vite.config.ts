/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The browser calls /api on the frontend's own origin and Vite forwards it to the backend
  // container, so the session cookie works without cross-origin setup (feature 002, research R8).
  server: {
    proxy: {
      "/api": "http://backend:8000",
      // The admin area's pages come from the backend too (feature 011). The Host is kept: the
      // admin library builds absolute links from it, and backend:8000 means nothing to a browser.
      // A regex key: /admin and /admin/... only, as Caddy routes them (not e.g. /admin-help).
      "^/admin(/|$)": { target: "http://backend:8000", changeOrigin: false },
    },
    // File-change events don't reach a Linux container from a Windows (or macOS) host folder,
    // so in Docker Vite polls instead; docker-compose.yml sets VITE_USE_POLLING=true.
    watch: {
      usePolling: process.env.VITE_USE_POLLING === "true",
    },
  },
  // Vitest shares Vite's config (research R4); jsdom lets tests render components without a browser.
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
