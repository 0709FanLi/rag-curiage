<template>
  <div class="page">
    <div 
      class="profile"
      @click="handle_version_gesture"
    >
      <div class="avatar">🙂</div>
      <div class="profile-text">
        <div class="name">我的</div>
        <div class="sub">{{ identifier }}</div>
      </div>
      <button class="logout" @click.stop="logout">退出</button>
    </div>

    <div class="section">
      <button class="row" @click="to_reports">
        <div class="row-left">
          <div class="row-title">我的报告</div>
          <div class="row-sub">查看已生成的健康报告</div>
        </div>
        <div class="arrow">›</div>
      </button>
      <button class="row" @click="to_conversations">
        <div class="row-left">
          <div class="row-title">我的对话</div>
          <div class="row-sub">查看历史问诊对话</div>
        </div>
        <div class="arrow">›</div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { use_auth_store } from '../stores/auth_store';
import { use_toast_store } from '../stores/toast_store';

const auth_store = use_auth_store();
const router = useRouter();
const toast = use_toast_store();

const identifier = computed<string>(() => auth_store.user?.identifier || '');

const app_version = ref<string>('0.0.0');
let last_tap_ms: number = 0;

async function load_version(): Promise<void> {
  try {
    const base = String(import.meta.env.BASE_URL || '/');
    const url = `${base}verson.txt`;
    const resp = await fetch(url, { cache: 'no-store' });
    const text = await resp.text();
    const m = text.match(/version:\s*([0-9]+(?:\.[0-9]+){2})/i);
    if (m && m[1]) {
      app_version.value = m[1];
    }
  } catch {
    // ignore
  }
}

function handle_version_gesture(): void {
  const now = Date.now();
  const delta = now - last_tap_ms;
  if (delta > 0 && delta < 350) {
    last_tap_ms = 0;
    toast.show(`版本号：${app_version.value}`, 2500);
    return;
  }
  last_tap_ms = now;
}

function logout(): void {
  auth_store.clear_auth();
  router.replace('/login');
}

function to_reports(): void {
  router.push('/reports');
}

function to_conversations(): void {
  router.push('/conversations');
}

onMounted(async () => {
  await load_version();
});
</script>

<style scoped>
.page {
  height: 100%;
  min-height: 0;
  background: var(--bg);
  padding: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.profile {
  background: var(--card);
  border-radius: 16px;
  border: 1px solid var(--border);
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar {
  width: 46px;
  height: 46px;
  border-radius: 23px;
  background: #f2effa;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.profile-text {
  flex: 1;
}
.name {
  font-weight: 700;
}
.sub {
  margin-top: 4px;
  color: var(--muted);
  font-size: 13px;
}
.logout {
  border: none;
  background: transparent;
  color: var(--primary);
  font-weight: 600;
}

.section {
  margin-top: 12px;
  background: var(--card);
  border-radius: 16px;
  border: 1px solid var(--border);
  overflow: hidden;
}
.row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px;
  background: transparent;
  border: none;
  text-align: left;
}
.row + .row {
  border-top: 1px solid var(--border);
}
.row-title {
  font-weight: 700;
}
.row-sub {
  margin-top: 4px;
  color: var(--muted);
  font-size: 13px;
}
.arrow {
  color: #c7c7cc;
  font-size: 20px;
}
</style>


