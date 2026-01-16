<template>
  <div class="history-page">
    <!-- 左侧：报告列表 -->
      <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="sidebar-header">
          <button class="menu-btn" @click="toggleSidebar">
            <img 
              :src="sidebarCollapsed ? menuCollapseIcon : menuExpandIcon" 
              alt="菜单" 
              class="menu-icon"
            />
          </button>
        </div>
        
        <div class="sidebar-content" v-show="!sidebarCollapsed">
          <!-- 开始新对话 -->
          <button class="new-chat-btn" @click="startNewChat">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span>开始新对话</span>
          </button>
          
          <!-- 查看历史报告 -->
          <button class="history-btn active">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
              <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span>查看历史报告</span>
          </button>
          
          <div class="history-section">
            <div class="section-title">最近对话</div>
            <div class="reports-list">
              <div 
                v-for="item in reportsList" 
                :key="item.session_id"
                class="report-item"
                @click="selectHistoryChat(item.session_id)"
              >
                <div class="report-preview">{{ item.preview }}</div>
                <div class="report-meta">
                  <span class="report-date">{{ formatDate(item.created_at) }}</span>
                </div>
              </div>
              
              <div v-if="reportsList.length === 0" class="empty-list">
                <p>暂无历史对话</p>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 折叠状态：只显示图标 -->
        <div class="sidebar-icons" v-show="sidebarCollapsed">
          <button class="icon-btn" @click="startNewChat" title="开始新对话">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </button>
          <button class="icon-btn active" title="查看历史报告">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
              <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </aside>

      <!-- 右侧：主内容区 -->
      <div class="main-content">
        <!-- 顶部头部 -->
        <header class="history-header">
          <div class="header-left"></div>
          <h1 class="page-title">查看历史报告</h1>
          <div class="header-right">
            <span class="username">{{ user.username || 'Lana' }}</span>
            <div class="user-avatar" @click="handleAvatarClick" title="点击退出登录">
              <img src="@/assets/avatar.png" class="u-avatar" alt="avatar" />
            </div>
          </div>
        </header>
        
        <!-- 报告详情 -->
        <main class="report-detail">
          <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <div v-else-if="currentReport" class="report-content-wrapper">
          <!-- 报告信息栏 -->
          <div class="report-info-bar">
            <div class="info-left">
              <span class="info-label">生成时间</span>
              <span class="info-value">{{ formatDateTime(currentReport.created_at) }}</span>
            </div>
            <div class="navigation-buttons">
              <button 
                class="view-newer-btn" 
                @click="viewNewerReport"
                :disabled="currentReportIndex <= 0"
                v-if="currentReportIndex > 0"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                查看上一个报告
              </button>
              <button 
                class="view-older-btn" 
                @click="viewOlderReport"
                :disabled="currentReportIndex >= reportsList.length - 1"
              >
                查看更早报告
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M19 12H5M5 12L12 5M5 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- HTML报告内容：使用 iframe 渲染完整 HTML 文档（避免 v-html 插入 <!DOCTYPE html>/<html> 导致空白） -->
          <div class="html-report">
            <iframe class="html-report-iframe" :src="report_iframe_src" />
          </div>

          <!-- OCR分析和标签展示区 -->
          <div
            v-if="
              sessionData &&
              (sessionData.ocr_text ||
                (sessionData.ocr_tags && sessionData.ocr_tags.length > 0))
            "
            class="ocr-analysis-section"
          >
            <h3 class="section-title">📋 体检报告分析</h3>
            
            <!-- OCR识别文本 -->
            <div v-if="sessionData.ocr_text" class="ocr-text-card">
              <h4 class="card-title">🔍 OCR识别内容</h4>
              <div class="ocr-text-content">{{ sessionData.ocr_text }}</div>
            </div>

            <!-- 提取的标签 -->
            <div v-if="sessionData.ocr_tags && sessionData.ocr_tags.length > 0" class="tags-card">
              <h4 class="card-title">🏷️ 提取的健康标签 ({{ sessionData.ocr_tags.length }})</h4>
              <div class="tags-list">
                <span v-for="(tag, index) in sessionData.ocr_tags" :key="index" class="tag-item">
                  {{ tag }}
                </span>
              </div>
              <!-- 标定的赛道信息 -->
              <div v-if="sessionData.track && sessionData.track.length > 0" class="track-info">
                <span class="track-label">标定赛道：</span>
                <span class="track-value">{{ formatTracks(sessionData.track) }}</span>
              </div>
            </div>
          </div>

          <!-- 免责声明 -->
          <div class="disclaimer-text">
            *本报告仅供参考，不作为医学诊断依据
          </div>

          <!-- 底部商品推荐区
               说明：后端支持“无标签兜底（-03 规则）”，因此不再要求必须有 OCR 标签才显示入口 -->
          <div v-if="sessionData" class="products-section">
            <!-- 初始状态：推荐产品按钮 + 左侧图标 -->
            <div v-if="!showProducts" class="recommend-trigger">
              <div class="trigger-icons">
                <div class="icon-circle">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="8" r="3" fill="#8B7FE5"/>
                    <path d="M5 20C5 16 8 14 12 14C16 14 19 16 19 20" fill="#8B7FE5"/>
                  </svg>
                </div>
                <div class="icon-circle">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <rect x="4" y="4" width="7" height="7" rx="1" fill="#6750A4"/>
                    <rect x="13" y="4" width="7" height="7" rx="1" fill="#6750A4"/>
                    <rect x="4" y="13" width="7" height="7" rx="1" fill="#6750A4"/>
                    <rect x="13" y="13" width="7" height="7" rx="1" fill="#6750A4"/>
                  </svg>
                </div>
                <div class="icon-circle">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2L15 8L22 9L17 14L18 21L12 18L6 21L7 14L2 9L9 8L12 2Z" fill="#8B7FE5"/>
                  </svg>
                </div>
              </div>
              <button class="recommend-btn" @click="fetchProductRecommendations()">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M9 3H15M3 9H21M3 15H21M9 21H15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                推荐产品
              </button>
            </div>

            <!-- 展开状态：产品列表 + 换一换按钮 -->
            <div v-else class="products-expanded">
            <!-- 换一换按钮 -->
            <div class="products-header">
              <div class="change-products">
                  <button class="change-btn" @click="changeProducts">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    <path d="M21 3V8H16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  换一换
                </button>
              </div>
            </div>

            <!-- 商品卡片 -->
            <div class="products-grid">
              <div v-for="product in products" :key="product.rule_id" class="product-card">
                <!-- 产品图片 -->
                <div class="product-image">
                  <img :src="product.product_info.image_url" 
                       :alt="product.product_info.name"
                       @error="handleImageError($event, product)" />
                </div>
                <div class="product-info">
                  <h4 class="product-title">{{ product.product_info.name }}</h4>
                  <p class="product-desc">{{ product.product_info.description }}</p>
                  <div class="product-tags">
                    <span v-for="(feature, idx) in product.product_info.features" :key="idx" class="product-tag">
                      {{ feature }}
                    </span>
                  </div>
                  <p class="product-price">¥ {{ product.product_info.price }}</p>
                  <div class="product-actions">
                    <button class="view-details-btn" @click="showProductDetail(product)">查看详情</button>
                    <button @click="buyProduct(product.product_info.link)" class="buy-now-btn">去购买</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

          <div v-else class="empty-detail">
            <p>请从左侧选择一个报告查看</p>
          </div>
        </main>
      </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'

// 导入图标
import menuExpandIcon from '@/assets/icons/menu-expand.png'
import menuCollapseIcon from '@/assets/icons/menu-collapse.png'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const user = computed(() => authStore.user || {})

const reportsList = ref([]) // 所有报告列表，按时间倒序
const currentReportIndex = ref(0) // 当前显示的报告索引（0 = 最新）
const currentReport = ref(null)
const sessionData = ref(null) // 会话数据（包含OCR文本和标签）
const loading = ref(false)
const sidebarCollapsed = ref(false)
const showProducts = ref(false) // 是否显示产品列表
const products = ref([]) // 推荐产品列表
const report_iframe_refresh_key = ref(Date.now())

// 默认占位图列表（3个不同的SVG占位图，不带文字）
const defaultProductImages = [
  // 占位图1 - 紫色渐变 + 瓶子图标
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8ZGVmcz4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZ3JhZDEiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdHlsZT0ic3RvcC1jb2xvcjojRThFM0ZGO3N0b3Atb3BhY2l0eToxIiAvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0eWxlPSJzdG9wLWNvbG9yOiNENEM1Rjk7c3RvcC1vcGFjaXR5OjEiIC8+CiAgICA8L2xpbmVhckdyYWRpZW50PgogIDwvZGVmcz4KICA8cmVjdCB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0idXJsKCNncmFkMSkiIHJ4PSI4Ii8+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMTUwLCAxMDApIj4KICAgIDxyZWN0IHg9Ii0yNSIgeT0iLTE1IiB3aWR0aD0iNTAiIGhlaWdodD0iNjAiIGZpbGw9IiM4QjdGRTUiIHJ4PSI1Ii8+CiAgICA8cmVjdCB4PSItMjAiIHk9Ii0yMyIgd2lkdGg9IjQwIiBoZWlnaHQ9IjEyIiBmaWxsPSIjNjc1MEE0IiByeD0iMyIvPgogICAgPGNpcmNsZSBjeD0iLTEwIiBjeT0iMTAiIHI9IjQiIGZpbGw9IiNFOEUzRkYiIG9wYWNpdHk9IjAuNyIvPgogICAgPGNpcmNsZSBjeD0iOCIgY3k9IjIwIiByPSIzIiBmaWxsPSIjRThFM0ZGIiBvcGFjaXR5PSIwLjciLz4KICA8L2c+Cjwvc3ZnPgo=',
  // 占位图2 - 蓝色渐变 + 药片图标
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8ZGVmcz4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZ3JhZDIiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdHlsZT0ic3RvcC1jb2xvcjojRTZGNEZGO3N0b3Atb3BhY2l0eToxIiAvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0eWxlPSJzdG9wLWNvbG9yOiNDNUU1RkY7c3RvcC1vcGFjaXR5OjEiIC8+CiAgICA8L2xpbmVhckdyYWRpZW50PgogIDwvZGVmcz4KICA8cmVjdCB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0idXJsKCNncmFkMikiIHJ4PSI4Ii8+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMTUwLCAxMDApIj4KICAgIDxlbGxpcHNlIGN4PSIwIiBjeT0iMCIgcng9IjQwIiByeT0iMjgiIGZpbGw9IiM0MEE5RkYiIG9wYWNpdHk9IjAuOSIvPgogICAgPGVsbGlwc2UgY3g9IjAiIGN5PSIwIiByeD0iMzUiIHJ5PSIyMyIgZmlsbD0iIzYwQjhGRiIvPgogICAgPGxpbmUgeDE9Ii00MCIgeTE9IjAiIHgyPSI0MCIgeTI9IjAiIHN0cm9rZT0iI0U2RjRGRiIgc3Ryb2tlLXdpZHRoPSIzIi8+CiAgICA8Y2lyY2xlIGN4PSItMTIiIGN5PSItOCIgcj0iNSIgZmlsbD0iI0U2RjRGRiIgb3BhY2l0eT0iMC42Ii8+CiAgPC9nPgo8L3N2Zz4K',
  // 占位图3 - 绿色渐变 + 胶囊图标
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8ZGVmcz4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZ3JhZDMiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdHlsZT0ic3RvcC1jb2xvcjojRTZGRkY0O3N0b3Atb3BhY2l0eToxIiAvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0eWxlPSJzdG9wLWNvbG9yOiNDNUZGRDg7c3RvcC1vcGFjaXR5OjEiIC8+CiAgICA8L2xpbmVhckdyYWRpZW50PgogIDwvZGVmcz4KICA8cmVjdCB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0idXJsKCNncmFkMykiIHJ4PSI4Ii8+CiAgPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMTUwLCAxMDApIj4KICAgIDxyZWN0IHg9Ii0zMCIgeT0iLTE4IiB3aWR0aD0iNjAiIGhlaWdodD0iMzYiIGZpbGw9IiM0MEQ5N0EiIHJ4PSIxOCIvPgogICAgPHJlY3QgeD0iLTMwIiB5PSItMTgiIHdpZHRoPSIzMCIgaGVpZ2h0PSIzNiIgZmlsbD0iIzYwRUY5MCIgcng9IjE4Ii8+CiAgICA8Y2lyY2xlIGN4PSIxMCIgY3k9Ii02IiByPSI0IiBmaWxsPSIjRTZGRkY0IiBvcGFjaXR5PSIwLjUiLz4KICAgIDxjaXJjbGUgY3g9IjE1IiBjeT0iOCIgcj0iMyIgZmlsbD0iI0U2RkZGNCIgb3BhY2l0eT0iMC41Ii8+CiAgPC9nPgo8L3N2Zz4K'
]

// 图片加载失败处理
const handleImageError = (event, product) => {
  console.log(`产品图片加载失败: ${product.product_info.name}`)
  // 根据产品的 rule_id 哈希值选择一个默认图片
  const index = Math.abs(hashCode(product.rule_id)) % defaultProductImages.length
  event.target.src = defaultProductImages[index]
  // 防止无限循环（如果默认图也失败）
  event.target.onerror = null
}

// 简单的字符串哈希函数
const hashCode = (str) => {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // Convert to 32bit integer
  }
  return hash
}

// 格式化赛道显示
const formatTracks = (tracks) => {
  if (!tracks || tracks.length === 0) return '未知'
  if (typeof tracks === 'string') return tracks
  return tracks.join('、')
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const startNewChat = () => {
  router.push('/chat')
}

const viewHistory = () => {
  // 已经在历史页面，不需要跳转，或许可以刷新列表或重置
  loadReportsList()
}

const reportContent = computed(() => {
  if (!currentReport.value || !currentReport.value.content) return ''
  if (currentReport.value.content.html) {
    return currentReport.value.content.html
  }
  return ''
})

const report_iframe_src = computed(() => {
  if (!currentReport.value || !currentReport.value.session_id) return ''
  if (!authStore.token) return ''

  const base =
    import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8010/api/v1')

  const safe_base = String(base).replace(/\/+$/, '')
  const sid = encodeURIComponent(String(currentReport.value.session_id))
  const token = encodeURIComponent(String(authStore.token || ''))
  return `${safe_base}/report/${sid}/html?token=${token}&_=${report_iframe_refresh_key.value}`
})

const formatDate = (dateStr) => {
  // 兼容性处理：如果后端返回的是 UTC 字符串且不带 Z/+（旧数据），强制加上 Z
  let dateInput = dateStr
  if (typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+')) {
    dateInput = dateStr + 'Z'
  }

  const date = new Date(dateInput)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  
  return `${date.getMonth() + 1}/${date.getDate()}`
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  
  try {
    // 兼容性处理：如果后端返回的是 UTC 字符串且不带 Z/+（旧数据），强制加上 Z 以确保被识别为 UTC
    let dateInput = dateStr
    if (typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+')) {
      dateInput = dateStr + 'Z'
    }
    
    const date = new Date(dateInput)
    if (isNaN(date.getTime())) return ''
    
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    
    return `${year}-${month}-${day} ${hours}:${minutes}`
  } catch (e) {
    console.error('日期格式化错误:', e)
    return ''
  }
}

const loadReportsList = async () => {
  try {
    const res = await request.get('/report/list')
    reportsList.value = res.reports || []
    
    // 默认加载最新报告（索引 0）
    if (reportsList.value.length > 0) {
      currentReportIndex.value = 0
      await loadReportByIndex(0)
    }
  } catch (error) {
    console.error('加载报告列表失败:', error)
    ElMessage.error('加载报告列表失败')
  }
}

// 点击左侧"最近对话"项，跳转到对话页面（只读模式）
const selectHistoryChat = (sessionId) => {
  router.push({
    path: '/chat',
    query: {
      sessionId: sessionId,
      readOnly: 'true'
    }
  })
}

// 根据索引加载报告
const loadReportByIndex = async (index) => {
  if (index < 0 || index >= reportsList.value.length) {
    return
  }
  
  // 切换报告时重置产品显示状态
  showProducts.value = false
  
  loading.value = true
  const sessionId = reportsList.value[index].session_id
  
  try {
    const res = await request.get(`/report/${sessionId}`)
    currentReport.value = res
    report_iframe_refresh_key.value = Date.now()
    currentReportIndex.value = index
    
    // 获取session数据（包含OCR文本和标签）
    if (res.session_id) {
      try {
        console.log('=== History页面获取Session数据 ===', `session_id: ${res.session_id}`)
        const sessionRes = await request.get(`/chat/session/${res.session_id}`)
        console.log('Session响应:', sessionRes)
        console.log('OCR文本长度:', sessionRes.ocr_text?.length || 0)
        console.log('OCR标签:', sessionRes.ocr_tags)
        sessionData.value = sessionRes
        
        // 不自动获取产品推荐，等待用户点击"推荐产品"按钮
        if (sessionRes.ocr_tags && sessionRes.ocr_tags.length > 0) {
          console.log('History页面 - 检测到OCR标签，用户可点击按钮获取产品推荐')
        } else {
          console.log('History页面 - 没有OCR标签，不显示产品推荐区域')
        }
      } catch (error) {
        console.error('获取session数据失败:', error)
        sessionData.value = null
      }
    } else {
      console.warn('报告没有session_id，无法获取OCR数据')
      sessionData.value = null
    }
    
    // 如果报告正在生成，触发生成并轮询
    if (res.content && res.content.status === 'generating') {
      await generateAndPoll(sessionId)
    } else if (
      res.content &&
      res.content.status === 'completed' &&
      typeof res.content.html === 'string' &&
      (!res.content.html.trim() || res.content.html.trim().startsWith('{'))
    ) {
      // 生产环境兜底：completed 但 html 为 JSON（异常数据），自动重跑修复
      await generateAndPoll(sessionId)
    }
  } catch (error) {
    console.error('加载报告详情失败:', error)
    ElMessage.error('加载报告详情失败')
  } finally {
    loading.value = false
  }
}

// 查看更早报告
const viewOlderReport = async () => {
  const nextIndex = currentReportIndex.value + 1
  if (nextIndex < reportsList.value.length) {
    await loadReportByIndex(nextIndex)
  }
}

// 查看上一个报告（更新的报告）
const viewNewerReport = async () => {
  const prevIndex = currentReportIndex.value - 1
  if (prevIndex >= 0) {
    await loadReportByIndex(prevIndex)
  }
}

// 获取产品推荐
const fetchProductRecommendations = async (autoLoad = false) => {
  try {
    // 使用currentReport中的session_id
    if (!currentReport.value || !currentReport.value.session_id) {
      console.error('无法获取session_id:', currentReport.value)
      if (!autoLoad) {
        ElMessage.error('无法获取会话ID')
      }
      return
    }
    
    const sessionId = currentReport.value.session_id
    console.log(`获取产品推荐: session_id=${sessionId}`)
    
    // 允许无 OCR 标签：后端会走兜底规则（rule_id 以 -03 结尾）
    
    const response = await request.get(`/report/${sessionId}/recommendations`)
    console.log('产品推荐响应:', response)
    
    if (response.success && response.recommendations) {
      products.value = response.recommendations
      showProducts.value = true
      console.log(`成功获取 ${response.total} 个产品推荐`)
      if (!autoLoad) {
        ElMessage.success(`为您推荐了 ${response.total} 款产品`)
      }
    } else {
      products.value = []
      if (!autoLoad) {
        ElMessage.warning('暂无推荐产品')
      }
    }
  } catch (error) {
    console.error('获取产品推荐失败:', error)
    if (!autoLoad) {
      ElMessage.error(error.message || '获取产品推荐失败')
    }
  }
}

// 查看产品详情
const showProductDetail = (product) => {
  ElMessageBox.alert(
    `
    <div style="text-align: left;">
      <h3>${product.product_info.name}</h3>
      <p><strong>价格：</strong>¥${product.product_info.price}</p>
      <p><strong>描述：</strong>${product.product_info.description}</p>
      <p><strong>用法：</strong>${product.product_info.usage}</p>
      <p><strong>特点：</strong>${product.product_info.features.join('、')}</p>
      <p><strong>匹配标签：</strong>${product.matched_tags.join('、')}</p>
    </div>
    `,
    '产品详情',
    {
      confirmButtonText: '关闭',
      dangerouslyUseHTMLString: true
    }
  )
}

// 购买产品
const buyProduct = (url) => {
  window.open(url, '_blank')
}

// 避免重复开启轮询导致 /report/:id 并发请求
let reportPollInterval = null
let pollingSessionId = null

const stopReportPolling = () => {
  if (reportPollInterval) {
    clearInterval(reportPollInterval)
    reportPollInterval = null
  }
  pollingSessionId = null
}

const generateAndPoll = async (sessionId) => {
  try {
    // 防止重复启动
    if (pollingSessionId === sessionId && reportPollInterval) {
      return
    }
    stopReportPolling()
    pollingSessionId = sessionId

    await request.post(`/report/${sessionId}/generate`)
    
    let attempts = 0
    // 10 分钟（300次 * 2s）：OCR 解析 PDF + 多段 LLM 可能超过 3 分钟
    const maxAttempts = 300
    
    reportPollInterval = setInterval(async () => {
      attempts++
      
      if (attempts > maxAttempts) {
        stopReportPolling()
        ElMessage.warning('报告仍在生成中（耗时较长）。可继续等待或稍后刷新页面查看结果。')
        loading.value = false
        return
      }
      
      try {
        const res = await request.get(`/report/${sessionId}`)
        
        if (res.content && res.content.status === 'completed') {
          stopReportPolling()
          currentReport.value = res
          report_iframe_refresh_key.value = Date.now()
          loading.value = false
        }
      } catch (error) {
        console.error('轮询错误:', error)
      }
    }, 2000)
  } catch (error) {
    console.error('触发生成失败:', error)
    loading.value = false
  }
}

const selectReport = async (sessionId) => {
  selectedSessionId.value = sessionId
  await loadReportDetail(sessionId)
}

const changeProducts = () => {
  ElMessage.success('换一换功能暂未实现')
}

const handleAvatarClick = () => {
  ElMessageBox.confirm(
    '确定要退出登录吗？',
    '退出登录',
    {
      confirmButtonText: '确定退出',
      cancelButtonText: '取消',
      type: 'warning',
      center: true
    }
  ).then(() => {
    authStore.logout()
    ElMessage.success('已退出登录')
    router.push('/')
  }).catch(() => {
    // 用户取消
  })
}

onMounted(() => {
  loadReportsList()
})
</script>

<style scoped>
* {
  box-sizing: border-box;
}

.history-page {
  display: flex;
  height: 100vh;
  background: #F5F5F7;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

/* 右侧：主内容区 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #F3EDF7;
  overflow: hidden;
}

/* 顶部导航栏 */
.history-header {
  height: 64px;
  background: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: relative;
  flex-shrink: 0;
}

.history-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 24px;
  right: 24px;
  height: 1px;
  background: #F2F2F7;
}

.header-left {
  width: 40px;
}

.page-title {
  flex: 1;
  text-align: center;
  font-size: 18px;
  font-weight: 600;
  color: #1C1C1E;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  font-size: 15px;
  font-weight: 600;
  color: #1C1C1E;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.u-avatar{
  width: 100%;
}
.user-avatar:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(103, 80, 164, 0.3);
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  font-weight: 600;
  font-size: 16px;
}

/* 左侧：报告列表 */
.sidebar {
  width: 220px;
  background: #FFFFFF;
  border-radius: 32px;
  margin: 12px;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.sidebar.collapsed {
  width: 80px;
  background: #6750A4;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #E5E5EA;
}

.sidebar.collapsed .sidebar-header {
  border-bottom-color: rgba(255, 255, 255, 0.2);
  padding: 20px 0;
  display: flex;
  justify-content: center;
}

.menu-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #1C1C1E;
  transition: background 0.2s, color 0.2s;
  padding: 0;
}

.sidebar.collapsed .menu-btn {
  color: #FFFFFF;
}

.menu-btn:hover {
  background: #F2F2F7;
}

.sidebar.collapsed .menu-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.menu-icon {
  width: 24px;
  height: 24px;
  display: block;
}

.sidebar.collapsed .menu-icon {
  filter: brightness(0) invert(1);
}

.sidebar-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* 折叠状态下的图标按钮 */
.sidebar-icons {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 20px 0;
}

.icon-btn {
  width: 56px;
  height: 56px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  color: #FFFFFF;
  transition: background 0.2s;
  padding: 0;
}

.icon-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.icon-btn svg {
  color: #FFFFFF;
  width: 30px !important;
  height: 30px !important;
}

.icon-btn.active {
  background: rgba(255, 255, 255, 0.2);
}

.new-chat-btn {
  width: 100%;
  padding: 8px 16px;
  margin-bottom: 12px;
  border: none;
  background: #EADDFF;
  border-radius: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 500;
  color: #4F378A;
  transition: all 0.2s;
}

.new-chat-btn:hover {
  background: #E1D4F8;
}

.new-chat-btn svg {
  color: #6750A4;
}

.history-btn {
  width: 100%;
  padding: 12px 16px;
  margin-bottom: 12px;
  border: none;
  background: transparent;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #4F378A;
  transition: all 0.2s;
}

.history-btn:hover {
  background: #F2F2F7;
}

.history-btn.active {
  background: #F2F2F7;
  color: #4F378A;
  font-weight: 600;
}

.history-btn svg {
  color: #4F378A;
  flex-shrink: 0;
}

.history-section {
  margin-top: 24px;
}

.section-title {
  font-size: 14px;
  color: #49454F;
  margin-bottom: 8px;
  font-weight: 500;
  padding: 0 16px;
}

.reports-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.report-item {
  padding: 12px 16px;
  background: transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 1px solid transparent;
}

.report-item:hover {
  background: #F2F2F7;
  border-color: #E5E5EA;
  transform: translateX(4px);
}

.report-preview {
  font-size: 13px;
  color: #1D192B;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  font-weight: 500;
  margin: 0;
}

.report-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-date {
  font-size: 11px;
  color: #8E8E93;
}

.empty-list {
  text-align: center;
  padding: 20px;
  color: #8E8E93;
  font-size: 13px;
}

/* 右侧：报告详情 */
.report-detail {
  flex: 1;
  overflow-y: auto;
  background: #F3EDF7;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid #E5E5EA;
  border-top-color: #6750A4;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state p {
  color: #8E8E93;
}

.empty-detail {
  text-align: center;
  padding: 60px 20px;
  color: #8E8E93;
}

.report-content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 20px;
}

/* 报告信息栏 */
.report-info-bar {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.navigation-buttons {
  display: flex;
  gap: 12px;
}

.info-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-label {
  font-size: 13px;
  color: #8E8E93;
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: #1C1C1E;
}

.view-older-btn,
.view-newer-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: transparent;
  border: 1px solid #6750A4;
  border-radius: 20px;
  color: #6750A4;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.view-older-btn:hover,
.view-newer-btn:hover {
  background: #6750A4;
  color: #FFFFFF;
}

.view-older-btn:disabled,
.view-newer-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: #C7C7CC;
  color: #C7C7CC;
}

.view-older-btn:disabled:hover,
.view-newer-btn:disabled:hover {
  background: transparent;
  color: #C7C7CC;
}

/* HTML报告内容 */
.html-report {
  background: #FFFFFF;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.html-report-iframe {
  width: 100%;
  height: 900px;
  border: 0;
  display: block;
}

/* 报告内容样式（复用Report.vue的样式） */
:deep(.report-container) {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 评分区域样式 */
:deep(.score-section) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  background: #F9F9FB;
  border-radius: 12px;
  margin-bottom: 16px;
}

:deep(.score-circle) {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: conic-gradient(#6750A4 0% 65%, #E5E5EA 65% 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  flex-shrink: 0;
}

:deep(.score-circle::before) {
  content: '';
  position: absolute;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: #FFFFFF;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

:deep(.score-value) {
  position: relative;
  font-size: 32px !important;
  font-weight: 700 !important;
  color: #6750A4 !important;
  z-index: 1;
  line-height: 1 !important;
  margin: 0 !important;
}

:deep(.score-circle .score-label) {
  position: relative;
  font-size: 11px !important;
  color: #8E8E93 !important;
  z-index: 1;
  margin-top: 4px;
  text-align: center;
  line-height: 1.2;
}

:deep(.risk-info) {
  flex: 1;
  margin-left: 32px;
}

/* ========== OCR分析区 ========== */
.ocr-analysis-section {
  background: #F8F9FA;
  border-radius: 16px;
  padding: 24px;
  margin-top: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.ocr-analysis-section .section-title {
  font-size: 20px;
  font-weight: 600;
  color: #1A1A1A;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ocr-text-card,
.tags-card {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.ocr-text-card:last-child,
.tags-card:last-child {
  margin-bottom: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #333333;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.ocr-text-content {
  font-size: 14px;
  line-height: 1.8;
  color: #555555;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
  background: #F8F9FA;
  border-radius: 8px;
  border: 1px solid #E5E7EB;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  padding: 6px 16px;
  background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
  color: #FFFFFF;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(102, 126, 234, 0.2);
  transition: all 0.3s ease;
}

.track-info {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #E5E5EA;
  display: flex;
  align-items: center;
  gap: 8px;
}

.track-label {
  font-size: 14px;
  font-weight: 600;
  color: #666666;
}

.track-value {
  font-size: 14px;
  font-weight: 500;
  color: #8B7FE5;
  background: #F0EDFF;
  padding: 4px 12px;
  border-radius: 12px;
}

.tag-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
}

/* 产品推荐区样式 */
.products-section {
  margin-top: 32px;
}

.disclaimer-text {
  font-size: 12px;
  font-weight: 600;
  color: #1C1C1E;
  margin: 16px 0 20px 0;
}

/* 推荐产品触发区域 */
.recommend-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  background: #FFFFFF;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.trigger-icons {
  display: flex;
  gap: 12px;
}

.icon-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #F5F5F7 0%, #E5E5EA 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.recommend-btn {
  padding: 14px 32px;
  background: #8B7FE5;
  color: #FFFFFF;
  border: none;
  border-radius: 28px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(139, 127, 229, 0.3);
}

.recommend-btn:hover {
  background: #7B6FD5;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 127, 229, 0.4);
}

/* 产品展开区域 */
.products-expanded {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.products-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.products-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

@media (max-width: 1024px) {
  .products-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .products-grid {
    grid-template-columns: 1fr;
  }
}

.product-card {
  background: #FFFFFF;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s, box-shadow 0.2s;
}

.product-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.product-image-placeholder {
  height: 180px;
  background: linear-gradient(135deg, #F5F5F7 0%, #E5E5EA 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.product-image {
  height: 180px;
  overflow: hidden;
  background: #F5F5F7;
}

.product-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0;
}

.product-tag {
  display: inline-block;
  padding: 4px 10px;
  background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
  color: #FFFFFF;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.product-price {
  font-size: 18px;
  font-weight: 700;
  color: #FF3B30;
  margin: 8px 0;
}

.product-info {
  padding: 16px;
}

.product-title {
  font-size: 16px;
  font-weight: 600;
  color: #1C1C1E;
  margin: 0 0 8px 0;
}

.product-desc {
  font-size: 13px;
  color: #8E8E93;
  line-height: 1.5;
  margin: 0 0 16px 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.product-actions {
  display: flex;
  gap: 8px;
}

.view-details-btn,
.buy-now-btn {
  flex: 1;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.view-details-btn {
  background: #F2F2F7;
  color: #1C1C1E;
}

.view-details-btn:hover {
  background: #E5E5EA;
}

.buy-now-btn {
  background: #6750A4;
  color: #FFFFFF;
}

.buy-now-btn:hover {
  background: #5A3D99;
}

.change-products {
  display: inline-block;
}

.change-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  background: #FFFFFF;
  border: 2px solid #6750A4;
  border-radius: 24px;
  color: #6750A4;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.change-btn:hover {
  background: #6750A4;
  color: #FFFFFF;
}

.change-btn svg {
  transition: transform 0.3s;
}

.change-btn:hover svg {
  transform: rotate(180deg);
}

/* 滚动条样式 */
.reports-list::-webkit-scrollbar,
.report-detail::-webkit-scrollbar {
  width: 6px;
}

.reports-list::-webkit-scrollbar-track,
.report-detail::-webkit-scrollbar-track {
  background: transparent;
}

.reports-list::-webkit-scrollbar-thumb,
.report-detail::-webkit-scrollbar-thumb {
  background: #C7C7CC;
  border-radius: 3px;
}

.reports-list::-webkit-scrollbar-thumb:hover,
.report-detail::-webkit-scrollbar-thumb:hover {
  background: #AEAEB2;
}
</style>

