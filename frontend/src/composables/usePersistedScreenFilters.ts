/**
 * 选股条件：进入页面恢复、修改后防抖写入 localStorage
 */
import { watch, onMounted, type Ref } from 'vue'
import {
  loadPcScreenFilters,
  savePcScreenFilters,
  loadMobileScreenFilters,
  saveMobileScreenFilters,
  type PcScreenFilters,
  type MobileScreenFilters,
} from '@/utils/screenFiltersStorage'

type PcParams = Omit<PcScreenFilters, 'selectedSignals'>

export function usePersistedPcScreenFilters(
  params: PcParams,
  selectedSignals: Ref<string[]>,
) {
  function snapshot(): PcScreenFilters {
    return {
      change_pct_min: params.change_pct_min,
      change_pct_max: params.change_pct_max,
      volume_min: params.volume_min,
      volume_max: params.volume_max,
      industry: params.industry,
      pe_max: params.pe_max,
      pb_max: params.pb_max,
      dual_cross: params.dual_cross,
      level: params.level,
      pool_size: params.pool_size,
      selectedSignals: [...selectedSignals.value],
    }
  }

  function applySaved(saved: Partial<PcScreenFilters>) {
    if (saved.change_pct_min !== undefined) params.change_pct_min = saved.change_pct_min
    if (saved.change_pct_max !== undefined) params.change_pct_max = saved.change_pct_max
    if (saved.volume_min !== undefined) params.volume_min = saved.volume_min
    if (saved.volume_max !== undefined) params.volume_max = saved.volume_max
    if (saved.industry !== undefined) params.industry = saved.industry
    if (saved.pe_max !== undefined) params.pe_max = saved.pe_max
    if (saved.pb_max !== undefined) params.pb_max = saved.pb_max
    if (saved.dual_cross !== undefined) params.dual_cross = saved.dual_cross
    if (saved.level) params.level = saved.level
    if (saved.pool_size) params.pool_size = saved.pool_size
    if (saved.selectedSignals) selectedSignals.value = [...saved.selectedSignals]
  }

  onMounted(() => {
    const saved = loadPcScreenFilters()
    if (saved) applySaved(saved)
  })

  let timer: ReturnType<typeof setTimeout> | null = null
  watch(
    [() => params, selectedSignals],
    () => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => savePcScreenFilters(snapshot()), 400)
    },
    { deep: true },
  )

  return { persistNow: () => savePcScreenFilters(snapshot()), applySaved }
}

export function usePersistedMobileScreenFilters(filters: MobileScreenFilters) {
  function applySaved(saved: Partial<MobileScreenFilters>) {
    if (saved.change_pct_min !== undefined) filters.change_pct_min = saved.change_pct_min
    if (saved.change_pct_max !== undefined) filters.change_pct_max = saved.change_pct_max
    if (saved.volume_min !== undefined) filters.volume_min = saved.volume_min
    if (saved.volume_max !== undefined) filters.volume_max = saved.volume_max
    if (saved.pe_max !== undefined) filters.pe_max = saved.pe_max
    if (saved.pb_max !== undefined) filters.pb_max = saved.pb_max
    if (saved.signals !== undefined) filters.signals = saved.signals
  }

  onMounted(() => {
    const saved = loadMobileScreenFilters()
    if (saved) applySaved(saved)
  })

  let timer: ReturnType<typeof setTimeout> | null = null
  watch(
    () => ({ ...filters }),
    () => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => saveMobileScreenFilters({ ...filters }), 400)
    },
    { deep: true },
  )

  return { persistNow: () => saveMobileScreenFilters({ ...filters }), applySaved }
}
