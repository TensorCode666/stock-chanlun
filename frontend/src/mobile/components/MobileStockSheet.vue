<template>
  <!-- 遮罩 -->
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="modelValue" class="sheet-overlay" @click.self="$emit('update:modelValue', false)">
        <div class="sheet-panel" :class="{ 'sheet-sheet--open': modelValue }">
          <!-- 拖拽条 -->
          <div class="sheet-handle" @click="$emit('update:modelValue', false)">
            <div class="handle-bar" />
          </div>

          <!-- Tab 切换 -->
          <div class="sheet-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="sheet-tab"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
              <span v-if="tab.key === 'comment' && commentCount > 0" class="tab-badge">{{ commentCount }}</span>
            </button>
          </div>

          <!-- Tab 内容 -->
          <div class="sheet-content">

            <!-- 行情数据 Tab -->
            <div v-if="activeTab === 'quote'" class="tab-quote">
              <div v-if="quote" class="quote-grid">
                <div class="q-item">
                  <span class="q-label">开盘</span>
                  <span class="q-value mono">{{ quote.open?.toFixed(2) || '—' }}</span>
                </div>
                <div class="q-item">
                  <span class="q-label">最高</span>
                  <span class="q-value mono price-up">{{ quote.high?.toFixed(2) || '—' }}</span>
                </div>
                <div class="q-item">
                  <span class="q-label">最低</span>
                  <span class="q-value mono price-down">{{ quote.low?.toFixed(2) || '—' }}</span>
                </div>
                <div class="q-item">
                  <span class="q-label">昨收</span>
                  <span class="q-value mono">{{ quote.prev_close?.toFixed(2) || '—' }}</span>
                </div>
                <div class="q-item">
                  <span class="q-label">成交量</span>
                  <span class="q-value mono">{{ fmtVol(quote.volume) || '—' }}</span>
                </div>
                <div class="q-item">
                  <span class="q-label">成交额</span>
                  <span class="q-value mono">{{ fmtAmt(quote.amount) || '—' }}</span>
                </div>
              </div>
              <p v-else class="tab-empty">暂无行情数据</p>

              <!-- 基本资料 -->
              <div v-if="info && infoRows.length" class="info-section">
                <div class="info-title">基本资料</div>
                <div class="info-grid">
                  <div v-for="row in infoRows" :key="row.key" class="info-cell">
                    <span class="info-label">{{ row.label }}</span>
                    <span class="info-value mono">{{ row.value }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 缠论信号 Tab -->
            <div v-if="activeTab === 'signals'" class="tab-signals">
              <MultiLevelTrendChips v-if="levelTrends.length" :trends="levelTrends" class="sheet-level-trends" />
              <!-- 走势判断 -->
              <div v-if="chanlunResult" class="trend-block">
                <div class="trend-badge" :class="trendClass">
                  {{ chanlunResult.trend || '—' }}
                </div>
                <p class="trend-desc">{{ chanlunResult.summary || '暂无数据' }}</p>
              </div>

              <!-- 信号列表 -->
              <div v-if="chanlunResult?.signals?.length" class="signals-list">
                <div
                  v-for="(sig, idx) in chanlunResult.signals"
                  :key="idx"
                  class="signal-card"
                  :class="signalBadgeClass(sig.type)"
                >
                  <div class="sig-head">
                    <span class="badge" :class="signalBadgeClass(sig.type)">{{ sig.type }}</span>
                    <span class="sig-level">{{ sig.level }}</span>
                    <span class="sig-time mono">{{ sig.datetime?.slice(0, 16) }}</span>
                  </div>
                  <p class="sig-desc">{{ sig.description }}</p>
                  <div class="sig-meta">
                    <span>置信度</span>
                    <div class="confidence-bar">
                      <div class="confidence-fill" :style="{ width: `${(sig.confidence ?? 0) * 100}%` }" />
                    </div>
                    <span class="mono">{{ ((sig.confidence ?? 0) * 100).toFixed(0) }}%</span>
                  </div>
                  <div v-if="sig.stop_loss || sig.take_profit" class="sig-extra">
                    <span v-if="sig.stop_loss">止损: <b class="mono">{{ sig.stop_loss.toFixed(2) }}</b></span>
                    <span v-if="sig.take_profit">止盈: <b class="mono">{{ sig.take_profit.toFixed(2) }}</b></span>
                  </div>
                </div>
              </div>
              <p v-else class="tab-empty">暂无缠论信号</p>
            </div>

            <!-- AI策略 Tab -->
            <div v-if="activeTab === 'ai'" class="tab-ai">
              <MobileAIChat v-if="modelValue" :stock-code="stockCode" />
            </div>

            <!-- 笔记 Tab -->
            <div v-if="activeTab === 'comment'" class="tab-comment">
              <MobileCommentSection v-if="modelValue" :stock-code="stockCode" />
            </div>

          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, defineAsyncComponent } from 'vue'
import type { Quote, StockInfoFields, Signal, AISignal } from '@/api/stock'
import { useCommentStore } from '@/stores/comment'
import { useVolumeFormatter } from '@/composables/useFormatters'
import type { LevelTrendChip } from '@/composables/useMultiLevelTrends'
import MultiLevelTrendChips from '@/components/Signal/MultiLevelTrendChips.vue'

const MobileCommentSection = defineAsyncComponent(
  () => import('./MobileCommentSection.vue'),
)
const MobileAIChat = defineAsyncComponent(() => import('./MobileAIChat.vue'))

const props = defineProps<{
  modelValue: boolean
  stockCode: string
  quote: Quote | null
  info: StockInfoFields | null
  chanlunResult: {
    trend: string
    summary: string
    signals: Signal[]
  } | null
  aiSignal: AISignal | null
  levelTrends: LevelTrendChip[]
}>()

defineEmits<{
  'update:modelValue': [val: boolean]
}>()

const commentStore = useCommentStore()
const { formatVolume, formatAmount } = useVolumeFormatter()
const commentCount = computed(() => commentStore.getComments(props.stockCode).length)

const tabs = [
  { key: 'quote', label: '行情' },
  { key: 'signals', label: '缠论信号' },
  { key: 'ai', label: 'AI策略' },
  { key: 'comment', label: '笔记' },
]

const activeTab = ref('quote')

const trendClass = computed(() => {
  const t = props.chanlunResult?.trend
  if (t === '上涨') return 'trend-up'
  if (t === '下跌') return 'trend-down'
  return 'trend-side'
})

function signalBadgeClass(type: string) {
  if (/买/i.test(type)) return 'badge-buy'
  if (/卖/i.test(type)) return 'badge-sell'
  return 'badge-wait'
}

function fmtVol(v?: number) {
  return formatVolume(v ?? null)
}

function fmtAmt(v?: number) {
  return formatAmount(v ?? null)
}

const infoRows = computed(() => {
  const s = props.info
  if (!s) return []
  const rows: { key: string; label: string; value: string }[] = []
  const push = (key: string, label: string, value: string) => {
    if (value !== '—') rows.push({ key, label, value })
  }
  const get = (k: string) => (s as any)[k]
  const fmt = (v: number | null | undefined) => v != null && !Number.isNaN(v) ? String(v) : '—'
  push('pe', '市盈率', fmt(get('市盈率')))
  push('pb', '市净率', fmt(get('市净率')))
  push('amp', '振幅', get('振幅') != null ? `${Number(get('振幅')).toFixed(2)}%` : '—')
  push('amt', '成交额', fmtAmt(get('成交额')))
  const chg = get('涨跌额')
  if (chg != null && !Number.isNaN(chg)) {
    push('chg', '涨跌额', `${chg > 0 ? '+' : ''}${Number(chg).toFixed(2)}`)
  }
  return rows
})
</script>

<style scoped>
/* ── Overlay ── */
.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 200;
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}

.sheet-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-primary);
  border-top: 1px solid var(--border-strong);
  border-radius: 20px 20px 0 0;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom, 0px);
  overflow: hidden;
}

/* ── Handle ── */
.sheet-handle {
  display: flex;
  justify-content: center;
  padding: 12px 0 8px;
  cursor: pointer;
}
.handle-bar {
  width: 36px;
  height: 4px;
  background: var(--border-strong);
  border-radius: 2px;
}

/* ── Tabs ── */
.sheet-tabs {
  display: flex;
  padding: 0 16px 12px;
  gap: 4px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.sheet-tab {
  flex: 1;
  padding: 8px 0;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.15s, color 0.15s;
  min-height: 36px;
  position: relative;
}
.sheet-tab.active {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.18) 0%, rgba(52, 211, 153, 0.12) 100%);
  color: var(--accent-cyan);
}

.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--accent-blue);
  color: #fff;
  font-size: 0.6rem;
  font-weight: 700;
  margin-left: 4px;
  line-height: 1;
}

.tab-comment {
  /* 无特殊样式，直接渲染 MobileCommentSection */
}

/* ── Content ── */
.sheet-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.tab-empty {
  color: var(--text-muted);
  font-size: 0.85rem;
  text-align: center;
  padding: 24px 0;
}

/* ── Quote ── */
.quote-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.q-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: var(--bg-card);
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
}
.q-label { font-size: 0.7rem; color: var(--text-muted); }
.q-value { font-size: 0.9rem; font-weight: 600; }

.info-section { margin-top: 4px; }
.info-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 10px;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.info-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: var(--bg-card);
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
}
.info-label { font-size: 0.68rem; color: var(--text-muted); }
.info-value { font-size: 0.82rem; font-weight: 600; }

/* ── Signals ── */
.sheet-level-trends {
  margin-bottom: 12px;
}
.trend-block {
  margin-bottom: 16px;
}
.trend-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 8px;
}
.trend-up { background: rgba(239, 68, 68, 0.14); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.25); }
.trend-down { background: rgba(34, 197, 94, 0.14); color: var(--accent-green); border: 1px solid rgba(34, 197, 94, 0.25); }
.trend-side { background: rgba(245, 158, 11, 0.12); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.28); }
.trend-desc { font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5; }

.signals-list { display: flex; flex-direction: column; gap: 10px; }
.signal-card {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sig-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sig-level {
  font-size: 0.7rem;
  color: var(--text-muted);
}
.sig-time {
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-left: auto;
}
.sig-desc {
  font-size: 0.82rem;
  color: var(--text-primary);
  line-height: 1.45;
}
.sig-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.72rem;
  color: var(--text-muted);
}
.sig-meta .confidence-bar { flex: 1; }
.sig-extra {
  display: flex;
  gap: 12px;
  font-size: 0.72rem;
  color: var(--text-muted);
}

/* ── AI ── */
.ai-card { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.ai-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ai-level { font-size: 0.8rem; color: var(--text-muted); font-weight: 600; }
.ai-direction {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
}
.dir-buy { background: rgba(239, 68, 68, 0.12); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.3); }
.dir-sell { background: rgba(34, 197, 94, 0.12); color: var(--accent-green); border: 1px solid rgba(34, 197, 94, 0.3); }
.ai-conf {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.72rem;
  color: var(--text-muted);
}
.ai-conf .confidence-bar { width: 60px; }
.ai-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.ai-tag {
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  font-size: 0.72rem;
  color: var(--text-secondary);
}
.ai-desc {
  font-size: 0.85rem;
  color: var(--text-primary);
  line-height: 1.5;
  background: var(--bg-secondary);
  padding: 10px 12px;
  border-radius: 8px;
}
.ai-prices {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.ap-item {
  font-size: 0.78rem;
  color: var(--text-muted);
}
.ai-divergence, .ai-resonance {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  color: var(--text-secondary);
}
.div-label, .res-label {
  background: rgba(167, 139, 250, 0.12);
  color: var(--accent-purple);
  border: 1px solid rgba(167, 139, 250, 0.25);
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;
  flex-shrink: 0;
}
.ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
}
.ai-loading .spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.tab-ai {
  min-height: 200px;
  display: flex;
  flex-direction: column;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Transition ── */
.sheet-enter-active, .sheet-leave-active {
  transition: opacity 0.25s ease;
}
.sheet-enter-active .sheet-panel,
.sheet-leave-active .sheet-panel {
  transition: transform 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.sheet-enter-from, .sheet-leave-to {
  opacity: 0;
}
.sheet-enter-from .sheet-panel {
  transform: translateY(100%);
}
.sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>
