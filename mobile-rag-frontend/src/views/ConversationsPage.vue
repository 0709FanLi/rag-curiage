<template>
  <div class="page">
    <div class="header">
      <button class="back" @click="go_back" aria-label="返回">‹</button>
      <div class="title">对话</div>
      <div class="spacer" />
    </div>

    <div class="content">
      <div v-if="error_text" class="state error">{{ error_text }}</div>
      <div v-else-if="loading" class="state">加载中...</div>
      <div v-else-if="sessions.length === 0" class="state">暂无对话</div>

      <div v-else class="list">
        <button v-for="s in sessions" :key="s.session_id" class="item" @click="open_session(s.session_id)">
          <div class="main">
            <div class="line1">会话 #{{ s.session_id }}</div>
            <div class="line2">{{ s.preview }}</div>
          </div>
          <div class="arrow">›</div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { http_request } from '../services/http';

type SessionPreview = {
  session_id: number;
  preview: string;
  updated_at: string;
};

type SessionListResponse = { sessions: SessionPreview[] };

const router = useRouter();

const sessions = ref<SessionPreview[]>([]);
const loading = ref<boolean>(false);
const error_text = ref<string>('');

async function load_sessions(): Promise<void> {
  error_text.value = '';
  loading.value = true;
  try {
    const res = await http_request<SessionListResponse>({ url: '/chat/sessions', method: 'GET' });
    sessions.value = res.sessions || [];
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.data?.detail || '加载失败';
    error_text.value = String(detail);
  } finally {
    loading.value = false;
  }
}

function go_back(): void {
  router.replace('/me');
}

function open_session(session_id: number): void {
  router.push(`/chat/${session_id}`);
}

onMounted(async () => {
  await load_sessions();
});
</script>

<style scoped>
.page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.header {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  padding: 12px 14px;
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 10;
}
.title {
  font-weight: 700;
  text-align: center;
}
.back {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 24px;
  line-height: 36px;
  padding: 0;
}
.spacer {
  width: 36px;
  height: 36px;
}
.content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.state {
  padding: 14px;
  color: var(--muted);
}
.state.error {
  color: #d93025;
}
.list {
  padding: 12px 14px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.item {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--card);
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
}
.line1 {
  font-weight: 700;
}
.line2 {
  margin-top: 6px;
  font-size: 13px;
  color: var(--muted);
}
.arrow {
  color: #c7c7cc;
  font-size: 20px;
}
</style>


