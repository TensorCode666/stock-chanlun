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
        <div class="search-box">
          <div class="search-wrap" @click="searchInput?.focus()">
            <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              ref="searchInput"
              v-model="keyword"
              @keydown.enter="search"
              @keydown.escape="keyword = ''; results = []"
              @focus="onSearchFocus"
              @blur="onSearchBlur"
              placeholder="输入股票代码或名称... (按 / 快速聚焦)"
              class="search-input"
            />
            <button v-if="keyword" class="search-clear" @click="keyword = ''; results = []" aria-label="清除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
            <!-- 实时搜索下拉 -->
            <div v-if="liveResults.length > 0 && showHistory" class="live-dropdown">
              <div
                v-for="item in liveResults"
                :key="item.code"
                class="live-item"
                v-bind="stockLinkPrefetchHandlers(item.code)"
                @mousedown.prevent="keyword = item.code; search()"
              >
                <span class="live-name">{{ item.name }}</span>
                <span class="live-code mono">{{ item.code }}</span>
              </div>
            </div>
            <!-- 无结果提示 -->
            <div v-else-if="liveError === 'no-results' && showHistory && keyword.trim().length >= 2" class="live-no-results">
              未找到 "{{ keyword.trim() }}" 相关股票
            </div>
            <!-- 搜索历史 -->
            <div v-else-if="showHistory && searchHistory.length > 0 && !results.length" class="search-history">
              <div class="history-head">
                <span>最近搜索</span>
                <button class="clear-btn" @click.stop="clearHistory">清除</button>
              </div>
              <div
                v-for="h in searchHistory"
                :key="h"
                class="history-item"
                @mousedown.prevent="selectHistory(h)"
              >{{ h }}</div>
            </div>
          </div>
          <button class="btn btn-primary search-btn" @click="search" :disabled="searching || !keyword.trim()">
            <span v-if="searching">搜索中...</span>
            <span v-else>搜索</span>
          </button>
        </div>
        <!-- 快捷键提示按钮 -->
        <button class="kbd-hint-btn" @click="showKbdHint = !showKbdHint" title="快捷键">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="6" width="20" height="12" rx="2"/>
            <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M8 14h8"/>
          </svg>
        </button>
        <!-- 主题切换按钮 -->
        <button class="theme-btn" @click="toggleTheme" :title="isDark ? '切换亮色模式' : '切换暗色模式'">
          <!-- 暗色模式图标（太阳 = 亮色） -->
          <svg v-if="isDark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
          <!-- 亮色模式图标（月亮 = 暗色） -->
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </button>
        <!-- 快捷键提示浮层 -->
        <Transition name="kbd-fade">
          <div v-if="showKbdHint" class="kbd-hint-panel" @click.stop>
            <div class="kbd-panel-title">快捷键</div>
            <div class="kbd-list">
              <div class="kbd-item"><kbd>/</kbd><span>聚焦搜索框</span></div>
              <div class="kbd-item"><kbd>R</kbd><span>刷新当前页面</span></div>
              <div class="kbd-item"><kbd>1/5</kbd><span>切换 1分钟 / 5分钟</span></div>
              <div class="kbd-item"><kbd>D</kbd><span>切换日线</span></div>
              <div class="kbd-item"><kbd>W</kbd><span>切换周线</span></div>
              <div class="kbd-item"><kbd>M</kbd><span>切换月线</span></div>
            </div>
            <button class="kbd-close" @click="showKbdHint = false">知道了</button>
          </div>
        </Transition>
        <div v-if="searchError" class="search-error-inline">{{ searchError }}</div>
      </div>
    </nav>

    <!-- 搜索结果 -->
    <div v-if="results.length > 0" class="container">
      <div
        class="results"
        :class="{ 'search-vscroll': enableSearchVirtual }"
        v-bind="enableSearchVirtual ? searchContainerProps : {}"
      >
        <div v-if="enableSearchVirtual" class="search-vscroll-spacer" v-bind="searchWrapperProps">
          <div class="search-vscroll-inner" :style="{ transform: `translateY(${searchOffsetY}px)` }">
            <div
              v-for="stock in searchDisplay"
              :key="stock.code"
              class="stock-card card"
              :style="{ height: SEARCH_ROW_H + 'px' }"
              @click="goToStock(stock.code)"
              v-bind="stockLinkPrefetchHandlers(stock.code)"
            >
              <div class="stock-info">
                <span class="stock-code mono">{{ stock.code }}</span>
                <span class="stock-name">{{ stock.name }}</span>
              </div>
              <div class="stock-arrow">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9 18l6-6-6-6"/>
                </svg>
              </div>
            </div>
          </div>
        </div>
        <template v-else>
          <div
            v-for="stock in searchDisplay"
            :key="stock.code"
            class="stock-card card"
            @click="goToStock(stock.code)"
            v-bind="stockLinkPrefetchHandlers(stock.code)"
          >
            <div class="stock-info">
              <span class="stock-code mono">{{ stock.code }}</span>
              <span class="stock-name">{{ stock.name }}</span>
            </div>
            <div class="stock-arrow">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 18l6-6-6-6"/>
              </svg>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 首页 -->
    <div v-else class="container">

      <!-- ── 主体：大盘（左） + 热门股（右） ── -->
      <div class="main-grid">

        <!-- 左侧：今日大盘 -->
        <section class="panel panel-market">
          <div class="panel-head">
            <h2 class="panel-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
              今日大盘
            </h2>
            <span class="panel-sub">指数 · 涨跌家数 · 行业板块</span>
          </div>

          <!-- 加载骨架 -->
          <div v-if="marketLoading" class="skel-grid">
            <div v-for="i in 6" :key="i" class="skel-card" />
          </div>

          <div v-else-if="!marketError" class="market-body">
            <!-- 主要指数 -->
            <div class="indices-grid">
              <div
                v-for="(ix, key) in marketData.indices"
                :key="key"
                class="index-card"
                :class="ix.change_pct >= 0 ? 'card-up' : 'card-down'"
              >
                <div class="idx-top">
                  <span class="idx-name">{{ ix.name }}</span>
                  <span class="idx-pct mono"
                    :class="ix.change_pct >= 0 ? 'price-up' : 'price-down'"
                  >{{ ix.change_pct >= 0 ? '+' : '' }}{{ ix.change_pct.toFixed(2) }}%</span>
                </div>
                <div class="idx-bot">
                  <span class="idx-price mono">{{ ix.price > 0 ? ix.price.toFixed(2) : '—' }}</span>
                  <span class="idx-code mono">{{ ix.code }}</span>
                </div>
              </div>
            </div>

            <!-- 涨跌家数 -->
            <div class="breadth-card">
              <div class="breadth-label">A 股涨跌家数</div>
              <div class="breadth-counts">
                <div class="bc-item">
                  <span class="bc-num price-up">{{ marketData.market_breadth.advancers }}</span>
                  <span class="bc-tag">上涨</span>
                </div>
                <div class="bc-sep" />
                <div class="bc-item">
                  <span class="bc-num price-down">{{ marketData.market_breadth.decliners }}</span>
                  <span class="bc-tag">下跌</span>
                </div>
                <div class="bc-sep" />
                <div class="bc-item">
                  <span class="bc-num bc-flat">{{ marketData.market_breadth.unchanged }}</span>
                  <span class="bc-tag">平盘</span>
                </div>
              </div>
              <div v-if="breadthTotal > 0" class="breadth-bar">
                <span class="bb-up" :style="{ flex: Math.max(marketData.market_breadth.advancers, 1) }" />
                <span class="bb-flat" :style="{ flex: Math.max(marketData.market_breadth.unchanged, 1) }" />
                <span class="bb-down" :style="{ flex: Math.max(marketData.market_breadth.decliners, 1) }" />
              </div>
            </div>

            <!-- 当日热门板块（涨幅靠前，填补涨跌家数下方空白） -->
            <div class="hot-boards-block">
              <div class="hot-boards-head">
                <span class="hot-boards-title">当日热门板块</span>
                <span v-if="hotBoardsToday.length" class="hot-boards-hint">按行业涨幅排序</span>
              </div>
              <div v-if="hotBoardsToday.length" class="hot-boards-grid">
                <div
                  v-for="(b, idx) in hotBoardsToday"
                  :key="'hb-' + idx"
                  class="hot-board-cell"
                  :class="sectorPillClass(b.change_pct)"
                  @click="goSector(b.name)"
                  v-bind="sectorLinkPrefetchHandlers(b.name)"
                >
                  <span class="hb-name">{{ b.name }}</span>
                  <span class="hb-pct mono"
                    :class="b.change_pct >= 0 ? 'price-up' : 'price-down'"
                  >{{ b.change_pct >= 0 ? '+' : '' }}{{ b.change_pct.toFixed(2) }}%</span>
                </div>
              </div>
              <p v-else class="hot-boards-empty" @click="() => fetchMarket(true)" role="button" tabindex="0" @keydown.enter="() => fetchMarket(true)">
                暂无板块数据（点击重试）
              </p>
            </div>

            <!-- 行业板块横条 -->
            <div v-if="allSectors.length" class="sectors-block">
              <div class="sectors-head">
                <span>行业板块</span>
                <span class="sectors-count">共 {{ allSectors.length }} 个</span>
              </div>
              <div class="sectors-scroll">
                <div class="sectors-track">
                  <div
                    v-for="(s, idx) in allSectors"
                    :key="'s-' + idx"
                    class="sector-pill"
                    :class="sectorPillClass(s.change_pct)"
                    :title="`${s.name} ${s.change_pct >= 0 ? '+' : ''}${s.change_pct.toFixed(2)}%`"
                    @click="goSector(s.name)"
                    v-bind="sectorLinkPrefetchHandlers(s.name)"
                  >
                    <span class="pill-name">{{ s.name }}</span>
                    <span class="pill-pct mono"
                    >{{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 领涨 / 领跌 两侧 -->
            <div v-if="sectorTopList.length || sectorBottomList.length" class="sectors-split">
              <div v-if="sectorTopList.length">
                <div class="split-label split-label-up">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="18 15 12 9 6 15"/>
                  </svg>
                  领涨
                </div>
                <ul class="sectors-list">
                  <li v-for="(s, i) in sectorTopList" :key="'t-' + i" class="sector-item" @click="goSector(s.name)" v-bind="sectorLinkPrefetchHandlers(s.name)">
                    <span class="si-name">{{ s.name }}</span>
                    <span class="si-pct mono price-up">+{{ s.change_pct.toFixed(2) }}%</span>
                  </li>
                </ul>
              </div>
              <div v-if="sectorBottomList.length">
                <div class="split-label split-label-down">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                  领跌
                </div>
                <ul class="sectors-list">
                  <li v-for="(s, i) in sectorBottomList" :key="'b-' + i" class="sector-item" @click="goSector(s.name)" v-bind="sectorLinkPrefetchHandlers(s.name)">
                    <span class="si-name">{{ s.name }}</span>
                    <span class="si-pct mono"
                      :class="s.change_pct >= 0 ? 'price-up' : 'price-down'"
                    >{{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <p v-else class="panel-err">{{ marketError }}
            <button class="retry-btn" @click="() => fetchMarket(true)">重试</button>
          </p>
        </section>

        <!-- 右侧：热门股票 -->
        <section class="panel panel-hot">
          <div class="panel-head">
            <h2 class="panel-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>
              </svg>
              热门股票
            </h2>
            <span class="panel-sub">今日人气</span>
          </div>

          <div v-if="hotLoading" class="hot-skeleton">
            <div v-for="i in 10" :key="i" class="hot-skel-cell" />
          </div>

          <div v-else-if="hotStocks.length > 0" class="hot-list">
            <button
              v-for="s in hotStocks"
              :key="s.code"
              class="hot-card"
              @click="goToStock(s.code)"
              v-bind="stockLinkPrefetchHandlers(s.code)"
            >
              <span class="hot-rank">{{ s.rank }}</span>
              <div class="hot-info">
                <span class="hot-code mono">{{ s.code }}</span>
                <span class="hot-name">{{ s.name || '—' }}</span>
              </div>
              <span
                v-if="s.change_pct != null"
                class="hot-pct mono"
                :class="s.change_pct >= 0 ? 'price-up' : 'price-down'"
              >{{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</span>
            </button>
          </div>

          <p v-else-if="hotError" class="panel-err">{{ hotError }}
            <button class="retry-btn" @click="() => fetchHot(true)">重试</button>
          </p>
          <p v-else class="panel-hint">暂无数据</p>
        </section>

      </div><!-- /main-grid -->

      <!-- ── 底部：财经新闻 ── -->
      <section class="panel panel-news">
        <div class="panel-head">
          <h2 class="panel-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/>
              <path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>
            </svg>
            财经要闻
          </h2>
          <span class="panel-sub">市场资讯 · 5 分钟更新</span>
        </div>

        <div v-if="newsLoading" class="news-skeleton">
          <div v-for="i in 5" :key="i" class="news-skel-row" />
        </div>

        <div v-else-if="newsList.length > 0" class="news-grid">
          <a
            v-for="item in newsList"
            :key="item.url"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="news-card"
            title="点击在新标签页打开（将离开本应用）"
          >
            <div class="news-meta">
              <span class="news-source">{{ item.source }}</span>
              <span class="news-time">{{ formatTime(item.time) }}</span>
            </div>
            <p class="news-title">{{ item.title }}</p>
            <p v-if="item.digest" class="news-digest">{{ item.digest }}</p>
          </a>
        </div>

        <p v-else-if="newsError" class="panel-err">{{ newsError }}
          <button class="retry-btn" @click="() => fetchNews(true)">重试</button>
        </p>
        <p v-else class="panel-hint">暂无新闻</p>
      </section>

    </div><!-- /container -->

    <div v-if="searchError" class="error-msg">{{ searchError }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import toast from '../composables/useToast'
import { useHomeDashboard, formatNewsTime } from '../composables/useHomeDashboard'
import { useDebouncedStockSearch } from '../composables/useDebouncedStockSearch'
import { useVisibilityRefresh } from '../composables/useVisibilityRefresh'
import { useVirtualScroll } from '../composables/useVirtualScroll'
import { stockLinkPrefetchHandlers, sectorLinkPrefetchHandlers } from '../utils/prefetchStock'

const AUTO_REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes

const router = useRouter()
const keyword = ref('')
const results = ref<{ code: string; name: string }[]>([])
const searching = ref(false)
const searchError = ref('')
const searchHistory = ref<string[]>(JSON.parse(localStorage.getItem('search_history') ?? 'null') ?? [])
const showHistory = ref(false)
const showKbdHint = ref(false)
const isDark = ref(localStorage.getItem('theme') === 'dark')

function toggleTheme() {
  isDark.value = !isDark.value
  const theme = isDark.value ? 'dark' : 'light'
  localStorage.setItem('theme', theme)
  document.documentElement.setAttribute('data-theme', theme)
}
const blurTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const searchInput = ref<{ focus: () => void } | null>(null)
const MAX_RESULTS = 100
const maxResults = computed(() => Math.min(results.value.length, MAX_RESULTS))
const searchList = computed(() => results.value.slice(0, maxResults.value))
const SEARCH_ROW_H = 56
const enableSearchVirtual = computed(() => searchList.value.length > 40)
const {
  visibleItems: searchVisible,
  containerProps: searchContainerProps,
  wrapperProps: searchWrapperProps,
  offsetY: searchOffsetY,
} = useVirtualScroll({
  items: searchList,
  itemHeight: SEARCH_ROW_H,
  overscan: 4,
  maxHeight: 520,
})
const searchDisplay = computed(() =>
  enableSearchVirtual.value ? searchVisible.value : searchList.value,
)

function onSearchFocus() {
  showHistory.value = true
}

function onSearchBlur() {
  blurTimer.value = setTimeout(() => { showHistory.value = false }, 150)
}

function saveHistory(q: string) {
  const q2 = q.trim()
  if (!q2) return
  const h = searchHistory.value.filter(x => x !== q2)
  h.unshift(q2)
  searchHistory.value = h.slice(0, 10)
  localStorage.setItem('search_history', JSON.stringify(searchHistory.value))
}

function clearHistory() {
  searchHistory.value = []
  localStorage.removeItem('search_history')
}

const {
  results: liveResults,
  loading: liveLoading,
  errorCode: liveError,
  runQuery: liveSearch,
  searchImmediate,
  clear: clearLiveSearch,
} = useDebouncedStockSearch()

watch(keyword, (val) => {
  liveSearch(val)
  if (!val.trim()) {
    results.value = []
    searchError.value = ''
    clearLiveSearch()
  }
})

async function search() {
  if (!keyword.value.trim()) return
  saveHistory(keyword.value.trim())
  searching.value = true
  searchError.value = ''
  showHistory.value = false
  try {
    results.value = await searchImmediate(keyword.value)
    if (results.value.length === 0) {
      toast.info('未找到相关股票，请尝试其他关键词')
    }
  } catch (e: unknown) {
    searchError.value = e instanceof Error ? e.message : '搜索失败'
    toast.error('搜索失败，请重试')
  } finally {
    searching.value = false
  }
}

function selectHistory(q: string) {
  keyword.value = q
  search()
}

function goToStock(code: string) {
  router.push(`/stock/${code}`)
}

function goSector(name: string) {
  router.push(`/sector/${encodeURIComponent(name)}`)
}

const {
  marketData,
  marketLoading,
  marketError,
  hotStocks,
  hotLoading,
  hotError,
  newsList,
  newsLoading,
  newsError,
  fetchHot,
  fetchMarket,
  fetchNews,
  refreshAll,
} = useHomeDashboard(20, 8)

const formatTime = formatNewsTime

const sectorTopList = computed(() => marketData.value.sectors_top ?? [])
const sectorBottomList = computed(() => marketData.value.sectors_bottom ?? [])
const allSectors = computed(() => marketData.value.sectors ?? [])
const breadthTotal = computed(() => {
  const b = marketData.value.market_breadth
  return b.advancers + b.decliners + b.unchanged
})
/** 当日涨幅靠前的行业板块（后端已按涨跌幅降序） */
const hotBoardsToday = computed(() => (marketData.value.sectors ?? []).slice(0, 12))
function sectorPillClass(pct: number) {
  return pct > 0 ? 'pill-up' : pct < 0 ? 'pill-down' : 'pill-flat'
}

function handleGlobalKey(e: KeyboardEvent) {
  // 忽略输入框中按 / 的情况
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') {
    return
  }
  if (e.key === '/') {
    e.preventDefault()
    const input = document.querySelector('.search-input') as HTMLInputElement
    input?.focus()
  }
}

const { stop: stopAutoRefresh } = useVisibilityRefresh(
  () => refreshAll(false),
  AUTO_REFRESH_INTERVAL,
)

onMounted(async () => {
  await refreshAll(false)
  window.addEventListener('keydown', handleGlobalKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKey)
  stopAutoRefresh()
})
</script>

<style scoped>
.layout { min-height: 100vh; }

/* ── Nav ── */
.nav { border-bottom: 1px solid var(--border); }
.nav-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 24px;
  position: relative;
}
.search-box {
  margin-left: auto;
  display: flex;
  gap: 8px;
  max-width: 380px;
  flex: 1;
  position: relative;
  align-items: center;
}
.search-wrap { position: relative; flex: 1; display: flex; align-items: center; gap: 6px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 0 10px; transition: border-color 0.15s; }
.search-wrap:focus-within { border-color: var(--accent-blue); }
.search-icon { flex-shrink: 0; color: var(--text-muted); }
.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 0.875rem;
  padding: 7px 0;
}
.search-input:focus { border-color: var(--accent-blue); }

.search-clear {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: color 0.15s;
}
.search-clear:hover { color: var(--text-primary); }

.search-btn { flex-shrink: 0; min-width: 68px; }
.search-btn:disabled { opacity: 0.6; cursor: default; filter: none; }

.search-error-inline { position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 200; background: var(--bg-card); border: 1px solid var(--accent-red); border-radius: 8px; padding: 6px 12px; font-size: 0.8rem; color: var(--accent-red); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

.search-history {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  z-index: 100;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}

.live-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  max-height: 280px;
  overflow-y: auto;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  z-index: 200;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  scrollbar-width: thin;
}
.live-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 14px;
  cursor: pointer;
  transition: background 0.1s;
  border-bottom: 1px solid var(--divider);
}
.live-item:last-child { border-bottom: none; }
.live-item:hover { background: var(--bg-hover); }
.live-name { font-size: 0.875rem; font-weight: 600; color: var(--text-primary); }
.live-code { font-size: 0.75rem; color: var(--text-muted); }

.live-no-results {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  z-index: 200;
  padding: 10px 14px;
  font-size: 0.8rem;
  color: var(--text-muted);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px 4px;
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.clear-btn {
  background: none;
  border: none;
  color: var(--accent-blue);
  font-size: 0.7rem;
  cursor: pointer;
  padding: 0;
}
.history-item {
  padding: 8px 12px;
  font-size: 0.82rem;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.12s;
}
.history-item:hover { background: var(--bg-hover); }

/* ── 容器 ── */
.container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Panel ── */
.panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}
.panel-sub { font-size: 0.72rem; color: var(--text-secondary); }
.panel-err { font-size: 0.78rem; color: var(--accent-red); margin: 8px 0 0; }
.panel-hint { font-size: 0.78rem; color: var(--text-muted); margin: 8px 0 0; }
.retry-btn {
  margin-left: 10px;
  padding: 2px 10px;
  font-size: 0.72rem;
  color: var(--accent-blue);
  background: rgba(56, 189, 248, 0.10);
  border: 1px solid rgba(56, 189, 248, 0.3);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.retry-btn:hover { background: rgba(56, 189, 248, 0.20); }

/* ── 主体两栏：左大盘 + 右热门（等高、顶对齐） ── */
.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(380px, 0.65fr);
  gap: 16px;
  align-items: stretch;
}
@media (max-width: 900px) {
  .main-grid { grid-template-columns: 1fr; }
}

/* ── 大盘面板 ── */
.panel-market { display: flex; flex-direction: column; min-height: 0; }
.market-body { display: flex; flex-direction: column; gap: 14px; flex: 1; min-height: 0; }

/* 指数网格 */
.indices-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
@media (max-width: 640px) { .indices-grid { grid-template-columns: repeat(2, 1fr); } }
.index-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  transition: border-color 0.15s;
}
.card-up { border-left: 3px solid var(--accent-red); background: rgba(239,68,68,0.04); }
.card-down { border-left: 3px solid var(--accent-green); background: rgba(34,197,94,0.04); }
.idx-top { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 6px; }
.idx-name { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.idx-pct { font-size: 0.8rem; font-weight: 700; }
.idx-bot { display: flex; align-items: center; justify-content: space-between; font-size: 0.7rem; }
.idx-price { color: var(--text-secondary); }
.idx-code { color: var(--text-muted); }

/* 涨跌家数 */
.breadth-card {
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.breadth-label { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.breadth-counts { display: flex; align-items: center; justify-content: space-around; }
.bc-item { text-align: center; }
.bc-num { font-size: 1.3rem; font-weight: 800; display: block; line-height: 1; }
.bc-tag { font-size: 0.7rem; color: var(--text-secondary); }
.bc-flat { color: var(--text-muted); }
.bc-sep { width: 1px; height: 32px; background: var(--border); }
.breadth-bar {
  display: flex;
  height: 6px;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 12px;
  background: var(--bg-secondary);
}
.bb-up { background: var(--accent-red); min-width: 0; }
.bb-flat { background: var(--text-muted); opacity: 0.45; min-width: 0; }
.bb-down { background: var(--accent-green); min-width: 0; }

/* 当日热门板块网格 */
.hot-boards-block {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-secondary);
  flex: 1;
  min-height: 120px;
  display: flex;
  flex-direction: column;
}
.hot-boards-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.hot-boards-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.hot-boards-hint { font-size: 0.68rem; color: var(--text-secondary); }
.hot-boards-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
@media (max-width: 900px) {
  .hot-boards-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 520px) {
  .hot-boards-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.hot-board-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px 6px;
  border-radius: 8px;
  border: 1px solid var(--border);
  min-height: 56px;
  text-align: center;
}
.hot-board-cell.pill-up { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.2); }
.hot-board-cell.pill-down { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.2); }
.hot-board-cell.pill-flat { background: var(--bg-card); }
.hb-name {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.25;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hb-pct { font-size: 0.78rem; font-weight: 700; }
.hot-boards-empty {
  margin: 0;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.15s, color 0.15s;
  padding: 12px;
}
.hot-boards-empty:hover {
  background: var(--bg-hover);
  color: var(--accent-blue);
}

/* 全部行业板块 */
.sectors-block {}
.sectors-head { display: flex; align-items: center; gap: 8px; font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
.sectors-count { font-size: 0.7rem; color: var(--text-secondary); text-transform: none; }
.sectors-scroll { overflow-x: auto; scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
.sectors-scroll::-webkit-scrollbar { height: 4px; }
.sectors-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
.sectors-track { display: flex; gap: 6px; min-width: min-content; }
.sector-pill {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 6px 10px;
  border-radius: 8px;
  min-width: 62px;
  border: 1px solid transparent;
  cursor: default;
  transition: opacity 0.15s;
}
.sector-pill:hover { opacity: 0.75; }
.sector-pill, .sector-item, .hot-board-cell { cursor: pointer; }
.pill-up { background: rgba(239,68,68,0.10); border-color: rgba(239,68,68,0.22); }
.pill-up .pill-name, .pill-up .pill-pct { color: var(--accent-red); }
.pill-down { background: rgba(34,197,94,0.10); border-color: rgba(34,197,94,0.22); }
.pill-down .pill-name, .pill-down .pill-pct { color: var(--accent-green); }
.pill-flat { background: var(--bg-secondary); border-color: var(--border); }
.pill-flat .pill-name { color: var(--text-secondary); }
.pill-flat .pill-pct { color: var(--text-muted); }
.pill-name { font-size: 0.72rem; font-weight: 600; line-height: 1.2; text-align: center; }
.pill-pct { font-size: 0.7rem; font-weight: 600; }

/* 领涨领跌 */
.sectors-split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 480px) { .sectors-split { grid-template-columns: 1fr; } }
.split-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}
.split-label-up { color: var(--accent-red); }
.split-label-down { color: var(--accent-green); }
.sectors-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.sector-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 0.8rem; }
.si-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.si-pct { flex-shrink: 0; font-weight: 700; }

/* ── 热门股面板：双列网格，与左侧同排等高 ── */
.panel-hot {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.hot-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  flex: 1;
  align-content: start;
}
@media (max-width: 480px) {
  .hot-list { grid-template-columns: 1fr; }
}
.hot-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  color: inherit;
  font: inherit;
  text-align: left;
  width: 100%;
  min-width: 0;
  transition: border-color 0.15s, background 0.15s;
}
.hot-card:hover { border-color: var(--accent-blue); background: var(--bg-hover); }
.hot-rank {
  flex-shrink: 0;
  width: 1.15rem;
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--text-muted);
  text-align: center;
}
.hot-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.hot-code { font-size: 0.72rem; color: var(--accent-blue); }
.hot-name { font-size: 0.78rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hot-pct { flex-shrink: 0; font-size: 0.72rem; font-weight: 700; }

/* ── 新闻面板 ── */
.news-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
@media (max-width: 640px) { .news-grid { grid-template-columns: 1fr; } }
.news-card {
  display: block;
  padding: 14px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, background 0.15s;
}
.news-card:hover { border-color: var(--accent-blue); background: var(--bg-hover); }
.news-card::after {
  content: '';
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-left: 4px;
  vertical-align: middle;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpath d='M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'/%3E%3Cpolyline points='15 3 21 3 21 9'/%3E%3Cline x1='10' y1='14' x2='21' y2='3'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: center;
  opacity: 0.5;
}
.news-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.news-source { font-size: 0.68rem; font-weight: 700; color: var(--accent-blue); background: rgba(56,189,248,0.12); padding: 2px 6px; border-radius: 4px; }
.news-time { font-size: 0.68rem; color: var(--text-muted); }
.news-title { font-size: 0.875rem; font-weight: 600; line-height: 1.4; color: var(--text-primary); margin: 0 0 5px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.news-digest { font-size: 0.75rem; color: var(--text-secondary); line-height: 1.5; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

/* ── 骨架屏 ── */
.skel-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
@media (max-width: 640px) { .skel-grid { grid-template-columns: repeat(2, 1fr); } }
.skel-card {
  height: 56px;
  border-radius: 10px;
  background: linear-gradient(90deg, var(--bg-secondary) 25%, var(--border) 50%, var(--bg-secondary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.hot-skeleton {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  flex: 1;
  align-content: start;
}
@media (max-width: 480px) {
  .hot-skeleton { grid-template-columns: 1fr; }
}
.hot-skel-cell {
  height: 44px;
  border-radius: 10px;
  background: linear-gradient(90deg, var(--bg-secondary) 25%, var(--border) 50%, var(--bg-secondary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.news-skeleton { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.news-skel-row { height: 100px; border-radius: 10px; background: linear-gradient(90deg, var(--bg-secondary) 25%, var(--border) 50%, var(--bg-secondary) 75%); background-size: 200% 100%; animation: shimmer 1.2s infinite; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* ── 其他 ── */
.results {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 480px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.results.search-vscroll {
  max-height: 520px;
}
.search-vscroll-spacer { position: relative; width: 100%; }
.search-vscroll-inner { width: 100%; }
.results.search-vscroll .stock-card {
  margin-bottom: 8px;
  box-sizing: border-box;
}
.stock-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: all 0.15s;
}
.stock-card:hover { background: var(--bg-hover); border-color: var(--accent-blue); transform: translateX(4px); }
.stock-card:active { transform: translateX(2px) scale(0.99); }
.stock-info { display: flex; flex-direction: column; gap: 4px; }
.stock-code { font-size: 0.9rem; color: var(--accent-blue); }
.stock-name { font-size: 1.1rem; font-weight: 600; }
.stock-arrow { color: var(--text-muted); }
.error-msg { color: var(--accent-red); text-align: center; margin-top: 16px; }

/* ── 快捷键提示 ── */
.kbd-hint-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.kbd-hint-btn:hover {
  border-color: var(--accent-blue);
  color: var(--accent-blue);
  background: rgba(14, 165, 233, 0.08);
}

.kbd-hint-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  min-width: 240px;
  z-index: 300;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}
.kbd-panel-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 12px;
}
.kbd-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.kbd-item { display: flex; align-items: center; gap: 10px; font-size: 0.8rem; }
.kbd-item kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  padding: 2px 6px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 5px;
  font-size: 0.7rem;
  font-family: var(--font-mono);
  color: var(--text-primary);
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}
.kbd-item span { color: var(--text-secondary); }
.kbd-close {
  width: 100%;
  padding: 7px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}
.kbd-close:hover { border-color: var(--accent-blue); color: var(--accent-blue); }

.kbd-fade-enter-active, .kbd-fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.kbd-fade-enter-from, .kbd-fade-leave-to { opacity: 0; transform: translateY(-4px); }

/* ── 主题切换按钮 ── */
.theme-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.theme-btn:hover {
  border-color: var(--accent-amber);
  color: var(--accent-amber);
  background: rgba(245, 158, 11, 0.08);
}
</style>
