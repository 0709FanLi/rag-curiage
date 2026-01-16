import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(() => {
  // 用于 NGINX UA 分流：PC 站点部署在 /pc/ 下（可通过环境变量覆盖）
  const base = process.env.VITE_PUBLIC_BASE || '/pc/'
  return {
  base,
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3001,
    host: '0.0.0.0',
    proxy: {
      // 允许在开发环境下用相对路径访问后端，避免跨域/Network Error
      // 例如：GET http://localhost:3001/api/v1/admin/records/116/sales-script
      '/api': {
        target: 'http://localhost:8010',
        changeOrigin: true,
      },
    },
  }
}
})
