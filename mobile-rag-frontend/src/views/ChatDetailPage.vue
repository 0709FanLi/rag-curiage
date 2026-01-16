<template>
  <div class="page">
    <div class="header">
      <button class="back" @click="go_back" aria-label="返回">‹</button>
      <div class="title">健康对话</div>
      <div class="spacer" />
    </div>

    <div ref="scroll_ref" class="messages">
      <div v-for="(m, idx) in messages" :key="idx" class="msg-row" :class="m.role">
        <div class="bubble">{{ get_message_main_text(m.content) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { http_request } from '../services/http';

type MessageItem = { role: 'user' | 'assistant'; content: string };

type SessionHistoryResponse = {
  session_id: number | null;
  messages: { role: string; content: string }[];
};

const route = useRoute();
const router = useRouter();

const session_id = Number(route.params.session_id || 0);

const messages = ref<MessageItem[]>([]);
let popstate_handler: ((event: PopStateEvent) => void) | null = null;

const scroll_ref = ref<HTMLElement | null>(null);

function normalize_role(role: string): 'user' | 'assistant' {
  const r = String(role || '').toLowerCase();
  if (r === 'user' || r === 'human') {
    return 'user';
  }
  return 'assistant';
}

function normalize_messages(raw: { role: string; content: string }[]): MessageItem[] {
  return (raw || []).map((m) => ({ role: normalize_role(m.role), content: String(m.content || '') }));
}

function get_message_main_text(text: string): string {
  const content = String(text || '');
  const markers = Array.from(content.matchAll(/(^|\\s)([A-D])[\\.。、、]\\s*/g));
  if (!markers.length) {
    return content;
  }
  const first = markers[0];
  if (!first) {
    return content;
  }
  const first_index = first.index ?? -1;
  if (first_index <= 0) {
    return content;
  }
  return content.slice(0, first_index).trim();
}

function scroll_to_bottom(): void {
  nextTick(() => {
    if (!scroll_ref.value) {
      return;
    }
    scroll_ref.value.scrollTop = scroll_ref.value.scrollHeight;
  });
}

async function load_session(): Promise<void> {
  const res = await http_request<SessionHistoryResponse>({ url: `/chat/session/${session_id}`, method: 'GET' });
  messages.value = normalize_messages(res.messages || []);
  scroll_to_bottom();
}

function go_back(): void {
  router.replace('/conversations');
}

function install_force_back_to_list(): void {
  try {
    window.history.pushState({ trap: 'chat_detail' }, '');
  } catch {
    // ignore
  }
  popstate_handler = () => {
    if (popstate_handler) {
      window.removeEventListener('popstate', popstate_handler);
      popstate_handler = null;
    }
    router.replace('/conversations');
  };
  window.addEventListener('popstate', popstate_handler);
}

onMounted(async () => {
  install_force_back_to_list();
  await load_session();
});

onBeforeUnmount(() => {
  if (popstate_handler) {
    window.removeEventListener('popstate', popstate_handler);
    popstate_handler = null;
  }
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
  padding: 10px 12px;
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  gap: 8px;
  position: sticky;
  top: 0;
  z-index: 10;
}
.title {
  text-align: center;
  font-weight: 700;
}
.spacer {
  width: 36px;
  height: 36px;
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

.messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px 14px 10px;
  background: var(--bg);
}
.msg-row {
  display: flex;
  margin-bottom: 10px;
}
.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 78%;
  padding: 12px 12px;
  border-radius: 14px;
  background: var(--card);
  border: 1px solid var(--border);
  font-size: 15px;
  line-height: 1.5;
  white-space: pre-wrap;
}
.msg-row.user .bubble {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.options {
  padding: 10px 14px 0;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.option-btn {
  text-align: left;
  background: var(--card);
  border: 1px solid #d9d9d9;
  border-radius: 14px;
  padding: 12px 12px;
  font-size: 15px;
}
.option-btn:disabled {
  opacity: 0.6;
}

.composer {
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  display: flex;
  gap: 10px;
  background: var(--card);
  border-top: 1px solid var(--border);
}
.composer-input {
  flex: 1;
  padding: 12px 12px;
  border-radius: 12px;
  border: 1px solid #d9d9d9;
  font-size: 16px;
}
.composer-send {
  padding: 0 14px;
  border-radius: 12px;
  border: none;
  background: var(--primary);
  color: #fff;
}
.composer-send:disabled {
  opacity: 0.6;
}
</style>


