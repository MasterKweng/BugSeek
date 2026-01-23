import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { spaFallback } from './vite-plugin-spa-fallback'

export default defineConfig({
  plugins: [react(), spaFallback()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
  preview: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
})