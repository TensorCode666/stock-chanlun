/**
 * 多级别缠论趋势摘要（daily / weekly / 30min），供策略卡片展示。
 */
import { ref, watch, type MaybeRefOrGetter, toValue } from 'vue'
import { stockApi } from '@/api/stock'
import { peekApiCache } from '@/utils/apiCache'
import { multiLevelPrefetchKey } from '@/utils/prefetchStock'

export type LevelTrendChip = {
  level: string
  label: string
  trend: string
  signalsCount: number
}

const LEVEL_LABELS: Record<string, string> = {
  daily: '日线',
  weekly: '周线',
  monthly: '月线',
  '30min': '30分',
  '60min': '60分',
  '15min': '15分',
  '5min': '5分',
  '1min': '1分',
}

function parseLevels(raw: Record<string, unknown>): LevelTrendChip[] {
  const order = ['daily', 'weekly', '30min', '60min', '15min', '5min', '1min', 'monthly']
  const chips: LevelTrendChip[] = []

  for (const [level, value] of Object.entries(raw)) {
    if (typeof value !== 'object' || value === null || !('trend' in value)) continue
    const row = value as { trend?: string; signals_count?: number }
    const trend = String(row.trend ?? '').trim()
    if (!trend || trend === '数据不足') continue
    chips.push({
      level,
      label: LEVEL_LABELS[level] ?? level,
      trend,
      signalsCount: Number(row.signals_count) || 0,
    })
  }

  chips.sort((a, b) => {
    const ia = order.indexOf(a.level)
    const ib = order.indexOf(b.level)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
  return chips
}

export function useMultiLevelTrends(
  stockCode: MaybeRefOrGetter<string>,
  levels = 'daily,weekly,30min',
) {
  const levelTrends = ref<LevelTrendChip[]>([])
  const loading = ref(false)

  async function fetchTrends(force = false) {
    const code = toValue(stockCode).trim()
    if (!code || !/^\d{6}$/.test(code)) {
      levelTrends.value = []
      return
    }

    const cacheKey = multiLevelPrefetchKey(code, levels)
    let hadCache = false

    if (!force) {
      const peek = peekApiCache<Awaited<ReturnType<typeof stockApi.chanlunMultiLevel>>>(cacheKey)
      if (peek) {
        levelTrends.value = parseLevels(peek.data.data.levels ?? {})
        hadCache = true
        if (!peek.isStale) {
          loading.value = false
          return
        }
      }
    }

    loading.value = !hadCache
    try {
      const res = await stockApi.chanlunMultiLevel(code, levels, { force })
      levelTrends.value = parseLevels(res.data.levels ?? {})
    } catch {
      if (!hadCache) levelTrends.value = []
    } finally {
      loading.value = false
    }
  }

  watch(
    () => toValue(stockCode),
    () => {
      void fetchTrends()
    },
    { immediate: true },
  )

  return { levelTrends, loading, refreshTrends: () => fetchTrends(true) }
}
