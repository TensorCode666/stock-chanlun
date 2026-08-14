"""加密货币行情与缠论分析路由（Binance 数据源）。"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Request

from core.crypto_analysis import DEFAULT_KLINE_LIMIT, run_crypto_analysis, serialize_crypto_analysis
from core.kline_serialize import df_to_kline_dicts
from deps import check_chanlun_rate_limits, check_kline_rate_limits, check_light_api_rate_limits, client_ip
from services.binance_service import get_kline_hist, get_realtime_quote, normalize_symbol, search_symbols

router = APIRouter()
log = logging.getLogger(__name__)

LEVEL_PATTERN = "^(1min|5min|15min|30min|60min|daily|weekly|monthly)$"


@router.get("/api/crypto/search", tags=["加密货币"], summary="搜索交易对")
async def crypto_search(request: Request, q: str = Query(..., min_length=1)):
    check_light_api_rate_limits(client_ip(request))
    results = await asyncio.to_thread(search_symbols, q)
    return {"results": results}


@router.get("/api/crypto/{symbol}/quote", tags=["加密货币"], summary="24 小时行情快照")
async def crypto_quote(request: Request, symbol: str):
    check_light_api_rate_limits(client_ip(request))
    quote = await asyncio.to_thread(get_realtime_quote, symbol)
    if not quote:
        raise HTTPException(status_code=404, detail=f"未找到交易对 {normalize_symbol(symbol)}")
    return quote


@router.get("/api/crypto/{symbol}/kline", tags=["加密货币"], summary="K 线数据")
async def crypto_kline(
    request: Request,
    symbol: str,
    level: str = Query("daily", pattern=LEVEL_PATTERN),
    limit: int = Query(500, ge=20, le=1000),
):
    check_kline_rate_limits(client_ip(request))
    df = await asyncio.to_thread(get_kline_hist, symbol, level, limit)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"未获取到 {normalize_symbol(symbol)} {level} K 线数据")
    return {"symbol": normalize_symbol(symbol), "level": level, "klines": df_to_kline_dicts(df)}


@router.get("/api/crypto/{symbol}/chanlun", tags=["加密货币"], summary="缠论完整分析")
async def crypto_chanlun(
    request: Request,
    symbol: str,
    level: str = Query("daily", pattern=LEVEL_PATTERN),
    limit: int = Query(DEFAULT_KLINE_LIMIT, ge=20, le=1000),
):
    check_chanlun_rate_limits(client_ip(request))
    result = await asyncio.to_thread(run_crypto_analysis, normalize_symbol(symbol), level, limit)
    return serialize_crypto_analysis(result)
