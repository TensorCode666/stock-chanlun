<template>
  <div class="card comment-card">
    <div class="card-header">
      <span class="card-title">我的笔记</span>
      <span class="comment-count">{{ comments.length }}</span>
    </div>

    <!-- 加载态 -->
    <div v-if="store.isLoading(stockCode)" class="comment-loading">
      <div class="mini-spinner" />
      <span>加载中...</span>
    </div>

    <!-- 新增笔记表单（编辑模式下隐藏） -->
    <div v-if="editingId === null" class="comment-form">
      <textarea
        v-model="formContent"
        class="form-textarea"
        placeholder="记录你的分析思路..."
        rows="3"
        @keydown.ctrl.enter="submit"
        @keydown.meta.enter="submit"
      />
      <div class="form-footer">
        <span class="form-hint">Ctrl+Enter 发送</span>
        <button
          class="btn btn-primary btn-sm"
          @click="submit"
          :disabled="!formContent.trim() || submitting"
        >
          {{ submitting ? '保存...' : '发布' }}
        </button>
      </div>
    </div>

    <!-- 空列表提示 -->
    <div v-if="!store.isLoading(stockCode) && comments.length === 0 && editingId === null" class="comment-empty">
      暂无笔记，点击上方输入框记录分析
    </div>

    <!-- 错误提示 -->
    <div v-if="storeError" class="comment-error">{{ storeError }}</div>

    <!-- 笔记列表 -->
    <div v-if="comments.length > 0" class="comment-list">
      <TransitionGroup name="comment-item">
        <div
          v-for="c in comments"
          :key="c.id"
          class="comment-item"
          :class="{ 'comment-item--editing': editingId === c.id }"
          :data-comment-id="c.id"
        >
          <!-- 卡片视图（不在编辑状态时显示） -->
          <template v-if="editingId !== c.id">
            <div class="ci-meta">
              <span class="ci-time">{{ formatTime(c.createdAt) }}</span>
              <span v-if="c.updatedAt !== c.createdAt" class="ci-edited">(已编辑)</span>
            </div>
            <p class="ci-content">{{ c.content }}</p>
            <div class="ci-actions">
              <button class="ci-btn" @click="startEdit(c)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                编辑
              </button>
              <button class="ci-btn ci-btn--danger" @click="confirmDelete(c.id)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                </svg>
                删除
              </button>
            </div>
          </template>

          <!-- 行内编辑视图（正在编辑当前笔记时显示） -->
          <template v-else>
            <textarea
              v-model="formContent"
              class="form-textarea"
              placeholder="修改笔记..."
              rows="3"
              @keydown.ctrl.enter="submit"
              @keydown.meta.enter="submit"
            />
            <div class="form-footer">
              <span class="form-hint">Ctrl+Enter 保存</span>
              <div class="form-actions">
                <button class="btn btn-ghost btn-sm" @click="cancelEdit">取消</button>
                <button
                  class="btn btn-primary btn-sm"
                  @click="submit"
                  :disabled="!formContent.trim() || submitting"
                >
                  {{ submitting ? '保存...' : '保存修改' }}
                </button>
              </div>
            </div>
          </template>
        </div>
      </TransitionGroup>
    </div>

    <!-- 删除确认 -->
    <div v-if="deleteId" class="delete-confirm-overlay" @click.self="deleteId = null">
      <div class="delete-confirm-dialog">
        <p class="dc-title">删除笔记</p>
        <p class="dc-body">确定要删除这条笔记吗？删除后无法恢复。</p>
        <div class="dc-actions">
          <button class="btn btn-ghost btn-sm" @click="deleteId = null">取消</button>
          <button class="btn btn-danger btn-sm" @click="doDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useCommentStore } from '../../stores/comment'
import type { Comment } from '../../api/stock'
import toast from '../../composables/useToast'

const props = defineProps<{ stockCode: string }>()

const store = useCommentStore()

watch(
  () => props.stockCode,
  code => {
    if (code) void store.fetchComments(code)
  },
  { immediate: true },
)

const comments = computed(() => store.getComments(props.stockCode))
const storeError = computed(() => store.getError(props.stockCode))

// editingId === null → 新增模式
// editingId === c.id → 编辑 c 这条笔记
const editingId = ref<string | null>(null)
const formContent = ref('')
const submitting = ref(false)

async function submit() {
  const content = formContent.value.trim()
  if (!content || submitting.value) return
  submitting.value = true
  try {
    if (editingId.value) {
      await store.updateComment(props.stockCode, editingId.value, content)
      toast.success('修改已保存')
    } else {
      await store.addComment(props.stockCode, content)
      toast.success('笔记发布成功')
    }
    const prevId = editingId.value
    cancelEdit()
    if (prevId) {
      nextTick(() => {
        const el = document.querySelector(`[data-comment-id="${prevId}"]`)
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    }
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '操作失败，请重试')
  } finally {
    submitting.value = false
  }
}

function startEdit(c: Comment) {
  editingId.value = c.id
  formContent.value = c.content
}

function cancelEdit() {
  editingId.value = null
  formContent.value = ''
}

const deleteId = ref<string | null>(null)

function confirmDelete(id: string) { deleteId.value = id }

async function doDelete() {
  if (!deleteId.value) return
  try {
    await store.deleteComment(props.stockCode, deleteId.value)
    toast.success('笔记已删除')
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '删除失败，请重试')
  } finally {
    deleteId.value = null
  }
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  } catch {
    return iso
  }
}
</script>

<style scoped>
.comment-card { padding: 14px 16px; }

/* ── Header ── */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.comment-count {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
}

/* ── Loading ── */
.comment-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}
.mini-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Form ── */
.comment-form {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  transition: border-color 0.15s;
}
.comment-form:focus-within {
  border-color: rgba(56, 189, 248, 0.5);
}
.form-textarea {
  width: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.8125rem;
  line-height: 1.6;
  resize: none;
  outline: none;
  transition: border-color 0.15s;
  min-height: 72px;
  -webkit-appearance: none;
}
.form-textarea:focus { border-color: var(--accent-blue); }
.form-textarea::placeholder { color: var(--text-muted); }
.form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.form-hint { font-size: 0.65rem; color: var(--text-muted); }
.form-actions { display: flex; gap: 6px; }

/* ── Empty ── */
.comment-empty {
  font-size: 0.78rem;
  color: var(--text-muted);
  text-align: center;
  padding: 8px 0 12px;
}

/* ── Error ── */
.comment-error {
  font-size: 0.78rem;
  color: var(--accent-red);
  padding: 6px 0;
}

/* ── List ── */
.comment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 520px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.comment-item {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: border-color 0.15s;
}
.comment-item:hover { border-color: var(--border-strong); }
.comment-item--editing {
  border-color: rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.04);
}

.ci-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ci-time { font-size: 0.68rem; color: var(--text-muted); }
.ci-edited { font-size: 0.65rem; color: var(--text-muted); font-style: italic; }
.ci-content {
  font-size: 0.8125rem;
  color: var(--text-primary);
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
  margin: 0;
}
.ci-actions {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}
.ci-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 5px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.68rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.12s, border-color 0.12s, background 0.12s;
  min-height: 26px;
}
.ci-btn:hover { color: var(--text-primary); border-color: var(--border-strong); background: var(--bg-hover); }
.ci-btn--danger:hover { color: var(--accent-red); border-color: rgba(239,68,68,0.4); background: rgba(239,68,68,0.08); }

/* ── Delete Confirm ── */
.delete-confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}
.delete-confirm-dialog {
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-radius: 14px;
  padding: 20px;
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dc-title { font-size: 0.95rem; font-weight: 700; color: var(--text-primary); margin: 0; }
.dc-body { font-size: 0.825rem; color: var(--text-secondary); line-height: 1.5; margin: 0; }
.dc-actions { display: flex; gap: 8px; justify-content: flex-end; }

/* ── Transitions ── */
.comment-item-enter-active, .comment-item-leave-active {
  transition: opacity 0.2s ease, max-height 0.25s ease;
  overflow: hidden;
  max-height: 200px;
}
.comment-item-enter-from, .comment-item-leave-to {
  opacity: 0;
  max-height: 0;
}
.toast-enter-active, .toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
</style>
