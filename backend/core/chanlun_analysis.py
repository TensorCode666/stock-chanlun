"""缠论分析：K 线拉取 + 引擎（供路由与 AI 复用）。"""
from __future__ import annotations

import pandas as pd
from fastapi import HTTPException

from chanlun.elements import ChanlunAnalysis
from chanlun.engine import ChanlunEngine
from core.kline_serialize import analysis_klines_to_df
from services.akshare_service import get_kline_hist  # used by run_analysis
from utils import chanlun_cache, chanlun_multi_cache

DEFAULT_KLINE_LIMIT = 500
SCREENING_KLINE_LIMIT = 200


def chanlun_cache_key(code: str, level: str, kline_limit: int = DEFAULT_KLINE_LIMIT) -> str:
    """缓存键含 K 线窗口长度，避免选股(200)与全量(500)互相污染。"""
    return f"{code}:{level}:{kline_limit}"


def level_to_period(level: str) -> str:
    mapping = {
        "1min": "5",
        "5min": "5",
        "15min": "15",
        "30min": "30",
        "60min": "60",
        "daily": "daily",
        "weekly": "weekly",
        "monthly": "monthly",
    }
    return mapping.get(level, "daily")


def run_analysis(code: str, level: str, kline_limit: int = DEFAULT_KLINE_LIMIT) -> ChanlunAnalysis:
    cache_key = chanlun_cache_key(code, level, kline_limit)
    cached = chanlun_cache.get(cache_key)
    if cached is not None:
        return cached

    period = level_to_period(level)
    df = get_kline_hist(code, period=period, start_date=None, adjust="qfq", limit=kline_limit)

    if df.empty or len(df) < 20:
        raise HTTPException(
            status_code=404,
            detail=f"{code} {level}级别K线数据不足（仅{len(df) if not df.empty else 0}根），请换日线/30分钟级别尝试",
        )

    if len(df) > kline_limit:
        df = df.tail(kline_limit).reset_index(drop=True)

    engine = ChanlunEngine(df)
    result = engine.analyze(level=level)
    result.stock_code = code

    chanlun_cache.set(cache_key, result)
    chanlun_multi_cache.delete_prefix(f"multi:{code}:")
    return result


def get_kline_df_for_ai(
    code: str, level: str, kline_limit: int = DEFAULT_KLINE_LIMIT
) -> tuple[pd.DataFrame, ChanlunAnalysis]:
    result = run_analysis(code, level, kline_limit=kline_limit)
    return analysis_klines_to_df(result.klines), result
