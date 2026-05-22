import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyTarget = process.env.VITE_API_URL || 'http://localhost:3282'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 7668,
    proxy: {
      '/api': proxyTarget,
      '/health': proxyTarget,
      '/ingest': proxyTarget,
      '/llm': proxyTarget,
      '/projects': proxyTarget,
      '/schema': proxyTarget,
      '/auth': proxyTarget,
      '/invites': proxyTarget,
      '/waitlist': proxyTarget,
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
