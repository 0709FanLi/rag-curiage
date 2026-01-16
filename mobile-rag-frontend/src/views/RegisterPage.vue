<template>
  <div class="page">
    <div class="logo-wrap">
        <img :src="logo" alt="logo" class="logo" />
    </div>
    <div class="card">
      <div class="title">注册</div>

      <div class="field">
        <label class="label">手机号</label>
        <input v-model="phone" class="input" placeholder="请输入手机号" />
      </div>

      <div class="field">
        <label class="label">邮箱</label>
        <input v-model="email" class="input" placeholder="请输入邮箱" />
      </div>

      <div class="field otp">
        <div class="otp-left">
          <label class="label">邮箱验证码</label>
          <input v-model="email_code" class="input" placeholder="请输入6位验证码" />
        </div>
        <button class="otp-btn" :disabled="otp_loading || otp_cooldown > 0" @click="handle_send_code">
          {{ otp_cooldown > 0 ? `${otp_cooldown}s` : '发送验证码' }}
        </button>
      </div>

      <div class="field">
        <label class="label">密码</label>
        <input v-model="password" class="input" type="password" placeholder="至少6位" />
      </div>

      <button class="primary" :disabled="loading" @click="handle_register">
        {{ loading ? '注册中...' : '注册' }}
      </button>

      <div class="hint">
        已有账号？
        <RouterLink class="link" to="/login">去登录</RouterLink>
      </div>

      <div v-if="info_text" class="info">{{ info_text }}</div>
      <div v-if="error_text" class="error">{{ error_text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import { useRouter } from 'vue-router';
import { register_with_email, send_email_code } from '../services/auth_api';
import { get_error_message } from '../utils/api_error';

import logo from '../assets/logo.png';

const email = ref<string>('');
const phone = ref<string>('');
const email_code = ref<string>('');
const password = ref<string>('');
const loading = ref<boolean>(false);
const error_text = ref<string>('');
const info_text = ref<string>('');

const otp_loading = ref<boolean>(false);
const otp_cooldown = ref<number>(0);
let timer: number | null = null;

const router = useRouter();

function start_cooldown(seconds: number): void {
  otp_cooldown.value = seconds;
  if (timer) {
    window.clearInterval(timer);
  }
  timer = window.setInterval(() => {
    otp_cooldown.value -= 1;
    if (otp_cooldown.value <= 0 && timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }, 1000);
}

async function handle_send_code(): Promise<void> {
  error_text.value = '';
  info_text.value = '';
  if (!email.value.trim()) {
    error_text.value = '请先填写邮箱';
    return;
  }
  if (!phone.value.trim()) {
    error_text.value = '请先填写手机号';
    return;
  }
  otp_loading.value = true;
  try {
    await send_email_code(email.value.trim());
    info_text.value = '验证码已发送到邮箱，请查收';
    start_cooldown(60);
  } catch (err: any) {
    error_text.value = get_error_message(err, '发送失败');
  } finally {
    otp_loading.value = false;
  }
}

async function handle_register(): Promise<void> {
  error_text.value = '';
  info_text.value = '';
  if (!email.value.trim() || !phone.value.trim() || !email_code.value.trim() || !password.value) {
    error_text.value = '请完整填写注册信息';
    return;
  }
  loading.value = true;
  try {
    await register_with_email({
      email: email.value.trim(),
      phone: phone.value.trim(),
      email_code: email_code.value.trim(),
      password: password.value,
    });
    await router.replace('/login');
  } catch (err: any) {
    const message = get_error_message(err, '注册失败');
    if (message.includes('账号已存在')) {
      error_text.value = '该邮箱/手机号已注册，请直接登录';
      return;
    }
    error_text.value = message;
  } finally {
    loading.value = false;
  }
}

onBeforeUnmount(() => {
  if (timer) {
    window.clearInterval(timer);
    timer = null;
  }
});
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
  margin-bottom: 100px;
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
.otp {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
.otp-left {
  flex: 1;
}
.otp-btn {
  height: 44px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid #d9d9d9;
  background: #f2effa;
  color: var(--primary);
  font-size: 14px;
}
.otp-btn:disabled {
  opacity: 0.6;
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
.info {
  margin-top: 12px;
  color: #188038;
  font-size: 14px;
}
.error {
  margin-top: 12px;
  color: #d93025;
  font-size: 14px;
}
</style>


