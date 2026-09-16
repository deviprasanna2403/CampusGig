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
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
