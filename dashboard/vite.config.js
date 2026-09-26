import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  // `vite preview` does not inherit server.proxy, and the built console still
  // talks to the API on :8000, so it needs its own.
  preview: {
    port: 4173,
    proxy: { '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
