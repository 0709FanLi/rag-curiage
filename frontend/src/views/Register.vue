<template>
  <div class="register-container">
    <div class="register-card">
      <img src="@/assets/logo.png" alt="logo" class="register-logo" />
      <p class="register-subtitle">注册您的健康管理账号</p>
      
      <div class="input-field">
        <p class="field-label">账号</p>
        <div class="input-wrapper" :class="{ error: usernameError }">
          <input 
            v-model="form.username" 
            type="text"
            class="field-input" 
            placeholder="请输入账号（英文字母或数字）"
            @input="validateUsername"
          />
        </div>
        <p v-if="usernameError" class="error-text">{{ usernameError }}</p>
        <p class="hint-text">账号只能包含英文字母和数字，长度 3-20 位</p>
      </div>
      
      <div class="input-field">
        <p class="field-label">密码</p>
        <div class="input-wrapper" :class="{ error: passwordError }">
          <input 
            v-model="form.password" 
            type="password"
            class="field-input" 
            placeholder="请输入密码"
            @input="validatePassword"
          />
        </div>
        <p v-if="passwordError" class="error-text">{{ passwordError }}</p>
      </div>
      
      <div class="input-field">
        <p class="field-label">确认密码</p>
        <div class="input-wrapper" :class="{ error: confirmPasswordError }">
          <input 
            v-model="form.confirmPassword" 
            type="password"
            class="field-input" 
            placeholder="请再次输入密码"
            @input="validateConfirmPassword"
          />
        </div>
        <p v-if="confirmPasswordError" class="error-text">{{ confirmPasswordError }}</p>
      </div>
      
      <div class="button-group">
        <button 
          class="register-button" 
          @click="handleRegister"
          :disabled="loading || !isFormValid"
        >
          {{ loading ? '注册中...' : '注  册' }}
        </button>
      </div>
      
      <div class="login-link">
        已有账号？
        <router-link to="/">立即登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const form = ref({
  username: '',
  password: '',
  confirmPassword: ''
})

const usernameError = ref('')
const passwordError = ref('')
const confirmPasswordError = ref('')

const validateUsername = () => {
  const username = form.value.username
  if (!username) {
    usernameError.value = ''
    return false
  }
  
  // 只允许英文字母和数字
  if (!/^[a-zA-Z0-9]+$/.test(username)) {
    usernameError.value = '账号只能包含英文字母和数字'
    return false
  }
  
  if (username.length < 3 || username.length > 20) {
    usernameError.value = '账号长度需要在 3-20 位之间'
    return false
  }
  
  usernameError.value = ''
  return true
}

const validatePassword = () => {
  const password = form.value.password
  if (!password) {
    passwordError.value = ''
    return false
  }
  
  if (password.length < 6) {
    passwordError.value = '密码长度至少 6 位'
    return false
  }
  
  passwordError.value = ''
  
  // 如果确认密码已填写，同时校验
  if (form.value.confirmPassword) {
    validateConfirmPassword()
  }
  
  return true
}

const validateConfirmPassword = () => {
  const confirmPassword = form.value.confirmPassword
  if (!confirmPassword) {
    confirmPasswordError.value = ''
    return false
  }
  
  if (confirmPassword !== form.value.password) {
    confirmPasswordError.value = '两次输入的密码不一致'
    return false
  }
  
  confirmPasswordError.value = ''
  return true
}

const isFormValid = computed(() => {
  return form.value.username && 
         form.value.password && 
         form.value.confirmPassword &&
         !usernameError.value && 
         !passwordError.value && 
         !confirmPasswordError.value &&
         form.value.password === form.value.confirmPassword
})

const handleRegister = async () => {
  // 最终校验
  const isUsernameValid = validateUsername()
  const isPasswordValid = validatePassword()
  const isConfirmValid = validateConfirmPassword()
  
  if (!isUsernameValid || !isPasswordValid || !isConfirmValid) {
    return
  }
  
  loading.value = true
  try {
    await request.post('/auth/register', {
      username: form.value.username,
      password: form.value.password
    })
    
    ElMessage.success('注册成功，请登录')
    router.push('/')
  } catch (error) {
    console.error(error)
    // 错误消息由 request.js 统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 容器样式 - 淡紫色背景，占满全屏 */
.register-container {
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

/* 注册卡片 - 白色卡片，圆角，边框 */
.register-card {
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

.register-logo{
  width: 150px;
  margin: 0 auto;
}

.register-title {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 24px;
  font-weight: 600;
  color: #1e1e1e;
  margin: 0;
  text-align: center;
}

.register-subtitle {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 14px;
  color: #8E8E93;
  margin: -12px 0 8px 0;
  text-align: center;
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
  border-color: #6750A4;
}

.input-wrapper.error {
  border-color: #FF3B30;
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

/* 提示文字 */
.hint-text {
  font-size: 12px;
  color: #8E8E93;
  margin: 0;
}

/* 错误文字 */
.error-text {
  font-size: 12px;
  color: #FF3B30;
  margin: 0;
}

/* 按钮组 - 对应 Figma 的 Button Group */
.button-group {
  display: flex;
  gap: 16px;
  width: 100%;
  margin-top: 8px;
}

/* 注册按钮 */
.register-button {
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

.register-button:hover:not(:disabled) {
  background-color: #5A3D99;
  border-color: #5A3D99;
}

.register-button:active:not(:disabled) {
  background-color: #4F378A;
  border-color: #4F378A;
  transform: scale(0.98);
}

.register-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 登录链接 */
.login-link {
  text-align: center;
  font-size: 14px;
  color: #8E8E93;
}

.login-link a {
  color: #6750A4;
  text-decoration: none;
  font-weight: 500;
}

.login-link a:hover {
  text-decoration: underline;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .register-card {
    max-width: 100%;
    padding: 24px 20px;
  }
  
  .input-field {
    gap: 6px;
  }
}
</style>

