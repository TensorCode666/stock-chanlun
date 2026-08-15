<template>
  <div class="comment-section">
    <!-- 头部 -->
    <div class="cs-head">
      <div class="cs-title-row">
        <span class="cs-title">我的笔记</span>
        <span class="cs-count">{{ comments.length }} 条</span>
      </div>
      <button class="btn btn-primary cs-add-btn" @click="startAdd">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        写笔记
      </button>
    </div>

    <!-- 新增 / 编辑表单 -->
    <Transition name="form-slide">
      <div v-if="formVisible" class="comment-form">
        <div class="form-textarea-wrap">
          <textarea
            ref="textareaRef"
            v-model="formContent"
            class="form-textarea"
            :placeholder="editingId ? '修改笔记...' : '记录你的分析思路...'"
            rows="3"
            @keydown.enter.ctrl="submitForm"
            @keydown.enter.meta="submitForm"
          />
          <div class="form-hint">Ctrl+Enter 发送</div>
        </div>
        <div class="form-actions">
          <button class="btn btn-ghost" @click="cancelForm">取消</button>
          <button
            class="btn btn-primary"
            @click="submitForm"
            :disabled="!formContent.trim() || submitting"
          >
            {{ submitting ? '保存中...' : editingId ? '保存修改' : '发布' }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- 评论列表 -->
    <div v-if="comments.length === 0 && !formVisible" class="cs-empty">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <p>暂无笔记</p>
      <p class="empty-hint">点击上方「写笔记」记录分析</p>
    </div>

    <div v-else class="cs-list">
      <TransitionGroup name="comment">
        <div
          v-for="c in comments"
          :key="c.id"
          class="comment-card"
          :class="{ 'comment--editing': editingId === c.id }"
        >
          <!-- 查看模式 -->
          <template v-if="editingId !== c.id">
            <div class="cc-meta">
              <span class="cc-time">{{ formatTime(c.createdAt) }}</span>
              <span v-if="c.updatedAt !== c.createdAt" class="cc-edited">(已编辑)</span>
            </div>
            <p class="cc-content">{{ c.content }}</p>
            <div class="cc-actions">
              <button class="cc-btn" @click="startEdit(c)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                编辑
              </button>
              <button class="cc-btn cc-btn--danger" @click="confirmDelete(c.id)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                </svg>
                删除
              </button>
            </div>
          </template>

          <!-- 编辑模式 -->
          <template v-else>
            <div class="form-textarea-wrap">
              <textarea
                ref="editTextareaRef"
                v-model="formContent"
                class="form-textarea"
                placeholder="修改笔记..."
                rows="3"
                @keydown.enter.ctrl="submitForm"
                @keydown.enter.meta="submitForm"
              />
              <div class="form-hint">Ctrl+Enter 发送</div>
            </div>
            <div class="form-actions">
              <button class="btn btn-ghost" @click="cancelForm">取消</button>
              <button
                class="btn btn-primary"
                @click="submitForm"
                :disabled="!formContent.trim() || submitting"
              >
                {{ submitting ? '保存中...' : '保存修改' }}
              </button>
            </div>
          </template>
        </div>
      </TransitionGroup>
    </div>

    <!-- 删除确认对话框 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="deleteConfirmId" class="confirm-overlay" @click.self="deleteConfirmId = null">
          <div class="confirm-dialog">
            <p class="confirm-title">删除笔记</p>
            <p class="confirm-body">确定要删除这条笔记吗？删除后无法恢复。</p>
            <div class="confirm-actions">
              <button class="btn btn-ghost" @click="deleteConfirmId = null">取消</button>
              <button class="btn btn-danger" @click="doDelete">确认删除</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useCommentStore } from '@/stores/comment'

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

// ── 表单状态 ─────────────────────────────────────────────────────────────
const formVisible = ref(false)
const editingId = ref<string | null>(null)
const formContent = ref('')
const submitting = ref(false)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const editTextareaRef = ref<HTMLTextAreaElement | null>(null)

async function startAdd() {
  editingId.value = null
  formContent.value = ''
  formVisible.value = true
  await nextTick()
  textareaRef.value?.focus()
}

async function startEdit(c: { id: string; content: string }) {
  editingId.value = c.id
  formContent.value = c.content
  formVisible.value = true
  await nextTick()
  editTextareaRef.value?.focus()
}

function cancelForm() {
  formVisible.value = false
  editingId.value = null
  formContent.value = ''
}

async function submitForm() {
  const content = formContent.value.trim()
  if (!content || submitting.value) return
  submitting.value = true
  try {
    if (editingId.value) {
      store.updateComment(props.stockCode, editingId.value, content)
    } else {
      store.addComment(props.stockCode, content)
    }
    cancelForm()
  } finally {
    submitting.value = false
  }
}

// ── 删除 ────────────────────────────────────────────────────────────────
const deleteConfirmId = ref<string | null>(null)

function confirmDelete(id: string) {
  deleteConfirmId.value = id
}

function doDelete() {
  if (deleteConfirmId.value) {
    store.deleteComment(props.stockCode, deleteConfirmId.value)
    deleteConfirmId.value = null
  }
}

// ── 时间格式化 ───────────────────────────────────────────────────────────
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
.comment-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Head ── */
.cs-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.cs-title-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.cs-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-secondary);
}
.cs-count {
  font-size: 0.7rem;
  color: var(--text-muted);
}
.cs-add-btn {
  padding: 7px 14px;
  min-height: 36px;
  font-size: 0.8rem;
}

/* ── Form ── */
.comment-form {
  background: var(--bg-secondary);
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.form-textarea-wrap {
  position: relative;
}
.form-textarea {
  width: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  line-height: 1.6;
  resize: none;
  outline: none;
  transition: border-color 0.15s;
  min-height: 80px;
  -webkit-appearance: none;
}
.form-textarea:focus {
  border-color: var(--accent-blue);
}
.form-textarea::placeholder {
  color: var(--text-muted);
}
.form-hint {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-align: right;
  margin-top: 4px;
}
.form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.form-actions .btn {
  flex: 0;
  padding: 7px 16px;
  min-height: 36px;
  font-size: 0.8rem;
}

/* ── Empty ── */
.cs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 32px 16px;
  color: var(--text-muted);
  text-align: center;
}
.empty-icon {
  color: var(--text-muted);
  margin-bottom: 4px;
  opacity: 0.5;
}
.cs-empty p {
  font-size: 0.85rem;
  margin: 0;
}
.empty-hint {
  font-size: 0.75rem !important;
  color: var(--text-muted);
}

/* ── Comment List ── */
.cs-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.comment-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: border-color 0.15s;
}
.comment--editing {
  border-color: rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.04);
}

.cc-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cc-time {
  font-size: 0.68rem;
  color: var(--text-muted);
}
.cc-edited {
  font-size: 0.65rem;
  color: var(--text-muted);
  font-style: italic;
}
.cc-content {
  font-size: 0.875rem;
  color: var(--text-primary);
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
  margin: 0;
}
.cc-actions {
  display: flex;
  gap: 8px;
  margin-top: 2px;
}
.cc-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  min-height: 30px;
}
.cc-btn:active {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.cc-btn--danger:hover {
  color: var(--accent-red);
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
}

/* ── Delete Confirm ── */
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  backdrop-filter: blur(4px);
}
.confirm-dialog {
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-radius: 16px;
  padding: 20px;
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.confirm-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.confirm-body {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}
.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.confirm-actions .btn {
  flex: 0;
  padding: 8px 18px;
  min-height: 40px;
  font-size: 0.85rem;
}

/* ── Animations ── */
.form-slide-enter-active, .form-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.form-slide-enter-from, .form-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.comment-enter-active, .comment-leave-active {
  transition: opacity 0.2s ease, max-height 0.25s ease;
  overflow: hidden;
  max-height: 200px;
}
.comment-enter-from, .comment-leave-to {
  opacity: 0;
  max-height: 0;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
