import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { spaFallback } from './vite-plugin-spa-fallback'

const createManualChunk = (id: string) => {
  if (!id.includes('node_modules')) {
    return undefined
  }

  if (
    id.includes('/react/') ||
    id.includes('/react-dom/') ||
    id.includes('/scheduler/') ||
    id.includes('/react-router-dom/') ||
    id.includes('/react-router/')
  ) {
    return 'react-vendor'
  }

  if (
    id.includes('/@tanstack/react-query/') ||
    id.includes('/axios/') ||
    id.includes('/zustand/')
  ) {
    return 'data-vendor'
  }

  if (
    id.includes('/@antv/g6/') ||
    id.includes('/d3/')
  ) {
    return 'graph-vendor'
  }

  if (
    id.includes('/@uiw/react-codemirror/') ||
    id.includes('/@codemirror/')
  ) {
    return 'editor-vendor'
  }

  if (
    id.includes('/@dnd-kit/')
  ) {
    return 'dnd-vendor'
  }

  return undefined
}

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
        manualChunks: createManualChunk,
      },
    },
  },
})
