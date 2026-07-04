import { createRouter, createWebHistory } from 'vue-router'
import { peekApiCache } from '../utils/apiCache'
import {
  chanlunPrefetchKey,
  multiLevelPrefetchKey,
  prefetchMultiLevelChanlun,
  prefetchSectorRouteChunks,
  prefetchSectorStocks,
  prefetchStockChanlun,
  prefetchStockRouteChunks,
} from '../utils/prefetchStock'

const router = createRouter({
  // 与 vite.config.ts 的 base: '/stock-chanlun/' 保持一致
  history: createWebHistory('/stock-chanlun/'),
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0, behavior: 'smooth' }
  },
  routes: [
    // ── PC 端路由 ──────────────────────────────────────────────────────
    { path: '/', component: () => import('../views/HomeView.vue') },
    { path: '/stock/:code', component: () => import('../views/StockView.vue') },
    { path: '/watchlist', component: () => import('../views/WatchlistView.vue') },
    { path: '/screen', component: () => import('../views/StockScreenView.vue') },
    { path: '/sector/:name', component: () => import('../views/SectorView.vue') },

    // ── Mobile 端路由（前缀 /m/）──────────────────────────────────────
    {
      path: '/m',
      component: () => import('../mobile/components/MobileLayout.vue'),
      children: [
        { path: '', component: () => import('../mobile/views/MobileHomeView.vue') },
        { path: 'stock/:code', component: () => import('../mobile/views/MobileStockView.vue') },
        { path: 'watchlist', component: () => import('../mobile/views/MobileWatchlistView.vue') },
        { path: 'screen', component: () => import('../mobile/views/MobileScreenView.vue') },
        { path: 'sector/:name', component: () => import('../mobile/views/MobileSectorView.vue') },
      ],
    },
  ],
})

router.beforeEach(to => {
  const code = typeof to.params.code === 'string' ? to.params.code : ''
  if (/^\d{6}$/.test(code) && (to.path.startsWith('/stock/') || to.path.startsWith('/m/stock/'))) {
    prefetchStockRouteChunks()
    const dailyKey = chanlunPrefetchKey(code)
    if (!peekApiCache(dailyKey)) prefetchStockChanlun(code)
    const multiKey = multiLevelPrefetchKey(code)
    if (!peekApiCache(multiKey)) prefetchMultiLevelChanlun(code)
  }

  const name = typeof to.params.name === 'string' ? decodeURIComponent(to.params.name) : ''
  if (name && (to.path.startsWith('/sector/') || to.path.startsWith('/m/sector/'))) {
    prefetchSectorRouteChunks()
    prefetchSectorStocks(name)
  }

  return true
})

export default router
