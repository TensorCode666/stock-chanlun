import axios from 'axios'
import { API_CACHE_TTL, getApiCache, setApiCache, invalidateApiCache, peekApiCache, scheduleApiRevalidate } from '../utils/apiCache'

/**
 * 与 FastAPI 约定一致：所有业务接口挂在 `/api` 下。
 * - 开发：相对路径走 Vite 代理（支持 base 子路径 `/stock-chanlun/api`）
 * - 生产：若只填了域名（如 https://x.railway.app），自动补 `/api`
 */
export function resolveApiBaseURL(): string {
  const raw = import.meta.env.VITE_API_BASE_URL
  const custom = raw != null ? String(raw).trim() : ''
  if (custom !== '') {
    let u = custom.replace(/\/+$/, '')
    if (/^https?:\/\//i.test(u)) {
      try {
        const { pathname } = new URL(u)
        if (pathname === '/' || pathname === '') {
          u = `${u}/api`
        }
      } catch {
        /* ignore */
      }
    }
    return u
  }
  const base = import.meta.env.BASE_URL || '/'
  if (base === '/' || base === '') {
    return '/api'
  }
  const normalized = base.endsWith('/') ? base : `${base}/`
  const joined = `${normalized}api`.replace(/([^:]\/)\/+/g, '$1')
  return joined.replace(/\/+$/, '') || '/api'
}

const api = axios.create({
  baseURL: resolveApiBaseURL(),
  timeout: 60000,
})

const inflightGetRequests = new Map<string, Promise<unknown>>()
let searchAbortController: AbortController | null = null

export function normalizeApiError(error: unknown): Error {
  if (!axios.isAxiosError(error)) {
    if (error instanceof Error) return error
    return new Error('请求失败，请重试')
  }

  const status = error.response?.status
  const data = error.response?.data
  const msg = data?.message || data?.detail || data?.error || error.message

  if (status === 401) return new Error('登录已过期，请重新登录')
  if (status === 403) return new Error('无权限访问该资源')
  if (status === 404) return new Error(data?.detail || data?.message || '请求的资源不存在')
  if (status === 429) return new Error('请求过于频繁，请稍后再试')
  if (status && status >= 500) {
    return new Error(data?.detail || data?.message || '服务器开小差了，请稍后重试')
  }
  if (error.code === 'ECONNABORTED') return new Error('请求超时，请检查网络后重试')
  if (!navigator.onLine) return new Error('网络已断开，请检查网络连接')
  return new Error(msg || '请求失败，请重试')
}

function withGetDedupe<T>(key: string, factory: () => Promise<T>): Promise<T> {
  const existing = inflightGetRequests.get(key) as Promise<T> | undefined
  if (existing) return existing

  const promise = factory().finally(() => {
    inflightGetRequests.delete(key)
  })
  inflightGetRequests.set(key, promise)
  return promise
}

type GetCacheOptions = { signal?: AbortSignal; force?: boolean }

async function withGetCached<T>(
  key: string,
  ttlMs: number,
  factory: () => Promise<T>,
  options?: GetCacheOptions,
): Promise<T> {
  if (options?.signal) return factory()

  if (!options?.force) {
    const peek = peekApiCache<T>(key)
    if (peek) {
      if (peek.isStale) {
        scheduleApiRevalidate(key, ttlMs, factory)
      }
      return peek.data
    }
  }

  const dedupeKey = options?.force ? `${key}:refresh` : key
  return withGetDedupe(dedupeKey, async () => {
    if (!options?.force) {
      const hit = getApiCache<T>(key)
      if (hit != null) return hit
    }
    const data = await factory()
    setApiCache(key, data, ttlMs)
    return data
  })
}

// ─── 全局错误拦截 ──────────────────────────────────────────────────────────────

api.interceptors.response.use(
  response => response,
  error => {
    return Promise.reject(normalizeApiError(error))
  }
)

// ─── Types ───────────────────────────────────────────────────────────────────

export interface KLine {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface Bi {
  id: string
  start: string
  end: string
  direction: 'up' | 'down'
  high: number
  low: number
  start_price?: number
  end_price?: number
}

export interface XiangSegment {
  id: string
  start: string
  end: string
  direction: 'up' | 'down'
  high: number
  low: number
  start_price?: number
  end_price?: number
}

export interface Zhongshu {
  id: string
  start: string
  end: string
  range_high: number
  range_low: number
}

export interface Signal {
  type: string
  level: string
  price: number
  datetime: string
  confidence: number
  stop_loss?: number
  take_profit?: number
  description: string
}

export interface StockScreenResult {
  code: string
  name: string
  price: number
  change_pct: number
  volume: number
  amount: number
  industry: string | null
  pe: number | null
  pb: number | null
  latest_signal: string | null
  latest_signal_date: string | null
  latest_signal_conf: number | null
  has_dual_cross: boolean
  dual_cross_date: string | null
  trend: string
}

export interface SupportResistance {
  type: 'support' | 'resistance'
  price: number
  source: string
  relatedId: string
  datetime: string
  strength: number
}

export interface HotStock {
  rank: number
  code: string
  name: string
  change_pct?: number
  volume?: number
}

/** 板块内单只成分股 */
export interface SectorStock {
  rank: number
  code: string
  name: string
  price: number
  change_pct: number
  volume: number
  amount: number
  turnover_pct: number
  pe_ttm: number
  pb: number
}

/** 板块详情响应 */
export interface SectorDetail {
  sector_name: string
  board_type: 'industry' | 'concept' | null
  stocks: SectorStock[]
  total: number
}

/** 首页大盘概览：主要指数一行 */
export interface MarketOverviewIndex {
  code: string
  name: string
  price: number
  change_pct: number
}

export interface MarketOverview {
  indices: Record<string, MarketOverviewIndex>
  market_breadth: { advancers: number; decliners: number; unchanged: number }
  sectors: Array<{ name: string; change_pct: number; kind?: string }>
  sectors_top: Array<{ name: string; change_pct: number }>
  sectors_bottom: Array<{ name: string; change_pct: number }>
  /** 后端拉取失败时为 true，前端可提示重试 */
  stale?: boolean
  error?: string
}

export interface MarketSector {
  name: string
  change_pct: number
  kind?: string
}

export interface NewsItem {
  title: string
  time: string
  source: string
  url: string
  digest: string
}

export interface Quote {
  code: string
  name: string
  price: number
  change_pct: number
  volume: number
  high: number
  low: number
  open: number
  prev_close: number
  amount: number
  added_at?: string  // 自选添加时间（ISO 字符串）
}

/** 腾讯行情接口解析的基本面/行情字段（与后端 get_stock_info 一致） */
export interface DepthLevel {
  price: number
  volume: number
}

export interface StockDepth {
  asks: DepthLevel[]
  bids: DepthLevel[]
}

export interface BoardHighlight {
  label: string
  value: string
}

export interface StockBoards {
  industry: string
  highlights: BoardHighlight[]
}

export interface StockSymbolNewsItem {
  title: string
  time: string
  source: string
  url: string
}

export interface StockExtras {
  code: string
  exchange: string
  depth: StockDepth
  boards: StockBoards
  news: StockSymbolNewsItem[]
}

export interface StockInfoFields {
  代码?: string
  名称?: string
  现价?: number
  涨跌幅?: number
  涨跌额?: number
  成交量?: number
  成交额?: number
  振幅?: number
  最高?: number
  最低?: number
  今开?: number
  昨收?: number
  市净率?: number
  市盈率?: number
}

export interface ChanlunResult {
  stock_code: string
  level: string
  /** 实际 K 线周期（如 1min 级别对应 5 分钟数据） */
  data_period?: string
  trend: string
  summary: string
  /** 与 /kline 同结构，缠论接口一并返回时可省一次行情请求 */
  klines?: KLine[]
  total?: number
  bis: Bi[]
  xiangs: XiangSegment[]
  zhongshus: Zhongshu[]
  signals: Signal[]
  supportResistance: SupportResistance[]
}

export interface AISignal {
  stock_code: string
  level: string
  direction: string
  confidence: number
  risk_level: string
  entry_price?: number
  stop_loss?: number
  take_profit?: number
  holding_period: string
  description: string
  trend: string
  divergence?: { type: string; probability: number; description: string } | null
  resonance?: { 共振: boolean; direction?: string; levels?: string[]; description: string }
  llm?: {
    model: string
    used: boolean
    error?: string
    skipped?: boolean
  }
}

export interface Comment {
  id: string
  stockCode: string
  content: string
  createdAt: string
  updatedAt: string
}

export const stockApi = {
  search(q: string, options?: GetCacheOptions) {
    const trimmed = q.trim()
    if (!trimmed) {
      return Promise.resolve({
        data: { stocks: [] as { code: string; name: string }[], total: 0 },
      })
    }
    const key = `GET:/stocks/search?q=${encodeURIComponent(trimmed)}`
    return withGetCached(
      key,
      API_CACHE_TTL.search,
      () => {
        if (searchAbortController) searchAbortController.abort()
        searchAbortController = new AbortController()
        return api.get<{ stocks: { code: string; name: string }[]; total: number }>(
          `/stocks/search?q=${encodeURIComponent(trimmed)}`,
          { signal: searchAbortController.signal },
        )
      },
      options,
    )
  },

  hotStocks(limit = 15, options?: GetCacheOptions) {
    const key = `GET:/stocks/hot?limit=${limit}`
    return withGetCached(
      key,
      API_CACHE_TTL.hot,
      () =>
        api.get<{ stocks: HotStock[]; total: number; error?: string | null }>('/stocks/hot', {
          params: { limit },
          timeout: 60000,
        }),
      options,
    )
  },

  marketOverview(options?: GetCacheOptions) {
    return withGetCached(
      'GET:/market/overview',
      API_CACHE_TTL.market,
      () => api.get<MarketOverview>('/market/overview', { timeout: 90000 }),
      options,
    )
  },

  news(limit = 10, options?: GetCacheOptions) {
    const key = `GET:/news?limit=${limit}`
    return withGetCached(
      key,
      API_CACHE_TTL.news,
      () => api.get<{ items: NewsItem[] }>('/news', { params: { limit }, timeout: 20000 }),
      options,
    )
  },

  sectorStocks(name: string, options?: GetCacheOptions) {
    const key = `GET:/sector/${encodeURIComponent(name)}/stocks`
    return withGetCached(
      key,
      API_CACHE_TTL.sector,
      () => api.get<SectorDetail>(`/sector/${encodeURIComponent(name)}/stocks`, { timeout: 90000 }),
      options,
    )
  },

  info(code: string, options?: GetCacheOptions) {
    const key = `GET:/stocks/${code}/info`
    return withGetCached(
      key,
      API_CACHE_TTL.info,
      () => api.get<{ code: string; exchange: string; info: StockInfoFields }>(`/stocks/${code}/info`),
      options,
    )
  },

  extras(code: string, newsLimit = 8, options?: GetCacheOptions) {
    const key = `GET:/stocks/${code}/extras:${newsLimit}`
    return withGetCached(
      key,
      API_CACHE_TTL.extras,
      () =>
        api.get<StockExtras>(`/stocks/${code}/extras`, {
          params: { news_limit: newsLimit },
          timeout: 45000,
        }),
      options,
    )
  },

  quote(code: string, options?: GetCacheOptions) {
    const key = `GET:/stocks/${code}/quote`
    return withGetCached(
      key,
      API_CACHE_TTL.quote,
      () => api.get<Quote>(`/stocks/${code}/quote`),
      options,
    )
  },

  kline(
    code: string,
    level: string,
    limit = 500,
    startDate?: string,
    endDate?: string,
    options?: GetCacheOptions,
  ) {
    const params = new URLSearchParams({ level, limit: String(limit) })
    if (startDate) params.set('start_date', startDate)
    if (endDate) params.set('end_date', endDate)
    const key = `GET:/stocks/${code}/kline?${params.toString()}`
    return withGetCached(
      key,
      API_CACHE_TTL.kline,
      () =>
        api.get<{ klines: KLine[]; total: number }>(
          `/stocks/${code}/kline?${params.toString()}`,
          { signal: options?.signal },
        ),
      options,
    )
  },

  chanlun(code: string, level: string, options?: GetCacheOptions) {
    const key = `GET:/chanlun/${code}?level=${level}`
    return withGetCached(
      key,
      API_CACHE_TTL.chanlun,
      () =>
        api.get<ChanlunResult>(`/chanlun/${code}?level=${level}`, {
          signal: options?.signal,
        }),
      options,
    )
  },

  chanlunMultiLevel(
    code: string,
    levels = 'weekly,30min',
    options?: GetCacheOptions,
  ) {
    const key = `GET:/chanlun/${code}/multi-level?levels=${levels}`
    return withGetCached(
      key,
      API_CACHE_TTL.chanlunMulti,
      () =>
        api.get<{
          code: string
          levels: Record<string, unknown>
          count: number
          elapsed_ms: number
        }>(`/chanlun/${code}/multi-level?levels=${encodeURIComponent(levels)}`),
      options,
    )
  },

  aiSignal(
    code: string,
    level: string,
    model = 'deepseek',
    options?: { useLlm?: boolean; signal?: AbortSignal; force?: boolean },
  ) {
    const useLlm = options?.useLlm ?? false
    const params = new URLSearchParams({ level, model })
    if (useLlm) params.set('use_llm', 'true')
    const key = `GET:/chanlun/${code}/ai?${params.toString()}`
    const ttl = useLlm ? API_CACHE_TTL.aiSignalLlm : API_CACHE_TTL.aiSignalRule
    const timeout = useLlm ? 120000 : 45000
    return withGetCached(
      key,
      ttl,
      () =>
        api.get<AISignal>(`/chanlun/${code}/ai?${params.toString()}`, {
          timeout,
          signal: options?.signal,
        }),
      { force: options?.force, signal: options?.signal },
    )
  },


  watchlist(options?: GetCacheOptions) {
    const key = 'GET:/watchlist'
    return withGetCached(
      key,
      API_CACHE_TTL.watchlist,
      () => api.get<{ stocks: Quote[]; total: number }>('/watchlist'),
      options,
    )
  },

  addWatch(code: string) {
    invalidateApiCache('GET:/watchlist')
    return api.post(`/watchlist/${code}`)
  },

  removeWatch(code: string) {
    invalidateApiCache('GET:/watchlist')
    return api.delete(`/watchlist/${code}`)
  },

  getSettings(options?: GetCacheOptions) {
    return withGetCached(
      'GET:/settings',
      API_CACHE_TTL.settings,
      () => api.get<{ ai_model: string }>('/settings'),
      options,
    )
  },

  setAiModel(model: string) {
    return api.put<{ ai_model: string; ok: boolean }>('/settings', null, {
      params: { model },
    })
  },

  screenStocks(params: {
    change_pct_min?: number
    change_pct_max?: number
    volume_min?: number
    volume_max?: number
    industry?: string
    pe_max?: number
    pb_max?: number
    signals?: string
    dual_cross?: boolean
    level?: string
    pool_size?: number
  }) {
    const size = params.pool_size ?? 100
    return api.get<{ results: StockScreenResult[]; total: number }>(
      '/stocks/screen',
      { params, timeout: size >= 500 ? 180000 : 60000 }
    )
  },

  // ─── 评论笔记 ────────────────────────────────────────────────────────────

  getComments(code: string, options?: GetCacheOptions) {
    const key = `GET:/comments/${code}`
    return withGetCached(
      key,
      API_CACHE_TTL.comments,
      () => api.get<{ comments: Comment[]; total: number }>(`/comments/${code}`),
      options,
    )
  },

  addComment(code: string, content: string) {
    invalidateApiCache(`GET:/comments/${code}`)
    return api.post<{ comment: Comment; added: boolean }>(
      `/comments/${code}`,
      { content }
    )
  },

  updateComment(code: string, commentId: string, content: string) {
    invalidateApiCache(`GET:/comments/${code}`)
    return api.put<{ comment: Comment; updated: boolean }>(
      `/comments/${code}/${commentId}`,
      { content }
    )
  },

  deleteComment(code: string, commentId: string) {
    invalidateApiCache(`GET:/comments/${code}`)
    return api.delete<{ id: string; deleted: boolean }>(
      `/comments/${code}/${commentId}`
    )
  },

  // ─── AI 诊股对话（流式 SSE）────────────────────────────────────────────────

  async *aiDiagnosisStream(
    code: string,
    question: string,
    sessionId = 'default',
    model = 'deepseek',
    signal?: AbortSignal,
  ): AsyncGenerator<string, void, unknown> {
    const root = resolveApiBaseURL()
    const url = `${root}/ai/diagnosis`

    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        code,
        question,
        session_id: sessionId,
        model,
      }),
      signal,
    })
    if (!resp.ok) {
      let detail = ''
      try {
        detail = (await resp.clone().text()).trim()
      } catch {
        /* ignore */
      }
      const hint =
        detail && detail.length < 800 && !detail.includes('<!DOCTYPE')
          ? detail
          : ''
      throw new Error(
        hint ? `请求失败 (${resp.status}): ${hint}` : `请求失败: ${resp.status}`
      )
    }

    const reader = resp.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      if (signal?.aborted) {
        await reader.cancel().catch(() => {})
        throw new DOMException('Aborted', 'AbortError')
      }
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (!data || data === '[DONE]') continue
        let json: { token?: string; done?: boolean; error?: string }
        try {
          json = JSON.parse(data)
        } catch {
          // 仅解析失败才忽略；业务错误（json.error）须向上抛
          continue
        }
        if (json.token) yield json.token
        if (json.done) return
        if (json.error) throw new Error(json.error)
      }
    }
    // 流结束 flush：处理可能残留的无尾换行的最后一条事件
    buffer += decoder.decode()
    const tail = buffer.trim()
    if (tail.startsWith('data: ')) {
      const data = tail.slice(6).trim()
      if (data && data !== '[DONE]') {
        let json: { token?: string; done?: boolean; error?: string }
        try {
          json = JSON.parse(data)
        } catch {
          json = {}
        }
        if (json.token) yield json.token
        if (json.done) return
        if (json.error) throw new Error(json.error)
      }
    }
  },
}

export default api
