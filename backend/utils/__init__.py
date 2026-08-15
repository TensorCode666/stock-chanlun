"""
轻量级工具集合：LRU 缓存（带 TTL）、HTTP 重试装饰器、请求限流
"""
import time
import threading
import functools
import random
import httpx
from collections import OrderedDict
from typing import Any, Callable, Optional
import hashlib


class LRUCache:
    """
    线程安全的 LRU 缓存，支持 TTL。
    超过 maxsize 时自动淘汰最久未使用的条目。
    TTL 过期后条目失效（下次 get 时删除）。
    """

    def __init__(self, maxsize: int = 128, ttl: float = 300.0):
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            data, timestamp = entry
            if time.time() - timestamp > self._ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return data

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.time())
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def delete_prefix(self, prefix: str) -> int:
        """删除键名以 prefix 开头的条目，返回删除数量。"""
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for key in keys:
                del self._cache[key]
            return len(keys)

    def purge_expired(self) -> int:
        """主动清理过期条目，返回清理数量。"""
        with self._lock:
            now = time.time()
            keys_to_remove = [
                key for key, (_, timestamp) in self._cache.items()
                if now - timestamp > self._ttl
            ]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def stats(self) -> dict[str, int]:
        """返回缓存统计信息。"""
        with self._lock:
            return {
                "size": len(self._cache),
                "maxsize": self._maxsize,
                "ttl_seconds": int(self._ttl),
            }


# ── 缠论分析结果缓存（5分钟 TTL，最多缓存 256 只股票） ──────────────────────
chanlun_cache = LRUCache(maxsize=128, ttl=300.0)

# ── AI 策略信号缓存：规则 90s / LLM 5 分钟 ───────────────────────────────────
ai_signal_rule_cache = LRUCache(maxsize=128, ttl=90.0)
ai_signal_llm_cache = LRUCache(maxsize=64, ttl=300.0)

# 自选股行情聚合（15s，减轻批量 quote 压力）
watchlist_quote_cache = LRUCache(maxsize=8, ttl=15.0)

# 大盘概览 / 板块成分 / 财经新闻（与前端 API_CACHE_TTL 对齐）
market_overview_cache = LRUCache(maxsize=4, ttl=60.0)
sector_board_cache = LRUCache(maxsize=64, ttl=120.0)
stock_news_cache = LRUCache(maxsize=8, ttl=120.0)

# 多级别缠论聚合响应（90s，减轻 thread pool 重复开销）
chanlun_multi_cache = LRUCache(maxsize=128, ttl=90.0)


# ── HTTP 重试装饰器 ─────────────────────────────────────────────────────────
def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    jitter: float = 0.2,
    exceptions=(httpx.HTTPError, OSError),
):
    """
    HTTP 请求重试装饰器。

    用法:
        @with_retry(max_attempts=3, delay=1.0)
        def fetch_data(url):
            return client.get(url)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        # 指数退避 + 抖动，避免并发请求在同一时刻重试
                        wait = delay * attempt
                        if jitter > 0:
                            wait += random.uniform(0, jitter)
                        time.sleep(wait)
                    continue
            raise last_exc
        return wrapper
    return decorator


# ── 请求限流器 ────────────────────────────────────────────────────────────────

class RateLimiter:
    """
    令牌桶限流器：限制每秒/每分钟最多 N 次调用。
    线程安全，支持滑动窗口计数。

    用法:
        limiter = RateLimiter(max_calls=10, window_seconds=60)
        def my_api():
            if not limiter.try_acquire("user_123"):
                raise HTTPException(429, "请求过于频繁")
            return do_work()
    """

    def __init__(self, max_calls: int = 60, window_seconds: float = 60.0):
        self._max = max_calls
        self._window = window_seconds
        self._counts: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    def _make_key(self, identifier: str) -> str:
        """生成请求标识的哈希键，防止超长标识"""
        if len(identifier) <= 64:
            return identifier
        return hashlib.sha256(identifier.encode()).hexdigest()[:64]

    def prune_stale_keys(self, max_keys: int = 2000) -> int:
        """清理过期条目；键过多时丢弃最久未活动的标识。返回移除的键数量。"""
        now = time.time()
        cutoff = now - self._window
        removed = 0
        with self._lock:
            for key in list(self._counts.keys()):
                active = [t for t in self._counts[key] if t > cutoff]
                if not active:
                    del self._counts[key]
                    removed += 1
                else:
                    self._counts[key] = active
            overflow = len(self._counts) - max_keys
            if overflow > 0:
                ranked = sorted(
                    self._counts.items(),
                    key=lambda item: max(item[1]) if item[1] else 0,
                )
                for key, _ in ranked[:overflow]:
                    self._counts.pop(key, None)
                    removed += 1
        return removed

    def try_acquire(self, identifier: str = "global", tokens: int = 1) -> bool:
        """尝试获取令牌，返回是否允许请求"""
        key = self._make_key(identifier)
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            if len(self._counts) > 1500:
                self.prune_stale_keys()

            if key not in self._counts:
                self._counts[key] = []

            # 清理过期记录
            self._counts[key] = [t for t in self._counts[key] if t > cutoff]

            if len(self._counts[key]) + tokens <= self._max:
                self._counts[key].extend([now] * tokens)
                return True
            return False

    def get_remaining(self, identifier: str = "global") -> int:
        """获取剩余可用次数"""
        key = self._make_key(identifier)
        now = time.time()
        cutoff = now - self._window
        with self._lock:
            if key not in self._counts:
                return self._max
            active = [t for t in self._counts[key] if t > cutoff]
            return max(0, self._max - len(active))

    def reset(self, identifier: str = "global") -> None:
        """清除指定标识的计数"""
        key = self._make_key(identifier)
        with self._lock:
            self._counts.pop(key, None)

    def tracked_key_count(self) -> int:
        with self._lock:
            return len(self._counts)


# ── 限流：全局限流 + 按客户端 IP（见 deps.check_*）──────────────────────────
chanlun_global_limiter = RateLimiter(max_calls=500, window_seconds=60.0)
chanlun_ip_limiter = RateLimiter(max_calls=90, window_seconds=60.0)
kline_global_limiter = RateLimiter(max_calls=1000, window_seconds=60.0)
kline_ip_limiter = RateLimiter(max_calls=200, window_seconds=60.0)
ai_diagnosis_global_limiter = RateLimiter(max_calls=120, window_seconds=60.0)
ai_diagnosis_ip_limiter = RateLimiter(max_calls=30, window_seconds=60.0)
light_global_limiter = RateLimiter(max_calls=2000, window_seconds=60.0)
light_ip_limiter = RateLimiter(max_calls=300, window_seconds=60.0)
