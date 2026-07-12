/**
 * Composables 统一导出
 */

// Toast 提示
export { default as toast } from './useToast'

// 格式化工具
export { usePriceFormatter, useVolumeFormatter, useDateFormatter, useConfidenceFormatter } from './useFormatters'

// 防抖节流
export { useDebounce, useDebouncedCallback, useThrottle, useThrottledCallback } from './useDebounce'

// 本地存储
export { useStorage, useSessionStorage } from './useStorage'

// 剪贴板
export { useClipboard } from './useClipboard'

// 定时器
export { useInterval, useTimeout, useNow } from './useInterval'

// 可见性感知的定时刷新（429 退避）
export { useVisibilityRefresh } from './useVisibilityRefresh'

// 首页大盘数据
export { useHomeDashboard, emptyMarketOverview, formatNewsTime } from './useHomeDashboard'

export { useDebouncedStockSearch } from './useDebouncedStockSearch'
export type { StockSearchHit } from './useDebouncedStockSearch'

export { usePersistedPcScreenFilters, usePersistedMobileScreenFilters } from './usePersistedScreenFilters'

// 个股页数据加载
export { useStockPage } from './useStockPage'

// 板块成分股（缓存优先）
export { useSectorData } from './useSectorData'

// 选股 SSE 流
export { useScreenStream } from './useScreenStream'

export { useMultiLevelTrends } from './useMultiLevelTrends'
export type { LevelTrendChip } from './useMultiLevelTrends'

export {
  onStockLinkHover,
  onStockLinkTouch,
  onSectorLinkHover,
  onSectorLinkTouch,
  prefetchStockChanlun,
  prefetchMultiLevelChanlun,
  prefetchStockQuotes,
  prefetchStockRouteChunks,
  prefetchSectorRouteChunks,
  prefetchSectorStocks,
  chanlunPrefetchKey,
  multiLevelPrefetchKey,
  MULTI_LEVEL_TREND_LEVELS,
  stockLinkPrefetchHandlers,
  sectorLinkPrefetchHandlers,
} from '../utils/prefetchStock'

// K 线副图指标（MACD/RSI/SKDJ 一次计算）
export { useKlineIndicators } from './useKlineIndicators'

// 全局 Loading
export { useLoading, globalLoading } from './useLoading'