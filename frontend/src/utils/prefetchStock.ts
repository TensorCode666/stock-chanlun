/**
 * 列表交互时预取路由 chunk 与 API 缓存，缩短进入个股/板块页的等待时间。
 */
import { peekApiCache } from './apiCache'
import { stockApi } from '../api/stock'

/** 多级别趋势默认只拉周线+30分，日线由 loadAll 的缠论结果合并 */
export const MULTI_LEVEL_TREND_LEVELS = 'weekly,30min'

let routeChunksPrefetched = false
let sectorChunksPrefetched = false
const inflightChanlun = new Set<string>()
const inflightMulti = new Set<string>()
const inflightSector = new Set<string>()
const inflightQuotes = new Set<string>()

export function prefetchStockRouteChunks() {
  if (routeChunksPrefetched) return
  routeChunksPrefetched = true
  void import('../views/StockView.vue')
  void import('../mobile/views/MobileStockView.vue')
  void import('../components/Chart/KLineChart.vue')
}

export function prefetchSectorRouteChunks() {
  if (sectorChunksPrefetched) return
  sectorChunksPrefetched = true
  void import('../views/SectorView.vue')
  void import('../mobile/views/MobileSectorView.vue')
}

export function chanlunPrefetchKey(code: string, level = 'daily') {
  return `GET:/chanlun/${code}?level=${level}`
}

export function multiLevelPrefetchKey(code: string, levels = MULTI_LEVEL_TREND_LEVELS) {
  return `GET:/chanlun/${code.trim()}/multi-level?levels=${levels}`
}

function isStockCode(code: string) {
  return /^\d{6}$/.test(code.trim())
}

/** 预取缠论（含 K 线）；已缓存或进行中则跳过 */
export function prefetchStockChanlun(code: string, level = 'daily') {
  const trimmed = code.trim()
  if (!isStockCode(trimmed)) return

  prefetchStockRouteChunks()

  const key = chanlunPrefetchKey(trimmed, level)
  if (peekApiCache(key) || inflightChanlun.has(key)) return

  inflightChanlun.add(key)
  void stockApi
    .chanlun(trimmed, level)
    .catch(() => { /* 预取失败静默 */ })
    .finally(() => inflightChanlun.delete(key))
}

/** 预取多级别缠论（weekly+30min），供策略卡片与共振计算 */
export function prefetchMultiLevelChanlun(code: string, levels = MULTI_LEVEL_TREND_LEVELS) {
  const trimmed = code.trim()
  if (!isStockCode(trimmed)) return

  const key = multiLevelPrefetchKey(trimmed, levels)
  if (peekApiCache(key) || inflightMulti.has(key)) return

  inflightMulti.add(key)
  void stockApi
    .chanlunMultiLevel(trimmed, levels)
    .catch(() => { /* 预取失败静默 */ })
    .finally(() => inflightMulti.delete(key))
}

export function prefetchSectorStocks(name: string) {
  const trimmed = name.trim()
  if (!trimmed) return

  prefetchSectorRouteChunks()

  const key = `GET:/sector/${encodeURIComponent(trimmed)}/stocks`
  if (peekApiCache(key) || inflightSector.has(key)) return

  inflightSector.add(key)
  void stockApi
    .sectorStocks(trimmed)
    .catch(() => { /* 预取失败静默 */ })
    .finally(() => inflightSector.delete(key))
}

/** 预取行情/基本面/扩展信息，缩短个股页头部展示 */
export function prefetchStockQuotes(code: string) {
  const trimmed = code.trim()
  if (!isStockCode(trimmed) || inflightQuotes.has(trimmed)) return

  const quoteKey = `GET:/stocks/${trimmed}/quote`
  const infoKey = `GET:/stocks/${trimmed}/info`
  const extrasKey = `GET:/stocks/${trimmed}/extras:8`
  if (peekApiCache(quoteKey) && peekApiCache(infoKey) && peekApiCache(extrasKey)) return

  inflightQuotes.add(trimmed)
  void Promise.allSettled([
    stockApi.quote(trimmed),
    stockApi.info(trimmed),
    stockApi.extras(trimmed, 8),
  ])
    .catch(() => { /* 预取失败静默 */ })
    .finally(() => inflightQuotes.delete(trimmed))
}

export function onStockLinkHover(code: string, level = 'daily') {
  prefetchStockChanlun(code, level)
  prefetchMultiLevelChanlun(code)
  prefetchStockQuotes(code)
}

/** 移动端无 hover，touchstart 时触发同等预取 */
export function onStockLinkTouch(code: string, level = 'daily') {
  prefetchStockChanlun(code, level)
  prefetchMultiLevelChanlun(code)
  prefetchStockQuotes(code)
}

export function onSectorLinkHover(name: string) {
  prefetchSectorStocks(name)
}

export function onSectorLinkTouch(name: string) {
  prefetchSectorStocks(name)
}

/** 列表行绑定：PC hover + 移动 touch */
export function stockLinkPrefetchHandlers(code: string, level = 'daily') {
  return {
    onMouseenter: () => onStockLinkHover(code, level),
    onTouchstart: () => onStockLinkTouch(code, level),
  }
}

export function sectorLinkPrefetchHandlers(name: string) {
  return {
    onMouseenter: () => onSectorLinkHover(name),
    onTouchstart: () => onSectorLinkTouch(name),
  }
}
