/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Vitest shares Vite's config (research R4); jsdom lets tests render components without a browser.
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
