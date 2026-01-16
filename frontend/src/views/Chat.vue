<template>
  <div class="chat-container">
    <!-- 左侧边栏 -->
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
      
      <!-- 展开状态的内容 -->
      <div class="sidebar-content" v-show="!sidebarCollapsed">
        <!-- 开始新对话 -->
        <button class="new-chat-btn" @click="startNewChat">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <span>开始新对话</span>
        </button>
        
        <!-- 查看历史报告 -->
        <button class="history-btn" @click="viewHistory">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
            <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <span>查看历史报告</span>
        </button>
        
        <!-- 历史对话列表 -->
        <div class="history-section">
          <div class="section-title">最近对话</div>
          <div class="history-list">
            <div 
              v-for="item in historyItems" 
              :key="item.id" 
              class="history-item"
              :class="{ active: item.id === sessionId }"
              @click="viewHistoryReport(item.id)"
            >
              <div class="history-text">{{ item.preview }}</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 折叠状态：只显示图标 -->
      <div class="sidebar-icons" v-show="sidebarCollapsed">
        <button class="icon-btn" @click="startNewChat" title="开始新对话">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
        <button class="icon-btn" @click="viewHistory" title="查看历史报告">
          <svg viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
            <path d="M12 7V12L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </aside>
    
    <!-- 主聊天区域 -->
    <main class="chat-main">
      <!-- 顶部栏 -->
      <header class="chat-header">
          <img src="@/assets/logo.png" alt="logo" class="header-logo" />
        <div class="header-right">
          <span class="username">{{ user.username || 'Lana' }}</span>
          <div class="user-avatar" @click="handleAvatarClick" title="点击退出登录">
            <img v-if="user.avatar" :src="user.avatar" alt="avatar" />
            <img v-else src="@/assets/avatar.png" class="u-avatar" alt="avatar" />
          </div>
        </div>
      </header>
      
      <!-- 报告显示区域 -->
      <div v-if="showReport" class="report-display-area">
        <!-- 报告生成中 Loading -->
        <div v-if="reportLoading" class="report-loading">
          <div class="loading-spinner"></div>
          <p>报告生成中，请稍候...</p>
        </div>
        
        <!-- 报告内容 -->
        <div v-else-if="reportData && report_iframe_src" class="report-content-area">
          <!-- HTML报告区域：使用 iframe 渲染完整 HTML 文档（避免 v-html 插入 <!DOCTYPE html>/<html> 导致空白） -->
          <div class="html-report-section">
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

          <!-- 底部商品推荐区
               说明：后端支持“无标签兜底（-03 规则）”，因此不再要求必须有 OCR 标签才显示入口 -->
          <div v-if="reportData && reportData.session_id" class="products-recommendation">
            <!-- 免责声明 -->
            <div class="disclaimer-notice">
              *本报告仅供参考，不作为医学诊断依据
            </div>

            <!-- 初始状态：推荐产品按钮 + 左侧图标 -->
            <div v-if="!showProducts" class="recommend-trigger-area">
              <div class="trigger-icon-group">
                <div class="trigger-icon-circle">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="8" r="3" fill="#8B7FE5"/>
                    <path d="M5 20C5 16 8 14 12 14C16 14 19 16 19 20" fill="#8B7FE5"/>
                  </svg>
                </div>
                <div class="trigger-icon-circle">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <rect x="4" y="4" width="7" height="7" rx="1" fill="#6750A4"/>
                    <rect x="13" y="4" width="7" height="7" rx="1" fill="#6750A4"/>
                    <rect x="4" y="13" width="7" height="7" rx="1" fill="#6750A4"/>
                    <rect x="13" y="13" width="7" height="7" rx="1" fill="#6750A4"/>
                  </svg>
                </div>
                <div class="trigger-icon-circle">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2L15 8L22 9L17 14L18 21L12 18L6 21L7 14L2 9L9 8L12 2Z" fill="#8B7FE5"/>
                  </svg>
                </div>
              </div>
              <button class="show-products-btn" @click="fetchProductRecommendations()">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M9 3H15M3 9H21M3 15H21M9 21H15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                推荐产品
              </button>
            </div>

            <!-- 展开状态：产品列表 + 换一换按钮 -->
            <div v-else class="products-list-area">
              <!-- 换一换按钮 -->
              <div class="change-products-header">
                <button class="change-products-btn" @click="changeProducts">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    <path d="M21 3V8H16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  换一换
                </button>
              </div>

              <!-- 商品卡片列表 -->
              <div class="product-cards-grid">
                <div v-for="product in products" :key="product.rule_id" class="product-item-card">
                  <!-- 产品图片 -->
                  <div class="product-img-placeholder">
                    <img v-if="product.product_info.image_url" 
                         :src="product.product_info.image_url" 
                         :alt="product.product_info.name"
                         @error="handleImageError($event, product)"
                         style="width: 100%; height: 100%; object-fit: cover;" />
                    <svg v-else width="80" height="80" viewBox="0 0 100 100" fill="none">
                      <circle cx="50" cy="35" r="12" fill="#C7C7CC"/>
                      <path d="M30 70C30 60 40 55 50 55C60 55 70 60 70 70" fill="#C7C7CC"/>
                      <rect x="65" y="65" width="20" height="20" rx="4" fill="#C7C7CC"/>
                    </svg>
                  </div>
                  <div class="product-card-info">
                    <h4 class="product-card-title">{{ product.product_info.name }}</h4>
                    <p class="product-card-desc">{{ product.product_info.description }}</p>
                    <!-- 产品标签 -->
                    <div class="product-tags" v-if="product.product_info.features && product.product_info.features.length">
                      <span v-for="(feature, idx) in product.product_info.features.slice(0, 3)" :key="idx" class="product-tag">
                        {{ feature }}
                      </span>
                    </div>
                    <div class="product-card-actions">
                      <button class="product-detail-btn" @click="showProductDetail(product)">查看详情</button>
                      <button class="product-buy-btn" @click="buyProduct(product)">去购买</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 消息区域 -->
      <div v-else class="messages-container" ref="messagesRef">
        <div 
          v-for="(msg, index) in messages" 
          :key="index" 
          class="message-wrapper"
          :class="msg.role"
        >
          <!-- AI 消息：气泡 + 左侧头像 -->
          <template v-if="msg.role === 'assistant'">
            <div class="message-avatar">
              <img src="@/assets/kefu.png" alt="ai" class="ai-avatar" />
            </div>
            <div class="message-bubble">
              <div class="message-content" v-html="renderMessage(msg.content)"></div>
            </div>
          </template>
          
          <!-- 用户消息：气泡 + 右侧头像 -->
          <template v-else>
            <div class="message-bubble">
              <div class="message-content" v-html="renderMessage(msg.content)"></div>
            </div>
            <div class="message-avatar">
              <img src="@/assets/avatar.png" class="ai-avatar" alt="avatar" />
            </div>
          </template>
        </div>
        
        <!-- AI 思考中 - 精美 Loading -->
        <div v-if="loading" class="ai-loading-container">
          <div class="loading-card">
            <!-- 旋转动画 -->
            <div class="loading-spinner-wrapper">
              <div class="spinner-ring"></div>
              <div class="spinner-ring"></div>
              <div class="spinner-ring"></div>
              <div class="spinner-core">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2L15 8L22 9L17 14L18 21L12 18L6 21L7 14L2 9L9 8L12 2Z" fill="#8B7FE5"/>
                </svg>
              </div>
            </div>
            
            <!-- 动态提示文字 -->
            <div class="loading-text-container">
              <h3 class="loading-title">{{ loadingTitle }}</h3>
              <p class="loading-subtitle">{{ loadingSubtitle }}</p>
          </div>
            
            <!-- 进度提示 -->
            <div class="loading-progress">
              <div class="progress-bar">
                <div class="progress-fill"></div>
              </div>
              <span class="progress-hint">预计需要 3-5 秒</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 输入区域（已生成报告时隐藏输入框） -->
      <div v-if="!showReport" class="input-container">
        <!-- 只读模式提示 -->
        <div v-if="isReadOnly" class="readonly-notice">
          <span>📖 正在查看历史对话（只读模式）</span>
          <button class="exit-readonly-btn" @click="startNewChat">开始新对话</button>
        </div>
        
        <!-- 文件预览区域（图片/PDF） -->
        <div v-if="selectedImages.length > 0" class="images-preview">
          <div v-for="(fileItem, index) in selectedImages" :key="index" class="image-preview-item" @click="previewFile(fileItem)">
            <img v-if="fileItem.preview" :src="fileItem.preview" :alt="fileItem.name" class="preview-image" />
            <div v-else class="file-placeholder">
              <div class="file-badge">PDF</div>
              <div class="file-name">{{ fileItem.name }}</div>
            </div>
            <button class="remove-image-btn" @click.stop="removeImage(index)" title="删除">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
            <div class="image-info">{{ fileItem.name }}</div>
          </div>
        </div>

        <!-- 图片放大预览弹窗 -->
        <div v-if="showImagePreview" class="image-preview-modal" @click="closeImagePreview">
          <div class="image-preview-content">
            <img :src="previewImageUrl" alt="预览" class="preview-full-image" />
            <button class="close-preview-btn" @click="closeImagePreview">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>
        
        <div class="input-wrapper">
          <input 
            ref="fileInputRef"
            type="file" 
            accept="image/jpeg,image/jpg,image/png,application/pdf"
            multiple
            style="display: none"
            @change="handleFileSelect"
          />
          <button class="attach-btn" :title="`上传文件（图片<=${MAX_IMAGES}张，PDF<=${MAX_PDF_TOTAL_MB}MB）`" @click="triggerFileUpload" :disabled="loading || isReadOnly || uploading">
            <img :src="uploadIcon" alt="上传" class="upload-icon" />
            <span v-if="selectedImages.length > 0" class="image-count">{{ selectedImages.length }}</span>
          </button>
          <textarea 
          v-model="inputMessage"
            :placeholder="isReadOnly ? '查看历史对话（只读模式）' : '请输入您的健康困扰...'"
            @keydown.enter.exact.prevent="sendMessage"
            :disabled="loading || isReadOnly"
            rows="1"
          ></textarea>
          <button class="send-btn" @click="sendMessage" :disabled="loading || !inputMessage.trim() || isReadOnly">
            <img :src="sendIcon" alt="发送" class="send-icon" />
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownIt from 'markdown-it'

// 导入图标
import menuExpandIcon from '@/assets/icons/menu-expand.png'
import menuCollapseIcon from '@/assets/icons/menu-collapse.png'
import sendIcon from '@/assets/icons/send.png'
import uploadIcon from '@/assets/icons/upload.png'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const user = computed(() => authStore.user || {})
const md = new MarkdownIt()

const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const sessionId = ref(null)
const messagesRef = ref(null)
const sidebarCollapsed = ref(false)
const isReadOnly = ref(false) // 只读模式标记
const showReport = ref(false) // 是否显示报告
const reportData = ref(null) // 报告数据
const sessionData = ref(null) // 会话数据（包含OCR标签）
const showProducts = ref(false) // 是否显示产品列表
const products = ref([]) // 推荐产品列表
const reportLoading = ref(false) // 报告生成中

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

// 文件上传相关
const fileInputRef = ref(null)
const uploading = ref(false)
const selectedImages = ref([]) // 已选择的图片列表（待上传）
const MAX_IMAGES = 10
const MAX_PDF_TOTAL_MB = 50
const previewImageUrl = ref('') // 当前预览的图片URL
const showImagePreview = ref(false) // 是否显示图片预览弹窗

// 附件绑定：上传成功后仅绑定文件 URL 到 session（不做预解析）

// 报告轮询（避免重复开启导致同一接口并发请求两次）
let reportPollInterval = null
const pollingReportSessionId = ref(null)

const stopReportPolling = () => {
  if (reportPollInterval) {
    clearInterval(reportPollInterval)
    reportPollInterval = null
  }
  pollingReportSessionId.value = null
}

const resetUploadState = () => {
  // 清空“输入框上方的附件预览/队列”（这就是你看到一直残留的已上传文件）
  selectedImages.value = []
  uploading.value = false

  // 退出预览弹窗
  showImagePreview.value = false
  previewImageUrl.value = ''

  // 清空 input，避免同一文件无法再次触发 change
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

// Loading 动态文字
const loadingTitle = ref('正在分析您的健康状况')
const loadingSubtitle = ref('AI 正在为您生成个性化问题...')
const loadingTextIndex = ref(0)

// 历史对话列表（从后端获取）
const historyItems = ref([])

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const loadHistoryReports = async () => {
  try {
    const res = await request.get('/report/list')
    historyItems.value = res.reports.map(report => ({
      id: report.session_id,
      preview: report.preview,
      score: report.score,
      created_at: report.created_at
    }))
  } catch (error) {
    console.error('加载历史报告失败:', error)
  }
}

const viewHistory = () => {
  // 跳转到历史记录页面
  router.push({ name: 'History' })
}

const viewHistoryReport = async (targetSessionId) => {
  // 加载历史对话内容（只读模式）
  try {
    // 重置状态
    showReport.value = false
    showProducts.value = false
    reportData.value = null
    isReadOnly.value = true
    
    const res = await request.get(`/chat/session/${targetSessionId}`)
    
    // 切换到该 session
    sessionId.value = res.session_id
    messages.value = []
    
    if (res.messages && Array.isArray(res.messages)) {
      res.messages.forEach(msg => {
        messages.value.push({ role: msg.role, content: msg.content })
      })
    }
    
    // 标记为只读模式
    isReadOnly.value = true
    ElMessage.info('正在查看历史对话（只读模式）')
    
    scrollToBottom()
  } catch (error) {
    console.error(error)
    ElMessage.error('加载历史对话失败')
  }
}

const renderMessage = (content) => {
  // 过滤 <think> 标签内容（多重策略）
  let cleanContent = content
  
  // 策略1: 移除完整的 <think>...</think> 块
  cleanContent = cleanContent.replace(/<think>[\s\S]*?<\/think>/gi, '')
  
  // 策略2: 移除未闭合的 <think> 标签（从 <think> 到字符串末尾）
  cleanContent = cleanContent.replace(/<think>[\s\S]*$/gi, '')
  
  // 策略3: 移除任何剩余的 </think> 标签
  cleanContent = cleanContent.replace(/<\/think>/gi, '')
  
  // 策略4: 移除任何剩余的 <think> 标签
  cleanContent = cleanContent.replace(/<think>/gi, '')
  
  // 清理多余的空行
  cleanContent = cleanContent.replace(/\n\s*\n\s*\n+/g, '\n\n').trim()
  
  return md.render(cleanContent).trim()
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

const loadActiveSession = async () => {
  try {
    const activeSession = await request.get('/chat/active')

    // 检查是否有活跃会话
    if (!activeSession.session_id) {
      console.log('📝 没有活跃会话，创建新会话...')
      await startNewChat()
      return
    }

    sessionId.value = activeSession.session_id
    messages.value = []
    
    if (activeSession.messages && Array.isArray(activeSession.messages)) {
      activeSession.messages.forEach(msg => {
        messages.value.push({ role: msg.role, content: msg.content })
      })
    }
    
    console.log(`✅ 恢复会话 ${sessionId.value}，包含 ${messages.value.length} 条消息`)
    scrollToBottom()
  } catch (error) {
    console.log('📝 加载活跃会话失败，创建新会话...')
    await startNewChat()
  }
}

// 文件上传相关方法
const triggerFileUpload = () => {
  if (fileInputRef.value) {
    fileInputRef.value.click()
  }
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files || [])
  
  if (!files.length) return
  
  // 验证文件类型和大小
  const validFiles = []
  for (const file of files) {
    const isImage = ['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

    if (!isImage && !isPdf) {
      ElMessage.error(`${file.name} 格式不支持，仅支持 JPG/PNG/PDF`)
      continue
    }

    // 单文件大小限制（50MB）
    if (file.size > 50 * 1024 * 1024) {
      ElMessage.error(`${file.name} 文件过大，最大支持 50MB`)
      continue
    }

    validFiles.push(file)
  }

  // 图片数量限制（仅限制图片张数）
  const incomingImageCount = validFiles.filter(f => ['image/jpeg', 'image/jpg', 'image/png'].includes(f.type)).length
  const existingImageCount = selectedImages.value.filter(i => i.isImage).length
  if (existingImageCount + incomingImageCount > MAX_IMAGES) {
    ElMessage.warning(`图片最多${MAX_IMAGES}张，请分批选择（PDF不计入张数限制）`)
    return
  }

  // 添加到已选择列表 + 后台上传（上传成功后仅绑定附件列表，不做预解析）
  const newItems = []
  validFiles.forEach(file => {
    // 关键修复：同名文件视为“替换上传”（用户常见操作：修改同一个 PDF/图片后重新上传）
    // 否则旧文件仍保留在附件列表里，后端解析时会继续把旧内容混入，造成“解析还是之前的文件”错觉。
    const existingIndex = selectedImages.value.findIndex(
      (i) => i && i.name === file.name
    )
    if (existingIndex !== -1) {
      selectedImages.value.splice(existingIndex, 1)
      // 解绑旧附件（静默）
      syncAttachedFiles(true)
    }

    const isImage = ['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)
    const item = {
      file,
      preview: null,
      name: file.name,
      size: file.size,
      type: file.type,
      isImage,
      uploadedUrl: null
    }
    newItems.push(item)
    selectedImages.value.push(item)

    if (isImage) {
      const reader = new FileReader()
      reader.onload = (e) => {
        item.preview = e.target.result
      }
      reader.readAsDataURL(file)
    }
  })
  
  // 清空 file input
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
  
  if (validFiles.length > 0) {
    ElMessage.success(`已添加 ${validFiles.length} 个文件`)
  }

  // 后台上传到OSS并进入预解析队列（不阻塞用户继续聊天）
  uploadNewFilesToOssAndQueue(newItems)
}

// 删除已选择的图片
const removeImage = (index) => {
  selectedImages.value.splice(index, 1)
  syncAttachedFiles()
  ElMessage.success('已删除')
}

const previewFile = (fileItem) => {
  if (!fileItem || !fileItem.preview) return
  previewImageUrl.value = fileItem.preview
  showImagePreview.value = true
}

// 关闭图片预览
const closeImagePreview = () => {
  showImagePreview.value = false
  previewImageUrl.value = ''
}

const syncAttachedFiles = async (forceReparse = false) => {
  if (!sessionId.value) return
  const urls = selectedImages.value
    .filter(i => i.uploadedUrl)
    .map(i => i.uploadedUrl)
  try {
    await request.post('/chat/upload-report', {
      session_id: sessionId.value,
      file_urls: urls,
      force_reparse: forceReparse
    })
  } catch (e) {
    // 静默失败，不影响用户继续操作
  }
}

const uploadNewFilesToOssAndQueue = async (items) => {
  if (!items || items.length === 0) return
  if (!sessionId.value) return

  try {
    uploading.value = true

    for (const item of items) {
      // 已上传的不重复传
      if (item.uploadedUrl) continue
      const formData = new FormData()
      formData.append('file', item.file)
      const uploadResponse = await request.post('/upload/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      if (uploadResponse.success) {
        item.uploadedUrl = uploadResponse.file_url
        await syncAttachedFiles()
      }
    }
    // 不做预解析
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(error.message || '文件上传失败')
  } finally {
    uploading.value = false
  }
}

const startNewChat = async () => {
  try {
    messages.value = []
    isReadOnly.value = false // 退出只读模式
    showReport.value = false // 退出报告显示
    showProducts.value = false // 重置产品显示
    reportData.value = null
    sessionData.value = null

    // 关键：新对话必须清空旧的上传/解析队列与预览
    resetUploadState()
    // 关键：避免上一次报告轮询还在跑
    stopReportPolling()
    
    const res = await request.post('/chat/start')
    sessionId.value = res.session_id
    
    if (res.messages && Array.isArray(res.messages)) {
      res.messages.forEach(msg => {
        messages.value.push({ role: msg.role, content: msg.content })
      })
    }
    console.log(`✅ 创建新会话 ${sessionId.value}`)
    scrollToBottom()
    // 刷新历史记录，确保上一条会话（如果有）已保存并显示
    loadHistoryReports()
  } catch (error) {
    console.error(error)
  }
}

// Loading 文字轮换
const loadingTexts = [
  { title: '正在分析您的健康状况', subtitle: 'AI 正在为您生成个性化问题...' },
  { title: '深度理解您的需求', subtitle: '根据您的回答定制专属问卷...' },
  { title: '智能匹配健康方案', subtitle: '这可能需要几秒钟，请稍候...' }
]

let loadingInterval = null

const startLoadingAnimation = () => {
  loadingTextIndex.value = 0
  loadingTitle.value = loadingTexts[0].title
  loadingSubtitle.value = loadingTexts[0].subtitle
  
  loadingInterval = setInterval(() => {
    loadingTextIndex.value = (loadingTextIndex.value + 1) % loadingTexts.length
    loadingTitle.value = loadingTexts[loadingTextIndex.value].title
    loadingSubtitle.value = loadingTexts[loadingTextIndex.value].subtitle
  }, 2000)
}

const stopLoadingAnimation = () => {
  if (loadingInterval) {
    clearInterval(loadingInterval)
    loadingInterval = null
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || loading.value) return
  
  const content = inputMessage.value
  messages.value.push({ role: 'user', content })
  inputMessage.value = ''
  scrollToBottom()
  
  loading.value = true
  startLoadingAnimation()
  
  try {
    const res = await request.post('/chat/message', {
      session_id: sessionId.value,
      content
    })
    
    if (res.response) {
    messages.value.push({ role: 'assistant', content: res.response })
    } else if (res.messages && Array.isArray(res.messages)) {
      res.messages.forEach(msg => {
        messages.value.push({ role: 'assistant', content: msg })
      })
    }
    
    scrollToBottom()
    
    if (res.action === 'report') {
      // 延迟加载报告，让用户看到感谢语
      setTimeout(async () => {
        // 不显示消息，直接切换到报告加载状态
        await loadReport(sessionId.value)
      }, 2000)
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('发送失败，请重试')
  } finally {
    loading.value = false
    stopLoadingAnimation()
  }
}

const loadReport = async (reportSessionId) => {
  try {
    // 避免同一会话重复触发轮询导致 /report/:id 并发两次
    if (pollingReportSessionId.value === reportSessionId && reportLoading.value) {
      return
    }

    // 先切换到报告显示状态并显示 loading
    showReport.value = true
    reportLoading.value = true
    
    const res = await request.get(`/report/${reportSessionId}`)
    // 先保存一次 reportData，并刷新 iframe（/report/:id/html 内部会自行显示“生成中/自动刷新”）
    reportData.value = res
    report_iframe_refresh_key.value = Date.now()
    
    // 生产环境兜底：后端可能返回 completed 但 html 实际是 JSON（异常数据）
    // 这时应触发一次重新生成并轮询，而不是直接渲染 JSON
    const htmlInvalid = !!(
      res.content &&
      typeof res.content.html === 'string' &&
      (!res.content.html.trim() || res.content.html.trim().startsWith('{'))
    )

    // 生成中也尝试拉取 session 数据（OCR 文本通常会先于报告完成写入）
    if (res.session_id) {
      try {
        const sessionRes = await request.get(`/chat/session/${res.session_id}`)
        sessionData.value = sessionRes
      } catch (error) {
        console.error('Chat页面 - 获取session数据失败(生成中):', error)
      }
    }

    if (res.content && res.content.status === 'generating') {
      await generateAndPollReport(reportSessionId)
    } else if (res.content && res.content.status === 'completed' && htmlInvalid) {
      await generateAndPollReport(reportSessionId)
    } else {
      // 获取session数据（包含OCR标签）
      if (res.session_id) {
        try {
          const sessionRes = await request.get(`/chat/session/${res.session_id}`)
          sessionData.value = sessionRes
          console.log('Chat页面 - 获取session数据:', sessionRes)
          console.log('Chat页面 - OCR标签:', sessionRes.ocr_tags)
        } catch (error) {
          console.error('Chat页面 - 获取session数据失败:', error)
        }
      }
      
      reportLoading.value = false
      ElMessage.success('报告已生成！')
    }
  } catch (error) {
    console.error('加载报告失败:', error)
    ElMessage.error('加载报告失败')
    reportLoading.value = false
  }
}

const generateAndPollReport = async (reportSessionId) => {
  try {
    // 防止重复开启 interval（会导致同一接口每2秒并发请求两次）
    stopReportPolling()
    pollingReportSessionId.value = reportSessionId

    // 重要：生成报告前，确保附件已上传并绑定到 session（解析会在后端生成报告时执行）
    // 1) 若还有未上传的本地文件，先上传
    const notUploaded = selectedImages.value.filter(i => !i.uploadedUrl)
    if (notUploaded.length > 0) {
      await uploadNewFilesToOssAndQueue(notUploaded)
    }
    // 2) 同步绑定附件列表（静默）
    await syncAttachedFiles()

    // 触发报告生成（在图片解析后执行，确保OCR结果能进入提示词）
    await request.post(`/report/${reportSessionId}/generate`)
    
    let attempts = 0
    // 10 分钟（300次 * 2s）：OCR 解析 PDF + 多段 LLM 可能超过 3 分钟
    const maxAttempts = 300
    
    reportPollInterval = setInterval(async () => {
      attempts++
      
      if (attempts > maxAttempts) {
        stopReportPolling()
        // 报告 HTML iframe 仍会继续按后端 /html 页面的内置轮询刷新；
        // 这里只停止 JSON 轮询，避免无止境请求。
        ElMessage.warning('报告仍在生成中（耗时较长）。可继续等待或稍后刷新页面查看结果。')
        reportLoading.value = false
        return
      }
      
      try {
        const res = await request.get(`/report/${reportSessionId}`)
        
        if (res.content && res.content.status === 'completed') {
          stopReportPolling()
          reportData.value = res
          report_iframe_refresh_key.value = Date.now()
          
          // 获取session数据（包含OCR标签）
          if (res.session_id) {
            try {
              const sessionRes = await request.get(`/chat/session/${res.session_id}`)
              sessionData.value = sessionRes
              console.log('Chat页面 - 报告生成完成，获取session数据:', sessionRes)
              console.log('Chat页面 - OCR标签:', sessionRes.ocr_tags)
              
              // 不自动获取产品推荐，等待用户点击"推荐产品"按钮
              if (sessionRes.ocr_tags && sessionRes.ocr_tags.length > 0) {
                console.log('Chat页面 - 检测到OCR标签，用户可点击按钮获取产品推荐')
              } else {
                console.log('Chat页面 - 没有OCR标签，不显示产品推荐区域')
              }
            } catch (error) {
              console.error('Chat页面 - 获取session数据失败:', error)
            }
          }
          
          showReport.value = true
          reportLoading.value = false
          ElMessage.success('报告生成完成！')
          // 刷新侧边栏历史记录，确保包含新生成的报告
          loadHistoryReports()

          // 报告生成完成后清空“上传附件预览/队列”，避免 UI 误以为还有已上传文件
          resetUploadState()
        } else if (res.content && res.content.status === 'error') {
          stopReportPolling()
          ElMessage.error('报告生成失败：' + (res.content.error || '未知错误'))
          reportLoading.value = false
        }
      } catch (error) {
        console.error('轮询错误:', error)
      }
    }, 2000)
  } catch (error) {
    console.error('触发生成失败:', error)
    ElMessage.error('无法触发报告生成')
    reportLoading.value = false
  }
}

// 获取产品推荐
const fetchProductRecommendations = async (autoLoad = false) => {
  try {
    // 使用报告数据中的session_id
    if (!reportData.value || !reportData.value.session_id) {
      console.error('无法获取session_id:', reportData.value)
      if (!autoLoad) {
        ElMessage.error('无法获取会话ID')
      }
      return
    }
    
    const sessionId = reportData.value.session_id
    console.log(`Chat页面 - 获取产品推荐: session_id=${sessionId}`)
    
    // 允许无 OCR 标签：后端会走兜底规则（rule_id 以 -03 结尾）
    
    const response = await request.get(`/report/${sessionId}/recommendations`)
    console.log('Chat页面 - 产品推荐响应:', response)
    
    if (response.success && response.recommendations) {
      products.value = response.recommendations
      showProducts.value = true
      console.log(`Chat页面 - 成功获取 ${response.total} 个产品推荐`)
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
    console.error('Chat页面 - 获取产品推荐失败:', error)
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
const buyProduct = (product) => {
  const url = product?.product_info?.link
  if (!url) {
    ElMessage.warning('暂无购买链接')
    return
  }

  try {
    // 在用户点击事件中调用，通常不会被浏览器拦截
    window.open(String(url), '_blank')
  } catch (e) {
    // 兜底：如果 window.open 被拦截或异常，使用同窗口跳转
    window.location.href = String(url)
  }
}

const changeProducts = () => {
  // 重新获取产品推荐
  fetchProductRecommendations()
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

const reportContent = computed(() => {
  // 兼容保留：历史上这里用 v-html 渲染 HTML 片段；现在改用 iframe。
  if (!reportData.value) return { html: '' }
  if (reportData.value.content && reportData.value.content.html) {
    return { html: reportData.value.content.html }
  }
  return { html: '' }
})

const report_iframe_refresh_key = ref(Date.now())

const report_iframe_src = computed(() => {
  if (!reportData.value || !reportData.value.session_id) return ''
  if (!authStore.token) return ''

  const base =
    import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8010/api/v1')

  const safe_base = String(base).replace(/\/+$/, '')
  const sid = encodeURIComponent(String(reportData.value.session_id))
  const token = encodeURIComponent(String(authStore.token || ''))
  return `${safe_base}/report/${sid}/html?token=${token}&_=${report_iframe_refresh_key.value}`
})

onMounted(async () => {
  // 检查是否有只读模式参数
  const targetSessionId = route.query.sessionId
  const readOnly = route.query.readOnly === 'true'
  
  if (targetSessionId && readOnly) {
    // 只读模式：加载指定会话的历史记录
    await viewHistoryReport(parseInt(targetSessionId))
  } else {
    // 正常模式：加载或创建活跃会话
    await loadActiveSession()
  }
  
  loadHistoryReports()
})

onUnmounted(() => {
  stopReportPolling()
  stopLoadingAnimation()
})
</script>

<style scoped>
* {
  box-sizing: border-box;
}

.chat-container {
  display: flex;
  height: 100vh;
  background: #F5F5F7;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

/* ========== 左侧边栏 ========== */
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

.history-btn svg {
  color: #4F378A;
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

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
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

.history-item:hover {
  background: #F2F2F7;
  border-color: #E5E5EA;
  transform: translateX(4px);
}

.history-item.active {
  background: #E8E5F7;
  border-color: #6750A4;
}

.history-text {
  font-size: 13px;
  color: #1D192B;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  font-weight: 500;
}

.history-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-badge {
  font-size: 11px;
  color: #6750A4;
  background: #EADDFF;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

/* ========== 主聊天区域 ========== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
  margin: 12px;
  margin-left: 0;
  border-radius: 25px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.chat-header {
  height: 64px;
  background: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: relative;
}

.header-logo{
  width: 90px;
}

.chat-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 24px;
  right: 24px;
  height: 1px;
  background: #F2F2F7;
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

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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

/* ========== 消息区域 ========== */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 32px 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  margin-bottom: 16px;
}

.message-wrapper.assistant {
  justify-content: flex-start;
  flex-direction: row;
  /* 让 AI 头像与气泡顶部对齐（而不是垂直居中） */
  align-items: flex-start;
}

.message-wrapper.user {
  justify-content: flex-end;
  flex-direction: row;
}

.message-bubble {
  max-width: 680px;
  min-width: 100px;
  flex-shrink: 1;
}

.message-wrapper.assistant .message-bubble {
  background: #ECE6F0;
  border-radius: 20px 20px 20px 8px;
  padding: 11px 16px;
}

.message-wrapper.user .message-bubble {
  background: #625B71;
  border-radius: 20px 20px 8px 20px;
  padding: 11px 16px;
}

.message-content {
  font-size: 15px;
  line-height: 1.5;
  color: #1C1C1E;
  word-wrap: break-word;
  white-space: pre-wrap;
}

/* 去除 markdown 生成的 p 标签边距 */
.message-content :deep(p) {
  margin: 0 !important;
}

.message-content :deep(p:not(:last-child)) {
  margin-bottom: 8px !important; /* 段落之间保持间距 */
}

.message-wrapper.user .message-content {
  color: #FFFFFF;
}

.message-avatar {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 50%;
  align-self: flex-start;
  /* 让头像顶边与气泡内容第一行更接近对齐（气泡有 11px 上内边距） */
  margin-top: 2px;
  overflow: hidden;
}
.ai-avatar{
  width: 100%;
}

.avatar-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.avatar-circle.ai {
    background: linear-gradient(135deg, #8B7FE5 0%, #6750A4 100%);
}

/* ========== AI Loading 精美动画 ========== */
.ai-loading-container {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 40px 20px;
  animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.loading-card {
  background: linear-gradient(135deg, #FFFFFF 0%, #F8F7FC 100%);
  border-radius: 24px;
  padding: 40px;
  box-shadow: 
    0 8px 32px rgba(139, 127, 229, 0.15),
    0 2px 8px rgba(0, 0, 0, 0.05);
  max-width: 480px;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  border: 1px solid rgba(139, 127, 229, 0.1);
}

/* 旋转动画容器 */
.loading-spinner-wrapper {
  position: relative;
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 3px solid transparent;
  animation: spinRing 2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.spinner-ring:nth-child(1) {
  border-top-color: #8B7FE5;
  animation-delay: 0s;
}

.spinner-ring:nth-child(2) {
  width: 85%;
  height: 85%;
  border-top-color: #A89FF5;
  animation-delay: 0.15s;
}

.spinner-ring:nth-child(3) {
  width: 70%;
  height: 70%;
  border-top-color: #C5BFF8;
  animation-delay: 0.3s;
}

@keyframes spinRing {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.spinner-core {
  position: relative;
  z-index: 10;
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #8B7FE5 0%, #6750A4 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 
    0 4px 16px rgba(139, 127, 229, 0.4),
    inset 0 2px 8px rgba(255, 255, 255, 0.2);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    box-shadow: 
      0 4px 16px rgba(139, 127, 229, 0.4),
      inset 0 2px 8px rgba(255, 255, 255, 0.2);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 
      0 6px 24px rgba(139, 127, 229, 0.6),
      inset 0 2px 8px rgba(255, 255, 255, 0.3);
  }
}

/* 文字容器 */
.loading-text-container {
  text-align: center;
  animation: textFade 2s ease-in-out infinite;
}

@keyframes textFade {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.loading-title {
  font-size: 20px;
  font-weight: 600;
  color: #1C1C1E;
  margin: 0 0 8px 0;
  background: linear-gradient(135deg, #6750A4 0%, #8B7FE5 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.loading-subtitle {
  font-size: 15px;
  color: #8E8E93;
  margin: 0;
  line-height: 1.5;
}

/* 进度提示 */
.loading-progress {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: #E5E5EA;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #8B7FE5 0%, #A89FF5 50%, #8B7FE5 100%);
  background-size: 200% 100%;
  animation: progressSlide 2s linear infinite;
  border-radius: 2px;
}

@keyframes progressSlide {
  0% {
    width: 0%;
    background-position: 0% 0%;
  }
  50% {
    width: 70%;
    background-position: 100% 0%;
  }
  100% {
    width: 100%;
    background-position: 200% 0%;
  }
}

.progress-hint {
  font-size: 13px;
  color: #A0A0A8;
  text-align: center;
}

/* ========== 报告显示区域 ========== */
.report-display-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 48px 40px;
}

.report-loading {
  text-align: center;
  padding: 60px 20px;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid #E5E5EA;
  border-top-color: #6750A4;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.report-loading p {
  color: #8E8E93;
  font-size: 15px;
}

.report-content-area {
  max-width: 800px;
  margin: 0 auto;
}

.html-report-section {
  background: #FFFFFF;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 16px;
}

.html-report-iframe {
  width: 100%;
  height: 900px;
  border: 0;
  display: block;
}

/* 报告内容样式（与 History.vue 对齐，确保环形评分图可见） */
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

/* OCR分析和标签展示区 */
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
  gap: 8px;
}

.ocr-text-content {
  font-size: 14px;
  line-height: 1.6;
  color: #666666;
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
  gap: 12px;
  margin-bottom: 12px;
}

.tag-item {
  display: inline-block;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
  color: #FFFFFF;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
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

/* 产品推荐区域 */
.products-recommendation {
  margin-top: 16px;
}

.disclaimer-notice {
  font-size: 12px;
  font-weight: 600;
  color: #1C1C1E;
  margin: 0 0 20px 0;
}

.recommend-trigger-area {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  background: #FFFFFF;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.trigger-icon-group {
  display: flex;
  gap: 12px;
}

.trigger-icon-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #F5F5F7 0%, #E5E5EA 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.show-products-btn {
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

.show-products-btn:hover {
  background: #7B6FD5;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 127, 229, 0.4);
}

.products-list-area {
  animation: productFadeIn 0.3s ease-in;
}

@keyframes productFadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.change-products-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.change-products-btn {
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

.change-products-btn:hover {
  background: #6750A4;
  color: #FFFFFF;
}

.product-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 1024px) {
  .product-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .product-cards-grid {
    grid-template-columns: 1fr;
  }
}

.product-item-card {
  background: #FFFFFF;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s, box-shadow 0.2s;
}

.product-item-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.product-img-placeholder {
  height: 180px;
  background: linear-gradient(135deg, #F5F5F7 0%, #E5E5EA 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.product-card-info {
  padding: 16px;
}

.product-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #1C1C1E;
  margin: 0 0 8px 0;
}

.product-card-desc {
  font-size: 13px;
  color: #8E8E93;
  line-height: 1.5;
  margin: 0 0 16px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.product-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.product-tag {
  display: inline-block;
  padding: 4px 12px;
  background: linear-gradient(135deg, #F0EDFF 0%, #E8E3FF 100%);
  color: #6750A4;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.product-card-actions {
  display: flex;
  gap: 8px;
}

.product-detail-btn,
.product-buy-btn {
  flex: 1;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.product-detail-btn {
  background: #F2F2F7;
  color: #1C1C1E;
}

.product-detail-btn:hover {
  background: #E5E5EA;
}

.product-buy-btn {
  background: #6750A4;
  color: #FFFFFF;
}

.product-buy-btn:hover {
  background: #5A3D99;
}

/* ========== 输入区域 ========== */
.input-container {
  padding: 20px 48px 24px;
  background: #FFFFFF;
  border-top: 1px solid #E5E5EA;
}

.readonly-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #FFF4E6;
  border: 1px solid #FFE5B4;
  border-radius: 12px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #B06000;
}

.exit-readonly-btn {
  padding: 6px 16px;
  background: #6750A4;
  color: #FFFFFF;
  border: none;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.exit-readonly-btn:hover {
  background: #5A3D99;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: #ECE6F0;
  border-radius: 28px;
  padding: 14px 20px;
  border: none;
  max-width: 100%;
}

.attach-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8E8E93;
  transition: color 0.2s;
  flex-shrink: 0;
  position: relative;
}

.attach-btn:hover {
  color: #1C1C1E;
}

.attach-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.upload-icon {
  width: 20px;
  height: 20px;
  display: block;
  opacity: 0.6;
  transition: opacity 0.2s;
}

.attach-btn:hover .upload-icon {
  opacity: 1;
}

.image-count {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #8B7FE5;
  color: white;
  font-size: 10px;
  font-weight: 600;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 图片预览区域 */
.images-preview {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: #F5F5F7;
  border-radius: 12px 12px 0 0;
  overflow-x: auto;
  max-width: 100%;
}

.image-preview-item {
  position: relative;
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  border-radius: 8px;
  overflow: hidden;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.file-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: linear-gradient(135deg, #F5F5F7 0%, #E5E5EA 100%);
}

.file-badge {
  font-size: 11px;
  font-weight: 700;
  color: #FFFFFF;
  background: #FF3B30;
  padding: 2px 8px;
  border-radius: 10px;
}

.file-name {
  font-size: 10px;
  color: #1C1C1E;
  text-align: center;
  line-height: 1.2;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.image-preview-item:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-image-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border: none;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  padding: 0;
}

.remove-image-btn:hover {
  background: rgba(0, 0, 0, 0.8);
}

.remove-image-btn svg {
  width: 12px;
  height: 12px;
}

.image-info {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  font-size: 10px;
  padding: 2px 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 图片放大预览弹窗 */
.image-preview-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s;
}

.image-preview-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-full-image {
  max-width: 100%;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

.close-preview-btn {
  position: absolute;
  top: -40px;
  right: 0;
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.close-preview-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.input-wrapper textarea {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  outline: none;
  font-size: 15px;
  color: #1C1C1E;
  font-family: inherit;
  line-height: 1.5;
  max-height: 120px;
  padding: 6px 0;
}

.input-wrapper textarea::placeholder {
  color: #8E8E93;
}

.send-btn {
  width: 35px;
  height: 35px;
  border: none;
  background: #1C1C1E;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: #2C2C2E;
  transform: scale(1.05);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-icon {
  width: 20px;
  height: 20px;
  display: block;
  filter: brightness(0) invert(1);
}

/* ========== Markdown 样式 ========== */
.message-content :deep(p) {
  margin: 0 0 8px 0;
}

.message-content :deep(p:last-child) {
  margin: 0;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.message-content :deep(li) {
  margin: 4px 0;
}

.message-content :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}

.message-wrapper.user .message-content :deep(code) {
  background: rgba(255, 255, 255, 0.2);
}

/* ========== 滚动条样式 ========== */
.messages-container::-webkit-scrollbar,
.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track,
.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}

.messages-container::-webkit-scrollbar-thumb,
.sidebar-content::-webkit-scrollbar-thumb {
  background: #C7C7CC;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover,
.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: #AEAEB2;
}
</style>

