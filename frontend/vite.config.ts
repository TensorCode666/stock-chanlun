import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const basePath = (env.VITE_BASE_URL || '/stock-chanlun/').replace(/\/+$/, '')
  // 默认 8010：Windows 上 8000 常被不明进程占用，会导致代理打到异常监听（如 AI 诊股 SSE 返回 500）
  const apiDevTarget =
    (env.VITE_API_PROXY_TARGET && env.VITE_API_PROXY_TARGET.trim()) ||
    'http://127.0.0.1:8010'
  const apiProxy = {
    target: apiDevTarget,
    changeOrigin: true,
  } as const
  const proxy: Record<string, { target: string; changeOrigin: boolean; rewrite?: (p: string) => string }> = {
    '/api': { ...apiProxy },
  }
  if (basePath) {
    const prefix = `${basePath}/api`
    const esc = basePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    proxy[prefix] = {
      ...apiProxy,
      rewrite: (path: string) => path.replace(new RegExp(`^${esc}/api`), '/api'),
    }
  }

  return {
    plugins: [
      vue(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.ico'],
        manifest: {
          name: 'ChanStock 缠论分析',
          short_name: 'ChanStock',
          description: '缠论智能股票分析系统 — K线、笔段中枢、AI策略信号',
          theme_color: '#06080c',
          background_color: '#06080c',
          display: 'standalone',
          orientation: 'portrait',
          start_url: '/',
          icons: [
            {
              src: 'pwa-192.svg',
              sizes: '192x192',
              type: 'image/svg+xml',
            },
            {
              src: 'pwa-192.svg',
              sizes: '512x512',
              type: 'image/svg+xml',
              purpose: 'any maskable',
            },
          ],
        },
        workbox: {
          globPatterns: [
            'index.html',
            'assets/**/*.{js,css,woff2}',
            'favicon.ico',
            'pwa-192.svg',
          ],
          runtimeCaching: [
            {
              urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'google-fonts-cache',
                expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              },
            },
            {
              urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'gstatic-fonts-cache',
                expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              },
            },
          ],
        },
      }),
    ],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    base: env.VITE_BASE_URL || '/stock-chanlun/',
    server: {
      port: 5173,
      strictPort: false,
      proxy,
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return

            if (id.includes('echarts')) return 'vendor-echarts'
            if (id.includes('axios')) return 'vendor-axios'
            if (id.includes('vue-router')) return 'vendor-router'
            if (id.includes('pinia')) return 'vendor-pinia'
            if (id.includes('/vue/')) return 'vendor-vue'
          },
        },
      },
    }
  }
})
