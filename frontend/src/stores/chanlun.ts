import { defineStore } from 'pinia'
import { ref, watch, computed } from 'vue'
import { stockApi, type KLine, type ChanlunResult, type AISignal } from '../api/stock'
import { peekApiCache } from '../utils/apiCache'

export type LevelOption = '1min' | '5min' | '15min' | '30min' | '60min' | 'daily' | 'weekly' | 'monthly'

/** 指标显示配置 */
export interface IndicatorConfig {
  // 主图
  ma5: boolean
  ma20: boolean
  ma60: boolean
  bis: boolean
  xiangs: boolean
  zhongshus: boolean
  signals: boolean
  aiLines: boolean
  supportResistance: boolean
  // 副图
  volume: boolean
  macd: boolean
  rsi: boolean
  skdj: boolean
}

export const defaultIndicators: IndicatorConfig = {
  ma5: true,
  ma20: true,
  ma60: true,
  bis: true,
  /** 默认关闭线段，避免与「笔」叠两层折线导致杂乱；需要时在指标面板打开 */
  xiangs: false,
  zhongshus: true,
  signals: true,
  aiLines: true,
  supportResistance: true,
  volume: true,
  macd: true,
  rsi: false,
  skdj: false,
}

const INDICATOR_KEY = 'chanstock_indicators_v1'

function loadIndicators(): IndicatorConfig {
  try {
    const raw = localStorage.getItem(INDICATOR_KEY)
    if (!raw) return { ...defaultIndicators }
    return { ...defaultIndicators, ...JSON.parse(raw) as Partial<IndicatorConfig> }
  } catch { return { ...defaultIndicators } }
}

function isAbortError(e: unknown): boolean {
  return e instanceof Error && e.name === 'AbortError'
}

/** 按 YYYY-MM-DD 截取 K 线（chanlun 响应含全量 klines 时客户端筛选） */
function filterKlinesByDate(klines: KLine[], startDate?: string, endDate?: string): KLine[] {
  if (!startDate && !endDate) return klines
  return klines.filter(k => {
    const d = k.date.slice(0, 10)
    if (startDate && d < startDate) return false
    if (endDate && d > endDate) return false
    return true
  })
}

export const useChanlunStore = defineStore('chanlun', () => {
  const klines = ref<KLine[]>([])
  const chanlunResult = ref<ChanlunResult | null>(null)
  const aiSignal = ref<AISignal | null>(null)
  const loadingKline = ref(false)
  const loadingChanlun = ref(false)
  const loadingAI = ref(false)
  const errorKline = ref<string | null>(null)
  const errorChanlun = ref<string | null>(null)
  const errorAI = ref<string | null>(null)
  const currentLevel = ref<LevelOption>('daily')
  const aiModel = ref<string>('deepseek')
  const indicators = ref<IndicatorConfig>(loadIndicators())
  const klineUpdatedAt = ref<string | null>(null)
  const chanlunUpdatedAt = ref<string | null>(null)
  const aiUpdatedAt = ref<string | null>(null)

  /** 首屏无 K 线时显示图表骨架（chanlun 单请求已含 klines，通常不再单独拉 /kline） */
  const loadingChart = computed(
    () => (loadingChanlun.value || loadingKline.value) && klines.value.length === 0,
  )

  let loadSeq = 0
  let klineAbort: AbortController | null = null
  let chanlunAbort: AbortController | null = null
  let aiAbort: AbortController | null = null
  let settingsSynced = false

  async function syncAiModelFromServer() {
    if (settingsSynced) return
    settingsSynced = true
    try {
      const res = await stockApi.getSettings()
      const m = res.data?.ai_model
      if (m === 'deepseek' || m === 'gemini') aiModel.value = m
    } catch { /* ignore */ }
  }

  watch(indicators, (val) => {
    try { localStorage.setItem(INDICATOR_KEY, JSON.stringify(val)) } catch { /* ignore */ }
  }, { deep: true })

  function timeNow() {
    return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  function isStale(seq: number) {
    return seq !== loadSeq
  }

  function chanlunCacheKey(code: string, level: LevelOption) {
    return `GET:/chanlun/${code}?level=${level}`
  }

  function klineCacheKey(
    code: string,
    level: LevelOption,
    limit: number,
    startDate?: string,
    endDate?: string,
  ) {
    const params = new URLSearchParams({ level, limit: String(limit) })
    if (startDate) params.set('start_date', startDate)
    if (endDate) params.set('end_date', endDate)
    return `GET:/stocks/${code}/kline?${params.toString()}`
  }

  function aiSignalCacheKey(code: string, level: LevelOption, useLlm: boolean) {
    const params = new URLSearchParams({ level, model: aiModel.value })
    if (useLlm) params.set('use_llm', 'true')
    return `GET:/chanlun/${code}/ai?${params.toString()}`
  }

  function applyChanlunPayload(data: ChanlunResult) {
    chanlunResult.value = data
    if (data.klines?.length) {
      klines.value = data.klines
      klineUpdatedAt.value = timeNow()
    }
    chanlunUpdatedAt.value = timeNow()
    errorChanlun.value = null
  }

  async function fetchKline(
    code: string,
    level: LevelOption = 'daily',
    startDate?: string,
    endDate?: string,
    seq?: number,
    force = false,
  ) {
    const key = klineCacheKey(code, level, 500, startDate, endDate)
    let hadCached = false

    if (!force) {
      const peek = peekApiCache<{ data: { klines: KLine[] } }>(key)
      if (peek) {
        hadCached = true
        if (seq != null && isStale(seq)) return
        klines.value = peek.data.data.klines || []
        klineUpdatedAt.value = timeNow()
        errorKline.value = null
        if (!peek.isStale) return
        void stockApi
          .kline(code, level, 500, startDate, endDate, { force: true })
          .then(res => {
            if (seq != null && isStale(seq)) return
            klines.value = res.data.klines || []
            klineUpdatedAt.value = timeNow()
          })
          .catch(() => { /* 保留 stale */ })
        return
      }
    }

    klineAbort?.abort()
    klineAbort = new AbortController()
    const signal = klineAbort.signal
    loadingKline.value = !hadCached && klines.value.length === 0
    errorKline.value = null
    try {
      const res = await stockApi.kline(code, level, 500, startDate, endDate, { signal, force })
      if (seq != null && isStale(seq)) return
      klines.value = res.data.klines || []
      klineUpdatedAt.value = timeNow()
    } catch (e: unknown) {
      if (isAbortError(e)) return
      if (seq != null && isStale(seq)) return
      errorKline.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (seq == null || !isStale(seq)) loadingKline.value = false
    }
  }

  async function fetchChanlun(code: string, level: LevelOption = 'daily', seq?: number, force = false) {
    const key = chanlunCacheKey(code, level)
    let hadCached = false

    if (!force) {
      const peek = peekApiCache<{ data: ChanlunResult }>(key)
      if (peek) {
        hadCached = true
        if (seq != null && isStale(seq)) return
        applyChanlunPayload(peek.data.data)
        if (!peek.isStale) return
        void stockApi
          .chanlun(code, level, { force: true })
          .then(res => {
            if (seq != null && isStale(seq)) return
            applyChanlunPayload(res.data)
          })
          .catch(() => { /* 保留 stale */ })
        return
      }
    }

    chanlunAbort?.abort()
    chanlunAbort = new AbortController()
    const signal = chanlunAbort.signal
    loadingChanlun.value = !hadCached && klines.value.length === 0
    errorChanlun.value = null
    try {
      const res = await stockApi.chanlun(code, level, { signal, force })
      if (seq != null && isStale(seq)) return
      applyChanlunPayload(res.data)
    } catch (e: unknown) {
      if (isAbortError(e)) return
      if (seq != null && isStale(seq)) return
      errorChanlun.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (seq == null || !isStale(seq)) loadingChanlun.value = false
    }
  }

  async function fetchAISignal(
    code: string,
    level: LevelOption = 'daily',
    options?: { useLlm?: boolean; seq?: number; force?: boolean },
  ) {
    const useLlm = options?.useLlm ?? false
    const seq = options?.seq
    const force = options?.force ?? false
    const key = aiSignalCacheKey(code, level, useLlm)
    let hadCached = false

    if (!force) {
      const peek = peekApiCache<{ data: AISignal }>(key)
      if (peek) {
        hadCached = true
        if (seq != null && isStale(seq)) return
        aiSignal.value = peek.data.data
        aiUpdatedAt.value = timeNow()
        errorAI.value = null
        if (!peek.isStale) return
        void stockApi
          .aiSignal(code, level, aiModel.value, { useLlm, force: true })
          .then(res => {
            if (seq != null && isStale(seq)) return
            aiSignal.value = res.data
            aiUpdatedAt.value = timeNow()
          })
          .catch(() => { /* 保留 stale */ })
        return
      }
    }

    aiAbort?.abort()
    aiAbort = new AbortController()
    const signal = aiAbort.signal
    loadingAI.value = !hadCached && !aiSignal.value
    errorAI.value = null
    try {
      const res = await stockApi.aiSignal(code, level, aiModel.value, {
        useLlm,
        signal,
        force,
      })
      if (seq != null && isStale(seq)) return
      aiSignal.value = res.data
      aiUpdatedAt.value = timeNow()
    } catch (e: unknown) {
      if (isAbortError(e)) return
      if (seq != null && isStale(seq)) return
      errorAI.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (seq == null || !isStale(seq)) loadingAI.value = false
    }
  }

  async function loadAll(
    code: string,
    level: LevelOption = 'daily',
    startDate?: string,
    endDate?: string,
    options?: { force?: boolean },
  ) {
    void syncAiModelFromServer()
    const seq = ++loadSeq
    const force = options?.force ?? false
    currentLevel.value = level
    const hasDateFilter = Boolean(startDate || endDate)

    // 缠论与 AI 策略并行拉取（不同接口，可重叠等待）
    const aiTask = fetchAISignal(code, level, { useLlm: false, seq, force })

    await fetchChanlun(code, level, seq, force)

    if (!isStale(seq) && hasDateFilter && klines.value.length) {
      klines.value = filterKlinesByDate(klines.value, startDate, endDate)
    }

    if (!isStale(seq) && !klines.value.length && !errorChanlun.value) {
      await fetchKline(code, level, startDate, endDate, seq, force)
    }

    if (!isStale(seq)) {
      await aiTask
    }
  }

  async function setAiModel(model: string, code: string) {
    aiModel.value = model
    await stockApi.setAiModel(model)
    await fetchAISignal(code, currentLevel.value, { useLlm: true, force: true })
  }

  function toggleIndicator(key: keyof IndicatorConfig) {
    indicators.value[key] = !indicators.value[key]
  }

  function setIndicator(key: keyof IndicatorConfig, value: boolean) {
    indicators.value[key] = value
  }

  return {
    klines, chanlunResult, aiSignal,
    loadingKline, loadingChanlun, loadingAI, loadingChart,
    errorKline, errorChanlun, errorAI,
    currentLevel, aiModel, indicators,
    klineUpdatedAt, chanlunUpdatedAt, aiUpdatedAt,
    fetchKline, fetchChanlun, fetchAISignal, loadAll, setAiModel,
    toggleIndicator, setIndicator,
  }
})
