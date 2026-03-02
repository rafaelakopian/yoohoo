import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  build: {
    sourcemap: false,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: parseInt(process.env.FRONTEND_PORT || '1000'),
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      '/api': {
        target: `http://${process.env.API_HOST || 'localhost'}:${process.env.API_PORT || '8000'}`,
        changeOrigin: true,
      },
      '/health': {
        target: `http://${process.env.API_HOST || 'localhost'}:${process.env.API_PORT || '8000'}`,
        changeOrigin: true,
      },
      '/branding': {
        target: `http://${process.env.API_HOST || 'localhost'}:${process.env.API_PORT || '8000'}`,
        changeOrigin: true,
      },
    },
  },
})
