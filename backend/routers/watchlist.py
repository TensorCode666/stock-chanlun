from __future__ import annotations

import asyncio

from fastapi import APIRouter
from core.numbers import finite_float
from services.akshare_service import get_realtime_quote, normalize_stock_code
from stores.local_json import get_watchlist_map, watchlist_add, watchlist_remove
from utils import watchlist_quote_cache

router = APIRouter()


def _get_watchlist_response():
    wl = get_watchlist_map()
    if not wl:
        return {"stocks": []}

    codes = sorted(wl.keys())
    cache_key = ",".join(codes)
    cached = watchlist_quote_cache.get(cache_key)
    if cached is not None:
        return cached

    df = get_realtime_quote(codes)
    if df.empty:
        empty = {"stocks": [], "total": len(wl)}
        watchlist_quote_cache.set(cache_key, empty)
        return empty

    payload = {
        "stocks": [
            {
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": finite_float(row.get("最新价")),
                "change_pct": finite_float(row.get("涨跌幅")),
                "added_at": wl.get(str(row.get("代码", "")), ""),
            }
            for _, row in df.iterrows()
        ],
        "total": len(wl),
    }
    watchlist_quote_cache.set(cache_key, payload)
    return payload


@router.get("/api/watchlist", tags=["自选"])
async def get_watchlist():
    return await asyncio.to_thread(_get_watchlist_response)


def _invalidate_watchlist_cache() -> None:
    watchlist_quote_cache.clear()


@router.post("/api/watchlist/{code}", tags=["自选"])
async def add_watchlist(code: str):
    sym, _ = normalize_stock_code(code)
    added_at, is_new = watchlist_add(sym)
    _invalidate_watchlist_cache()
    wl = get_watchlist_map()
    return {
        "code": sym,
        "added": True,
        "added_at": added_at,
        "total": len(wl),
    }


@router.delete("/api/watchlist/{code}", tags=["自选"])
async def remove_watchlist(code: str):
    sym, _ = normalize_stock_code(code)
    watchlist_remove(sym)
    _invalidate_watchlist_cache()
    wl = get_watchlist_map()
    return {"code": sym, "removed": True, "total": len(wl)}
