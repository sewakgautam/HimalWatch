import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  webServer: {
    // Serves the static export, not `next dev` — this is the artifact
    // that actually ships, and e2e tests should exercise that, not the
    // dev server's different (SSR-ish) code paths.
    command: "pnpm exec serve out -p 4173 -s",
    port: 4173,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  use: {
    baseURL: "http://localhost:4173",
  },
});
