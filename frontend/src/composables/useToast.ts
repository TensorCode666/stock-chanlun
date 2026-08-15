/**
 * 全局 Toast 提示组件
 * 纯 JavaScript 实现，无需 Vue 实例
 */

interface ToastOptions {
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

let styleInjected = false

function injectStyles() {
  if (styleInjected || document.getElementById('toast-styles')) {
    styleInjected = true
    return
  }
  const style = document.createElement('style')
  style.id = 'toast-styles'
  style.textContent = `
    .toast-container {
      position: fixed;
      top: 60px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 8px;
      pointer-events: none;
    }
    .toast-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border-radius: 8px;
      background: var(--bg-card, #1a1a2e);
      border: 1px solid var(--border, #333);
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      font-size: 0.8125rem;
      min-width: 220px;
      max-width: 360px;
      pointer-events: auto;
      animation: toast-in 0.3s ease;
    }
    .toast-item.success { border-color: rgba(34,197,94,0.4); }
    .toast-item.success .toast-icon { color: #22c55e; }
    .toast-item.error { border-color: rgba(239,68,68,0.4); }
    .toast-item.error .toast-icon { color: #ef4444; }
    .toast-item.warning { border-color: rgba(245,158,11,0.4); }
    .toast-item.warning .toast-icon { color: #f59e0b; }
    .toast-item.info { border-color: rgba(14,165,233,0.4); }
    .toast-item.info .toast-icon { color: #0ea5e9; }
    .toast-icon { font-size: 16px; min-width: 16px; text-align: center; }
    .toast-msg { flex: 1; color: var(--text-primary, #e0e0e0); line-height: 1.4; }
    .toast-close {
      background: none; border: none; color: var(--text-muted, #888);
      cursor: pointer; font-size: 16px; padding: 2px; line-height: 1;
    }
    .toast-close:hover { color: var(--text-primary, #e0e0e0); }
    .toast-out { animation: toast-out 0.25s ease forwards; }
    @keyframes toast-in {
      from { opacity: 0; transform: translateY(-16px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes toast-out {
      to { opacity: 0; transform: translateY(-8px); }
    }
  `
  document.head.appendChild(style)
  styleInjected = true
}

function getContainer(): HTMLElement {
  let container = document.querySelector('.toast-container') as HTMLElement
  if (!container) {
    container = document.createElement('div')
    container.className = 'toast-container'
    document.body.appendChild(container)
  }
  return container
}

function show(options: ToastOptions): () => void {
  injectStyles()
  const { message, type, duration: requestedDuration } = options
  // 错误消息默认展示 4000ms，其他 2500ms
  const duration = requestedDuration ?? (type === 'error' ? 4000 : 2500)
  const container = getContainer()

  const icons: Record<string, string> = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ'
  }

  const toast = document.createElement('div')
  toast.className = `toast-item ${type}`
  // 用 textContent 而非 innerHTML，避免 message 内容被当作 HTML 注入（XSS）
  const icon = document.createElement('span')
  icon.className = 'toast-icon'
  icon.textContent = icons[type]
  const msg = document.createElement('span')
  msg.className = 'toast-msg'
  msg.textContent = message
  const btn = document.createElement('button')
  btn.className = 'toast-close'
  btn.title = '关闭'
  btn.textContent = '×'
  toast.append(icon, msg, btn)

  const close = () => {
    toast.classList.add('toast-out')
    setTimeout(() => toast.remove(), 250)
  }

  toast.querySelector('.toast-close')?.addEventListener('click', close)
  container.appendChild(toast)

  if (duration > 0) {
    setTimeout(close, duration)
  }

  return close
}

export const toast = {
  success: (message: string, duration?: number) => show({ message, type: 'success', duration }),
  error: (message: string, duration?: number) => show({ message, type: 'error', duration }),
  warning: (message: string, duration?: number) => show({ message, type: 'warning', duration }),
  info: (message: string, duration?: number) => show({ message, type: 'info', duration }),
}

export default toast
