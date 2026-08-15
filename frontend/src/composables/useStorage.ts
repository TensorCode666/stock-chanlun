/**
 * 本地存储 Hook - 支持响应式和 JSON 自动序列化
 */
import { ref, watch, type Ref } from 'vue'

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function useStorage<T>(key: string, defaultValue: T): [Ref<T>, (value: T) => void] {
  const initial = safeParse(localStorage.getItem(key), defaultValue)
  const value = ref<T>(initial) as Ref<T>

  function setItem(newValue: T) {
    value.value = newValue
    localStorage.setItem(key, JSON.stringify(newValue))
  }

  watch(value, (newVal) => {
    localStorage.setItem(key, JSON.stringify(newVal))
  }, { deep: true })

  return [value, setItem]
}

/**
 * Session Storage 版本
 */
export function useSessionStorage<T>(key: string, defaultValue: T): [Ref<T>, (value: T) => void] {
  const initial = safeParse(sessionStorage.getItem(key), defaultValue)
  const value = ref<T>(initial) as Ref<T>

  function setItem(newValue: T) {
    value.value = newValue
    sessionStorage.setItem(key, JSON.stringify(newValue))
  }

  watch(value, (newVal) => {
    sessionStorage.setItem(key, JSON.stringify(newVal))
  }, { deep: true })

  return [value, setItem]
}