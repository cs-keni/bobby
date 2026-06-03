import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Proxy API calls to Bobby's FastAPI server during development.
    // Set VITE_SERVER_URL in .env to override (e.g. VITE_SERVER_URL=http://192.168.1.x:8765)
    proxy: {
      "/api": {
        target: process.env.VITE_SERVER_URL ?? "http://localhost:8765",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
