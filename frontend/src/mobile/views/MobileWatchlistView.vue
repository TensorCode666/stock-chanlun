<template>
  <PullRefresh :refreshing="refreshing" @refresh="handleRefresh">
  <div class="watchlist-view">
    <div class="page-head">
      <div class="ph-row">
        <h2 class="page-title">我的自选</h2>
        <span class="page-count">{{ store.stocks.length }} 支</span>
        <button class="refresh-btn" @click="store.fetchWatchlist()" :class="{ spinning: store.loading }">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
        </svg>
      </button>
      </div>
      <div v-if="store.stocks.length > 0" class="sort-bar">
        <button
          v-for="opt in sortOptions"
          :key="opt.key"
          type="button"
          class="sort-chip"
          :class="{ active: sortKey === opt.key }"
          @click="cycleSort(opt.key)"
        >{{ opt.label }}{{ sortKey === opt.key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : '' }}</button>
      </div>
    </div>

    <div v-if="store.loading && store.stocks.length === 0" class="page-loading">
      <div v-for="i in 5" :key="i" class="skeleton w-skel" />
    </div>

    <div v-else-if="store.error" class="page-error">
      <p>{{ store.error }}</p>
      <button class="btn btn-ghost" @click="store.fetchWatchlist()">重试</button>
    </div>

    <div v-else-if="store.stocks.length === 0" class="page-empty">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
        <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
        <path d="M12 6v6l4 2"/>
      </svg>
      <p>暂无自选股</p>
      <p class="empty-hint">在个股页面点击「+自选」添加</p>
    </div>

    <div v-else-if="enableVirtualScroll" class="stock-list vscroll-wrap" v-bind="containerProps">
      <div class="vscroll-spacer" v-bind="wrapperProps">
        <div class="vscroll-inner" :style="{ transform: `translateY(${offsetY}px)` }">
          <button
            v-for="s in displayStocks"
            :key="s.code"
            class="stock-row"
            :style="{ height: ROW_H + 'px' }"
            @click="go(`/m/stock/${s.code}`)"
            v-bind="stockLinkPrefetchHandlers(s.code)"
          >
            <div class="sr-left">
              <div class="sr-name">{{ s.name || s.code }}</div>
              <div class="sr-code-row">
                <span class="sr-code mono">{{ s.code }}</span>
                <span v-if="s.added_at" class="sr-added">{{ fmtAdded(s.added_at) }}</span>
              </div>
            </div>
            <div class="sr-center">
              <div class="sr-price mono">{{ s.price > 0 ? s.price.toFixed(2) : '—' }}</div>
              <div class="sr-vol">{{ fmtVol(s.volume) }}</div>
            </div>
            <div class="sr-right">
              <div
                class="sr-pct mono"
                :class="s.change_pct > 0 ? 'price-up' : s.change_pct < 0 ? 'price-down' : 'price-flat'"
              >{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</div>
              <button
                class="remove-btn"
                @click.stop="remove(s.code)"
                title="删除自选"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                </svg>
              </button>
            </div>
          </button>
        </div>
      </div>
    </div>

    <div v-else class="stock-list">
      <button
        v-for="s in displayStocks"
        :key="s.code"
        class="stock-row"
            @click="go(`/m/stock/${s.code}`)"
            v-bind="stockLinkPrefetchHandlers(s.code)"
      >
        <div class="sr-left">
          <div class="sr-name">{{ s.name || s.code }}</div>
          <div class="sr-code-row">
            <span class="sr-code mono">{{ s.code }}</span>
            <span v-if="s.added_at" class="sr-added">{{ fmtAdded(s.added_at) }}</span>
          </div>
        </div>
        <div class="sr-center">
          <div class="sr-price mono">{{ s.price > 0 ? s.price.toFixed(2) : '—' }}</div>
          <div class="sr-vol">{{ fmtVol(s.volume) }}</div>
        </div>
        <div class="sr-right">
          <div
            class="sr-pct mono"
            :class="s.change_pct > 0 ? 'price-up' : s.change_pct < 0 ? 'price-down' : 'price-flat'"
          >{{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</div>
          <button
            class="remove-btn"
            @click.stop="remove(s.code)"
            title="删除自选"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
            </svg>
          </button>
        </div>
      </button>
    </div>
  </div>
  </PullRefresh>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWatchlistStore } from '@/stores/watchlist'
import toast from '@/composables/useToast'
import PullRefresh from '@/mobile/components/PullRefresh.vue'
import type { Quote } from '@/api/stock'
import { useVirtualScroll } from '@/composables/useVirtualScroll'
import { useVisibilityRefresh } from '@/composables/useVisibilityRefresh'
import { stockLinkPrefetchHandlers } from '@/utils/prefetchStock'
import { sortRows, type SortDir } from '@/utils/sortRows'

const AUTO_REFRESH_INTERVAL = 2 * 60 * 1000

const router = useRouter()
const store = useWatchlistStore()
const refreshing = ref(false)

type WlSortKey = 'change_pct' | 'name' | 'added_at'
const sortKey = ref<WlSortKey>('change_pct')
const sortDir = ref<SortDir>('desc')
const sortOptions = [
  { key: 'change_pct' as const, label: '涨跌幅' },
  { key: 'name' as const, label: '名称' },
  { key: 'added_at' as const, label: '添加' },
]

function cycleSort(key: WlSortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'name' ? 'asc' : 'desc'
  }
}

const sortedStocks = computed(() =>
  sortRows<Quote>([...store.stocks], sortKey.value, sortDir.value),
)

const ROW_H = 72
const enableVirtualScroll = computed(() => sortedStocks.value.length > 30)
const {
  visibleItems,
  containerProps,
  wrapperProps,
  offsetY,
} = useVirtualScroll({
  items: sortedStocks,
  itemHeight: ROW_H,
  overscan: 4,
  maxHeight: 560,
})
const displayStocks = computed(() =>
  enableVirtualScroll.value ? visibleItems.value : sortedStocks.value,
)

function fmtVol(v?: number) {
  if (!v) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return String(v)
}

function fmtAdded(iso: string): string {
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${m}-${day}`
  } catch {
    return ''
  }
}

function go(path: string) {
  router.push(path)
}

async function remove(code: string) {
  try {
    await store.removeStock(code)
  } catch {
    // 回滚已在 store 处理
  }
  toast.info('已从自选股移除')
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await store.fetchWatchlist(true)
  } catch (e: any) {
    toast.error(e.message || '刷新失败，请检查网络')
  } finally {
    refreshing.value = false
  }
}

onMounted(() => {
  store.fetchWatchlist()
})

useVisibilityRefresh(async () => {
  await store.fetchWatchlist(false)
}, AUTO_REFRESH_INTERVAL)
</script>

<style scoped>
.watchlist-view {
  padding: 16px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ph-row {
  display: flex;
  align-items: center;
  gap: 8px;
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
}
.sort-chip.active {
  border-color: rgba(56, 189, 248, 0.45);
  color: var(--accent-cyan);
}
.page-title {
  font-size: 1rem;
  font-weight: 700;
}
.page-count {
  font-size: 0.78rem;
  color: var(--text-muted);
  flex: 1;
}

.refresh-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
}
.refresh-btn:active {
  color: var(--accent-blue);
  background: var(--bg-hover);
}
.refresh-btn.spinning svg {
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.page-loading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.w-skel {
  height: 64px;
  border-radius: 10px;
}

.page-error {
  text-align: center;
  padding: 40px 24px;
  color: var(--accent-red);
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.page-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 24px;
  color: var(--text-muted);
  text-align: center;
}
.empty-icon {
  color: var(--text-muted);
  margin-bottom: 8px;
}
.empty-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.stock-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stock-row {
  display: flex;
  align-items: center;
  gap: 12px;
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
.stock-row:active {
  border-color: var(--accent-blue);
  background: var(--bg-hover);
}

.sr-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.sr-name {
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sr-code {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.sr-code-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sr-added {
  font-size: 0.65rem;
  color: var(--text-muted);
  opacity: 0.7;
}

.sr-center {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  min-width: 72px;
}
.sr-price {
  font-size: 0.9rem;
  font-weight: 700;
}
.sr-vol {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.sr-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.sr-pct {
  font-size: 0.85rem;
  font-weight: 700;
}

.remove-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
}
.remove-btn:hover {
  color: var(--accent-red);
  background: rgba(239, 68, 68, 0.1);
}

.vscroll-wrap {
  max-height: 560px;
  overflow-y: auto;
}
.vscroll-spacer { position: relative; }
.vscroll-inner { width: 100%; }
</style>
