"""加密货币缠论分析：K 线拉取 + 引擎（结构与 core.chanlun_analysis 对齐，数据源换成 Binance）。"""
from __future__ import annotations

from fastapi import HTTPException

from chanlun.elements import ChanlunAnalysis
from chanlun.engine import ChanlunEngine
from services.binance_service import get_kline_hist
from utils import LRUCache

DEFAULT_KLINE_LIMIT = 500

# 独立缓存实例，避免与 A 股缠论缓存（utils.chanlun_cache）键冲突
crypto_chanlun_cache = LRUCache(maxsize=64, ttl=60.0)


def crypto_cache_key(symbol: str, level: str, kline_limit: int = DEFAULT_KLINE_LIMIT) -> str:
    return f"{symbol}:{level}:{kline_limit}"


def run_crypto_analysis(symbol: str, level: str, kline_limit: int = DEFAULT_KLINE_LIMIT) -> ChanlunAnalysis:
    cache_key = crypto_cache_key(symbol, level, kline_limit)
    cached = crypto_chanlun_cache.get(cache_key)
    if cached is not None:
        return cached

    df = get_kline_hist(symbol, period=level, limit=kline_limit)

    if df.empty or len(df) < 20:
        raise HTTPException(
            status_code=404,
            detail=f"{symbol} {level}级别K线数据不足（仅{len(df) if not df.empty else 0}根），请确认交易对代码或换用日线级别尝试",
        )

    if len(df) > kline_limit:
        df = df.tail(kline_limit).reset_index(drop=True)

    engine = ChanlunEngine(df)
    result = engine.analyze(level=level)
    result.stock_code = symbol

    crypto_chanlun_cache.set(cache_key, result)
    return result


def serialize_crypto_analysis(result: ChanlunAnalysis) -> dict:
    """将 ChanlunAnalysis 转为前端 JSON。加密货币 K 线级别与拉取周期一一对应，无需 A 股的分钟数据降级备注。"""
    return {
        "symbol": result.stock_code,
        "level": result.level,
        "trend": result.trend,
        "summary": result.summary,
        "klines": [
            {
                "date": str(k.date)[:19],
                "open": k.open,
                "high": k.high,
                "low": k.low,
                "close": k.close,
                "volume": k.volume,
            }
            for k in result.klines
        ],
        "bis": [
            {
                "id": b.id,
                "start": str(b.start)[:19],
                "end": str(b.end)[:19],
                "direction": b.direction,
                "high": b.high,
                "low": b.low,
                "start_price": b.start_price,
                "end_price": b.end_price,
            }
            for b in result.bis
        ],
        "zhongshus": [
            {
                "id": z.id,
                "start": str(z.start)[:19],
                "end": str(z.end)[:19],
                "range_high": z.range_high,
                "range_low": z.range_low,
            }
            for z in result.zhongshus
        ],
        "signals": [
            {
                "type": s.type,
                "level": s.level,
                "price": s.price,
                "datetime": str(s.datetime)[:19],
                "confidence": s.confidence,
                "stop_loss": s.stop_loss,
                "take_profit": s.take_profit,
                "description": s.description,
            }
            for s in result.signals
        ],
        "supportResistance": [
            {
                "type": lvl.type,
                "price": lvl.price,
                "source": lvl.source,
                "relatedId": lvl.related_id,
                "datetime": str(lvl.datetime)[:19],
                "strength": lvl.strength,
            }
            for lvl in result.support_resistance
        ],
    }
