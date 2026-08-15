<template>
  <div class="stock-view">
    <div v-if="showInitialLoading" class="page-loading">
      <div class="spinner" />
      <span>分析中，请稍候...</span>
    </div>

    <div v-else-if="error" class="page-error">
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="loadData(true)">重试</button>
    </div>

    <template v-else>
      <div class="stock-header card">
        <div class="sh-left">
          <div class="sh-name">{{ headerQuote?.name || stockCode }}</div>
          <div class="sh-code mono">{{ stockCode }}</div>
        </div>
        <div class="sh-right">
          <div class="sh-price mono">{{ headerQuote?.price != null ? headerQuote.price.toFixed(2) : '—' }}</div>
          <div class="sh-change mono" :class="changeClass">{{ changeText }}</div>
        </div>
      </div>

      <div class="chart-section">
        <MobileKLineChart
          :klines="store.klines"
          :bis="store.chanlunResult?.bis || []"
          :xiangs="store.chanlunResult?.xiangs || []"
          :zhongshus="store.chanlunResult?.zhongshus || []"
          :signals="store.chanlunResult?.signals || []"
          :ai-signal="store.aiSignal"
          :support-resistance="store.chanlunResult?.supportResistance || []"
          :indicators="store.indicators"
          :zoom-start="zoomStart"
          :zoom-end="zoomEnd"
          :loading="store.loadingChart"
          @zoom-change="onZoomChange"
        />
      </div>

      <div class="chart-controls">
        <div class="level-tabs">
          <button
            v-for="lv in levels"
            :key="lv.value"
            class="level-tab"
            :class="{ active: currentLevel === lv.value }"
            @click="changeLevel(lv.value)"
          >{{ lv.label }}</button>
        </div>
        <MobileIndicatorSelector />
        <button class="btn btn-ghost btn-sm" @click="showSheet = true">详情</button>
      </div>

      <MultiLevelTrendChips
        v-if="levelTrends.length"
        :trends="levelTrends"
        class="mobile-level-trends"
      />

      <div v-if="store.chanlunResult?.signals?.length" class="signals-preview">
        <div class="sp-head">
          <span class="sp-title">缠论信号</span>
          <span class="sp-count">{{ store.chanlunResult.signals.length }} 个</span>
          <button
            v-if="store.chanlunResult.signals.length > 3"
            class="expand-btn"
            @click="signalsExpanded = !signalsExpanded"
          >
            {{ signalsExpanded ? '收起' : `查看全部(${store.chanlunResult.signals.length})` }}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              :style="{ transform: signalsExpanded ? 'rotate(180deg)' : '' }">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>
        <div class="sp-list">
          <div
            v-for="(sig, idx) in store.chanlunResult.signals.slice(0, signalsExpanded ? undefined : 3)"
            :key="idx"
            class="sp-item"
            :class="signalBadgeClass(sig.type)"
          >
            <span class="sp-badge badge" :class="signalBadgeClass(sig.type)">{{ sig.type }}</span>
            <span class="sp-desc">{{ sig.description }}</span>
          </div>
        </div>
      </div>

      <div class="action-bar">
        <button
          v-if="store.aiSignal?.llm?.skipped"
          class="btn btn-ghost"
          :disabled="store.loadingAI"
          @click="onDeepAnalyze"
        >
          {{ store.loadingAI ? '分析中…' : 'LLM深度' }}
        </button>
        <button class="btn btn-ghost" @click="loadData(true)" :disabled="loadingAny">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          刷新
        </button>
        <button class="btn" :class="isWatching ? 'btn-danger' : 'btn-primary'" @click="toggleWatch">
          {{ isWatching ? '取消自选' : '+自选' }}
        </button>
      </div>
    </template>

    <MobileStockSheet
      v-if="sheetMounted"
      v-model="showSheet"
      :stock-code="stockCode"
      :quote="quote"
      :info="stockInfo"
      :chanlun-result="store.chanlunResult"
      :ai-signal="store.aiSignal"
      :loading-a-i="store.loadingAI"
      :level-trends="levelTrends"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, defineAsyncComponent } from 'vue'
import { useDebouncedCallback } from '@/composables/useDebounce'
import { useRoute } from 'vue-router'
import type { LevelOption } from '@/stores/chanlun'
import { useWatchlistStore } from '@/stores/watchlist'
import type { Quote } from '@/api/stock'
import toast from '@/composables/useToast'
import { useStockPage } from '@/composables/useStockPage'
import { useMultiLevelTrends } from '@/composables/useMultiLevelTrends'
import { MULTI_LEVEL_TREND_LEVELS } from '@/utils/prefetchStock'
import { getStockLevel, setStockLevel, resolveStockLevel } from '@/utils/stockLevelStorage'
import { useVisibilityRefresh } from '@/composables/useVisibilityRefresh'
import { API_CACHE_TTL } from '@/utils/apiCache'
import MultiLevelTrendChips from '@/components/Signal/MultiLevelTrendChips.vue'
import MobileKLineChart from '../components/MobileKLineChart.vue'
import MobileIndicatorSelector from '../components/MobileIndicatorSelector.vue'

const MobileStockSheet = defineAsyncComponent(
  () => import('../components/MobileStockSheet.vue'),
)

const route = useRoute()
const { store, quote, stockInfo, loadStock, changeLevel: changeLevelBase, refreshAIStrategy, refreshQuotes } = useStockPage()
const watchlistStore = useWatchlistStore()

const CHART_ZOOM_KEY = 'chanstock_m_chart_zoom_v1'

const zoomStart = ref(0)
const zoomEnd = ref(100)
const showSheet = ref(false)
const sheetMounted = ref(false)
const signalsExpanded = ref(false)

function restoreChartZoom() {
  try {
    const raw = localStorage.getItem(CHART_ZOOM_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as { start?: number; end?: number }
    if (typeof parsed.start === 'number' && typeof parsed.end === 'number') {
      zoomStart.value = parsed.start
      zoomEnd.value = parsed.end
    }
  } catch {
    /* ignore */
  }
}

watch(showSheet, (open) => {
  if (open) sheetMounted.value = true
})

const isWatching = computed(() =>
  watchlistStore.stocks.some(s => s.code === stockCode.value),
)

const onZoomChange = useDebouncedCallback((s: number, e: number) => {
  zoomStart.value = s
  zoomEnd.value = e
  try {
    localStorage.setItem(CHART_ZOOM_KEY, JSON.stringify({ start: s, end: e }))
  } catch {
    /* ignore */
  }
}, 80)

const stockCode = computed(() => route.params.code as string)
const { levelTrends } = useMultiLevelTrends(
  stockCode,
  MULTI_LEVEL_TREND_LEVELS,
  () => store.chanlunResult,
)
const currentLevel = computed(() => store.currentLevel)
const loadingAny = computed(() => store.loadingKline || store.loadingChanlun)
const showInitialLoading = computed(
  () => loadingAny.value && !store.klines.length && !store.chanlunResult,
)
const error = computed(() =>
  store.errorKline || store.errorChanlun
)

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

function _num(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const headerQuote = computed((): Quote | null => {
  const q = quote.value
  const s = stockInfo.value as Record<string, unknown> | null
  if (!q && !s) return null
  const price = _num(q?.price) ?? _num(s?.['现价'])
  if (price == null) return null
  const name = (q?.name != null && String(q.name).trim() !== '' ? String(q.name) : '') ||
    (s?.['名称'] != null ? String(s['名称']).trim() : '') || ''
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

function signalBadgeClass(type: string) {
  if (/买/i.test(type)) return 'badge-buy'
  if (/卖/i.test(type)) return 'badge-sell'
  return 'badge-wait'
}

async function changeLevel(level: LevelOption) {
  setStockLevel(stockCode.value, level)
  await changeLevelBase(stockCode.value, level)
}

async function loadData(force = false) {
  await loadStock(stockCode.value, currentLevel.value, undefined, undefined, { force })
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
  try {
    if (isWatching.value) {
      await watchlistStore.removeStock(stockCode.value)
      toast.info('已从自选股移除')
    } else {
      await watchlistStore.addStock(stockCode.value)
      toast.success('已添加到自选股')
    }
  } catch (e: unknown) {
    toast.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(() => {
  restoreChartZoom()
  const saved = resolveStockLevel(stockCode.value)
  if (saved) store.currentLevel = saved
  void watchlistStore.fetchWatchlist()
  loadData()
})

useVisibilityRefresh(
  () => refreshQuotes(stockCode.value),
  API_CACHE_TTL.quote,
)

watch(() => route.params.code, code => {
  const saved = resolveStockLevel(String(code || ''))
  if (saved) store.currentLevel = saved
  signalsExpanded.value = false
  loadData()
})
</script>

<style scoped>
.stock-view {
  padding: 12px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stock-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
}
.sh-left { display: flex; flex-direction: column; gap: 3px; }
.sh-name {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
}
.sh-code {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.sh-right { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }
.sh-price {
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1;
}
.sh-change {
  font-size: 0.9rem;
  font-weight: 600;
}

.chart-section {
  height: 380px;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
}

.chart-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.level-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px;
}

.level-tab {
  padding: 6px 10px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 500;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
  min-height: 32px;
}
.level-tab.active {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(52, 211, 153, 0.12) 100%);
  color: var(--accent-cyan);
  font-weight: 600;
}

.btn-sm {
  padding: 8px 12px;
  min-height: 36px;
  font-size: 0.8rem;
}

.mobile-level-trends {
  margin-bottom: 10px;
  padding: 0 2px;
}

.signals-preview {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sp-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.expand-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--accent-blue);
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.15s;
  margin-left: auto;
}
.expand-btn:active { background: var(--bg-hover); }
.expand-btn svg { transition: transform 0.2s; }
.sp-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-secondary);
}
.sp-count {
  font-size: 0.7rem;
  color: var(--text-muted);
}
.sp-list { display: flex; flex-direction: column; gap: 8px; }
.sp-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border);
}
.sp-badge {
  flex-shrink: 0;
  font-size: 0.72rem;
  padding: 2px 8px;
}
.sp-desc {
  font-size: 0.78rem;
  color: var(--text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.action-bar {
  display: flex;
  gap: 8px;
  padding-bottom: 8px;
}
.action-bar .btn {
  flex: 1;
}

.page-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 50vh;
  color: var(--text-secondary);
  font-size: 0.9rem;
}
.spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.page-error {
  text-align: center;
  padding: 60px 24px;
  color: var(--accent-red);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
</style>
