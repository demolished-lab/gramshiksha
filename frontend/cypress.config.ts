import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    baseUrl: 'https://4176-i1cb7z9k2xjl94yxuu7x3-8355cdc3.sg2.manus.computer',
    supportFile: false,
    specPattern: 'cypress/e2e/**/*.cy.ts',
    video: false,
    screenshotOnRunFailure: true,
    retries: { runMode: 1, openMode: 0 },
    defaultCommandTimeout: 10000,
    pageLoadTimeout: 30000,
    viewportWidth: 1280,
    viewportHeight: 800,
  },
});
