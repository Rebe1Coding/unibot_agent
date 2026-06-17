import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Prod build is served by FastAPI under /static; dev runs at root with API proxied to :8002.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8002',
      '/health': 'http://localhost:8002',
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
    assetsDir: 'assets',
  },
}));
