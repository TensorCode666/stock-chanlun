/**
 * 个股页：缠论/K线/AI 与行情扩展信息加载（PC / 移动共用）
 */
import { ref } from 'vue'
import { stockApi, type Quote, type StockInfoFields, type StockExtras } from '../api/stock'
import { useChanlunStore, type LevelOption } from '../stores/chanlun'
import { useCommentStore } from '../stores/comment'
import { peekApiCache } from '../utils/apiCache'

export function useStockPage() {
  const store = useChanlunStore()
  const commentStore = useCommentStore()

  const quote = ref<Quote | null>(null)
  const stockInfo = ref<StockInfoFields | null>(null)
  const extras = ref<StockExtras | null>(null)

  async function loadQuoteExtras(code: string, force = false) {
    const settled = await Promise.allSettled([
      stockApi.quote(code, { force }),
      stockApi.info(code, { force }),
      stockApi.extras(code, 8, { force }),
    ])
    if (settled[0].status === 'fulfilled') quote.value = settled[0].value.data as Quote
    else quote.value = null
    if (settled[1].status === 'fulfilled') {
      const inf = settled[1].value.data.info
      stockInfo.value = inf && Object.keys(inf).length ? inf : null
    } else stockInfo.value = null
    if (settled[2].status === 'fulfilled') extras.value = settled[2].value.data
    else extras.value = null
  }

  async function loadComments(code: string, force = false) {
    await commentStore.fetchComments(code, force)
  }

  async function loadStock(
    code: string,
    level: LevelOption,
    startDate?: string,
    endDate?: string,
    options?: { force?: boolean; loadComments?: boolean },
  ) {
    if (!code) return
    const force = options?.force ?? false
    const tasks: Promise<unknown>[] = [
      store.loadAll(code, level, startDate, endDate, { force }),
      loadQuoteExtras(code, force),
    ]
    if (options?.loadComments) {
      tasks.push(loadComments(code, force))
    }
    await Promise.all(tasks)
  }

  async function changeLevel(code: string, level: LevelOption) {
    await store.loadAll(code, level, undefined, undefined, { force: false })
  }

  async function refreshAIStrategy(code: string, options?: { useLlm?: boolean }) {
    await store.fetchAISignal(code, store.currentLevel, { ...options, force: true })
  }

  async function refreshQuotes(code: string) {
    if (!code) return
    const quoteKeys = [
      `GET:/stocks/${code}/quote`,
      `GET:/stocks/${code}/info`,
      `GET:/stocks/${code}/extras:8`,
    ]
    const needsFetch = quoteKeys.some(k => {
      const peek = peekApiCache(k)
      return !peek || peek.isStale
    })
    if (!needsFetch) return
    await loadQuoteExtras(code, true)
  }

  return {
    store,
    quote,
    stockInfo,
    extras,
    loadStock,
    changeLevel,
    loadQuoteExtras,
    refreshQuotes,
    loadComments,
    refreshAIStrategy,
  }
}
