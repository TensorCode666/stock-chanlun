<template>
  <div class="layout">
    <!-- Nav -->
    <nav class="nav">
      <div class="nav-inner">
        <router-link to="/" class="nav-brand">ChanStock</router-link>
        <div class="nav-links">
          <router-link to="/" class="nav-link">首页</router-link>
          <router-link to="/screen" class="nav-link">选股</router-link>
          <router-link to="/watchlist" class="nav-link">自选股</router-link>
        </div>
        <div class="nav-actions">
          <!-- AI 模型切换 -->
          <div class="ai-model-switch">
            <button
              class="model-btn"
              :class="{ active: store.aiModel === 'deepseek' }"
              @click="switchModel('deepseek')"
              title="DeepSeek"
            >DS</button>
            <button
              class="model-btn"
              :class="{ active: store.aiModel === 'gemini' }"
              @click="switchModel('gemini')"
              title="Gemini"
            >GM</button>
          </div>
          <button class="btn btn-ghost" @click="refreshData" :disabled="loadingAny">
            {{ loadingAny ? '加载中...' : '刷新' }}
          </button>
          <button class="btn btn-ghost" @click="toggleWatch" :class="{ 'btn-danger': isWatching, 'btn-loading': watchToggling }" :disabled="loadingAny || watchToggling">
            <span v-if="watchToggling" class="btn-spinner" />
            <span v-else>{{ isWatching ? '取消自选' : '+自选' }}</span>
          </button>
        </div>
      </div>
    </nav>

    <!-- 全局加载骨架屏 -->
    <div v-if="showInitialLoading" class="loading-overlay">
      <div class="loading-progress">
        <div class="loading-steps">
          <div v-for="step in loadingSteps" :key="step.key" class="loading-step" :class="step.status">
            <div class="step-dot" />
            <span class="step-label">{{ step.label }}</span>
          </div>
        </div>
        <div class="spinner" />
      </div>
    </div>

    <div v-else-if="error" class="error-page">
      <div class="error-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <p class="error-message">{{ error }}</p>
      <button class="btn btn-primary" @click="refreshData">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
        重试（R键）
      </button>
    </div>

    <template v-else>
    <div class="main-grid" :style="mainGridStyle">
      <!-- Left: Stock info -->
      <aside v-if="layout.leftVisible" class="sidebar">
        <div class="card stock-info-card">
          <div class="stock-header">
            <div>
              <div class="stock-code-label mono">{{ stockCode }}</div>
              <div class="stock-name-label">{{ headerQuote?.name || stockCode }}</div>
            </div>
            <div class="stock-price-block">
              <div class="price-current mono">
                {{ headerQuote?.price != null ? headerQuote.price.toFixed(2) : '—' }}
              </div>
              <div
                class="price-change mono"
                :class="changeClass"
              >
                {{ changeText }}
              </div>
            </div>
          </div>

          <div class="price-stats">
            <div class="stat-row">
              <span class="stat-label">开盘</span>
              <span class="stat-value mono">{{ statPrice(headerQuote?.open) }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">最高</span>
              <span class="stat-value mono price-up">{{ statPrice(headerQuote?.high) }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">最低</span>
              <span class="stat-value mono price-down">{{ statPrice(headerQuote?.low) }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">成交量</span>
              <span class="stat-value mono">{{ formatVolume(headerQuote?.volume) || '—' }}</span>
            </div>
          </div>
        </div>

        <!-- Level selector -->
        <div class="card">
          <div class="card-title">分析级别 <span class="level-hint">快捷键: 1/5/D/W/M</span></div>
          <div class="level-tabs">
            <button
              v-for="lv in levels"
              :key="lv.value"
              class="level-tab"
              :class="{ active: currentLevel === lv.value }"
              @click="changeLevel(lv.value)"
            >{{ lv.label }}</button>
          </div>
        </div>

        <!-- Trend info -->
        <div class="card">
          <div class="card-title">走势判断</div>
          <div class="trend-info">
            <div class="trend-badge" :class="trendClass">
              {{ store.chanlunResult?.trend || '—' }}
            </div>
            <div class="trend-desc">
              {{ store.chanlunResult?.summary || '暂无数据' }}
            </div>
          </div>
        </div>

        <!-- Signals -->
        <SignalCard :signals="store.chanlunResult?.signals || []" :updated-at="store.chanlunUpdatedAt" />
      </aside>

      <!-- Center: Chart -->
      <div class="chart-area">
        <div class="chart-header">
          <div class="chart-header-left">
            <div class="level-tabs chart-level-tabs">
              <button
                v-for="lv in levels"
                :key="lv.value"
                class="level-tab"
                :class="{ active: currentLevel === lv.value }"
                @click="changeLevel(lv.value)"
              >{{ lv.label }}</button>
            </div>
            <!-- 时间筛选 -->
            <div class="date-filter" :class="{ 'has-filter': startDate || endDate }">
              <button class="date-filter-toggle" @click="toggleDatePanel" :class="{ active: startDate || endDate }">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                  <line x1="16" y1="2" x2="16" y2="6"/>
                  <line x1="8" y1="2" x2="8" y2="6"/>
                  <line x1="3" y1="10" x2="21" y2="10"/>
                </svg>
                <span v-if="!startDate && !endDate">时间筛选</span>
                <span v-else class="date-filter-active-text">{{ formatFilterText() }}</span>
              </button>
              <div v-if="showDatePanel" class="date-panel">
                <div class="date-panel-row">
                  <label class="date-panel-label">开始日期</label>
                  <input
                    type="date"
                    v-model="startDate"
                    :max="endDate || undefined"
                    class="date-panel-input"
                  />
                </div>
                <div class="date-panel-row">
                  <label class="date-panel-label">结束日期</label>
                  <input
                    type="date"
                    v-model="endDate"
                    :min="startDate || undefined"
                    class="date-panel-input"
                  />
                </div>
                <div class="date-panel-actions">
                  <button class="date-panel-reset" @click="resetDateFilter" v-if="startDate || endDate">清除</button>
                  <button class="date-panel-apply" @click="applyDateFilter">应用</button>
                </div>
              </div>
            </div>
          </div>
          <div class="chart-actions">
            <IndicatorSelector />
            <button class="btn btn-ghost chart-action-btn" @click="exportCSV" title="导出 K 线 CSV">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              导出
            </button>
          </div>
          <span v-if="store.klineUpdatedAt" class="chart-timestamp">K线 {{ store.klineUpdatedAt }}</span>
        </div>

        <!-- 主图区域上方：基本资料（与左侧行情互补） -->
        <div v-if="infoPanelRows.length > 0 || financeRows.length > 0" class="company-info card">
          <div class="company-info-head">
            <div class="company-info-head-left">
              <span class="company-info-title">基本资料</span>
              <span v-if="stockInfo?.名称" class="company-info-name">{{ stockInfo.名称 }}</span>
            </div>
            <div class="company-info-actions layout-control">
              <button
                class="ci-action-btn"
                :class="{ active: !layout.leftVisible }"
                @click="layout.leftVisible = !layout.leftVisible"
                :title="layout.leftVisible ? '隐藏左侧栏' : '显示左侧栏'"
              >
                左
              </button>
              <button
                class="ci-action-btn"
                :class="{ active: !layout.rightVisible }"
                @click="layout.rightVisible = !layout.rightVisible"
                :title="layout.rightVisible ? '隐藏右侧栏' : '显示右侧栏'"
              >
                右
              </button>
              <button class="ci-action-btn ci-action-btn--wide" @click="toggleLayoutPanel" title="布局设置">
                布局
              </button>

              <div v-if="showLayoutPanel" class="layout-panel">
                <div class="lp-title">布局设置</div>

                <div class="lp-row">
                  <span class="lp-label">左侧栏</span>
                  <button class="lp-toggle" :class="{ on: layout.leftVisible }" @click="layout.leftVisible = !layout.leftVisible">
                    {{ layout.leftVisible ? '显示' : '隐藏' }}
                  </button>
                </div>
                <div class="lp-slider" v-if="layout.leftVisible">
                  <input type="range" min="200" max="360" step="10" v-model.number="layout.leftWidth" />
                  <span class="lp-val mono">{{ layout.leftWidth }}px</span>
                </div>

                <div class="lp-row">
                  <span class="lp-label">右侧栏</span>
                  <button class="lp-toggle" :class="{ on: layout.rightVisible }" @click="layout.rightVisible = !layout.rightVisible">
                    {{ layout.rightVisible ? '显示' : '隐藏' }}
                  </button>
                </div>
                <div class="lp-slider" v-if="layout.rightVisible">
                  <input type="range" min="240" max="460" step="10" v-model.number="layout.rightWidth" />
                  <span class="lp-val mono">{{ layout.rightWidth }}px</span>
                </div>
              </div>
            </div>
          </div>
          <div class="company-info-sections">
            <section v-if="infoPanelRows.length" class="ci-section">
              <div class="ci-section-head">
                <span class="ci-section-title">基本指标</span>
              </div>
              <div class="company-info-grid">
                <div
                  v-for="row in infoPanelRows"
                  :key="row.key"
                  class="company-info-cell"
                >
                  <span class="ci-label">{{ row.label }}</span>
                  <span
                    class="ci-value mono"
                    :class="row.valueClass"
                  >{{ row.value }}</span>
                </div>
              </div>
            </section>

            <section v-if="financeRows.length" class="ci-section">
              <div class="ci-section-head">
                <span class="ci-section-title">市值股本</span>
              </div>
              <div class="company-info-grid">
                <div
                  v-for="row in financeRows"
                  :key="row.key"
                  class="company-info-cell"
                >
                  <span class="ci-label">{{ row.label }}</span>
                  <span class="ci-value mono">{{ row.value }}</span>
                </div>
              </div>
            </section>
          </div>
        </div>

        <KLineChart
          :klines="store.klines"
          :bis="store.chanlunResult?.bis || []"
          :xiangs="store.chanlunResult?.xiangs || []"
          :zhongshus="store.chanlunResult?.zhongshus || []"
          :signals="store.chanlunResult?.signals || []"
          :ai-signal="store.aiSignal"
          :support-resistance="store.chanlunResult?.supportResistance || []"
          :indicators="store.indicators"
          :loading="store.loadingChart"
        />
      </div>

      <!-- Right: AI Strategy + Notes -->
      <aside v-if="layout.rightVisible" class="sidebar-right">
        <CommentSection :stock-code="stockCode" />
        <StrategyCard
          :signal="store.aiSignal"
          :updated-at="store.aiUpdatedAt"
          :loading="store.loadingAI"
          :level-trends="levelTrends"
          @deep-analyze="onDeepAnalyze"
        />
      </aside>
    </div>
    <AiSuspendedBallChat :stock-code="stockCode" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted, nextTick, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'
import type { LevelOption } from '../stores/chanlun'
import { useWatchlistStore } from '../stores/watchlist'
import type { StockInfoFields, StockExtras, Quote } from '../api/stock'
import toast from '../composables/useToast'
import { resolveApiBaseURL } from '../api/stock'
import { useStockPage } from '../composables/useStockPage'
import { useMultiLevelTrends } from '../composables/useMultiLevelTrends'
import { MULTI_LEVEL_TREND_LEVELS } from '../utils/prefetchStock'
import { useVisibilityRefresh } from '../composables/useVisibilityRefresh'
import { API_CACHE_TTL } from '../utils/apiCache'
const KLineChart = defineAsyncComponent(
  () => import('../components/Chart/KLineChart.vue'),
)
import SignalCard from '../components/Signal/SignalCard.vue'
import StrategyCard from '../components/Signal/StrategyCard.vue'
import IndicatorSelector from '../components/IndicatorSelector.vue'
import CommentSection from '../components/Signal/CommentSection.vue'
const AiSuspendedBallChat = defineAsyncComponent(
  () => import('../components/AiSuspendedBallChat.vue'),
)

const route = useRoute()
const { store, quote, stockInfo, extras, loadStock, changeLevel: changeLevelBase, refreshAIStrategy, refreshQuotes } = useStockPage()

async function changeLevel(level: LevelOption) {
  await changeLevelBase(stockCode.value, level)
}
const watchlistStore = useWatchlistStore()

const watchToggling = ref(false)

const isWatching = computed(() =>
  watchlistStore.stocks.some(s => s.code === stockCode.value)
)

const stockCode = computed(() => route.params.code as string)
const { levelTrends } = useMultiLevelTrends(stockCode, MULTI_LEVEL_TREND_LEVELS, () => store.chanlunResult)
const currentLevel = computed(() => store.currentLevel)
const loadingAny = computed(() =>
  store.loadingKline || store.loadingChanlun
)

/** 首屏无 K 线时全屏加载；已有数据时仅局部刷新，避免遮挡图表 */
const showInitialLoading = computed(
  () => loadingAny.value && !store.klines.length && !store.chanlunResult,
)

const loadingSteps = computed(() => [
  { key: 'kline', label: 'K线数据', status: (store.loadingChanlun || store.loadingKline) ? 'loading' : store.klines.length ? 'done' : 'pending' },
  { key: 'chanlun', label: '缠论分析', status: store.loadingChanlun ? 'loading' : store.chanlunResult ? 'done' : 'pending' },
  { key: 'ai', label: 'AI策略', status: store.loadingAI ? 'loading' : store.aiSignal ? 'done' : 'pending' },
])

const error = computed(() =>
  store.errorKline || store.errorChanlun
)
type StockViewLayout = {
  leftVisible: boolean
  rightVisible: boolean
  leftWidth: number
  rightWidth: number
}

const LAYOUT_KEY = 'chanstock_stockview_layout_v1'
const layout = ref<StockViewLayout>({
  leftVisible: true,
  rightVisible: true,
  leftWidth: 240,
  rightWidth: 280,
})

const showLayoutPanel = ref(false)
let layoutPanelClickHandler: ((e: MouseEvent) => void) | null = null

function toggleLayoutPanel() {
  showLayoutPanel.value = !showLayoutPanel.value
  if (showLayoutPanel.value) {
    nextTick(() => {
      layoutPanelClickHandler = (e: MouseEvent) => {
        const el = document.querySelector('.layout-control')
        if (el && !el.contains(e.target as Node)) {
          showLayoutPanel.value = false
          cleanupLayoutPanelHandler()
        }
      }
      setTimeout(() => document.addEventListener('click', layoutPanelClickHandler!), 0)
    })
  } else {
    cleanupLayoutPanelHandler()
  }
}

function cleanupLayoutPanelHandler() {
  if (layoutPanelClickHandler) {
    document.removeEventListener('click', layoutPanelClickHandler)
    layoutPanelClickHandler = null
  }
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function loadLayout() {
  try {
    const raw = localStorage.getItem(LAYOUT_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Partial<StockViewLayout>
    layout.value = {
      leftVisible: parsed.leftVisible ?? true,
      rightVisible: parsed.rightVisible ?? true,
      leftWidth: clamp(Number(parsed.leftWidth ?? 240) || 240, 200, 360),
      rightWidth: clamp(Number(parsed.rightWidth ?? 280) || 280, 240, 460),
    }
  } catch {
    // ignore
  }
}

function persistLayout() {
  try {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout.value))
  } catch {
    // ignore
  }
}

const mainGridStyle = computed(() => {
  const cols = [
    layout.value.leftVisible ? `${layout.value.leftWidth}px` : null,
    'minmax(0, 1fr)',
    layout.value.rightVisible ? `${layout.value.rightWidth}px` : null,
  ].filter(Boolean)

  return {
    gridTemplateColumns: cols.join(' '),
  }
})

// 时间筛选
function getOneYearAgo(): string {
  const date = new Date()
  date.setFullYear(date.getFullYear() - 1)
  return date.toISOString().split('T')[0]
}

const startDate = ref(getOneYearAgo())
const endDate = ref('')
const showDatePanel = ref(false)
const dateFilterRef = ref<HTMLElement | null>(null)
let datePanelClickHandler: ((e: MouseEvent) => void) | null = null

function toggleDatePanel() {
  showDatePanel.value = !showDatePanel.value
  if (showDatePanel.value) {
    nextTick(() => {
      datePanelClickHandler = (e: MouseEvent) => {
        const filterEl = document.querySelector('.date-filter')
        if (filterEl && !filterEl.contains(e.target as Node)) {
          showDatePanel.value = false
          cleanupDatePanelHandler()
        }
      }
      setTimeout(() => document.addEventListener('click', datePanelClickHandler!), 0)
    })
  } else {
    cleanupDatePanelHandler()
  }
}

function cleanupDatePanelHandler() {
  if (datePanelClickHandler) {
    document.removeEventListener('click', datePanelClickHandler)
    datePanelClickHandler = null
  }
}

function formatFilterText() {
  if (startDate.value && endDate.value) {
    return `${startDate.value} ~ ${endDate.value}`
  } else if (startDate.value) {
    return `${startDate.value} 至今`
  } else if (endDate.value) {
    return `~ ${endDate.value}`
  }
  return '时间筛选'
}

function resetDateFilter() {
  startDate.value = getOneYearAgo()
  endDate.value = ''
  showDatePanel.value = false
  cleanupDatePanelHandler()
  loadStock(stockCode.value, currentLevel.value, startDate.value || undefined, endDate.value || undefined)
}

function applyDateFilter() {
  showDatePanel.value = false
  cleanupDatePanelHandler()
  loadStock(stockCode.value, currentLevel.value, startDate.value || undefined, endDate.value || undefined)
}

function _num(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function statPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

/** 左侧报价区：合并 /quote 与 /info，任一来源有有效现价即展示；避免 quote 对象不完整时全是「—」 */
const headerQuote = computed((): Quote | null => {
  const q = quote.value
  const s = stockInfo.value as Record<string, unknown> | null
  if (!q && !s) return null

  const price = _num(q?.price) ?? _num(s?.['现价'])
  if (price == null) return null

  const name =
    (q?.name != null && String(q.name).trim() !== '' ? String(q.name) : '') ||
    (s?.['名称'] != null ? String(s['名称']).trim() : '') ||
    ''
  const code = String(q?.code ?? s?.['代码'] ?? stockCode.value)

  return {
    code,
    name,
    price,
    change_pct: _num(q?.change_pct) ?? _num(s?.['涨跌幅']) ?? 0,
    volume: _num(q?.volume) ?? _num(s?.['成交量']) ?? 0,
    amount: _num(q?.amount) ?? _num(s?.['成交额']) ?? 0,
    high: _num(q?.high) ?? _num(s?.['最高']) ?? 0,
    low: _num(q?.low) ?? _num(s?.['最低']) ?? 0,
    open: _num(q?.open) ?? _num(s?.['今开']) ?? 0,
    prev_close: _num(q?.prev_close) ?? _num(s?.['昨收']) ?? 0,
  }
})

const levels = [
  { value: '1min' as LevelOption, label: '1分' },
  { value: '5min' as LevelOption, label: '5分' },
  { value: '15min' as LevelOption, label: '15分' },
  { value: '30min' as LevelOption, label: '30分' },
  { value: '60min' as LevelOption, label: '60分' },
  { value: 'daily' as LevelOption, label: '日线' },
  { value: 'weekly' as LevelOption, label: '周线' },
  { value: 'monthly' as LevelOption, label: '月线' },
]

const changeClass = computed(() => {
  const hq = headerQuote.value
  if (!hq) return ''
  return hq.change_pct > 0 ? 'price-up' : hq.change_pct < 0 ? 'price-down' : 'price-flat'
})

const changeText = computed(() => {
  const hq = headerQuote.value
  if (!hq) return ''
  const pct = hq.change_pct
  return `${pct > 0 ? '+' : ''}${pct?.toFixed(2) || 0}%`
})

const trendClass = computed(() => {
  const t = store.chanlunResult?.trend
  if (t === '上涨') return 'trend-up'
  if (t === '下跌') return 'trend-down'
  return 'trend-side'
})

type InfoRow = { key: string; label: string; value: string; valueClass?: string }

function fmtRatio(v?: number): string {
  if (v == null || Number.isNaN(v) || v === 0) return '—'
  return v.toFixed(2)
}

function fmtAmount(v?: number): string {
  if (v == null || Number.isNaN(v) || v === 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return v.toFixed(0)
}

const infoPanelRows = computed((): InfoRow[] => {
  const s = stockInfo.value
  if (!s) return []
  const rows: InfoRow[] = []
  const push = (
    key: string,
    label: string,
    value: string,
    valueClass?: string
  ) => {
    if (value !== '—') rows.push({ key, label, value, valueClass })
  }
  const chg = (s as any).涨跌额
  let chgClass: string | undefined
  if (chg != null && !Number.isNaN(chg)) {
    if (chg > 0) chgClass = 'price-up'
    else if (chg < 0) chgClass = 'price-down'
  }
  push('pe', '市盈率', fmtRatio((s as any).市盈率))
  push('pb', '市净率', fmtRatio((s as any).市净率))
  if ((s as any).振幅 != null && !Number.isNaN((s as any).振幅) && (s as any).振幅 !== 0) {
    push('amp', '振幅', `${(s as any).振幅.toFixed(2)}%`)
  }
  push('amt', '成交额', fmtAmount((s as any).成交额))
  if (chg != null && !Number.isNaN(chg)) {
    const t = `${chg > 0 ? '+' : ''}${chg.toFixed(2)}`
    push('chg_amt', '涨跌额', t, chgClass)
  }
  push('prev', '昨收', (s as any).昨收 != null && !Number.isNaN((s as any).昨收) && (s as any).昨收 !== 0 ? (s as any).昨收.toFixed(2) : '—')
  return rows
})

/** 基本资料增强：市值/股本/换手率（来自 extras.boards） */
const financeRows = computed((): InfoRow[] => {
  const b = extras.value?.boards
  if (!b) return []
  const rows: InfoRow[] = []
  const push = (key: string, label: string, value: string) => {
    if (value && value !== '—') rows.push({ key, label, value })
  }
  // 市值格式化
  const fmtMkt = (v?: string | number) => {
    if (v == null) return '—'
    const n = typeof v === 'string' ? parseFloat(v) : v
    if (!Number.isFinite(n) || n === 0) return '—'
    if (n >= 1e12) return (n / 1e12).toFixed(2) + '万亿'
    if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
    return n.toFixed(2) + '万'
  }
  const fmtShares = (v?: string | number) => {
    if (v == null) return '—'
    const n = typeof v === 'string' ? parseFloat(v) : v
    if (!Number.isFinite(n) || n === 0) return '—'
    if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
    if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
    return n.toFixed(0)
  }
  for (const h of b.highlights ?? []) {
    if (h.label.includes('总市值')) push('mkt_cap', '总市值', fmtMkt(h.value))
    else if (h.label.includes('流通市值')) push('float_cap', '流通市值', fmtMkt(h.value))
    else if (h.label.includes('总股本')) push('total_shares', '总股本', fmtShares(h.value))
    else if (h.label.includes('流通股')) push('float_shares', '流通股', fmtShares(h.value))
    else if (h.label.includes('上市时间')) push('listed_date', '上市时间', h.value)
  }
  return rows
})

// 注：已移除个股页中间竖栏（盘口/板块/新闻），相关展示逻辑不再需要

async function loadData(force = false) {
  await loadStock(
    stockCode.value,
    currentLevel.value,
    startDate.value || undefined,
    endDate.value || undefined,
    { force },
  )
}

function refreshData() {
  void loadData(true)
}

async function onDeepAnalyze() {
  try {
    await refreshAIStrategy(stockCode.value, { useLlm: true })
    toast.success('LLM 深度分析已完成')
  } catch (e: unknown) {
    toast.error(e instanceof Error ? e.message : '深度分析失败')
  }
}

async function toggleWatch() {
  if (watchToggling.value) return
  watchToggling.value = true
  try {
    if (isWatching.value) {
      await watchlistStore.removeStock(stockCode.value)
      toast.success('已从自选股移除')
    } else {
      await watchlistStore.addStock(stockCode.value)
      toast.success('已添加到自选股')
    }
  } catch (e: any) {
    toast.error(e.message || '操作失败，请重试')
  } finally {
    watchToggling.value = false
  }
}

async function switchModel(model: string) {
  if (model === store.aiModel) return
  try {
    await store.setAiModel(model, stockCode.value)
    toast.success('已切换模型并完成 LLM 分析')
  } catch (e: unknown) {
    toast.error(e instanceof Error ? e.message : '模型切换失败')
  }
}

function formatVolume(v?: number) {
  if (!v) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toString()
}

function exportCSV() {
  const code = stockCode.value
  const level = currentLevel.value
  const url = `${resolveApiBaseURL()}/stocks/${encodeURIComponent(code)}/export?level=${encodeURIComponent(level)}`
  window.open(url, '_blank')
}

// 键盘快捷键
function handleKeydown(e: KeyboardEvent) {
  // 忽略输入框中的按键
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') {
    return
  }

  switch (e.key) {
    case 'r':
    case 'R':
      if (!loadingAny.value) loadData(true)
      break
    case '1':
      changeLevel('1min')
      break
    case '5':
      changeLevel('5min')
      break
    case 'd':
    case 'D':
      changeLevel('daily')
      break
    case 'w':
    case 'W':
      changeLevel('weekly')
      break
    case 'm':
    case 'M':
      changeLevel('monthly')
      break
  }
}

onMounted(() => {
  loadLayout()
  void watchlistStore.fetchWatchlist()
  loadData()
  window.addEventListener('keydown', handleKeydown)
})

useVisibilityRefresh(
  () => refreshQuotes(stockCode.value),
  API_CACHE_TTL.quote,
)

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  cleanupLayoutPanelHandler()
})

watch(() => route.params.code, () => { void loadData() })

watch(layout, persistLayout, { deep: true })
</script>

<style scoped>
.layout { min-height: 100vh; }

.nav-actions { display: flex; gap: 8px; margin-left: auto; }

.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: var(--bg-base);
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.loading-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 200px;
}

.loading-step {
  display: flex;
  align-items: center;
  gap: 10px;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.3s;
}

.loading-step.pending .step-dot { background: var(--border); }
.loading-step.loading .step-dot {
  background: var(--accent-blue);
  animation: pulse 1s ease-in-out infinite;
}
.loading-step.done .step-dot { background: var(--accent-green); }

.step-label {
  font-size: 0.85rem;
  transition: color 0.3s;
}
.loading-step.pending .step-label { color: var(--text-muted); }
.loading-step.loading .step-label { color: var(--text-primary); }
.loading-step.done .step-label { color: var(--accent-green); }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

@keyframes spin { to { transform: rotate(360deg); } }
.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.btn-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 1.5px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.btn-loading { opacity: 0.7; cursor: not-allowed !important; }
.btn-danger { color: var(--accent-red) !important; }

.error-page {
  text-align: center;
  padding: 80px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.error-icon {
  color: var(--accent-red);
  opacity: 0.6;
}
.error-message {
  color: var(--text-secondary);
  font-size: 0.95rem;
  margin: 0;
  max-width: 320px;
}
.error-page .btn {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.main-grid {
  display: grid;
  gap: 16px;
  padding: 16px 24px;
  max-width: 1760px;
  margin: 0 auto;
  align-items: start;
}

.sidebar { display: flex; flex-direction: column; gap: 12px; }

.sidebar-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  height: calc(100vh - 88px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
  position: sticky;
  top: 0;
  align-self: start;
}
.sidebar-right::-webkit-scrollbar { width: 5px; }
.sidebar-right::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

.stock-info-card { padding: 16px; }
.stock-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.stock-code-label { font-size: 0.75rem; color: var(--text-muted); }
.stock-name-label { font-size: 1.1rem; font-weight: 700; }
.price-current { font-size: 1.8rem; font-weight: 700; }
.price-change { font-size: 0.9rem; margin-top: 4px; }

.price-stats { display: flex; flex-direction: column; gap: 8px; }
.stat-row { display: flex; justify-content: space-between; }
.stat-label { color: var(--text-muted); font-size: 0.85rem; }
.stat-value { font-size: 0.85rem; }

.trend-info { display: flex; flex-direction: column; gap: 8px; }
.trend-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  width: fit-content;
}
.trend-up { background: rgba(239, 68, 68, 0.14); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.25); }
.trend-down { background: rgba(34, 197, 94, 0.14); color: var(--accent-green); border: 1px solid rgba(34, 197, 94, 0.25); }
.trend-side { background: rgba(245, 158, 11, 0.12); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.28); }
.trend-desc { font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5; }

.ai-model-switch {
  display: flex;
  gap: 4px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 4px;
}
.model-btn {
  padding: 5px 12px;
  border-radius: 7px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.model-btn.active {
  background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
  color: #fff;
  box-shadow: 0 2px 10px rgba(14, 165, 233, 0.35);
}
.model-btn:hover:not(.active) { color: var(--text-primary); background: rgba(255, 255, 255, 0.06); }

.chart-area { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.chart-header { display: flex; align-items: center; gap: 8px; }
.chart-level-tabs { flex-shrink: 0; }
.chart-actions { margin-left: auto; display: flex; align-items: center; gap: 6px; }
.chart-action-btn { font-size: 0.72rem; padding: 5px 10px; display: flex; align-items: center; gap: 4px; }
.chart-timestamp { font-size: 0.65rem; color: var(--text-muted); font-family: var(--font-mono); white-space: nowrap; }
.layout-control { position: relative; }
.layout-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 220px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  z-index: 120;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
}
.lp-title {
  font-size: 0.72rem;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 10px;
}
.lp-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.lp-row + .lp-row { margin-top: 10px; }
.lp-label { font-size: 0.78rem; color: var(--text-secondary); font-weight: 600; }
.lp-toggle {
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
}
.lp-toggle.on {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.35);
  color: var(--accent-blue);
}
.lp-slider {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.lp-slider input[type="range"] { flex: 1; }
.lp-val { font-size: 0.72rem; color: var(--text-muted); min-width: 56px; text-align: right; }

.company-info {
  padding: 14px 16px;
  flex-shrink: 0;
}
.company-info-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.company-info-head-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.company-info-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.ci-action-btn {
  padding: 4px 9px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.15s;
  line-height: 1.2;
}
.ci-action-btn:hover {
  border-color: rgba(14, 165, 233, 0.35);
  color: var(--text-primary);
}
.ci-action-btn.active {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.35);
  color: var(--accent-blue);
}
.ci-action-btn--wide { font-weight: 800; padding: 4px 12px; }
.company-info-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.company-info-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 520px;
}
.company-info-sections {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 14px;
}
.ci-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 12px 12px 10px;
  min-width: 0;
}
.ci-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.ci-section-title {
  font-size: 0.68rem;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.company-info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 14px;
}
.company-info-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.ci-label {
  font-size: 0.66rem;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}
.ci-value {
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.25;
}

@media (max-width: 1320px) {
  .company-info-sections { grid-template-columns: 1fr; }
}
@media (max-width: 980px) {
  .company-info-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

/* 时间筛选器样式 */
.chart-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.date-filter {
  position: relative;
}

.date-filter-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.date-filter-toggle:hover {
  border-color: var(--accent-blue);
  color: var(--text-primary);
}

.date-filter-toggle.active {
  background: rgba(14, 165, 233, 0.1);
  border-color: var(--accent-blue);
  color: var(--accent-blue);
}

.date-filter-active-text {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.date-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  min-width: 220px;
}

.date-panel-row {
  margin-bottom: 12px;
}

.date-panel-row:last-of-type {
  margin-bottom: 14px;
}

.date-panel-label {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-bottom: 6px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.date-panel-input {
  width: 100%;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 0.8rem;
  color: var(--text-primary);
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.date-panel-input:focus {
  border-color: var(--accent-blue);
}

.date-panel-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.date-panel-reset {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.75rem;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.date-panel-reset:hover {
  color: var(--accent-red);
  border-color: var(--accent-red);
}

.date-panel-apply {
  padding: 6px 14px;
  background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
  border: none;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.date-panel-apply:hover {
  filter: brightness(1.1);
}

@media (max-width: 1320px) {
  .main-grid { grid-template-columns: 220px minmax(0, 1fr) 280px; }
}
@media (max-width: 1200px) {
  .main-grid { grid-template-columns: 200px 1fr; }
  .sidebar-right { display: none; }
}
@media (max-width: 768px) {
  .main-grid { grid-template-columns: 1fr; }
  .sidebar { display: none; }
}
</style>