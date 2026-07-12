/**
 * 多级别缠论趋势摘要（weekly / 30min + 日线合并），供策略卡片展示。
 */
import { ref, watch, type MaybeRefOrGetter, toValue } from 'vue'
import { stockApi } from '@/api/stock'
import { peekApiCache } from '@/utils/apiCache'
import { MULTI_LEVEL_TREND_LEVELS, multiLevelPrefetchKey } from '@/utils/prefetchStock'

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

const LEVEL_ORDER = ['daily', 'weekly', '30min', '60min', '15min', '5min', '1min', 'monthly']

type DailySource = { trend?: string; signals?: unknown[] } | null | undefined

function sortChips(chips: LevelTrendChip[]) {
  chips.sort((a, b) => {
    const ia = LEVEL_ORDER.indexOf(a.level)
    const ib = LEVEL_ORDER.indexOf(b.level)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
  return chips
}

function parseLevels(raw: Record<string, unknown>): LevelTrendChip[] {
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

  return sortChips(chips)
}

function mergeDailyChip(chips: LevelTrendChip[], daily: DailySource): LevelTrendChip[] {
  const trend = String(daily?.trend ?? '').trim()
  if (!trend || trend === '数据不足') return chips
  const dailyChip: LevelTrendChip = {
    level: 'daily',
    label: LEVEL_LABELS.daily,
    trend,
    signalsCount: Array.isArray(daily?.signals) ? daily.signals.length : 0,
  }
  return sortChips([dailyChip, ...chips.filter(c => c.level !== 'daily')])
}

export function useMultiLevelTrends(
  stockCode: MaybeRefOrGetter<string>,
  levels = MULTI_LEVEL_TREND_LEVELS,
  dailySource?: MaybeRefOrGetter<DailySource>,
) {
  const levelTrends = ref<LevelTrendChip[]>([])
  const loading = ref(false)

  function applyTrends(raw: Record<string, unknown>) {
    levelTrends.value = mergeDailyChip(parseLevels(raw), toValue(dailySource))
  }

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
        applyTrends(peek.data.data.levels ?? {})
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
      applyTrends(res.data.levels ?? {})
    } catch {
      if (!hadCache) levelTrends.value = mergeDailyChip([], toValue(dailySource))
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

  if (dailySource) {
    watch(
      () => toValue(dailySource),
      () => {
        levelTrends.value = mergeDailyChip(levelTrends.value, toValue(dailySource))
      },
      { deep: true },
    )
  }

  return { levelTrends, loading, refreshTrends: () => fetchTrends(true) }
}
