<template>
  <div class="page">
    <div class="header">
      <div class="header-spacer" />
      <div class="header-title">问诊</div>
      <div class="header-spacer" />
    </div>

    <div ref="scroll_ref" class="messages">
      <div v-if="show_upload_hint" class="upload-hint">
        <div class="upload-hint-text">
          可上传图片/PDF 报告，点击下方 <span class="hint-plus">+</span> 上传文件
        </div>
        <button class="upload-hint-close" type="button" aria-label="关闭提示" @click="dismiss_upload_hint">
          ×
        </button>
      </div>

      <div v-for="(m, idx) in messages" :key="idx" class="msg-row" :class="m.role">
        <div v-if="m.role === 'assistant'" class="msg-avatar" aria-hidden="true">
          <img class="msg-avatar-img" :src="kefu_icon" alt="ai" />
        </div>
        <div class="bubble">
          <template v-if="m.kind === 'thinking'">
            <span class="thinking-text">正在思考中</span>
            <span class="dots" aria-hidden="true">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </span>
          </template>
          <template v-else>
            {{ get_message_main_text(m.content) }}
          </template>
        </div>
        <div v-if="m.role === 'user'" class="msg-avatar right" aria-hidden="true">
          <img class="msg-avatar-img" :src="user_icon" alt="user" />
        </div>
      </div>
    </div>

    <div v-if="last_assistant_options.length" class="options">
      <button
        v-for="opt in last_assistant_options"
        :key="opt.key"
        class="option-btn"
        :disabled="sending"
        @click="send_option(opt.key)"
      >
        {{ opt.key }}. {{ opt.label }}
      </button>
    </div>

    <div v-if="uploaded_files.length" class="upload-preview">
      <button
        v-for="f in uploaded_files"
        :key="f.id"
        class="file-chip"
        :class="{ uploading: f.status === 'uploading', error: f.status === 'error' }"
        type="button"
        @click="handle_file_click(f)"
      >
        <img v-if="f.kind === 'image'" class="thumb" :src="f.url" alt="uploaded" />
        <div v-else class="pdf-icon">PDF</div>
        <button
          v-if="f.status !== 'uploading'"
          class="file-remove"
          type="button"
          aria-label="删除"
          @click.stop="remove_uploaded_file(f.id)"
        >
          ×
        </button>
        <div v-if="f.status === 'uploading'" class="file-mask" aria-hidden="true">
          <span class="file-spinner" />
        </div>
        <div v-else-if="f.status === 'error'" class="file-mask error" aria-hidden="true">
          <span class="file-error-text">!</span>
        </div>
      </button>

    </div>

    <div class="composer">
      <input
        ref="file_input_ref"
        class="file-input"
        type="file"
        multiple
        accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png"
        @change="handle_file_change"
      />
      <button class="upload-btn" @click="open_file_picker" aria-label="上传文件">
        +
      </button>
      <input
        v-model="input_text"
        class="composer-input"
        placeholder="请输入..."
        :disabled="sending"
        @keydown.enter.prevent="send_message"
      />
      <button class="composer-send" :disabled="sending" @click="send_message">{{ sending ? '发送中' : '发送' }}</button>
    </div>

    <div v-if="lightbox_url" class="lightbox" @click="close_lightbox">
      <img class="lightbox-img" :src="lightbox_url" alt="preview" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { http_request } from '../services/http';
import { use_toast_store } from '../stores/toast_store';
import { upload_file } from '../services/upload_api';

import kefu_icon from '../assets/kefu.png';
import user_icon from '../assets/user.png';

type MessageItem = { role: 'user' | 'assistant'; content: string; kind?: 'normal' | 'thinking' };
type OptionItem = { key: string; label: string };

type ActiveSessionResponse = {
  session_id: number | null;
  messages: { role: string; content: string }[];
};

type StartSessionResponse = {
  session_id: number;
  messages: { role: string; content: string }[];
};

type ChatResponse = {
  messages?: string[] | null;
  response?: string | null;
  action: 'chat' | 'report';
  report_data?: unknown;
};

type UploadedFileItem = {
  id: string;
  kind: 'image' | 'pdf';
  url: string;
  name: string;
  status: 'uploading' | 'ready' | 'error';
  object_url?: string;
};

const router = useRouter();
const toast = use_toast_store();

const session_id = ref<number | null>(null);
const messages = ref<MessageItem[]>([]);
const input_text = ref<string>('');
const sending = ref<boolean>(false);
const uploading_count = ref<number>(0);
const uploaded_files = ref<UploadedFileItem[]>([]);
const lightbox_url = ref<string>('');
let attach_debounce_timer: number | null = null;
const show_upload_hint = ref<boolean>(false);
let upload_hint_timer: number | null = null;
let report_redirect_timer: number | null = null;

const UPLOAD_HINT_DISMISSED_KEY = 'healthy_rag_upload_hint_dismissed';

const scroll_ref = ref<HTMLElement | null>(null);
const file_input_ref = ref<HTMLInputElement | null>(null);

const MAX_OCR_IMAGES = 10;
const MAX_PDF_TOTAL_MB_PER_BATCH = 50;

function make_temp_id(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function infer_kind(file: File): 'image' | 'pdf' {
  const t = (file.type || '').toLowerCase();
  if (t === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
    return 'pdf';
  }
  return 'image';
}

function add_upload_placeholder(file: File): string {
  const id = make_temp_id();
  const kind = infer_kind(file);
  let object_url: string | undefined;
  let url = '';
  if (kind === 'image') {
    try {
      object_url = URL.createObjectURL(file);
      url = object_url;
    } catch {
      // ignore
    }
  }
  const item: UploadedFileItem = {
    id,
    kind,
    url,
    name: file.name,
    status: 'uploading',
    object_url,
  };
  uploaded_files.value = [...uploaded_files.value, item];
  return id;
}

function update_uploaded_item(
  id: string,
  patch: Partial<UploadedFileItem>,
): void {
  const idx = uploaded_files.value.findIndex((x) => x.id === id);
  if (idx < 0) {
    return;
  }
  const prev = uploaded_files.value[idx];
  if (!prev) {
    return;
  }
  // 如果将 object_url 替换成服务端 URL，释放本地 object URL
  if (
    prev.object_url &&
    patch.url &&
    patch.url !== prev.object_url &&
    prev.object_url.startsWith('blob:')
  ) {
    try {
      URL.revokeObjectURL(prev.object_url);
    } catch {
      // ignore
    }
    patch.object_url = undefined;
  }
  const next = { ...prev, ...patch };
  const copy = [...uploaded_files.value];
  copy[idx] = next;
  uploaded_files.value = copy;
}

function cleanup_all_object_urls(): void {
  for (const f of uploaded_files.value) {
    if (f.object_url && f.object_url.startsWith('blob:')) {
      try {
        URL.revokeObjectURL(f.object_url);
      } catch {
        // ignore
      }
    }
  }
}

function open_file_picker(): void {
  file_input_ref.value?.click();
}

function bytes_to_mb(bytes: number): number {
  return bytes / 1024 / 1024;
}

async function handle_file_change(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement | null;
  const files = Array.from(input?.files || []);
  // reset input so selecting same file again still triggers change
  if (input) {
    input.value = '';
  }
  if (!files.length) {
    return;
  }
  if (!session_id.value) {
    await start_new_chat();
  }
  if (!session_id.value) {
    toast.show('会话未就绪，请稍后重试');
    return;
  }

  const images = files.filter((f) => (f.type || '').startsWith('image/'));
  const pdfs = files.filter((f) => (f.type || '').toLowerCase() === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));

  if (images.length > MAX_OCR_IMAGES) {
    toast.show(`最多上传 ${MAX_OCR_IMAGES} 张图片`);
    return;
  }

  const pdf_total_mb = pdfs.reduce((acc, f) => acc + bytes_to_mb(f.size || 0), 0);
  if (pdf_total_mb > MAX_PDF_TOTAL_MB_PER_BATCH) {
    toast.show(`PDF 总大小不能超过 ${MAX_PDF_TOTAL_MB_PER_BATCH}MB`);
    return;
  }

  // 并发上传：选中文件后立即出现预览占位（loading），上传成功后替换为真实文件
  for (const f of files) {
    const placeholder_id = add_upload_placeholder(f);
    void upload_one_file(f, placeholder_id);
  }
}

async function upload_one_file(file: File, placeholder_id: string): Promise<void> {
  uploading_count.value += 1;
  try {
    const res = await upload_file(file);
    if (!res?.success || !res.file_url) {
      throw new Error('上传失败');
    }

    update_uploaded_item(placeholder_id, {
      kind: infer_kind(file),
      url: res.file_url,
      name: file.name,
      status: 'ready',
    });
    schedule_attach_sync();
  } catch (err: any) {
    const detail =
      err?.response?.data?.detail ||
      err?.data?.detail ||
      err?.message ||
      '上传失败，请稍后再试';
    toast.show(String(detail));
    update_uploaded_item(placeholder_id, { status: 'error' });
  } finally {
    uploading_count.value = Math.max(0, uploading_count.value - 1);
  }
}

function schedule_attach_sync(): void {
  // 静默同步附件列表到后端（不做 OCR/解析）
  if (!session_id.value) {
    return;
  }
  if (attach_debounce_timer) {
    window.clearTimeout(attach_debounce_timer);
    attach_debounce_timer = null;
  }
  attach_debounce_timer = window.setTimeout(() => {
    void sync_attached_files();
  }, 300);
}

async function sync_attached_files(): Promise<void> {
  if (!session_id.value) {
    return;
  }
  const urls = uploaded_files.value
    .filter((f) => f.status === 'ready' && Boolean(f.url))
    .map((f) => f.url);
  try {
    await http_request({
      url: '/chat/upload-report',
      method: 'POST',
      data: { session_id: session_id.value, file_urls: urls },
      timeout: 30_000,
    });
  } catch {
    // 静默失败：不影响用户继续操作
  }
}

function handle_file_click(f: UploadedFileItem): void {
  if (f.status === 'uploading') {
    return;
  }
  if (f.status === 'error') {
    toast.show('上传失败，请重试');
    return;
  }
  if (f.kind === 'pdf') {
    toast.show('暂不支持预览 PDF');
    return;
  }
  lightbox_url.value = f.url;
}

function remove_uploaded_file(id: string): void {
  const idx = uploaded_files.value.findIndex((x) => x.id === id);
  if (idx < 0) {
    return;
  }
  const item = uploaded_files.value[idx];
  if (item?.object_url && item.object_url.startsWith('blob:')) {
    try {
      URL.revokeObjectURL(item.object_url);
    } catch {
      // ignore
    }
  }
  const copy = [...uploaded_files.value];
  copy.splice(idx, 1);
  uploaded_files.value = copy;
  schedule_attach_sync();
}

function close_lightbox(): void {
  lightbox_url.value = '';
}

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

function parse_options(text: string): OptionItem[] {
  const content = String(text || '');
  const markers = Array.from(content.matchAll(/(^|\\s)([A-D])[\\.。、、]\\s*/g));
  if (!markers.length) {
    return [];
  }
  const first = markers[0];
  if (!first) {
    return [];
  }
  const first_index = first.index ?? -1;
  if (first_index < 0) {
    return [];
  }
  const opts: OptionItem[] = [];
  for (let i = 0; i < markers.length; i += 1) {
    const cur = markers[i];
    if (!cur) {
      continue;
    }
    const key = String(cur[2] ?? '').trim();
    if (!key) {
      continue;
    }
    const start = (cur.index ?? 0) + String(cur[0] ?? '').length;
    const next = markers[i + 1];
    const end = next ? (next.index ?? content.length) : content.length;
    const label = content.slice(start, end).trim();
    if (label) {
      opts.push({ key, label });
    }
  }
  return opts;
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

const last_assistant_options = computed<OptionItem[]>(() => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const msg = messages.value[i];
    if (msg && msg.role === 'assistant' && msg.kind !== 'thinking') {
      return parse_options(msg.content);
    }
  }
  return [];
});

function scroll_to_bottom(): void {
  nextTick(() => {
    if (!scroll_ref.value) {
      return;
    }
    scroll_ref.value.scrollTop = scroll_ref.value.scrollHeight;
  });
}

async function load_active(): Promise<void> {
  const res = await http_request<ActiveSessionResponse>({ url: '/chat/active', method: 'GET' });
  session_id.value = res.session_id;
  messages.value = normalize_messages(res.messages || []);
  if (!session_id.value) {
    await start_new_chat();
  } else {
    scroll_to_bottom();
  }
}

async function start_new_chat(): Promise<void> {
  const res = await http_request<StartSessionResponse>({
    url: '/chat/start',
    method: 'POST',
    data: {},
  });
  session_id.value = res.session_id;
  messages.value = normalize_messages(res.messages || []);
  scroll_to_bottom();
}

async function send_message_with_content(content: string): Promise<void> {
  if (!session_id.value) {
    await start_new_chat();
  }
  const trimmed = content.trim();
  if (!trimmed) {
    return;
  }

  input_text.value = '';
  messages.value.push({ role: 'user', content: trimmed });
  messages.value.push({ role: 'assistant', content: '', kind: 'thinking' });
  scroll_to_bottom();

  sending.value = true;
  try {
    const res = await http_request<ChatResponse>({
      url: '/chat/message',
      method: 'POST',
      data: { session_id: session_id.value, content: trimmed },
      timeout: 180_000,
    });

    const last = messages.value[messages.value.length - 1];
    if (last && last.kind === 'thinking') {
      messages.value.pop();
    }

    const assistant_texts: string[] = [];
    if (res.messages && Array.isArray(res.messages)) {
      assistant_texts.push(...res.messages);
    } else if (res.response) {
      assistant_texts.push(res.response);
    }

    for (const t of assistant_texts) {
      messages.value.push({ role: 'assistant', content: t });
    }

    if (res.action === 'report') {
      if (session_id.value) {
        // 触发后台生成（否则报告会一直卡在 generating）
        try {
          await http_request({
            url: `/report/${session_id.value}/generate`,
            method: 'POST',
            data: {},
            timeout: 30_000,
          });
        } catch {
          // 触发失败不阻断跳转
        }

        // 倒计时 3s 后跳转报告详情页
        if (report_redirect_timer) {
          window.clearTimeout(report_redirect_timer);
          report_redirect_timer = null;
        }

        let remain = 3;
        const tick = () => {
          if (remain <= 0) {
            router.push(`/report/${session_id.value}`);
            report_redirect_timer = null;
            return;
          }
          toast.show(`正在生成报告，即将跳转报告详情页（${remain}s）`, 1100);
          remain -= 1;
          report_redirect_timer = window.setTimeout(tick, 1000);
        };
        tick();
      }
    }
    scroll_to_bottom();
  } finally {
    const last = messages.value[messages.value.length - 1];
    if (last && last.kind === 'thinking') {
      messages.value.pop();
    }
    sending.value = false;
  }
}

async function send_message(): Promise<void> {
  await send_message_with_content(input_text.value);
}

async function send_option(option_key: string): Promise<void> {
  await send_message_with_content(option_key);
}

onMounted(async () => {
  await load_active();

  // 进入页面的提示气泡：若用户手动关闭过，则不再提示；否则每次进入都会提示 3s 后自动隐藏
  try {
    const dismissed = localStorage.getItem(UPLOAD_HINT_DISMISSED_KEY);
    if (!dismissed) {
      show_upload_hint.value = true;
      if (upload_hint_timer) {
        window.clearTimeout(upload_hint_timer);
      }
      upload_hint_timer = window.setTimeout(() => {
        show_upload_hint.value = false;
        upload_hint_timer = null;
      }, 3000);
    }
  } catch {
    // ignore
  }
});

onBeforeUnmount(() => {
  if (attach_debounce_timer) {
    window.clearTimeout(attach_debounce_timer);
    attach_debounce_timer = null;
  }
  cleanup_all_object_urls();
});

function dismiss_upload_hint(): void {
  show_upload_hint.value = false;
  if (upload_hint_timer) {
    window.clearTimeout(upload_hint_timer);
    upload_hint_timer = null;
  }
  try {
    localStorage.setItem(UPLOAD_HINT_DISMISSED_KEY, '1');
  } catch {
    // ignore
  }
}
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
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-title {
  text-align: center;
  font-weight: 700;
}
.header-spacer {
  width: 36px;
  height: 36px;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px 14px 10px;
  background: var(--bg);
  position: relative;
}

.upload-hint {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
}
.upload-hint-text {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.4;
}
.hint-plus {
  color: var(--primary);
  font-weight: 800;
}
.upload-hint-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 18px;
  line-height: 28px;
  padding: 0;
}

.msg-row {
  display: flex;
  margin-bottom: 10px;
}
.msg-row.user {
  justify-content: flex-end;
  align-items: flex-start;
}
.msg-row.assistant {
  justify-content: flex-start;
  align-items: flex-start;
}
.msg-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  overflow: hidden;
  flex: 0 0 auto;
  margin-right: 8px;
  margin-top: 2px; /* 与气泡第一行更贴近 */
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: #fff;
}
.msg-avatar.right {
  margin-right: 0;
  margin-left: 8px;
}
.msg-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
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
.upload-preview {
  padding: 10px 12px;
  background: var(--bg);
  display: flex;
  gap: 10px;
  overflow-x: auto;
  align-items: center;
}
.file-chip {
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--card);
  position: relative;
  overflow: hidden;
}
.file-chip.uploading {
  opacity: 0.95;
}
.file-chip.error {
  border-color: rgba(217, 48, 37, 0.6);
}
.file-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 9px;
  border: none;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  font-size: 14px;
  line-height: 18px;
  padding: 0;
  z-index: 3;
}
.file-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.65);
}
.file-mask.error {
  background: rgba(255, 235, 235, 0.8);
}
.file-spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid #e5e5ea;
  border-top-color: var(--primary);
  animation: uploadSpin 0.9s linear infinite;
}
.file-error-text {
  width: 18px;
  height: 18px;
  border-radius: 9px;
  background: rgba(217, 48, 37, 0.9);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 12px;
  line-height: 18px;
}
.thumb {
  width: 100%;
  height: 100%;
  border-radius: 12px;
  object-fit: cover;
}
.pdf-icon {
  width: 100%;
  height: 100%;
  border-radius: 12px;
  background: rgba(103, 80, 164, 0.12);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}
.file-input {
  display: none;
}
.upload-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: 1px solid #d9d9d9;
  background: #fff;
  color: var(--primary);
  font-size: 22px;
  line-height: 38px;
  padding: 0;
}
.upload-btn:disabled {
  opacity: 0.6;
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

.thinking-text {
  color: var(--muted);
}
.dots {
  display: inline-flex;
  gap: 4px;
  margin-left: 6px;
  vertical-align: middle;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 3px;
  background: #c7c7cc;
  animation: dotPulse 1.2s infinite ease-in-out;
}
.dot:nth-child(2) {
  animation-delay: 0.15s;
}
.dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes dotPulse {
  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  40% {
    transform: translateY(-2px);
    opacity: 1;
  }
}

.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 9999;
}
.lightbox-img {
  max-width: 92vw;
  max-height: 92vh;
  border-radius: 12px;
  background: #fff;
}

</style>


