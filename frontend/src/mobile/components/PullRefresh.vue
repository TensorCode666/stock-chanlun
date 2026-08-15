<template>
  <div
    class="pull-refresh"
    @touchstart="onTouchStart"
    @touchmove="onTouchMove"
    @touchend="onTouchEnd"
    :class="{ 'is-refreshing': isRefreshing, 'is-pulling': pullDistance > 0 }"
  >
    <div class="pull-indicator" :style="{ height: pullDistance > 0 ? pullDistance + 'px' : '0px' }">
      <div v-if="isRefreshing" class="pull-spinner">
        <div class="spinner" />
      </div>
      <div v-else class="pull-arrow" :class="{ 'arrow-down': pullDistance > 60 }">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="18 15 12 9 6 15"/>
        </svg>
      </div>
      <span class="pull-text">{{ isRefreshing ? '刷新中...' : pullDistance > 60 ? '释放刷新' : '下拉刷新' }}</span>
    </div>
    <div class="pull-content">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  refreshing?: boolean
}>()

const emit = defineEmits<{ refresh: [] }>()

const pullDistance = ref(0)
const isRefreshing = ref(false)
let startY = 0
let isPulling = false

watch(() => props.refreshing, (newVal) => {
  if (newVal === false && isRefreshing.value) {
    isRefreshing.value = false
    pullDistance.value = 0
  }
})

function onTouchStart(e: TouchEvent) {
  // 移动端真实滚动容器是 .mobile-main，而非 window（window.scrollY 恒为 0）
  const scroller = (e.currentTarget as HTMLElement | null)?.closest('.mobile-main') as HTMLElement | null
  const scrollTop = scroller?.scrollTop ?? window.scrollY
  if (scrollTop <= 0 && !isRefreshing.value) {
    startY = e.touches[0].clientY
    isPulling = true
  }
}

function onTouchMove(e: TouchEvent) {
  if (!isPulling) return
  const currentY = e.touches[0].clientY
  const diff = currentY - startY
  if (diff > 0) {
    pullDistance.value = Math.min(diff * 0.4, 80)
    e.preventDefault()
  }
}

function onTouchEnd() {
  isPulling = false
  if (pullDistance.value > 60 && !isRefreshing.value) {
    isRefreshing.value = true
    pullDistance.value = 0
    emit('refresh')
  } else {
    pullDistance.value = 0
  }
}
</script>

<style scoped>
.pull-refresh {
  position: relative;
  min-height: 100vh;
}

.pull-indicator {
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  padding-top: 12px;
  z-index: 10;
  pointer-events: none;
}

.pull-content {
  background: var(--bg-base);
}

.pull-arrow {
  color: var(--text-muted);
  transition: transform 0.2s;
}

.arrow-down {
  transform: rotate(180deg);
}

.is-pulling .pull-arrow {
  animation: bounce-down 0.6s ease infinite;
}

.is-refreshing .pull-arrow {
  display: none;
}

@keyframes bounce-down {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(3px); }
}

.pull-text {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.pull-spinner {
  padding: 8px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
