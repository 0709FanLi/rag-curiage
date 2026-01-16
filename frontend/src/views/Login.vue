<template>
  <div class="login-container">
    <div class="login-card">
      <img src="@/assets/logo.png" alt="logo" class="login-logo" />
      <p class="login-subtitle">登录您的健康管理账号</p>
      
      <div class="input-field">
        <p class="field-label">账号</p>
        <div class="input-wrapper">
          <input 
            v-model="form.username" 
            type="text"
            class="field-input" 
            placeholder="请输入账号"
            @keydown.enter="handleLogin"
          />
        </div>
      </div>
      
      <div class="input-field">
        <p class="field-label">密码</p>
        <div class="input-wrapper">
          <input 
            v-model="form.password" 
            type="password"
            class="field-input" 
            placeholder="请输入密码"
            @keydown.enter="handleLogin"
          />
        </div>
      </div>
      
      <div class="button-group">
        <button 
          class="login-button" 
          @click="handleLogin"
          :disabled="loading"
        >
          {{ loading ? '登录中...' : '登  录' }}
        </button>
      </div>
      
      <div class="register-link">
        还没有账号？
        <router-link to="/register">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = ref({
  username: '',
  password: ''
})

const handleLogin = async () => {
  loading.value = true
  try {
    // 后端使用 OAuth2PasswordRequestForm（只支持 application/x-www-form-urlencoded）
    // 注意：不要用 FormData + 强行写 urlencoded，否则后端可能解析不到字段。
    const form_data = new URLSearchParams()
    form_data.append('username', form.value.username)
    form_data.append('password', form.value.password)

    const res = await request.post('/auth/login', form_data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    
    authStore.setToken(res.access_token, { username: res.username, id: res.user_id })
    ElMessage.success('登录成功')
    router.push('/chat')
  } catch (error) {
    console.error(error)
    ElMessage.error(error?.response?.data?.detail || '登录失败，请检查账号密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
  .login-logo{
    width: 150px;
    margin: 0 auto;
  }
/* 容器样式 - 淡紫色背景，占满全屏 */
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 100vh;
  background-color: #fef7ff;
  padding: 20px;
  margin: 0;
  box-sizing: border-box;
}

/* 登录卡片 - 白色卡片，圆角，边框 */
.login-card {
  width: 100%;
  max-width: 561px;
  min-width: 320px;
  background-color: #ffffff;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  box-sizing: border-box;
}

/* Input Field - 对应 Figma 的 Input Field 组件 */
.input-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

/* 字段标签 */
.field-label {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 16px;
  font-weight: 400;
  line-height: 1.4;
  color: #1e1e1e;
  margin: 0;
  padding: 0;
}

/* 输入框包装器 */
.input-wrapper {
  width: 100%;
  min-width: 240px;
  background-color: #ffffff;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  padding: 12px 16px;
  transition: border-color 0.2s ease;
}

.input-wrapper:hover {
  border-color: #8c8c8c;
}

.input-wrapper:focus-within {
  border-color: #2c2c2c;
}

/* 输入框本身 */
.field-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 16px;
  font-weight: 400;
  line-height: 1;
  color: #1e1e1e;
  padding: 0;
  margin: 0;
  min-width: 0;
}

.field-input::placeholder {
  color: #b3b3b3;
}

/* 按钮组 - 对应 Figma 的 Button Group */
.button-group {
  display: flex;
  gap: 16px;
  width: 100%;
}

/* 标题样式 */
.login-title {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 24px;
  font-weight: 600;
  color: #1e1e1e;
  margin: 0;
  text-align: center;
}

.login-subtitle {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 14px;
  color: #8E8E93;
  margin: -12px 0 8px 0;
  text-align: center;
}

/* 登录按钮 */
.login-button {
  flex: 1;
  min-width: 0;
  background-color: #6750A4;
  border: 1px solid #6750A4;
  border-radius: 8px;
  padding: 12px;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 16px;
  font-weight: 500;
  line-height: 1;
  color: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.login-button:hover:not(:disabled) {
  background-color: #5A3D99;
  border-color: #5A3D99;
}

.login-button:active:not(:disabled) {
  background-color: #4F378A;
  border-color: #4F378A;
  transform: scale(0.98);
}

.login-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 注册链接 */
.register-link {
  text-align: center;
  font-size: 14px;
  color: #8E8E93;
}

.register-link a {
  color: #6750A4;
  text-decoration: none;
  font-weight: 500;
}

.register-link a:hover {
  text-decoration: underline;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-card {
    max-width: 100%;
    padding: 20px;
  }
  
  .input-field {
    gap: 6px;
  }
}
</style>

