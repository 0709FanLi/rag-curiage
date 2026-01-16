<template>
  <div class="dashboard-container">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h3 class="page-title">运营决策看板</h3>
        <p class="page-subtitle">实时监控 AI 服务负载与赛道热度</p>
      </div>
      <el-button class="export-btn" icon="Download">导出报表</el-button>
    </div>

    <!-- Metrics Cards -->
    <el-row :gutter="24" class="mb-4">
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-icon theme-blue">
            <el-icon><ChatLineSquare /></el-icon>
          </div>
          <div class="metric-label">总咨询会话 (SESSIONS)</div>
          <div class="metric-value">{{ formatNumber(metrics.consults) }}</div>
          <!-- <div class="metric-trend text-success">
            <el-icon><Top /></el-icon> 12.5%
          </div> -->
        </div>
      </el-col>
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-icon theme-indigo">
            <el-icon><Document /></el-icon>
          </div>
          <div class="metric-label">报告生成量</div>
          <div class="metric-value">{{ formatNumber(metrics.reports) }}</div>
          <!-- <div class="metric-trend text-success">
            <el-icon><Top /></el-icon> 8.2%
          </div> -->
        </div>
      </el-col>
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-icon theme-green">
            <el-icon><Aim /></el-icon>
          </div>
          <div class="metric-label">报告转化率</div>
          <!-- 保留两位小数 -->
          <div class="metric-value text-success">{{ Number(metrics.conversion_rate).toFixed(2) }}%</div>
          <!-- <small class="text-muted">≤100%</small> -->
        </div>
      </el-col>
      <!-- <el-col :span="6">
        <div class="metric-card">
          <div class="metric-icon theme-amber">
            <el-icon><Mouse /></el-icon>
          </div>
          <div class="metric-label">人均点击密度</div>
          <div class="metric-value text-warning">{{ metrics.click_density || 0 }}</div>
          <small class="text-muted">>1.0</small>
        </div>
      </el-col> -->
    </el-row>

    <!-- Charts Row -->
    <el-row :gutter="24" style="flex-wrap: wrap;margin-top: 70px;">
      <!-- Funnel Chart -->
      <el-col :span="14" style="margin-bottom: 24px;">
        <div class="chart-card">
          <h5 class="chart-title">AI 获客转化漏斗</h5>
          <div class="funnel-container">
            <div class="funnel-step">
              <div class="funnel-label">1. 会话接入</div>
              <div class="funnel-bar-bg">
                <div class="funnel-bar bg-secondary" style="width: 100%">100%</div>
              </div>
              <div class="funnel-val">{{ formatNumber(funnel.v1) }}</div>
            </div>
            
            <div class="funnel-step">
              <div class="funnel-label">2. 报告生成</div>
              <div class="funnel-bar-bg">
                <div class="funnel-bar bg-primary" :style="{ width: getPercentage(funnel.v2, funnel.v1) + '%' }">
                  {{ getPercentage(funnel.v2, funnel.v1) }}%
                </div>
              </div>
              <div class="funnel-val">{{ formatNumber(funnel.v2) }}</div>
            </div>
            
            <div class="funnel-step">
              <div class="funnel-label">3. 转化点击</div>
              <div class="funnel-bar-bg">
                <div class="funnel-bar bg-success" :style="{ width: getPercentage(funnel.v3, funnel.v1) + '%' }">
                  {{ getPercentage(funnel.v3, funnel.v1) }}%
                </div>
              </div>
              <div class="funnel-val">{{ formatNumber(funnel.v3) }}</div>
            </div>
          </div>
        </div>
      </el-col>
      
      <!-- Distribution Chart -->
      <el-col :span="10" style="margin-bottom: 24px;">
        <div class="chart-card">
          <h5 class="chart-title">热门赛道咨询量分布</h5>
          <div class="distribution-list">
            <div v-for="item in distribution" :key="item.name" class="dist-item">
              <div class="dist-header">
                <span>{{ item.name }}</span>
                <span>{{ item.value }}%</span>
              </div>
              <div class="progress-bg">
                <div class="progress-bar" 
                     :class="item.color || getColorClass(item.name)" 
                     :style="{ width: item.value + '%' }"></div>
              </div>
            </div>
          </div>
          <div class="chart-footer">
            <el-icon><InfoFilled /></el-icon>
            统计基于“评估会话数 (Sessions)”，真实反映业务负载。
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ChatLineSquare, Document, Aim, Mouse, Top, Download, InfoFilled } from '@element-plus/icons-vue'
import { getMetrics, getFunnel, getDistribution } from '@/api'

const metrics = ref({
  consults: 0,
  reports: 0,
  converting_reports: 0,
  total_clicks: 0,
  conversion_rate: 0,
  click_density: 0
})

const funnel = ref({
  v1: 0,
  v2: 0,
  v3: 0
})

const distribution = ref<any[]>([])

const getPercentage = (val: number | undefined | null, total: number | undefined | null) => {
  if (!total || !val || isNaN(val) || isNaN(total)) return 0
  return Math.round((val / total) * 100)
}

const getColorClass = (name: string) => {
  const map: Record<string, string> = {
    '睡眠与神经': 'bg-primary',
    '肠道与代谢': 'bg-success',
    '皮肤抗衰': 'bg-warning'
  }
  return map[name] || 'bg-secondary'
}

// 安全地格式化数字，避免 undefined 错误
const formatNumber = (val: number | undefined | null): string => {
  if (val === undefined || val === null || isNaN(val)) {
    return '0'
  }
  return val.toLocaleString()
}

onMounted(async () => {
  try {
    // Use Promise.all for parallel fetching
    const [mRes, fRes, dRes] = await Promise.all([
      getMetrics(),
      getFunnel(),
      getDistribution()
    ])
    metrics.value = mRes as any
    funnel.value = fRes as any
    // API 返回的数据结构是 { distribution: [...] }
    distribution.value = (dRes as any)?.distribution || (Array.isArray(dRes) ? dRes : [])
  } catch (e) {
    console.error('Failed to fetch dashboard data', e)
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  color: #0f172a;
}

.page-subtitle {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 0.9rem;
}

.export-btn {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #64748b;
}

.mb-4 {
  margin-bottom: 32px;
}

/* Metric Cards */
.metric-card {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  height: 100%;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  transition: transform 0.2s;
}

.metric-card:hover {
  transform: translateY(-2px);
}

.metric-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  margin-bottom: 16px;
}

.theme-blue { background-color: #eff6ff; color: #3b82f6; }
.theme-indigo { background-color: #eef2ff; color: #6366f1; }
.theme-green { background-color: #ecfdf5; color: #10b981; }
.theme-amber { background-color: #fffbeb; color: #f59e0b; }

.metric-label {
  font-size: 0.85rem;
  color: #64748b;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
  margin-bottom: 4px;
}

.metric-trend {
  font-size: 0.85rem;
  display: flex;
  align-items: center;
}

.text-success { color: #10b981; }
.text-warning { color: #f59e0b; }
.text-muted { color: #94a3b8; font-size: 0.85rem; }

/* Chart Cards */
.chart-card {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  border: 1px solid #e2e8f0;
  height: 100%;
}

.chart-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 24px 0;
}

/* Funnel */
.funnel-step {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.funnel-label {
  width: 100px;
  font-weight: 600;
  color: #64748b;
  font-size: 0.9rem;
}

.funnel-bar-bg {
  flex-grow: 1;
  background: #f1f5f9;
  height: 28px;
  border-radius: 6px;
  overflow: hidden;
  margin: 0 15px;
}

.funnel-bar {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 10px;
  color: white;
  font-weight: bold;
  font-size: 0.85rem;
  transition: width 1s ease;
}

.funnel-val {
  width: 60px;
  text-align: right;
  font-weight: bold;
  color: #0f172a;
}

/* Distribution */
.dist-item {
  margin-bottom: 16px;
}

.dist-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
  color: #475569;
  margin-bottom: 6px;
}

.progress-bg {
  height: 6px;
  background: #f1f5f9;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 3px;
}

.bg-primary { background-color: #3b82f6; }
.bg-success { background-color: #10b981; }
.bg-warning { background-color: #f59e0b; }
.bg-secondary { background-color: #94a3b8; }
.bg-info { background-color: #06b6d4; }
.bg-danger { background-color: #ef4444; }
.bg-dark { background-color: #1e293b; }

.chart-footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
  font-size: 0.8rem;
  color: #94a3b8;
  display: flex;
  align-items: center;
}

.chart-footer .el-icon {
  margin-right: 6px;
}
</style>
