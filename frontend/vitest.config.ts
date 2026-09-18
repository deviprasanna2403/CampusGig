import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Test config kept separate from vite.config.ts so the dev/proxy settings
// stay untouched and `vite build` is unaffected.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // The socket state machine is driven by timers (heartbeat, ping interval,
    // 5s CONNECTING timeout, retry backoff). Tests use vi.useFakeTimers().
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
