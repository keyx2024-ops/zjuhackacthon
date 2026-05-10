import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  root: 'src/frontend',
  plugins: [vue()],
  server: {
    port: 3888,
    proxy: {
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../../dist',
    emptyOutDir: true,
  },
});
