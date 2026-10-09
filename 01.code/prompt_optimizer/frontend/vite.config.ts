import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Vite 构建配置：开发代理将 /api 转发到后端 FastAPI 服务，生产环境由 Nginx 反代
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 开发环境跨域代理：前端 5173 -> 后端 8000
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // 代码分割：将大体积三方库拆分为独立 chunk，改善加载与缓存
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          antd: ['antd', '@ant-design/icons'],
          echarts: ['echarts'],
        },
      },
    },
  },
})