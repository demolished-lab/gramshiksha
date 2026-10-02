import { defineConfig } from 'vitest/config';

// Separate from vite.config.ts on purpose: the app build wants the React
// plugin and the dev proxy, tests run in plain node against the pure modules.
export default defineConfig({
  test: {
    environment: 'node',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
