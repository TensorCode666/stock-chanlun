import type { MobileScreenFilters, PcScreenFilters } from './screenFiltersStorage'

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function downloadPcScreenFiltersJson(filters: PcScreenFilters) {
  downloadJson(`chanstock-screen-filters-${Date.now()}.json`, {
    version: 1,
    platform: 'pc',
    exportedAt: new Date().toISOString(),
    filters,
  })
}

export function downloadMobileScreenFiltersJson(filters: MobileScreenFilters) {
  downloadJson(`chanstock-screen-filters-${Date.now()}.json`, {
    version: 1,
    platform: 'mobile',
    exportedAt: new Date().toISOString(),
    filters,
  })
}
