"""
加密货币数据服务 - 使用 Binance 公开 REST API 获取行情与 K 线

与 akshare_service.py（A 股）平行存在，供 crypto_routes / core.crypto_analysis 使用。
加密货币 7x24 小时连续交易，不涉及交易日对齐、复权等 A 股特有概念，
因此 K 线级别与 Binance interval 是直接映射，无需分钟数据降级或多数据源容灾。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import httpx
import pandas as pd

from utils import with_retry

log = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"

# 缠论/前端级别 -> Binance K 线 interval
LEVEL_TO_INTERVAL = {
    "1min": "1m",
    "5min": "5m",
    "15min": "15m",
    "30min": "30m",
    "60min": "1h",
    "4h": "4h",
    "daily": "1d",
    "weekly": "1w",
    "monthly": "1M",
}

_http_client: httpx.Client | None = None
_http_client_lock = threading.RLock()


def _get_client() -> httpx.Client:
    global _http_client
    with _http_client_lock:
        if _http_client is None:
            _http_client = httpx.Client(
                base_url=BASE_URL,
                timeout=15.0,
                follow_redirects=True,
                trust_env=False,
                headers={"User-Agent": "ChanStock/1.0"},
            )
        return _http_client


# ── 简易 TTL 缓存（与 akshare_service 同构，独立实例避免键冲突） ──────────────
_cache: dict[str, tuple] = {}
_cache_lock = threading.RLock()
_CACHE_MAX_ENTRIES = 512


def _cache_get(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        data, timestamp, ttl = entry
        if datetime.now().timestamp() - timestamp < ttl:
            return data
        _cache.pop(key, None)
        return None


def _cache_set(key: str, data, ttl: int = 60):
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES and key not in _cache:
            oldest_key = next(iter(_cache), None)
            if oldest_key is not None:
                _cache.pop(oldest_key, None)
        _cache[key] = (data, datetime.now().timestamp(), ttl)


def normalize_symbol(code: str) -> str:
    """规范化交易对代码，如 'btcusdt' / 'BTC-USDT' -> 'BTCUSDT'"""
    return code.strip().upper().replace("-", "").replace("_", "").replace("/", "")


@with_retry(max_attempts=3, delay=0.5)
def _get(path: str, params: dict) -> httpx.Response:
    client = _get_client()
    resp = client.get(path, params=params)
    resp.raise_for_status()
    return resp


def search_symbols(keyword: str, limit: int = 20) -> list[dict]:
    """按关键字搜索现货交易对（基于交易所信息缓存，TTL 1 小时）"""
    cache_key = "exchange_info:spot"
    info = _cache_get(cache_key)
    if info is None:
        try:
            resp = _get("/api/v3/exchangeInfo", {"permissions": "SPOT"})
            info = resp.json().get("symbols", [])
            _cache_set(cache_key, info, ttl=3600)
        except Exception as e:
            log.warning(f"[加密货币] 交易对列表获取失败: {e}")
            return []

    kw = keyword.strip().upper()
    if not kw:
        return []

    results = []
    for s in info:
        if s.get("status") != "TRADING":
            continue
        symbol = s.get("symbol", "")
        base = s.get("baseAsset", "")
        quote = s.get("quoteAsset", "")
        if kw in symbol or kw in base:
            results.append({"symbol": symbol, "baseAsset": base, "quoteAsset": quote})
            if len(results) >= limit:
                break
    return results


def get_realtime_quote(symbol: str) -> dict:
    """获取单个交易对的 24 小时行情快照"""
    sym = normalize_symbol(symbol)
    cache_key = f"ticker24h:{sym}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = _get("/api/v3/ticker/24hr", {"symbol": sym})
        data = resp.json()
        quote = {
            "symbol": data.get("symbol", sym),
            "lastPrice": float(data.get("lastPrice", 0) or 0),
            "priceChangePercent": float(data.get("priceChangePercent", 0) or 0),
            "highPrice": float(data.get("highPrice", 0) or 0),
            "lowPrice": float(data.get("lowPrice", 0) or 0),
            "openPrice": float(data.get("openPrice", 0) or 0),
            "volume": float(data.get("volume", 0) or 0),
            "quoteVolume": float(data.get("quoteVolume", 0) or 0),
        }
        _cache_set(cache_key, quote, ttl=5)
        return quote
    except Exception as e:
        log.warning(f"[加密货币] 行情获取失败 {sym}: {e}")
        return {}


def get_kline_hist(code: str, period: str = "daily", limit: int = 500) -> pd.DataFrame:
    """
    获取历史 K 线数据（Binance /api/v3/klines）。

    period: 与 LEVEL_TO_INTERVAL 的 key 一致（1min/5min/.../daily/weekly/monthly）
    limit: 最多返回根数（Binance 单次上限 1000）
    """
    interval = LEVEL_TO_INTERVAL.get(period)
    if interval is None:
        return pd.DataFrame()

    limit = max(20, min(int(limit), 1000))
    sym = normalize_symbol(code)
    cache_key = f"kline:{sym}:{interval}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = _get("/api/v3/klines", {"symbol": sym, "interval": interval, "limit": limit})
        rows = resp.json()
        if not isinstance(rows, list) or not rows:
            return pd.DataFrame()

        records = []
        for row in rows:
            # [openTime, open, high, low, close, volume, closeTime, ...]
            records.append({
                "date": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).replace(tzinfo=None),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })

        df = pd.DataFrame(records)
        # 分钟级数据波动快，短 TTL；日线以上波动慢，长 TTL
        ttl = 20 if interval.endswith("m") else (60 if interval == "1h" else 300)
        _cache_set(cache_key, df, ttl=ttl)
        return df
    except Exception as e:
        log.warning(f"[加密货币] K 线获取失败 {sym} {period}: {e}")
        return pd.DataFrame()
