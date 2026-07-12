<template>
  <header class="search-bar">
    <div class="search-inner">
      <div class="search-input-wrap">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          v-model="keyword"
          @keydown.enter="doSearch"
          placeholder="输入股票代码或名称... (按 / 快速搜索)"
          class="search-input"
          autocomplete="off"
          autocorrect="off"
          spellcheck="false"
          @input="onInput"
        />
        <button v-if="keyword" class="search-clear" @click="keyword = ''" aria-label="清除">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
        <button class="search-submit" @click="doSearch" :disabled="!keyword.trim()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 搜索历史 -->
    <div v-if="showHistory && history.length > 0 && !results.length && !searched" class="search-history">
      <div class="history-head">
        <span>最近搜索</span>
        <button class="clear-btn" @click="clearHistory">清除</button>
      </div>
      <div
        v-for="h in history"
        :key="h"
        class="history-item"
        @click="selectHistory(h)"
      >{{ h }}</div>
    </div>

    <!-- 搜索结果下拉 -->
    <div
      v-if="results.length > 0"
      class="search-results"
      :class="{ 'search-vscroll': enableSearchVirtual }"
      v-bind="enableSearchVirtual ? searchContainerProps : {}"
    >
      <div v-if="enableSearchVirtual" class="search-vscroll-spacer" v-bind="searchWrapperProps">
        <div class="search-vscroll-inner" :style="{ transform: `translateY(${searchOffsetY}px)` }">
          <button
            v-for="s in searchDisplay"
            :key="s.code"
            class="search-result-item"
            :style="{ height: SEARCH_ROW_H + 'px' }"
            v-bind="stockLinkPrefetchHandlers(s.code)"
            @click="select(s.code)"
          >
            <span class="sri-code mono">{{ s.code }}</span>
            <span class="sri-name">{{ s.name }}</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </button>
        </div>
      </div>
      <template v-else>
        <button
          v-for="s in searchDisplay"
          :key="s.code"
          class="search-result-item"
          v-bind="stockLinkPrefetchHandlers(s.code)"
          @click="select(s.code)"
        >
          <span class="sri-code mono">{{ s.code }}</span>
          <span class="sri-name">{{ s.name }}</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m9 18 6-6-6-6"/>
          </svg>
        </button>
      </template>
    </div>
    <!-- 搜索中 -->
    <div v-if="searching" class="search-loading">
      <div class="mini-spinner" />
      <span>搜索中...</span>
    </div>
    <div v-else-if="searched && results.length === 0 && searchErrorCode !== 'error'" class="search-empty">
      未找到「{{ keyword }}」相关股票
    </div>
    <div v-else-if="searchErrorCode === 'error'" class="search-empty">
      搜索失败，请稍后重试
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useDebouncedStockSearch } from '@/composables/useDebouncedStockSearch'
import { useVirtualScroll } from '@/composables/useVirtualScroll'
import { onStockLinkTouch, stockLinkPrefetchHandlers } from '@/utils/prefetchStock'

const emit = defineEmits<{ search: [code: string] }>()

const keyword = ref('')
const searched = ref(false)
const history = ref<string[]>(JSON.parse(localStorage.getItem('m_search_history') || '[]'))
const showHistory = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const {
  results,
  loading: searching,
  errorCode: searchErrorCode,
  runQuery,
  searchImmediate,
  clear: clearSearch,
} = useDebouncedStockSearch(300)

const SEARCH_ROW_H = 44
const enableSearchVirtual = computed(() => results.value.length > 20)
const {
  visibleItems: searchVisible,
  containerProps: searchContainerProps,
  wrapperProps: searchWrapperProps,
  offsetY: searchOffsetY,
} = useVirtualScroll({
  items: results,
  itemHeight: SEARCH_ROW_H,
  overscan: 3,
  maxHeight: 280,
})
const searchDisplay = computed(() =>
  enableSearchVirtual.value ? searchVisible.value : results.value,
)

function focus() {
  const input = document.querySelector('.search-input') as HTMLInputElement
  input?.focus()
}

defineExpose({ focus })

function onInput() {
  searched.value = false
  const q = keyword.value.trim()
  if (!q) {
    clearSearch()
    showHistory.value = true
    return
  }
  showHistory.value = false
  if (q.length >= 2) runQuery(keyword.value)
  else clearSearch()
}

watch(keyword, (val) => {
  if (!val.trim()) {
    clearSearch()
    searched.value = false
  }
})

async function doSearch() {
  if (!keyword.value.trim()) return
  saveHistory(keyword.value.trim())
  searched.value = false
  showHistory.value = false
  await searchImmediate(keyword.value)
  searched.value = true
}

function select(code: string) {
  onStockLinkTouch(code)
  saveHistory(code)
  results.value = []
  keyword.value = ''
  searched.value = false
  emit('search', code)
}

function saveHistory(q: string) {
  const q2 = q.trim()
  if (!q2) return
  const h = history.value.filter(x => x !== q2)
  h.unshift(q2)
  history.value = h.slice(0, 10)
  localStorage.setItem('m_search_history', JSON.stringify(history.value))
}

function clearHistory() {
  history.value = []
  localStorage.removeItem('m_search_history')
}

function selectHistory(q: string) {
  keyword.value = q
  showHistory.value = false
  doSearch()
}

// 全局快捷键：按 / 聚焦搜索框
function handleGlobalKey(e: KeyboardEvent) {
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') {
    return
  }
  if (e.key === '/') {
    e.preventDefault()
    const input = document.querySelector('.search-input') as HTMLInputElement
    input?.focus()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKey)
})
</script>

<style scoped>
.search-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: linear-gradient(180deg, rgba(11, 15, 20, 0.95) 0%, rgba(11, 15, 20, 0.88) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top, 0px));
}

.search-inner {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-input-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0 12px;
  height: 40px;
  transition: border-color 0.15s;
}

.search-input-wrap:focus-within {
  border-color: var(--accent-blue);
}

.search-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}

.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-family: var(--font-sans);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-clear {
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

.search-clear:hover {
  color: var(--text-primary);
}

.search-submit {
  background: var(--accent-blue);
  border: none;
  color: #fff;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: background 0.15s;
  flex-shrink: 0;
}
.search-submit:hover { background: #38bdf8; }
.search-submit:disabled {
  background: var(--border);
  color: var(--text-muted);
  cursor: default;
}

/* 搜索结果 */
.search-results {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  max-height: 280px;
  overflow-y: auto;
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-top: none;
  border-radius: 0 0 12px 12px;
  box-shadow: var(--shadow-md);
  z-index: 99;
  scrollbar-width: thin;
}
.search-results.search-vscroll {
  overflow-y: auto;
}
.search-vscroll-spacer { position: relative; width: 100%; }
.search-vscroll-inner { width: 100%; }

.search-result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--divider);
  color: inherit;
  font: inherit;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background 0.12s;
  min-height: 44px;
}

.search-result-item:last-child {
  border-bottom: none;
}

.search-result-item:active {
  background: var(--bg-hover);
}

.sri-code {
  font-size: 0.85rem;
  color: var(--accent-blue);
  min-width: 80px;
}

.sri-name {
  flex: 1;
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-result-item svg {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-empty {
  padding: 14px 16px;
  font-size: 0.85rem;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-top: none;
  border-radius: 0 0 12px 12px;
}

.search-history {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-top: none;
  border-radius: 0 0 12px 12px;
  z-index: 99;
  box-shadow: var(--shadow-md);
  overflow: hidden;
}
.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px 4px;
  font-size: 0.68rem;
  color: var(--text-muted);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.clear-btn {
  background: none;
  border: none;
  color: var(--accent-blue);
  font-size: 0.68rem;
  cursor: pointer;
  padding: 0;
  text-transform: none;
  letter-spacing: 0;
}
.history-item {
  padding: 10px 14px;
  font-size: 0.85rem;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.12s;
  border-bottom: 1px solid var(--divider);
}
.history-item:last-child { border-bottom: none; }
.history-item:active { background: var(--bg-hover); }

.search-loading {
  padding: 14px 16px;
  font-size: 0.85rem;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-top: none;
  border-radius: 0 0 12px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mini-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
