import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: { '/api': { target: 'http://localhost:8123', rewrite: (p) => p.replace(/^\/api/, '') } },
  },
  preview: { port: 4174, allowedHosts: ['.manus.computer'] },
  build: { chunkSizeWarningLimit: 700 },
});
