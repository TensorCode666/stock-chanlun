import { defineStore } from 'pinia'
import { ref } from 'vue'
import { stockApi } from '../api/stock'
import type { Comment } from '../api/stock'
import { peekApiCache, invalidateApiCache } from '../utils/apiCache'

export const useCommentStore = defineStore('comment', () => {
  // key: stockCode, value: comment list
  const cache = ref<Record<string, Comment[]>>({})
  const loadingMap = ref<Record<string, boolean>>({})
  const errorMap = ref<Record<string, string>>({})
  const fetchGen = ref<Record<string, number>>({})

  function bumpGen(code: string) {
    fetchGen.value[code] = (fetchGen.value[code] ?? 0) + 1
    return fetchGen.value[code]
  }

  async function fetchComments(code: string, force = false) {
    const cacheKey = `GET:/comments/${code}`
    const gen = bumpGen(code)

    if (!force) {
      const peek = peekApiCache<{ data: { comments?: Comment[] } }>(cacheKey)
      if (peek) {
        if (fetchGen.value[code] !== gen) return
        cache.value[code] = peek.data.data.comments ?? []
        errorMap.value[code] = ''
        if (!peek.isStale) return
        try {
          const res = await stockApi.getComments(code, { force: true })
          if (fetchGen.value[code] !== gen) return
          cache.value[code] = res.data.comments ?? []
        } catch {
          /* 保留 stale */
        }
        return
      }
      if (code in cache.value && !errorMap.value[code]) return
    }

    if (loadingMap.value[code]) return
    loadingMap.value[code] = true
    errorMap.value[code] = ''
    try {
      const res = await stockApi.getComments(code, { force })
      cache.value[code] = res.data.comments ?? []
    } catch (e: unknown) {
      errorMap.value[code] = (e as Error).message ?? '加载失败'
    } finally {
      loadingMap.value[code] = false
    }
  }

  async function addComment(code: string, content: string): Promise<Comment> {
    bumpGen(code)
    const res = await stockApi.addComment(code, content)
    if (!cache.value[code]) cache.value[code] = []
    cache.value[code].unshift(res.data.comment)
    invalidateApiCache(`GET:/comments/${code}`)
    return res.data.comment
  }

  async function updateComment(code: string, commentId: string, content: string): Promise<Comment> {
    bumpGen(code)
    const res = await stockApi.updateComment(code, commentId, content)
    const list = cache.value[code]
    if (list) {
      const idx = list.findIndex(c => c.id === commentId)
      if (idx >= 0) list[idx] = res.data.comment
    }
    invalidateApiCache(`GET:/comments/${code}`)
    return res.data.comment
  }

  async function deleteComment(code: string, commentId: string) {
    bumpGen(code)
    await stockApi.deleteComment(code, commentId)
    const list = cache.value[code]
    if (list) {
      cache.value[code] = list.filter(c => c.id !== commentId)
    }
    invalidateApiCache(`GET:/comments/${code}`)
  }

  function isLoading(code: string) { return !!loadingMap.value[code] }
  function getError(code: string) { return errorMap.value[code] ?? '' }
  function getComments(code: string): Comment[] { return cache.value[code] ?? [] }

  return { cache, fetchComments, addComment, updateComment, deleteComment, isLoading, getError, getComments }
})
