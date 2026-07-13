<template>
  <div class="screen-view">
    <div class="page-head">
      <h2 class="page-title">条件选股</h2>
    </div>

    <div class="filter-section">
      <div class="filter-row">
        <span class="filter-label">涨跌幅</span>
        <div class="filter-inputs">
          <input
            v-model.number="filters.change_pct_min"
            type="number"
            placeholder="-10"
            class="filter-input"
          />
          <span class="filter-sep">~</span>
          <input
            v-model.number="filters.change_pct_max"
            type="number"
            placeholder="10"
            class="filter-input"
          />
          <span class="filter-unit">%</span>
        </div>
      </div>

      <div class="filter-row">
        <span class="filter-label">成交量（万）</span>
        <div class="filter-inputs">
          <input
            v-model.number="filters.volume_min"
            type="number"
            placeholder="0"
            class="filter-input"
          />
          <span class="filter-sep">~</span>
          <input
            v-model.number="filters.volume_max"
            type="number"
            placeholder="∞"
            class="filter-input"
          />
        </div>
      </div>

      <div class="filter-row">
        <span class="filter-label">市盈率(PE)</span>
        <div class="filter-inputs">
          <input
            v-model.number="filters.pe_max"
            type="number"
            placeholder="≤50"
            class="filter-input"
          />
          <span class="filter-unit">倍</span>
        </div>
      </div>

      <div class="filter-row">
        <span class="filter-label">市净率(PB)</span>
        <div class="filter-inputs">
          <input
            v-model.number="filters.pb_max"
            type="number"
            placeholder="≤5"
            class="filter-input"
          />
          <span class="filter-unit">倍</span>
        </div>
      </div>

      <div class="filter-row">
        <span class="filter-label">缠论信号</span>
        <div class="filter-chips">
          <button
            v-for="sig in signalOptions"
            :key="sig.value"
            class="filter-chip"
            :class="{ active: filters.signals === sig.value }"
            @click="filters.signals = filters.signals === sig.value ? '' : sig.value"
          >{{ sig.label }}</button>
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn btn-ghost" @click="resetFilters">重置</button>
        <button type="button" class="btn btn-ghost" @click="exportFiltersJson">导出条件</button>
        <button v-if="screening" type="button" class="btn btn-ghost stop-screen-btn" @click="stopScreen">
          停止筛选
        </button>
        <button v-else type="button" class="btn btn-primary" @click="doScreen">
          开始筛选
        </button>
      </div>
    </div>

    <div v-if="screening" class="results-loading">
      <p v-if="isRetrying && screenError" class="retry-hint">{{ screenError }}</p>
      <div class="progress-wrap">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPct + '%' }" />
        </div>
        <span class="progress-text">{{ progressDone }} / {{ progressTotal }} 只</span>
      </div>
      <p v-if="results.length > 0" class="partial-hint">已命中 {{ results.length }} 只，可提前停止</p>
      <button type="button" class="btn btn-ghost btn-sm" @click="stopScreen">停止筛选</button>
      <div v-if="results.length === 0" class="spinner" />
      <span>{{ isRetrying ? '正在重连…' : results.length > 0 ? '持续筛选中…' : '筛选分析中...' }}</span>
    </div>

    <div v-else-if="screenError && results.length === 0" class="results-error">
      <p>{{ screenError }}</p>
      <button class="btn btn-ghost" @click="doScreen">重试</button>
    </div>

    <template v-if="results.length > 0">
      <p v-if="screenError" class="partial-hint">{{ screenError }}</p>
      <div class="results-head">
        <span class="results-count">共 <b>{{ total }}</b> 支符合条件的股票</span>
        <button type="button" class="btn btn-ghost btn-sm export-btn" @click="exportResults">导出</button>
      </div>
      <div class="sort-bar">
        <button
          v-for="opt in sortOptions"
          :key="opt.key"
          type="button"
          class="sort-chip"
          :class="{ active: sortKey === opt.key }"
          @click="cycleSort(opt.key)"
        >
          {{ opt.label }}{{ sortKey === opt.key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : '' }}
        </button>
      </div>
      <div
        class="results-list"
        :class="{ 'vscroll-wrap': enableVirtualScroll }"
        v-bind="enableVirtualScroll ? containerProps : {}"
      >
        <div v-if="enableVirtualScroll" class="vscroll-spacer" v-bind="wrapperProps">
          <div class="vscroll-inner" :style="{ transform: `translateY(${offsetY}px)` }">
            <button
              v-for="s in displayItems"
              :key="s.code"
              class="result-row"
              :style="{ height: ROW_H + 'px' }"
              @click="go(`/m/stock/${s.code}`)"
              v-bind="stockLinkPrefetchHandlers(s.code)"
            >
              <div class="rr-left">
                <div class="rr-name">{{ s.name }}</div>
                <div class="rr-meta">
                  <span class="rr-code mono">{{ s.code }}</span>
                  <span v-if="s.industry" class="rr-industry">{{ s.industry }}</span>
                </div>
              </div>
              <div class="rr-center">
                <div class="rr-price mono">{{ s.price > 0 ? s.price.toFixed(2) : '—' }}</div>
                <div class="rr-vol">{{ fmtVol(s.volume) }}</div>
              </div>
              <div class="rr-right">
                <div
                  class="rr-pct mono"
                  :class="s.change_pct > 0 ? 'price-up' : s.change_pct < 0 ? 'price-down' : 'price-flat'"
                >{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</div>
                <span v-if="s.latest_signal" class="rr-signal badge" :class="signalBadgeClass(s.latest_signal)">
                  {{ s.latest_signal }}
                </span>
              </div>
            </button>
          </div>
        </div>
        <template v-else>
          <button
            v-for="s in displayItems"
            :key="s.code"
            class="result-row"
            @click="go(`/m/stock/${s.code}`)"
            v-bind="stockLinkPrefetchHandlers(s.code)"
          >
            <div class="rr-left">
              <div class="rr-name">{{ s.name }}</div>
              <div class="rr-meta">
                <span class="rr-code mono">{{ s.code }}</span>
                <span v-if="s.industry" class="rr-industry">{{ s.industry }}</span>
              </div>
            </div>
            <div class="rr-center">
              <div class="rr-price mono">{{ s.price > 0 ? s.price.toFixed(2) : '—' }}</div>
              <div class="rr-vol">{{ fmtVol(s.volume) }}</div>
            </div>
            <div class="rr-right">
              <div
                class="rr-pct mono"
                :class="s.change_pct > 0 ? 'price-up' : s.change_pct < 0 ? 'price-down' : 'price-flat'"
              >{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</div>
              <span v-if="s.latest_signal" class="rr-signal badge" :class="signalBadgeClass(s.latest_signal)">
                {{ s.latest_signal }}
              </span>
            </div>
          </button>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { StockScreenResult } from '@/api/stock'
import { usePersistedMobileScreenFilters } from '@/composables/usePersistedScreenFilters'
import { useScreenStream } from '@/composables/useScreenStream'
import { useVirtualScroll } from '@/composables/useVirtualScroll'
import { downloadScreenResultsCsv } from '@/utils/exportScreenCsv'
import { downloadMobileScreenFiltersJson } from '@/utils/exportScreenFiltersJson'
import { sortRows, type SortDir } from '@/utils/sortRows'
import { stockLinkPrefetchHandlers } from '@/utils/prefetchStock'

const router = useRouter()
const {
  loading: screening,
  screenError,
  isRetrying,
  results,
  progress,
  runScreen: runScreenStream,
  stopScreen,
} = useScreenStream()

const signalOptions = [
  { label: '一买', value: '一买' },
  { label: '二买', value: '二买' },
  { label: '三买', value: '三买' },
  { label: '一卖', value: '一卖' },
  { label: '二卖', value: '二卖' },
  { label: '三卖', value: '三卖' },
]

const filters = reactive({
  change_pct_min: undefined as number | undefined,
  change_pct_max: undefined as number | undefined,
  volume_min: undefined as number | undefined,
  volume_max: undefined as number | undefined,
  pe_max: undefined as number | undefined,
  pb_max: undefined as number | undefined,
  signals: '',
})

const { persistNow: persistScreenFilters } = usePersistedMobileScreenFilters(filters)

type ScreenSortKey = 'change_pct' | 'name' | 'price'
const sortKey = ref<ScreenSortKey>('change_pct')
const sortDir = ref<SortDir>('desc')
const sortOptions = [
  { key: 'change_pct' as const, label: '涨跌幅' },
  { key: 'name' as const, label: '名称' },
  { key: 'price' as const, label: '现价' },
]

function cycleSort(key: ScreenSortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'name' ? 'asc' : 'desc'
  }
}

const sortedResults = computed(() =>
  sortRows<StockScreenResult>(results.value, sortKey.value, sortDir.value),
)

const total = computed(() => results.value.length)
const progressDone = computed(() => progress.value.done)
const progressTotal = computed(() => progress.value.total)
const ROW_H = 68
const enableVirtualScroll = computed(() => sortedResults.value.length > 30)
const {
  visibleItems,
  containerProps,
  wrapperProps,
  offsetY,
} = useVirtualScroll({
  items: sortedResults,
  itemHeight: ROW_H,
  overscan: 4,
  maxHeight: 480,
})
const displayItems = computed(() =>
  enableVirtualScroll.value ? visibleItems.value : sortedResults.value,
)
const progressPct = computed(() => {
  if (!progressTotal.value) return 0
  return Math.round(progressDone.value / progressTotal.value * 100)
})

function resetFilters() {
  filters.change_pct_min = undefined
  filters.change_pct_max = undefined
  filters.volume_min = undefined
  filters.volume_max = undefined
  filters.pe_max = undefined
  filters.pb_max = undefined
  filters.signals = ''
  results.value = []
  persistScreenFilters()
}

async function doScreen() {
  persistScreenFilters()
  await runScreenStream({
    change_pct_min: filters.change_pct_min,
    change_pct_max: filters.change_pct_max,
    volume_min: filters.volume_min,
    volume_max: filters.volume_max,
    pe_max: filters.pe_max,
    pb_max: filters.pb_max,
    signals: filters.signals || undefined,
    level: 'daily',
    pool_size: 100,
    max_results: 200,
  })
}

function go(path: string) {
  router.push(path)
}

function exportResults() {
  downloadScreenResultsCsv(sortedResults.value)
}

function exportFiltersJson() {
  downloadMobileScreenFiltersJson({ ...filters })
}

function fmtVol(v?: number) {
  if (!v) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return String(v)
}

function signalBadgeClass(type: string) {
  if (/买/i.test(type)) return 'badge-buy'
  if (/卖/i.test(type)) return 'badge-sell'
  return 'badge-wait'
}
</script>

<style scoped>
.screen-view {
  padding: 16px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-head { margin-bottom: 4px; }
.page-title {
  font-size: 1rem;
  font-weight: 700;
}

.filter-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 88px;
  flex-shrink: 0;
}

.filter-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.filter-input {
  flex: 1;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  outline: none;
  min-height: 40px;
  transition: border-color 0.15s;
  -webkit-appearance: none;
}
.filter-input:focus { border-color: var(--accent-blue); }
.filter-input::placeholder { color: var(--text-muted); }

.filter-sep {
  color: var(--text-muted);
  font-size: 0.8rem;
  flex-shrink: 0;
}

.filter-unit {
  font-size: 0.8rem;
  color: var(--text-muted);
  flex-shrink: 0;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
}

.filter-chip {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  min-height: 36px;
}
.filter-chip.active {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(52, 211, 153, 0.12) 100%);
  border-color: rgba(56, 189, 248, 0.4);
  color: var(--accent-cyan);
}

.filter-actions {
  display: flex;
  gap: 8px;
  padding-top: 4px;
}
.filter-actions .btn {
  flex: 1;
}

.results-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.retry-hint,
.partial-hint {
  margin: 0;
  width: 100%;
  max-width: 300px;
  padding: 8px 10px;
  font-size: 0.78rem;
  text-align: center;
  color: var(--accent-amber, #f59e0b);
  background: rgba(245, 158, 11, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(245, 158, 11, 0.25);
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

.progress-wrap {
  width: 100%;
  max-width: 300px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--bg-secondary);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-blue), #38bdf8);
  border-radius: 2px;
  transition: width 0.3s ease;
}
.progress-text {
  font-size: 0.72rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.results-error {
  text-align: center;
  padding: 40px 24px;
  color: var(--accent-red);
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.sort-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.sort-chip {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
}
.sort-chip.active {
  border-color: rgba(56, 189, 248, 0.45);
  color: var(--accent-cyan);
  background: rgba(56, 189, 248, 0.1);
}
.results-count {
  font-size: 0.82rem;
  color: var(--text-muted);
}
.results-count b {
  color: var(--accent-cyan);
  font-weight: 700;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.vscroll-wrap {
  overflow-y: auto;
  max-height: 480px;
  gap: 0;
}
.vscroll-spacer { position: relative; width: 100%; }
.vscroll-inner { width: 100%; }
.vscroll-wrap .result-row { margin-bottom: 6px; }

.result-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  color: inherit;
  font: inherit;
  text-align: left;
  width: 100%;
  transition: border-color 0.15s, background 0.15s;
  min-height: 60px;
}
.result-row:active {
  border-color: var(--accent-blue);
  background: var(--bg-hover);
}

.rr-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.rr-name {
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rr-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.rr-code {
  font-size: 0.68rem;
  color: var(--accent-blue);
}
.rr-industry {
  font-size: 0.65rem;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 1px 6px;
  border-radius: 4px;
}

.rr-center {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  min-width: 64px;
}
.rr-price {
  font-size: 0.875rem;
  font-weight: 700;
}
.rr-vol {
  font-size: 0.62rem;
  color: var(--text-muted);
}

.rr-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 64px;
}
.rr-pct {
  font-size: 0.875rem;
  font-weight: 700;
}
.rr-signal {
  font-size: 0.65rem;
  padding: 2px 6px;
}
</style>
