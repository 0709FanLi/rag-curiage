import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(() => {
  // 用于 NGINX UA 分流：移动站点部署在 /m/ 下（可通过环境变量覆盖）
  const base = process.env.VITE_PUBLIC_BASE || '/m/'
  return {
    base,
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  }
})
