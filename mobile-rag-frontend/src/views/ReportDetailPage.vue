<template>
  <div class="page">
    <div class="header">
      <button class="back" @click="go_back" aria-label="返回">‹</button>
      <div class="title">健康报告</div>
      <div class="spacer" />
    </div>

    <div v-if="error_text" class="state error">{{ error_text }}</div>
    <div v-else class="frame-wrap">
      <iframe class="frame" :src="iframe_src" />
      <div v-if="show_loading" class="loading-mask" aria-live="polite">
        <div class="progress">
          <div class="progress-bar" />
        </div>
      </div>
      <div v-else-if="show_retry" class="retry-mask">
        <div class="retry-card">
          <div class="retry-title">服务器繁忙</div>
          <button class="retry-btn" type="button" @click="retry_generation">重试</button>
        </div>
      </div>
    </div>

    <!-- 推荐产品入口：不依赖 OCR 标签；后端支持兜底规则（-03） -->
    <button
      v-if="!error_text && !show_loading && !show_retry"
      class="fab"
      type="button"
      @click="open_products"
    >
      推荐产品
    </button>

    <div v-if="products_open" class="sheet-mask" @click.self="close_products">
      <div class="sheet">
        <div class="sheet-header">
          <div class="sheet-title">推荐产品</div>
          <button class="sheet-close" type="button" aria-label="关闭" @click="close_products">×</button>
        </div>

        <div v-if="products_loading" class="sheet-state">加载中...</div>
        <div v-else-if="products_error" class="sheet-state error">{{ products_error }}</div>
        <div v-else-if="products.length === 0" class="sheet-state">暂无推荐产品</div>

        <div v-else class="product-list">
          <div v-for="p in products" :key="p.rule_id" class="product-card">
            <div class="product-img">
              <img v-if="p.product_info?.image_url" :src="p.product_info.image_url" :alt="p.product_info?.name || ''" />
              <div v-else class="product-img-placeholder">商品</div>
            </div>
            <div class="product-body">
              <div class="product-name">{{ p.product_info?.name || '-' }}</div>
              <div class="product-desc">{{ p.product_info?.description || '' }}</div>
              <div class="product-meta">
                <div class="product-price" v-if="p.product_info?.price">¥ {{ p.product_info.price }}</div>
                <div class="product-tags">
                  <span class="tag">{{ p.track }}</span>
                  <span class="tag subtle">{{ p.risk_level }}</span>
                  <span v-if="p.matched_tags?.length" class="tag subtle">命中：{{ p.matched_tags.join('、') }}</span>
                  <span v-else class="tag subtle">兜底推荐</span>
                </div>
              </div>
              <div class="product-actions">
                <button class="btn" type="button" @click="open_product_link(p)">去购买</button>
              </div>
            </div>
          </div>
        </div>

        <div class="sheet-footer">
          <button class="btn secondary" type="button" :disabled="products_loading" @click="fetch_recommendations">
            刷新
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { use_auth_store } from '../stores/auth_store';
import { use_toast_store } from '../stores/toast_store';
import { get_api_base_url, http_request } from '../services/http';

const router = useRouter();
const route = useRoute();
const auth_store = use_auth_store();
const toast = use_toast_store();

const error_text = ref<string>('');
const refresh_key = ref<number>(Date.now());
const show_loading = ref<boolean>(true);
const show_retry = ref<boolean>(false);
let poll_timer: number | null = null;
const POLL_INTERVAL_MS = 3000;
let popstate_handler: ((event: PopStateEvent) => void) | null = null;

const session_id = computed<number>(() => Number(route.params.session_id || 0));

type ProductRecommendationItem = {
  rule_id: string;
  track: string;
  risk_level: string;
  matched_tags: string[];
  product_info: {
    name?: string;
    brand?: string;
    description?: string;
    price?: number;
    image_url?: string;
    link?: string;
  };
};

type ProductRecommendationsResponse = {
  success: boolean;
  recommendations: ProductRecommendationItem[];
  total: number;
};

const products_open = ref<boolean>(false);
const products_loading = ref<boolean>(false);
const products_error = ref<string>('');
const products = ref<ProductRecommendationItem[]>([]);

const iframe_src = computed<string>(() => {
  const base = get_api_base_url().replace(/\/+$/, '');
  const token = encodeURIComponent(auth_store.token || '');
  const sid = encodeURIComponent(String(session_id.value || 0));
  return `${base}/report/${sid}/html?token=${token}&_=${refresh_key.value}`;
});

function refresh(): void {
  if (!auth_store.token) {
    error_text.value = '登录已过期，请重新登录';
    return;
  }
  if (!session_id.value) {
    error_text.value = '缺少 session_id';
    return;
  }
  error_text.value = '';
  refresh_key.value = Date.now();
  show_loading.value = true;
  show_retry.value = false;
}

function go_back(): void {
  router.replace('/reports');
}

function open_products(): void {
  products_open.value = true;
  // 首次打开时拉取一次
  if (!products.value.length && !products_loading.value) {
    void fetch_recommendations();
  }
}

function close_products(): void {
  products_open.value = false;
}

async function fetch_recommendations(): Promise<void> {
  if (!auth_store.token) {
    toast.show('请先登录');
    return;
  }
  if (!session_id.value) {
    toast.show('缺少 session_id');
    return;
  }
  products_error.value = '';
  products_loading.value = true;
  try {
    const res = await http_request<ProductRecommendationsResponse>({
      url: `/report/${session_id.value}/recommendations`,
      method: 'GET',
      timeout: 30_000,
    });
    products.value = Array.isArray(res?.recommendations) ? res.recommendations : [];
    if (!products.value.length) {
      toast.show('暂无推荐产品');
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.data?.detail || err?.message || '获取推荐失败';
    products_error.value = String(detail);
  } finally {
    products_loading.value = false;
  }
}

function open_product_link(p: ProductRecommendationItem): void {
  const link = p?.product_info?.link;
  if (!link) {
    toast.show('暂无购买链接');
    return;
  }
  try {
    window.location.href = String(link);
  } catch {
    toast.show('打开链接失败');
  }
}

function install_force_back_to_list(): void {
  try {
    // 添加一个历史状态，让浏览器“返回”触发 popstate，从而被我们接管跳转到列表页
    window.history.pushState({ trap: 'report_detail' }, '');
  } catch {
    // ignore
  }

  popstate_handler = () => {
    if (popstate_handler) {
      window.removeEventListener('popstate', popstate_handler);
      popstate_handler = null;
    }
    router.replace('/reports');
  };
  window.addEventListener('popstate', popstate_handler);
}

async function trigger_report_generation(): Promise<void> {
  // 关键：后端只有在调用该接口后才会启动后台生成
  await http_request({
    url: `/report/${session_id.value}/generate`,
    method: 'POST',
    data: {},
    timeout: 30_000,
  });
}

async function fetch_report_status(): Promise<{ status: string; html_len: number }> {
  const res = await http_request<any>({
    url: `/report/${session_id.value}`,
    method: 'GET',
    timeout: 30_000,
  });
  const status = String(res?.content?.status || '');
  const html = res?.content?.html;
  const html_len = typeof html === 'string' ? html.length : 0;
  return { status, html_len };
}

async function poll_once(): Promise<void> {
  const { status, html_len } = await fetch_report_status();
  if (status === 'completed' && html_len > 0) {
    refresh_key.value = Date.now();
    if (poll_timer) {
      window.clearTimeout(poll_timer);
      poll_timer = null;
    }
    show_retry.value = false;
    show_loading.value = false;
    return;
  }
  if (status === 'error') {
    if (poll_timer) {
      window.clearTimeout(poll_timer);
      poll_timer = null;
    }
    show_loading.value = false;
    show_retry.value = true;
    return;
  }
  // generating / empty: keep loading
  show_retry.value = false;
  show_loading.value = true;
}

function start_polling(): void {
  if (poll_timer) {
    window.clearTimeout(poll_timer);
    poll_timer = null;
  }

  const tick = async (): Promise<void> => {
    try {
      await poll_once();
    } catch {
      // 忽略：不阻断 iframe 自身刷新
    }
    // 仅在仍处于“生成中”时安排下一次轮询；已完成/错误则不再轮询
    if (show_loading.value && !show_retry.value) {
      poll_timer = window.setTimeout(() => {
        void tick();
      }, POLL_INTERVAL_MS);
    } else {
      if (poll_timer) {
        window.clearTimeout(poll_timer);
        poll_timer = null;
      }
    }
  };

  poll_timer = window.setTimeout(() => {
    void tick();
  }, POLL_INTERVAL_MS);
}

async function retry_generation(): Promise<void> {
  refresh();
  if (error_text.value) {
    return;
  }
  try {
    show_loading.value = true;
    show_retry.value = false;
    await trigger_report_generation();
  } catch {
    // 如果触发失败，展示重试
    show_loading.value = false;
    show_retry.value = true;
    return;
  }
  try {
    await poll_once();
  } catch {
    // ignore
  }
  if (show_loading.value && !show_retry.value) {
    start_polling();
  }
}

onMounted(async () => {
  refresh();
  if (error_text.value) {
    return;
  }
  install_force_back_to_list();
  try {
    await trigger_report_generation();
  } catch {
    // 触发失败不阻断 iframe 渲染（iframe 会显示错误/或一直 generating）
  }
  // 初始进入页先展示遮罩，并开始轮询，避免“空白页”体验
  show_loading.value = true;
  show_retry.value = false;
  // 立即请求一次状态（避免等待 3s 才有首个轮询请求）
  try {
    await poll_once();
  } catch {
    // ignore
  }
  if (show_loading.value && !show_retry.value) {
    start_polling();
  }
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
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg);
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
.state {
  padding: 14px;
  color: var(--muted);
}
.state.error {
  color: #d93025;
}
.frame-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
}
.frame {
  width: 100%;
  height: 100%;
  border: none;
  flex: 1;
  min-height: 0;
  background: #fff;
}
.loading-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
}
.progress {
  width: min(320px, 78vw);
  height: 10px;
  border-radius: 999px;
  background: #e9f5ee;
  overflow: hidden;
  border: 1px solid #d9e9df;
}
.progress-bar {
  height: 100%;
  width: 45%;
  border-radius: 999px;
  background: linear-gradient(90deg, #34d399, #22c55e, #86efac);
  animation: progressMove 1.2s ease-in-out infinite;
}
@keyframes progressMove {
  0% {
    transform: translateX(-90%);
    opacity: 0.6;
  }
  50% {
    transform: translateX(70%);
    opacity: 1;
  }
  100% {
    transform: translateX(220%);
    opacity: 0.6;
  }
}

.retry-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.96);
}
.retry-card {
  width: min(320px, 86vw);
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--card);
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}
.retry-title {
  font-weight: 700;
  color: var(--text);
}
.retry-btn {
  width: 100%;
  padding: 12px 12px;
  border-radius: 12px;
  border: none;
  background: var(--primary);
  color: #fff;
  font-size: 16px;
}

.fab {
  position: fixed;
  right: 14px;
  bottom: calc(16px + env(safe-area-inset-bottom));
  z-index: 50;
  border: none;
  border-radius: 999px;
  padding: 12px 14px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
}

.sheet-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}
.sheet {
  width: min(560px, 100%);
  max-height: min(72vh, 520px);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.sheet-header {
  padding: 12px 12px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.sheet-title {
  font-weight: 800;
}
.sheet-close {
  width: 32px;
  height: 32px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: #fff;
  color: var(--muted);
  font-size: 18px;
  line-height: 30px;
  padding: 0;
}
.sheet-state {
  padding: 12px;
  color: var(--muted);
}
.sheet-state.error {
  color: #d93025;
}
.product-list {
  padding: 10px 12px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 平板/横屏：2 列网格 */
@media (min-width: 520px) {
  .product-list {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
}

/* 更宽屏：3 列网格 */
@media (min-width: 900px) {
  .product-list {
    grid-template-columns: repeat(3, 1fr);
  }
}
.product-card {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
}

/* 多列展示时，卡片改为竖向排布，避免信息挤压 */
@media (min-width: 520px) {
  .product-card {
    grid-template-columns: 1fr;
  }

  .product-img {
    width: 100%;
    height: 96px;
  }
}
.product-img {
  width: 72px;
  height: 72px;
  border-radius: 12px;
  border: 1px solid var(--border);
  overflow: hidden;
  background: #f7f7fb;
  display: flex;
  align-items: center;
  justify-content: center;
}
.product-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.product-img-placeholder {
  font-size: 12px;
  color: var(--muted);
  font-weight: 700;
}
.product-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.product-name {
  font-weight: 800;
  color: var(--text);
}
.product-desc {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.product-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.product-price {
  font-weight: 800;
  color: var(--primary);
}
.product-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.tag {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(103, 80, 164, 0.12);
  color: var(--primary);
  border: 1px solid rgba(103, 80, 164, 0.16);
}
.tag.subtle {
  background: rgba(0, 0, 0, 0.04);
  color: var(--muted);
  border-color: rgba(0, 0, 0, 0.08);
}
.product-actions {
  margin-top: 2px;
}
.btn {
  width: 100%;
  border: none;
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--primary);
  color: #fff;
  font-weight: 700;
  white-space: nowrap;
}
.btn.secondary {
  background: #fff;
  color: var(--primary);
  border: 1px solid rgba(103, 80, 164, 0.35);
}
.btn:disabled {
  opacity: 0.6;
}
.sheet-footer {
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.9);
}
</style>


