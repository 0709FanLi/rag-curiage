<template>
  <div class="page">
    <div class="header">
      <button class="back" @click="go_back" aria-label="返回">‹</button>
      <div class="title">报告</div>
      <div class="spacer" />
    </div>

    <div class="content">
      <div v-if="error_text" class="state error">{{ error_text }}</div>
      <div v-else-if="loading" class="state">加载中...</div>
      <div v-else-if="reports.length === 0" class="state">暂无报告</div>

      <div v-else class="list">
        <button v-for="r in reports" :key="r.report_id" class="item" @click="open_report(r.session_id)">
          <div class="main">
            <div class="line1">{{ r.risk_level }}（{{ r.score }}）</div>
            <div class="line2">{{ r.preview }}</div>
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

type ReportItem = {
  session_id: number;
  report_id: number;
  score: number;
  risk_level: string;
  created_at: string;
  preview: string;
};

type ReportListResponse = { reports: ReportItem[] };

const router = useRouter();
const reports = ref<ReportItem[]>([]);
const loading = ref<boolean>(false);
const error_text = ref<string>('');

async function load_reports(): Promise<void> {
  error_text.value = '';
  loading.value = true;
  try {
    const res = await http_request<ReportListResponse>({ url: '/report/list', method: 'GET' });
    reports.value = res.reports || [];
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

function open_report(session_id: number): void {
  router.push(`/report/${session_id}`);
}

onMounted(async () => {
  await load_reports();
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


