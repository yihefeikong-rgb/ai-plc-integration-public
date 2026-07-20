import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  test: {
    environment: 'jsdom',
    globals: true,
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      // API 文档（FastAPI Swagger UI），dev 模式走 Vite proxy
      '/docs': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
