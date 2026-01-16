<template>
  <div class="page">
    <div class="logo-wrap">
        <img :src="logo" alt="logo" class="logo" />
    </div>
    <div class="card">
      <div class="title">登录</div>
      <div class="field">
        <label class="label">手机号或邮箱</label>
        <input v-model="identifier" class="input" placeholder="请输入手机号或邮箱" />
      </div>
      <div class="field">
        <label class="label">密码</label>
        <input v-model="password" class="input" type="password" placeholder="请输入密码" />
      </div>

      <button class="primary" :disabled="loading" @click="handle_login">
        {{ loading ? '登录中...' : '登录' }}
      </button>

      <div class="hint">
        没有账号？
        <RouterLink class="link" to="/register">去注册</RouterLink>
      </div>

      <div v-if="error_text" class="error">{{ error_text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { use_auth_store } from '../stores/auth_store';

import logo from '../assets/logo.png';

const identifier = ref<string>('');
const password = ref<string>('');
const loading = ref<boolean>(false);
const error_text = ref<string>('');

const auth_store = use_auth_store();
const router = useRouter();
const route = useRoute();

async function handle_login(): Promise<void> {
  error_text.value = '';
  if (!identifier.value.trim() || !password.value) {
    error_text.value = '请填写账号和密码';
    return;
  }
  loading.value = true;
  try {
    const { login_form } = await import('../services/auth_api');
    const res = await login_form(identifier.value.trim(), password.value);
    auth_store.set_auth(res.access_token, { identifier: identifier.value.trim(), user_id: res.user_id });
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/chat';
    await router.replace(redirect);
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.data?.detail || '登录失败';
    error_text.value = String(detail);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 18px;
}
.card {
  width: 100%;
  max-width: 420px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px;
}
.title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 12px;
}
.logo-wrap {
  display: flex;
  justify-content: center;
  margin: 6px 0 10px;
  margin-bottom: 145px;
}
.logo {
  width: min(220px, 70vw);
  height: auto;
  display: block;
}
.field {
  margin-top: 12px;
}
.label {
  display: block;
  font-size: 14px;
  color: var(--muted);
  margin-bottom: 6px;
}
.input {
  width: 100%;
  padding: 12px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 12px;
  font-size: 16px;
  outline: none;
}
.primary {
  width: 100%;
  margin-top: 16px;
  padding: 12px 12px;
  border: none;
  border-radius: 12px;
  background: var(--primary);
  color: #fff;
  font-size: 16px;
}
.primary:disabled {
  opacity: 0.6;
}
.hint {
  margin-top: 12px;
  font-size: 14px;
  color: var(--muted);
}
.link {
  color: var(--primary);
  font-weight: 600;
}
.error {
  margin-top: 12px;
  color: #d93025;
  font-size: 14px;
}
</style>


