<template>
  <div class="home-view">
    <!-- 加载骨架 -->
    <div v-if="allLoading" class="page-loading">
      <div v-for="i in 4" :key="i" class="skeleton sec-skel" />
    </div>

    <template v-else>
      <!-- 主要指数 -->
      <section class="sec-indices">
        <div class="sec-head">
          <span class="sec-title">大盘指数</span>
        </div>
        <div class="indices-scroll">
          <div
            v-for="(ix, key) in marketData.indices"
            :key="key"
            class="idx-card"
            :class="ix.change_pct >= 0 ? 'card-up' : 'card-down'"
            @click="go(`/m/stock/${ix.code}`)"
            v-bind="stockLinkPrefetchHandlers(ix.code)"
          >
            <div class="idx-top">
              <span class="idx-name">{{ ix.name }}</span>
              <span class="idx-pct mono"
                :class="ix.change_pct >= 0 ? 'price-up' : 'price-down'"
              >{{ ix.change_pct >= 0 ? '+' : '' }}{{ ix.change_pct.toFixed(2) }}%</span>
            </div>
            <div class="idx-price mono">{{ ix.price > 0 ? ix.price.toFixed(2) : '—' }}</div>
          </div>
        </div>
      </section>

      <!-- 涨跌家数 -->
      <section v-if="breadthTotal > 0" class="sec-breadth card">
        <div class="breadth-inner">
          <div class="bc-block">
            <span class="bc-num price-up">{{ marketData.market_breadth.advancers }}</span>
            <span class="bc-lbl">上涨</span>
          </div>
          <div class="bc-divider" />
          <div class="bc-block">
            <span class="bc-num bc-flat">{{ marketData.market_breadth.unchanged }}</span>
            <span class="bc-lbl">平盘</span>
          </div>
          <div class="bc-divider" />
          <div class="bc-block">
            <span class="bc-num price-down">{{ marketData.market_breadth.decliners }}</span>
            <span class="bc-lbl">下跌</span>
          </div>
        </div>
        <div class="breadth-bar">
          <span class="bb-up" :style="{ flex: Math.max(marketData.market_breadth.advancers, 1) }" />
          <span class="bb-flat" :style="{ flex: Math.max(marketData.market_breadth.unchanged, 1) }" />
          <span class="bb-down" :style="{ flex: Math.max(marketData.market_breadth.decliners, 1) }" />
        </div>
      </section>

      <!-- 热门板块 -->
      <section v-if="hotSectors.length" class="sec-sectors">
        <div class="sec-head">
          <span class="sec-title">热门板块</span>
          <span class="sec-sub">按涨幅排序</span>
        </div>
        <div class="sectors-scroll">
          <div
            v-for="(s, idx) in hotSectors"
            :key="'hs-' + idx"
            class="sector-chip"
            :class="s.change_pct >= 0 ? 'chip-up' : 'chip-down'"
            @click="go(`/m/sector/${encodeURIComponent(s.name)}`)"
            v-bind="sectorLinkPrefetchHandlers(s.name)"
          >
            <span class="chip-name">{{ s.name }}</span>
            <span class="chip-pct mono"
              :class="s.change_pct >= 0 ? 'price-up' : 'price-down'"
            >{{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</span>
          </div>
        </div>
      </section>

      <!-- 热门股票 -->
      <section class="sec-hot">
        <div class="sec-head">
          <span class="sec-title">人气股票</span>
          <span class="sec-sub">点击查看K线</span>
        </div>
        <div v-if="hotLoading" class="hot-grid">
          <div v-for="i in 8" :key="i" class="skeleton hot-skel" />
        </div>
        <div v-else-if="hotStocks.length > 0" class="hot-grid">
          <button
            v-for="s in hotStocks"
            :key="s.code"
            class="hot-card"
            @click="go(`/m/stock/${s.code}`)"
            v-bind="stockLinkPrefetchHandlers(s.code)"
          >
            <div class="hot-left">
              <span class="hot-rank">{{ s.rank }}</span>
              <div class="hot-info">
                <span class="hot-name">{{ s.name || '—' }}</span>
                <span class="hot-code mono">{{ s.code }}</span>
              </div>
            </div>
            <span
              v-if="s.change_pct != null"
              class="hot-pct mono"
              :class="s.change_pct >= 0 ? 'price-up' : 'price-down'"
            >{{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</span>
          </button>
        </div>
        <p v-else-if="hotError" class="sec-err">{{ hotError }}</p>
      </section>

      <!-- 财经新闻 -->
      <section class="sec-news">
        <div class="sec-head">
          <span class="sec-title">财经要闻</span>
        </div>
        <div v-if="newsLoading" class="news-list">
          <div v-for="i in 4" :key="i" class="skeleton news-skel" />
        </div>
        <div v-else-if="newsList.length > 0" class="news-list">
          <a
            v-for="item in newsList"
            :key="item.url"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="news-item"
          >
            <div class="news-meta">
              <span class="news-source">{{ item.source }}</span>
              <span class="news-time">{{ formatTime(item.time) }}</span>
            </div>
            <p class="news-title">{{ item.title }}</p>
          </a>
        </div>
        <p v-else class="sec-hint">暂无新闻</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHomeDashboard, formatNewsTime } from '@/composables/useHomeDashboard'
import { useVisibilityRefresh } from '@/composables/useVisibilityRefresh'
import { stockLinkPrefetchHandlers, sectorLinkPrefetchHandlers } from '@/utils/prefetchStock'

const router = useRouter()
const AUTO_REFRESH_INTERVAL = 5 * 60 * 1000

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
  allLoading,
  refreshAll,
} = useHomeDashboard(20, 10)

const formatTime = formatNewsTime

const breadthTotal = computed(() => {
  const b = marketData.value.market_breadth
  return b.advancers + b.decliners + b.unchanged
})
const hotSectors = computed(() => (marketData.value.sectors ?? []).slice(0, 16))

function go(path: string) {
  router.push(path)
}

useVisibilityRefresh(() => refreshAll(false), AUTO_REFRESH_INTERVAL)

onMounted(async () => {
  await refreshAll(false)
})
</script>

<style scoped>
.home-view {
  padding: 16px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sec-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.sec-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
}
.sec-sub {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.sec-err {
  font-size: 0.82rem;
  color: var(--accent-red);
  padding: 8px 0;
}
.sec-hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  padding: 8px 0;
}

.page-loading {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sec-skel { height: 80px; border-radius: 12px; }
.hot-skel { height: 56px; border-radius: 10px; }
.news-skel { height: 80px; border-radius: 10px; }

.indices-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 4px;
}
.indices-scroll::-webkit-scrollbar { display: none; }

.idx-card {
  flex-shrink: 0;
  width: 120px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 0.15s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.idx-card:active { opacity: 0.8; }
.card-up {
  border-left: 3px solid var(--accent-red);
  background: rgba(239, 68, 68, 0.04);
}
.card-down {
  border-left: 3px solid var(--accent-green);
  background: rgba(34, 197, 94, 0.04);
}
.idx-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}
.idx-name {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.idx-pct {
  font-size: 0.78rem;
  font-weight: 700;
  flex-shrink: 0;
}
.idx-price {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-secondary);
}

.sec-breadth { padding: 14px; }
.breadth-inner {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-bottom: 12px;
}
.bc-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.bc-num {
  font-size: 1.4rem;
  font-weight: 800;
  line-height: 1;
}
.bc-flat { color: var(--text-muted); }
.bc-lbl { font-size: 0.72rem; color: var(--text-muted); }
.bc-divider { width: 1px; height: 32px; background: var(--border); }
.breadth-bar {
  display: flex;
  height: 6px;
  border-radius: 4px;
  overflow: hidden;
  background: var(--bg-secondary);
}
.bb-up { background: var(--accent-red); min-width: 0; }
.bb-flat { background: var(--text-muted); opacity: 0.45; min-width: 0; }
.bb-down { background: var(--accent-green); min-width: 0; }

.sectors-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 4px;
}
.sectors-scroll::-webkit-scrollbar { display: none; }

.sector-chip {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 8px 12px;
  border-radius: 8px;
  min-width: 70px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.sector-chip:active { opacity: 0.75; }
.chip-up {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
}
.chip-up .chip-name { color: var(--text-primary); }
.chip-down {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
}
.chip-down .chip-name { color: var(--text-primary); }
.chip-name {
  font-size: 0.72rem;
  font-weight: 600;
  text-align: center;
  white-space: nowrap;
}
.chip-pct {
  font-size: 0.72rem;
  font-weight: 700;
}

.hot-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.hot-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  color: inherit;
  font: inherit;
  text-align: left;
  width: 100%;
  transition: border-color 0.15s, background 0.15s;
  min-height: 50px;
}
.hot-card:active {
  border-color: var(--accent-blue);
  background: var(--bg-hover);
}

.hot-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.hot-rank {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
  min-width: 16px;
}
.hot-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.hot-name {
  font-size: 0.82rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hot-code {
  font-size: 0.68rem;
  color: var(--accent-blue);
}
.hot-pct {
  font-size: 0.82rem;
  font-weight: 700;
  flex-shrink: 0;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.news-item {
  display: block;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, background 0.15s;
}
.news-item:active {
  border-color: var(--accent-blue);
  background: var(--bg-hover);
}
.news-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.news-source {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--accent-blue);
  background: rgba(56, 189, 248, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}
.news-time {
  font-size: 0.65rem;
  color: var(--text-muted);
}
.news-title {
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
