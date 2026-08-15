import type { MobileScreenFilters, PcScreenFilters } from './screenFiltersStorage'

type PcExportPayload = {
  version: number
  platform: 'pc'
  exportedAt?: string
  filters: Partial<PcScreenFilters>
}

type MobileExportPayload = {
  version: number
  platform: 'mobile'
  exportedAt?: string
  filters: Partial<MobileScreenFilters>
}

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
  } satisfies PcExportPayload)
}

export function downloadMobileScreenFiltersJson(filters: MobileScreenFilters) {
  downloadJson(`chanstock-screen-filters-${Date.now()}.json`, {
    version: 1,
    platform: 'mobile',
    exportedAt: new Date().toISOString(),
    filters,
  } satisfies MobileExportPayload)
}

export function parsePcScreenFiltersJson(raw: string): Partial<PcScreenFilters> | null {
  try {
    const data = JSON.parse(raw) as PcExportPayload
    if (data?.version !== 1 || data.platform !== 'pc' || typeof data.filters !== 'object' || !data.filters) {
      return null
    }
    return data.filters
  } catch {
    return null
  }
}

export function parseMobileScreenFiltersJson(raw: string): Partial<MobileScreenFilters> | null {
  try {
    const data = JSON.parse(raw) as MobileExportPayload
    if (data?.version !== 1 || data.platform !== 'mobile' || typeof data.filters !== 'object' || !data.filters) {
      return null
    }
    return data.filters
  } catch {
    return null
  }
}

export async function readFiltersJsonFile(file: File): Promise<string> {
  return file.text()
}
