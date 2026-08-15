import { ref, onUnmounted } from 'vue'
import { resolveApiBaseURL, type StockScreenResult } from '@/api/stock'
import { parseScreenSseLine, upsertScreenResult } from '@/utils/screenStreamParse'

export type ScreenStreamParams = Record<string, string | number | boolean | undefined | null>

const MAX_STREAM_RETRIES = 2
const RETRY_BASE_MS = 1500

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        reject(new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

function applyAbortOutcome(
  results: { value: StockScreenResult[] },
  screenError: { value: string },
) {
  if (results.value.length > 0) {
    screenError.value = `已停止筛选（已保留 ${results.value.length} 条结果）`
  }
}

export function useScreenStream() {
  const loading = ref(false)
  const hasSearched = ref(false)
  const screenError = ref('')
  const results = ref<StockScreenResult[]>([])
  const progress = ref({ done: 0, total: 0 })
  const isRetrying = ref(false)

  let abortCtrl: AbortController | null = null

  function cancelScreen() {
    abortCtrl?.abort()
    abortCtrl = null
  }

  function stopScreen() {
    if (!loading.value) return
    cancelScreen()
    loading.value = false
    isRetrying.value = false
    applyAbortOutcome(results, screenError)
  }

  function buildQueryString(params: ScreenStreamParams): string {
    const qs = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value == null || value === '') continue
      qs.set(key, String(value))
    }
    return qs.toString()
  }

  async function consumeStream(resp: Response, signal: AbortSignal): Promise<boolean> {
    if (!resp.body) throw new Error('无法读取选股流')

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let gotDone = false

    try {
      while (true) {
        if (signal.aborted) {
          await reader.cancel().catch(() => {})
          return false
        }
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          const item = parseScreenSseLine(line.trim())
          if (!item) continue
          if (item.type === 'progress') {
            progress.value = {
              done: Number(item.done) || 0,
              total: Number(item.total) || 0,
            }
          } else if (item.type === 'result') {
            upsertScreenResult(results.value, item.data as StockScreenResult)
          } else if (item.type === 'done') {
            gotDone = true
            return true
          }
        }
      }
      // 流正常结束时 flush 解码器，并处理可能残留的半行（避免丢掉结尾的 done/result）
      buf += decoder.decode()
      const trailing = buf.trim()
      if (trailing) {
        const item = parseScreenSseLine(trailing)
        if (item && item.type === 'done') gotDone = true
      }
    } finally {
      try {
        reader.releaseLock()
      } catch {
        /* ignore */
      }
    }

    return gotDone
  }

  async function runScreen(params: ScreenStreamParams) {
    cancelScreen()
    const ctrl = new AbortController()
    abortCtrl = ctrl
    const { signal } = ctrl

    loading.value = true
    hasSearched.value = true
    screenError.value = ''
    isRetrying.value = false
    results.value = []
    progress.value = { done: 0, total: 0 }

    const qs = buildQueryString(params)
    let attempt = 0

    try {
      while (attempt <= MAX_STREAM_RETRIES) {
        if (signal.aborted) return

        try {
          const resp = await fetch(`${resolveApiBaseURL()}/stocks/screen-stream?${qs}`, { signal })
          if (resp.status === 429) throw new Error('选股请求过于频繁，请稍后再试')
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

          isRetrying.value = false
          const gotDone = await consumeStream(resp, signal)
          if (signal.aborted) return
          if (gotDone) {
            screenError.value = ''
            return
          }

          if (attempt < MAX_STREAM_RETRIES) {
            attempt += 1
            isRetrying.value = true
            screenError.value = `连接中断，正在重试（${attempt}/${MAX_STREAM_RETRIES}）…`
            await sleep(RETRY_BASE_MS * attempt, signal)
            continue
          }

          if (results.value.length > 0) {
            screenError.value = '流提前结束，已保留部分结果'
          } else {
            throw new Error('选股流异常结束')
          }
          return
        } catch (e: unknown) {
          if (e instanceof Error && e.name === 'AbortError') return
          if (attempt < MAX_STREAM_RETRIES && results.value.length === 0) {
            attempt += 1
            isRetrying.value = true
            screenError.value = `连接失败，正在重试（${attempt}/${MAX_STREAM_RETRIES}）…`
            await sleep(RETRY_BASE_MS * attempt, signal)
            continue
          }
          throw e
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return
      const msg = e instanceof Error ? e.message : '选股失败，请检查网络后重试'
      if (results.value.length > 0) {
        screenError.value = `${msg}（已保留 ${results.value.length} 条结果）`
      } else {
        screenError.value = msg
        results.value = []
      }
      console.error('选股失败:', e)
    } finally {
      if (abortCtrl === ctrl) abortCtrl = null
      loading.value = false
      if (signal.aborted) {
        applyAbortOutcome(results, screenError)
      }
    }
  }

  function clearResults() {
    cancelScreen()
    results.value = []
    hasSearched.value = false
    screenError.value = ''
    progress.value = { done: 0, total: 0 }
    isRetrying.value = false
    loading.value = false
  }

  onUnmounted(cancelScreen)

  return {
    loading,
    hasSearched,
    screenError,
    isRetrying,
    results,
    progress,
    runScreen,
    stopScreen,
    clearResults,
    cancelScreen,
  }
}
