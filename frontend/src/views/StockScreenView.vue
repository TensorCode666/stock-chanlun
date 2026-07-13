<template>
  <div class="screen-layout">
    <!-- Nav -->
    <nav class="nav">
      <div class="nav-inner">
        <router-link to="/" class="nav-brand">ChanStock</router-link>
        <div class="nav-links">
          <router-link to="/" class="nav-link">首页</router-link>
          <router-link to="/screen" class="nav-link active">选股</router-link>
          <router-link to="/watchlist" class="nav-link">自选股</router-link>
        </div>
      </div>
    </nav>

    <div class="screen-body">
      <!-- ── 左侧：条件构建器 ── -->
      <aside class="sidebar">
        <div class="sidebar-inner">

          <div class="cond-section">
            <div class="cond-title">基础指标</div>

            <div class="cond-row">
              <label class="cond-label">涨跌幅区间（%）</label>
              <div class="range-inputs">
                <input v-model.number="params.change_pct_min" type="number" placeholder="最小" class="cond-input" step="0.1" />
                <span class="range-sep">~</span>
                <input v-model.number="params.change_pct_max" type="number" placeholder="最大" class="cond-input" step="0.1" />
              </div>
            </div>

            <div class="cond-row">
              <label class="cond-label">成交量区间（手）</label>
              <div class="range-inputs">
                <input v-model.number="params.volume_min" type="number" placeholder="最小" class="cond-input" />
                <span class="range-sep">~</span>
                <input v-model.number="params.volume_max" type="number" placeholder="最大" class="cond-input" />
              </div>
            </div>

            <div class="cond-row">
              <label class="cond-label">行业板块</label>
              <input v-model="params.industry" type="text" placeholder="如：银行、半导体" class="cond-input" />
            </div>

            <div class="cond-row">
              <label class="cond-label">市盈率（PE）上限</label>
              <input v-model.number="params.pe_max" type="number" placeholder="不限制" class="cond-input" />
            </div>

            <div class="cond-row">
              <label class="cond-label">市净率（PB）上限</label>
              <input v-model.number="params.pb_max" type="number" placeholder="不限制" class="cond-input" step="0.1" />
            </div>
          </div>

          <div class="cond-divider" />

          <div class="cond-section">
            <div class="cond-title">缠论信号</div>
            <div class="signal-grid">
              <label v-for="sig in signalOptions" :key="sig.value" class="signal-check" :class="{ 'is-buy': sig.buy, 'is-sell': !sig.buy }">
                <input type="checkbox" :value="sig.value" v-model="selectedSignals" />
                <span>{{ sig.label }}</span>
              </label>
            </div>
          </div>

          <div class="cond-divider" />

          <div class="cond-section">
            <div class="cond-title">MACD+SKDJ 共振</div>
            <label class="toggle-row">
              <input type="checkbox" v-model="params.dual_cross" />
              <span class="toggle-label">仅显示双金叉共振股票</span>
            </label>
          </div>

          <div class="cond-divider" />

          <div class="cond-section">
            <div class="cond-title">K线级别</div>
            <div class="level-btns">
              <button
                v-for="lvl in levelOptions"
                :key="lvl.value"
                class="level-btn"
                :class="{ active: params.level === lvl.value }"
                @click="params.level = lvl.value"
              >{{ lvl.label }}</button>
            </div>
          </div>

          <div class="cond-divider" />

          <div class="cond-section">
            <div class="cond-title">候选池</div>
            <div class="cond-row">
              <label class="cond-label">候选池大小</label>
              <div class="pool-btns">
                <button v-for="sz in poolSizes" :key="sz" class="pool-btn" :class="{ active: params.pool_size === sz }" @click="params.pool_size = sz">{{ sz }}</button>
              </div>
            </div>
          </div>

          <button v-if="loading" type="button" class="btn btn-ghost run-btn stop-screen-btn" @click="stopScreen">
            停止筛选
          </button>
          <template v-else>
            <div class="run-actions">
              <button type="button" class="btn btn-ghost run-btn" @click="resetFilters">重置条件</button>
              <button type="button" class="btn btn-ghost run-btn" @click="exportFiltersJson">导出条件 JSON</button>
              <button type="button" class="btn btn-primary run-btn" @click="runScreen">
                开始选股
              </button>
            </div>
          </template>

          <p v-if="loading" class="loading-hint">
            正在分析股票，请稍候…
            <template v-if="results.length > 0">（已命中 {{ results.length }} 只）</template>
          </p>
        </div>
      </aside>

      <!-- ── 右侧：结果区域 ── -->
      <main class="results-area">
        <!-- 结果标题栏 -->
        <div class="results-head" v-if="results.length > 0 || hasSearched">
          <span class="results-count">
            <template v-if="!loading">
              找到 <strong>{{ results.length }}</strong> 只符合条件的股票
            </template>
            <template v-else>分析中...</template>
          </span>
          <button v-if="results.length > 0" type="button" class="btn btn-ghost btn-sm" @click="exportResults">
            导出 CSV
          </button>
          <button v-if="results.length > 0" type="button" class="btn btn-ghost btn-sm" @click="clearResults">清除结果</button>
        </div>
        <p v-if="screenError && results.length > 0" class="partial-hint">{{ screenError }}</p>

        <!-- 进度（筛选进行中） -->
        <div v-if="loading" class="screen-progress-block">
          <p v-if="isRetrying && screenError" class="retry-hint">{{ screenError }}</p>
          <div class="progress-wrap">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: progressPct + '%' }" />
            </div>
            <span class="progress-text">
              正在分析 {{ progress.done }} / {{ progress.total }} 只股票...
            </span>
            <button type="button" class="btn btn-ghost btn-sm" @click="stopScreen">停止</button>
          </div>
        </div>

        <div v-if="loading && results.length === 0" class="skeleton-list">
          <div v-for="i in 8" :key="i" class="skeleton-row" />
        </div>

        <!-- 错误状态 -->
        <div v-else-if="!loading && screenError && results.length === 0" class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <p class="empty-title">选股失败</p>
          <p class="empty-sub">{{ screenError }}</p>
          <button class="btn btn-primary run-btn" @click="runScreen" style="margin-top:8px">重新选股</button>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!hasSearched" class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
            <circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.35-4.35"/>
          </svg>
          <p class="empty-title">设置条件后点击「开始选股」</p>
          <p class="empty-sub">系统将从今日涨幅榜候选池中筛选符合条件的股票</p>
        </div>

        <div v-else-if="!loading && results.length === 0 && hasSearched" class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
            <path d="M3 6h18M3 12h18M3 18h18"/>
          </svg>
          <p class="empty-title">没有符合条件的股票</p>
          <p class="empty-sub">尝试放宽条件或扩大候选池后重新筛选</p>
        </div>

        <!-- 结果表格（虚拟滚动，支持最多 200 条） -->
        <div v-else-if="results.length > 0" class="results-table-wrap">
          <div class="results-grid results-grid-header">
            <span class="sort-col" :class="{ active: sortKey === 'name' }" @click="setSort('name')">
              名称 <span class="sort-icon">{{ sortIcon('name') }}</span>
            </span>
            <span class="sort-col" :class="{ active: sortKey === 'code' }" @click="setSort('code')">
              代码 <span class="sort-icon">{{ sortIcon('code') }}</span>
            </span>
            <span class="sort-col" :class="{ active: sortKey === 'price' }" @click="setSort('price')">
              现价 <span class="sort-icon">{{ sortIcon('price') }}</span>
            </span>
            <span class="sort-col" :class="{ active: sortKey === 'change_pct' }" @click="setSort('change_pct')">
              涨跌幅 <span class="sort-icon">{{ sortIcon('change_pct') }}</span>
            </span>
            <span class="sort-col" :class="{ active: sortKey === 'industry' }" @click="setSort('industry')">
              行业 <span class="sort-icon">{{ sortIcon('industry') }}</span>
            </span>
            <span>缠论信号</span>
            <span class="sort-col" :class="{ active: sortKey === 'has_dual_cross' }" @click="setSort('has_dual_cross')">
              双金叉 <span class="sort-icon">{{ sortIcon('has_dual_cross') }}</span>
            </span>
            <span class="sort-col" :class="{ active: sortKey === 'trend' }" @click="setSort('trend')">
              趋势 <span class="sort-icon">{{ sortIcon('trend') }}</span>
            </span>
          </div>
          <div class="vscroll-wrap" v-bind="containerProps">
            <div class="vscroll-spacer" v-bind="wrapperProps">
              <div class="vscroll-inner" :style="{ transform: `translateY(${offsetY}px)` }">
                <div
                  v-for="stock in visibleItems"
                  :key="stock.code"
                  class="results-grid result-row"
                  :style="{ height: ROW_H + 'px' }"
                  @click="goToStock(stock.code)"
                  v-bind="stockLinkPrefetchHandlers(stock.code)"
                >
                  <span class="cell-name">{{ stock.name }}</span>
                  <span class="cell-code mono">{{ stock.code }}</span>
                  <span class="mono">{{ stock.price > 0 ? stock.price.toFixed(2) : '—' }}</span>
                  <span>
                    <span class="pct-badge" :class="stock.change_pct >= 0 ? 'pct-up' : 'pct-down'">
                      {{ stock.change_pct >= 0 ? '+' : '' }}{{ stock.change_pct.toFixed(2) }}%
                    </span>
                  </span>
                  <span class="cell-industry">{{ stock.industry || '—' }}</span>
                  <span>
                    <span v-if="stock.latest_signal" class="sig-badge" :class="signalClass(stock.latest_signal)">
                      {{ stock.latest_signal }}
                      <span class="sig-conf">{{ stock.latest_signal_conf != null ? (stock.latest_signal_conf * 100).toFixed(0) + '%' : '' }}</span>
                    </span>
                    <span v-else class="sig-none">—</span>
                  </span>
                  <span>
                    <span v-if="stock.has_dual_cross" class="cross-badge cross-yes">
                      是 <span class="cross-date">{{ stock.dual_cross_date }}</span>
                    </span>
                    <span v-else class="cross-badge cross-no">—</span>
                  </span>
                  <span class="cell-trend" :class="trendClass(stock.trend)">{{ stock.trend }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { usePersistedPcScreenFilters } from '../composables/usePersistedScreenFilters'
import { useRouter } from 'vue-router'
import { stockApi, type StockScreenResult } from '../api/stock'
import { useScreenStream } from '../composables/useScreenStream'
import { useVirtualScroll } from '../composables/useVirtualScroll'
import { downloadScreenResultsCsv } from '../utils/exportScreenCsv'
import { downloadPcScreenFiltersJson } from '../utils/exportScreenFiltersJson'
import { sortRows, type SortDir } from '../utils/sortRows'
import { stockLinkPrefetchHandlers } from '../utils/prefetchStock'

const router = useRouter()
const {
  loading,
  hasSearched,
  screenError,
  isRetrying,
  results,
  progress,
  runScreen: runScreenStream,
  stopScreen,
  clearResults: resetScreen,
} = useScreenStream()
const selectedSignals = ref<string[]>([])

type ScreenSortKey = 'change_pct' | 'name' | 'code' | 'price' | 'industry' | 'trend' | 'has_dual_cross'
const sortKey = ref<ScreenSortKey>('change_pct')
const sortDir = ref<SortDir>('desc')

function setSort(key: ScreenSortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'name' || key === 'code' || key === 'industry' ? 'asc' : 'desc'
  }
}

function sortIcon(key: ScreenSortKey): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? '▲' : '▼'
}

const sortedResults = computed(() =>
  sortRows<StockScreenResult>(results.value, sortKey.value, sortDir.value),
)

const ROW_H = 52
const { visibleItems, containerProps, wrapperProps, offsetY } = useVirtualScroll({
  items: sortedResults,
  itemHeight: ROW_H,
  overscan: 5,
  maxHeight: 560,
})
const progressPct = computed(() => {
  if (!progress.value.total) return 0
  return Math.round(progress.value.done / progress.value.total * 100)
})

const params = reactive({
  change_pct_min: null as number | null,
  change_pct_max: null as number | null,
  volume_min: null as number | null,
  volume_max: null as number | null,
  industry: '',
  pe_max: null as number | null,
  pb_max: null as number | null,
  dual_cross: false,
  level: 'daily',
  pool_size: 100,
})

const signalOptions = [
  { label: '一买', value: '一买', buy: true },
  { label: '二买', value: '二买', buy: true },
  { label: '三买', value: '三买', buy: true },
  { label: '一卖', value: '一卖', buy: false },
  { label: '二卖', value: '二卖', buy: false },
  { label: '三卖', value: '三卖', buy: false },
]

const levelOptions = [
  { label: '日线', value: 'daily' },
  { label: '周线', value: 'weekly' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

const poolSizes = [50, 100, 200, 500, 1000]

const { persistNow: persistScreenFilters } = usePersistedPcScreenFilters(params, selectedSignals)

function buildParams() {
  const p: Parameters<typeof stockApi.screenStocks>[0] = {
    level: params.level,
    pool_size: params.pool_size,
    dual_cross: params.dual_cross,
  }
  if (params.change_pct_min != null) p.change_pct_min = params.change_pct_min
  if (params.change_pct_max != null) p.change_pct_max = params.change_pct_max
  if (params.volume_min != null) p.volume_min = params.volume_min
  if (params.volume_max != null) p.volume_max = params.volume_max
  if (params.industry.trim()) p.industry = params.industry.trim()
  if (params.pe_max != null) p.pe_max = params.pe_max
  if (params.pb_max != null) p.pb_max = params.pb_max
  if (selectedSignals.value.length > 0) p.signals = selectedSignals.value.join(',')
  return p
}

async function runScreen() {
  persistScreenFilters()
  const p = buildParams()
  await runScreenStream({
    change_pct_min: p.change_pct_min,
    change_pct_max: p.change_pct_max,
    volume_min: p.volume_min,
    volume_max: p.volume_max,
    industry: p.industry,
    pe_max: p.pe_max,
    pb_max: p.pb_max,
    signals: p.signals,
    dual_cross: !!p.dual_cross,
    level: p.level ?? 'daily',
    pool_size: p.pool_size,
    max_results: 200,
  })
}

function clearResults() {
  resetScreen()
}

function resetFilters() {
  params.change_pct_min = null
  params.change_pct_max = null
  params.volume_min = null
  params.volume_max = null
  params.industry = ''
  params.pe_max = null
  params.pb_max = null
  params.dual_cross = false
  params.level = 'daily'
  params.pool_size = 100
  selectedSignals.value = []
  clearResults()
  persistScreenFilters()
}

function exportResults() {
  downloadScreenResultsCsv(sortedResults.value)
}

function exportFiltersJson() {
  downloadPcScreenFiltersJson({
    change_pct_min: params.change_pct_min,
    change_pct_max: params.change_pct_max,
    volume_min: params.volume_min,
    volume_max: params.volume_max,
    industry: params.industry,
    pe_max: params.pe_max,
    pb_max: params.pb_max,
    dual_cross: params.dual_cross,
    level: params.level,
    pool_size: params.pool_size,
    selectedSignals: [...selectedSignals.value],
  })
}

function goToStock(code: string) {
  const { href } = router.resolve({ path: `/stock/${code}` })
  window.open(href, '_blank', 'noopener,noreferrer')
}

function signalClass(sig: string): string {
  if (sig.includes('买')) return 'sig-buy'
  if (sig.includes('卖')) return 'sig-sell'
  return ''
}

function trendClass(trend: string): string {
  if (trend === '上涨') return 'trend-up'
  if (trend === '下跌') return 'trend-down'
  return 'trend-neutral'
}
</script>

<style scoped>
.screen-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
}

/* ── Nav ── */
.nav { border-bottom: 1px solid var(--border); background: var(--bg-primary); }
.nav-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
  height: 52px;
  display: flex;
  align-items: center;
  gap: 24px;
}
.nav-brand { font-family: 'Outfit', sans-serif; font-size: 1.05rem; font-weight: 700; color: var(--text-primary); text-decoration: none; letter-spacing: -0.01em; }
.nav-links { display: flex; gap: 4px; }
.nav-link { padding: 4px 12px; border-radius: 6px; font-size: 0.85rem; color: var(--text-secondary); text-decoration: none; transition: color 0.15s, background 0.15s; }
.nav-link:hover { color: var(--text-primary); background: var(--bg-hover); }
.nav-link.active { color: var(--accent-blue); font-weight: 600; }

/* ── Body ── */
.screen-body {
  flex: 1;
  display: grid;
  grid-template-columns: 260px 1fr;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
  gap: 24px;
  align-items: start;
}

/* ── Sidebar ── */
.sidebar { position: sticky; top: 24px; }
.sidebar-inner {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.cond-section { display: flex; flex-direction: column; gap: 10px; }
.cond-title { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 2px; }
.cond-row { display: flex; flex-direction: column; gap: 4px; }
.cond-label { font-size: 0.78rem; color: var(--text-secondary); }

.range-inputs { display: flex; align-items: center; gap: 6px; }
.range-sep { color: var(--text-muted); font-size: 0.8rem; }

.cond-input {
  flex: 1;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 0.8rem;
  padding: 5px 8px;
  font-family: 'Noto Sans SC', sans-serif;
  width: 100%;
  min-width: 0;
  transition: border-color 0.15s;
}
.cond-input:focus { outline: none; border-color: var(--accent-blue); }
.cond-input::placeholder { color: var(--text-muted); }

.cond-divider { height: 1px; background: var(--border); margin: 14px 0; }

/* Signal checkboxes */
.signal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.signal-check {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-primary);
  cursor: pointer;
  font-size: 0.8rem;
  transition: border-color 0.15s, background 0.15s;
  user-select: none;
}
.signal-check input { display: none; }
.signal-check.is-buy { color: var(--accent-green); }
.signal-check.is-sell { color: var(--accent-red); }
.signal-check:has(input:checked) {
  border-color: currentColor;
  background: rgba(255,255,255,0.04);
}
.signal-check.is-buy:has(input:checked) { background: rgba(34,197,94,0.08); }
.signal-check.is-sell:has(input:checked) { background: rgba(239,68,68,0.08); }

/* Toggle */
.toggle-row { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
.toggle-row input { accent-color: var(--accent-blue); width: 15px; height: 15px; }
.toggle-label { font-size: 0.8rem; color: var(--text-secondary); }

/* Level buttons */
.level-btns { display: flex; gap: 4px; flex-wrap: wrap; }
.level-btn {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
}
.level-btn:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.level-btn.active { background: rgba(56,189,248,0.12); border-color: var(--accent-blue); color: var(--accent-blue); font-weight: 600; }

/* Pool buttons */
.pool-btns { display: flex; gap: 4px; }
.pool-btn {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
}
.pool-btn:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.pool-btn.active { background: rgba(56,189,248,0.12); border-color: var(--accent-blue); color: var(--accent-blue); font-weight: 600; }

.run-btn {
  width: 100%;
  margin-top: 18px;
  padding: 10px;
  font-size: 0.9rem;
  font-weight: 700;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.run-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 18px;
}
.run-actions .run-btn { margin-top: 0; }
.run-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.loading-hint { font-size: 0.75rem; color: var(--text-muted); text-align: center; margin-top: 8px; }

/* ── Results area ── */
.results-area { min-height: 400px; display: flex; flex-direction: column; gap: 16px; }

.results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}
.results-count { font-size: 0.85rem; color: var(--text-secondary); }
.results-count strong { color: var(--text-primary); font-weight: 700; }

/* Skeleton */
.skeleton-list { display: flex; flex-direction: column; gap: 8px; }
.skeleton-row {
  height: 52px;
  background: var(--bg-card);
  border-radius: 8px;
  animation: shimmer 1.5s infinite;
  background: linear-gradient(90deg, var(--bg-card) 25%, rgba(255,255,255,0.04) 50%, var(--bg-card) 75%);
  background-size: 200% 100%;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

.screen-progress-block {
  margin-bottom: 12px;
}

.stop-screen-btn {
  margin-top: 4px;
}

.progress-wrap {
  margin-top: 12px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-primary);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-blue), #38bdf8);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.progress-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.retry-hint,
.partial-hint {
  margin: 0;
  padding: 8px 12px;
  font-size: 0.8rem;
  color: var(--accent-amber, #f59e0b);
  background: rgba(245, 158, 11, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(245, 158, 11, 0.25);
}

.partial-hint {
  margin-bottom: 8px;
}

/* Empty state */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 20px;
  text-align: center;
}
.empty-icon { color: var(--text-muted); }
.empty-title { font-size: 1rem; font-weight: 600; color: var(--text-secondary); }
.empty-sub { font-size: 0.82rem; color: var(--text-muted); max-width: 320px; }

/* Results grid（虚拟滚动） */
.results-table-wrap { display: flex; flex-direction: column; gap: 0; }
.results-grid {
  display: grid;
  grid-template-columns: minmax(64px, 1fr) 72px 72px 80px minmax(56px, 80px) 110px 110px 56px;
  align-items: center;
  padding: 0 12px;
  font-size: 0.82rem;
}
.results-grid-header {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--bg-secondary);
}
.sort-col {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
  border-radius: 4px;
  transition: color 0.15s;
}
.sort-col:hover,
.sort-col.active { color: var(--accent-blue); }
.sort-icon { font-size: 0.6rem; }
.vscroll-wrap {
  overflow-y: auto;
  max-height: 560px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.vscroll-spacer { position: relative; }
.vscroll-inner { width: 100%; }
.result-row {
  cursor: pointer;
  transition: background 0.12s;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.result-row:hover { background: var(--bg-hover); }

.cell-name { font-weight: 600; color: var(--text-primary); max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.cell-code { color: var(--accent-blue); font-size: 0.78rem; }
.cell-industry { color: var(--text-secondary); max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.cell-trend { font-weight: 600; }

.pct-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}
/* A 股习惯：涨红跌绿 */
.pct-up { background: rgba(239,68,68,0.12); color: var(--accent-red); }
.pct-down { background: rgba(34,197,94,0.12); color: var(--accent-green); }

.sig-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 600;
}
.sig-buy { background: rgba(34,197,94,0.1); color: var(--accent-green); }
.sig-sell { background: rgba(239,68,68,0.1); color: var(--accent-red); }
.sig-conf { margin-left: 4px; font-size: 0.7rem; opacity: 0.75; }
.sig-none { color: var(--text-muted); }

.cross-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 600;
}
.cross-yes { background: rgba(255,224,102,0.1); color: var(--accent-amber); }
.cross-no { color: var(--text-muted); }
.cross-date { margin-left: 4px; font-size: 0.7rem; font-weight: 400; opacity: 0.8; }

.trend-up { color: var(--accent-red); }
.trend-down { color: var(--accent-green); }
.trend-neutral { color: var(--text-secondary); }

/* Responsive */
@media (max-width: 768px) {
  .screen-body { grid-template-columns: 1fr; padding: 12px; }
  .sidebar { position: static; }
}
</style>
