/**
 * MACD / SKDJ 与 PC KLineChart 副图、主图标记同源算法。
 */
import type { KLine } from '../api/stock'

export function calcEMA(data: number[], period: number): number[] {
  const k = 2 / (period + 1)
  const ema = [data[0]]
  for (let i = 1; i < data.length; i++) {
    ema.push(data[i] * k + ema[i - 1] * (1 - k))
  }
  return ema
}

/** O(n) 滑动窗口均线 */
export function calcMA(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null)
  if (closes.length < period) return out
  let windowSum = 0
  for (let i = 0; i < period; i++) windowSum += closes[i]
  out[period - 1] = windowSum / period
  for (let i = period; i < closes.length; i++) {
    windowSum = windowSum - closes[i - period] + closes[i]
    out[i] = windowSum / period
  }
  return out
}

export function calcMACD(closes: number[]) {
  const ema12 = calcEMA(closes, 12)
  const ema26 = calcEMA(closes, 26)
  const dif = ema12.map((v, i) => v - ema26[i])
  const dea = calcEMA(dif, 9)
  return { dif, dea }
}

/** 通达信风格 SKDJ（与 SKDJChart.vue 一致） */
export function calcSKDJ(
  highs: number[],
  lows: number[],
  closes: number[],
  n = 9,
  smoothN = 3,
  smoothM = 1
) {
  const len = closes.length
  const rsv: (number | null)[] = new Array(len).fill(null)
  // 逐窗口重算最近 n 根的最高/最低。n 很小（默认 9），直接重算保证正确性；
  // 此前的“移出元素为极值时重置”滑动实现会在移出元素恰为极值时丢失窗口内其余值。
  for (let i = n - 1; i < len; i++) {
    let windowMin = Infinity
    let windowMax = -Infinity
    for (let j = i - n + 1; j <= i; j++) {
      if (lows[j] < windowMin) windowMin = lows[j]
      if (highs[j] > windowMax) windowMax = highs[j]
    }
    rsv[i] = windowMax === windowMin ? 50 : ((closes[i] - windowMin) / (windowMax - windowMin)) * 100
  }

  const sk: (number | null)[] = new Array(len).fill(null)
  let prevSk: number | null = null
  for (let i = 0; i < len; i++) {
    const r = rsv[i]
    if (r == null) continue
    prevSk = prevSk == null ? r : (smoothM * r + (smoothN - smoothM) * prevSk) / smoothN
    sk[i] = prevSk
  }

  const sd: (number | null)[] = new Array(len).fill(null)
  let prevSd: number | null = null
  for (let i = 0; i < len; i++) {
    const s = sk[i]
    if (s == null) continue
    prevSd = prevSd == null ? s : (smoothM * s + (smoothN - smoothM) * prevSd) / smoothN
    sd[i] = prevSd
  }

  return { sk, sd }
}

export function macdGoldCrossIndices(dif: number[], dea: number[]): number[] {
  const crosses: number[] = []
  for (let i = 1; i < dif.length; i++) {
    if (dif[i - 1] <= dea[i - 1] && dif[i] > dea[i]) crosses.push(i)
  }
  return crosses
}

/** RSI（相对强弱指数） */
export function calcRSI(closes: number[], period = 14): { rsi: (number | null)[] } {
  const len = closes.length
  const rsi: (number | null)[] = new Array(len).fill(null)
  if (len < period + 1) return { rsi }

  // 计算 N 日内涨跌幅均值
  const gains: number[] = []
  const losses: number[] = []
  for (let i = 1; i < len; i++) {
    const diff = closes[i] - closes[i - 1]
    gains.push(diff > 0 ? diff : 0)
    losses.push(diff < 0 ? -diff : 0)
  }

  let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period

  for (let i = period; i < len; i++) {
    if (avgLoss === 0) {
      // 横盘（无涨也无跌）时 RSI 应为中性 50；仅无下跌但有上涨时才为 100
      rsi[i] = avgGain === 0 ? 50 : 100
    } else {
      const rs = avgGain / avgLoss
      rsi[i] = 100 - 100 / (1 + rs)
    }
    // 移动窗口更新均值
    const g = gains[i - 1]
    const l = losses[i - 1]
    avgGain = (avgGain * (period - 1) + g) / period
    avgLoss = (avgLoss * (period - 1) + l) / period
  }

  return { rsi }
}

export function skdjGoldCrossIndices(sk: (number | null)[], sd: (number | null)[]): number[] {
  const crosses: number[] = []
  for (let i = 1; i < sk.length; i++) {
    const a = sk[i - 1]
    const b = sk[i]
    const ap = sd[i - 1]
    const bp = sd[i]
    if (a == null || b == null || ap == null || bp == null) continue
    if (a <= ap && b > bp) crosses.push(i)
  }
  return crosses
}

/** 当日 MACD 死叉：DIF 下穿 DEA */
export function macdDeathCrossAt(i: number, dif: number[], dea: number[], eps = 1e-9): boolean {
  if (i < 1) return false
  return dif[i - 1] >= dea[i - 1] - eps && dif[i] < dea[i] - eps
}

/** 当日 SKDJ 死叉：SK 下穿 SD */
export function skdjDeathCrossAt(i: number, sk: (number | null)[], sd: (number | null)[], eps = 1e-9): boolean {
  if (i < 1) return false
  const a = sk[i - 1]
  const b = sk[i]
  const ap = sd[i - 1]
  const bp = sd[i]
  if (a == null || b == null || ap == null || bp == null) return false
  return a >= ap - eps && b < bp - eps
}

function klineNumericSeries(klines: KLine[]) {
  const closes = klines.map(k => Number(k.close))
  const highs = klines.map(k => Number(k.high))
  const lows = klines.map(k => Number(k.low))
  if (!closes.length || closes.some(x => !Number.isFinite(x))) {
    return null
  }
  if (highs.some(x => !Number.isFinite(x)) || lows.some(x => !Number.isFinite(x))) return null
  return { closes, highs, lows }
}

/**
 * MACD 金叉与 SKDJ 金叉在 windowBars 根 K 线内共振；标记在较晚金叉日 hi=max(m,s)。
 * 必须：该日 DIF>DEA 且 SK>SD，且当日不能是任一指标的死叉 K 线。
 * 连续候选合并时保留每段最左一根（避免原先取最右一根落在已拐头/死叉附近误标）。
 * 返回 { indices, macdG, skG } 以便外部诊断（生产可删 debugInfo）。
 */
export function computeDualMacdSkdjMarkerIndices(
  klines: KLine[],
  windowBars: number,
  eps = 1e-9,
  precomputed?: {
    dif: number[]
    dea: number[]
    sk: (number | null)[]
    sd: (number | null)[]
  },
): { indices: number[]; macdG: number[]; skG: number[]; dates: string[] } {
  const series = klineNumericSeries(klines)
  if (!series || klines.length < 30) return { indices: [], macdG: [], skG: [], dates: [] }

  const { closes, highs, lows } = series
  const { dif, dea } = precomputed ?? calcMACD(closes)
  const skdj = precomputed
    ? { sk: precomputed.sk, sd: precomputed.sd }
    : calcSKDJ(highs, lows, closes)
  const { sk, sd } = skdj
  const macdG = macdGoldCrossIndices(dif, dea)
  const skG = skdjGoldCrossIndices(sk, sd)
  const dates = klines.map(k => k.date.slice(0, 10))

  const bullish = (i: number): boolean => {
    const a = sk[i]
    const b = sd[i]
    if (a == null || b == null) return false
    return dif[i] - dea[i] > eps && a - b > eps
  }

  const raw = new Set<number>()

  for (const m of macdG) {
    for (const s of skG) {
      const hi = Math.max(m, s)
      const lo = Math.min(m, s)
      const dist = hi - lo
      if (dist > windowBars) continue
      const macdDead = macdDeathCrossAt(hi, dif, dea, eps)
      const skdjDead = skdjDeathCrossAt(hi, sk, sd, eps)
      const bull = bullish(hi)
      if (!macdDead && !skdjDead && bull) raw.add(hi)
    }
  }

  const sorted = [...raw].sort((a, b) => a - b)
  if (sorted.length <= 1) return { indices: sorted, macdG, skG, dates }

  const merged: number[] = []
  let runStart = sorted[0]
  let runEnd = sorted[0]
  for (let k = 1; k < sorted.length; k++) {
    if (sorted[k] - runEnd <= 1) {
      runEnd = sorted[k]
    } else {
      merged.push(runStart)
      runStart = sorted[k]
      runEnd = sorted[k]
    }
  }
  merged.push(runStart)
  return { indices: merged, macdG, skG, dates }
}
