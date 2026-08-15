import type { ECharts } from './echarts'

type ZoomRange = { type?: string; start?: number; end?: number }

function readDataZoom(chart: ECharts): { inside?: ZoomRange; slider?: ZoomRange } {
  const dz = (chart.getOption() as { dataZoom?: ZoomRange[] }).dataZoom ?? []
  // 按 type 字段识别，而不是依赖数组下标顺序 [inside, slider]
  return {
    inside: dz.find(d => d.type === 'inside'),
    slider: dz.find(d => d.type === 'slider'),
  }
}

/** setOption 后恢复用户当前的 dataZoom 区间，避免指标切换时视图跳回默认 70–100% */
export function setChartOptionKeepDataZoom(
  chart: ECharts,
  option: Record<string, unknown>,
  notMerge = true,
) {
  const saved = readDataZoom(chart)
  chart.setOption(option, { notMerge })
  const dataZoom: ZoomRange[] = []
  if (saved.inside && saved.inside.start != null && saved.inside.end != null) {
    dataZoom.push({ type: 'inside', start: saved.inside.start, end: saved.inside.end })
  }
  if (saved.slider && saved.slider.start != null && saved.slider.end != null) {
    dataZoom.push({ type: 'slider', start: saved.slider.start, end: saved.slider.end })
  }
  if (dataZoom.length) chart.setOption({ dataZoom })
}
