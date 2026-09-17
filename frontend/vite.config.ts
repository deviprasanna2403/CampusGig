import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Dev proxy: the API client uses VITE_API_BASE_URL="" so calls go to
    // /api/v1/* on this origin and are forwarded to the Django backend —
    // no CORS involved in local development.
    proxy: {
      "/api": {
        // Backend origin; overridable so the dev server can point at a
        // backend on a non-default port (e.g. 8000 already taken).
        target: process.env.CAMPUSGIG_BACKEND_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        // Chat WebSocket (Channels) — ws: true forwards the upgrade.
        target: process.env.CAMPUSGIG_BACKEND_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
