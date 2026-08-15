from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from core.chanlun_analysis import level_to_period
from core.kline_serialize import df_to_kline_dicts
from core.numbers import finite_float
from deps import check_kline_rate_limits, check_light_api_rate_limits, check_screening_rate_limits, client_ip
from utils import market_overview_cache, sector_board_cache, stock_news_cache
from services.akshare_service import (
    get_board_constituents_em,
    get_daily_hot_stocks,
    get_kline_hist,
    get_market_overview_bundle,
    get_realtime_quote,
    get_stock_boards_em,
    get_stock_depth_em,
    get_stock_info,
    get_stock_news,
    get_stock_symbol_news_em,
    normalize_stock_code,
    search_stocks,
)

router = APIRouter()


def _search_stock_impl(q: str):
    df = search_stocks(q)
    if df.empty:
        return {"stocks": [], "total": 0}
    return {
        "stocks": df.head(20)[["code", "name"]].to_dict(orient="records"),
        "total": len(df),
    }


@router.get("/api/stocks/search", tags=["数据"])
async def search_stock(request: Request, q: str = Query(..., min_length=1)):
    check_light_api_rate_limits(client_ip(request))
    return await asyncio.to_thread(_search_stock_impl, q)


@router.get("/api/stocks/hot", tags=["数据"])
async def hot_stocks(request: Request, limit: int = Query(15, ge=1, le=50)):
    check_light_api_rate_limits(client_ip(request))
    def _run():
        stocks = get_daily_hot_stocks(limit)
        return {
            "stocks": stocks,
            "total": len(stocks),
            "error": None if stocks else "获取失败，请稍后重试",
        }

    return await asyncio.to_thread(_run)


@router.get("/api/stocks/screen", tags=["选股"])
async def screen_stocks_api(
    request: Request,
    change_pct_min: Optional[float] = Query(None, description="最小涨跌幅（%）"),
    change_pct_max: Optional[float] = Query(None, description="最大涨跌幅（%）"),
    volume_min: Optional[float] = Query(None, description="最小成交量（手）"),
    volume_max: Optional[float] = Query(None, description="最大成交量（手）"),
    industry: Optional[str] = Query(None, description="行业板块名称（精确匹配）"),
    pe_max: Optional[float] = Query(None, description="市盈率上限"),
    pb_max: Optional[float] = Query(None, description="市净率上限"),
    signals: Optional[str] = Query(None, description="逗号分隔买卖点类型，如 一买,二买"),
    dual_cross: bool = Query(False, description="是否必须 MACD+SKDJ 双金叉共振"),
    level: str = Query(
        "daily",
        pattern="^(1min|5min|15min|30min|60min|daily|weekly|monthly)$",
    ),
    pool_size: int = Query(100, ge=10, le=1000, description="候选池大小（最高 1000）"),
):
    check_screening_rate_limits(client_ip(request))
    from services.screening_service import screen_stocks

    signal_types: list[str] | None = None
    if signals:
        raw = [s.strip() for s in signals.split(",") if s.strip()]
        if raw:
            signal_types = raw

    def _run():
        return screen_stocks(
            change_pct_min=change_pct_min,
            change_pct_max=change_pct_max,
            volume_min=volume_min,
            volume_max=volume_max,
            industry=industry,
            pe_max=pe_max,
            pb_max=pb_max,
            signal_types=signal_types,
            require_dual_cross=dual_cross,
            level=level,
            pool_size=pool_size,
        )

    results = await asyncio.to_thread(_run)
    return {"results": results, "total": len(results)}


@router.get("/api/stocks/screen-stream", tags=["选股"])
def screen_stocks_stream_api(
    request: Request,
    change_pct_min: Optional[float] = Query(None, description="最小涨跌幅（%）"),
    change_pct_max: Optional[float] = Query(None, description="最大涨跌幅（%）"),
    volume_min: Optional[float] = Query(None, description="最小成交量（手）"),
    volume_max: Optional[float] = Query(None, description="最大成交量（手）"),
    industry: Optional[str] = Query(None, description="行业板块名称（精确匹配）"),
    pe_max: Optional[float] = Query(None, description="市盈率上限"),
    pb_max: Optional[float] = Query(None, description="市净率上限"),
    signals: Optional[str] = Query(None, description="逗号分隔买卖点类型，如 一买,二买"),
    dual_cross: bool = Query(False, description="是否必须 MACD+SKDJ 双金叉共振"),
    level: str = Query(
        "daily",
        pattern="^(1min|5min|15min|30min|60min|daily|weekly|monthly)$",
    ),
    pool_size: int = Query(100, ge=10, le=1000, description="候选池大小（最高 1000）"),
    max_results: int = Query(50, ge=1, le=200, description="最多返回条数"),
):
    check_screening_rate_limits(client_ip(request))
    from services.screening_service import screen_stocks_stream

    signal_types: list[str] | None = None
    if signals:
        raw = [s.strip() for s in signals.split(",") if s.strip()]
        if raw:
            signal_types = raw

    async def event_stream():
        iterator = screen_stocks_stream(
            change_pct_min=change_pct_min,
            change_pct_max=change_pct_max,
            volume_min=volume_min,
            volume_max=volume_max,
            industry=industry,
            pe_max=pe_max,
            pb_max=pb_max,
            signal_types=signal_types,
            require_dual_cross=dual_cross,
            level=level,
            pool_size=pool_size,
            max_results=max_results,
        )

        def _next_item():
            try:
                return True, next(iterator)
            except StopIteration:
                return False, None

        try:
            while True:
                if await request.is_disconnected():
                    break
                ok, item = await asyncio.to_thread(_next_item)
                if not ok:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            iterator.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/market/overview", tags=["数据"])
async def market_overview(request: Request):
    check_kline_rate_limits(client_ip(request))
    def _run():
        cached = market_overview_cache.get("overview")
        if cached is not None:
            return cached
        try:
            payload = get_market_overview_bundle()
            market_overview_cache.set("overview", payload)
            return payload
        except Exception as e:
            log.warning("大盘概览获取失败: %s", e)
            return {
                "indices": {},
                "market_breadth": {"advancers": 0, "decliners": 0, "unchanged": 0},
                "sectors": [],
                "sectors_top": [],
                "sectors_bottom": [],
                "stale": True,
                "error": str(e),
            }

    return await asyncio.to_thread(_run)


@router.get("/api/news", tags=["数据"])
async def news(request: Request, limit: int = Query(10, ge=1, le=30)):
    check_light_api_rate_limits(client_ip(request))

    def _run():
        key = f"limit={limit}"
        cached = stock_news_cache.get(key)
        if cached is not None:
            return cached
        payload = {"items": get_stock_news(limit)}
        stock_news_cache.set(key, payload)
        return payload

    return await asyncio.to_thread(_run)


@router.get("/api/sector/{name}/stocks", tags=["数据"])
async def sector_stocks(request: Request, name: str):
    check_light_api_rate_limits(client_ip(request))
    def _run():
        key = name.strip()
        cached = sector_board_cache.get(key)
        if cached is not None:
            return cached
        try:
            payload = get_board_constituents_em(name)
            sector_board_cache.set(key, payload)
            return payload
        except Exception as e:
            log.warning("板块「%s」获取失败: %s", name, e)
            return {"sector_name": name, "board_type": None, "stocks": [], "total": 0}

    return await asyncio.to_thread(_run)


@router.get("/api/stocks/{code}/info", tags=["数据"])
async def stock_info(request: Request, code: str):
    check_light_api_rate_limits(client_ip(request))
    def _run():
        sym, exchange = normalize_stock_code(code)
        info = get_stock_info(sym)
        return {"code": sym, "exchange": exchange, "info": info}

    return await asyncio.to_thread(_run)


@router.get("/api/stocks/{code}/extras", tags=["数据"])
async def stock_extras(
    request: Request,
    code: str,
    news_limit: int = Query(8, ge=1, le=20),
):
    check_light_api_rate_limits(client_ip(request))
    def _run():
        from concurrent.futures import ThreadPoolExecutor

        sym, exchange = normalize_stock_code(code)
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_depth = pool.submit(get_stock_depth_em, sym)
            f_boards = pool.submit(get_stock_boards_em, sym)
            f_news = pool.submit(get_stock_symbol_news_em, sym, news_limit)
            # 任一子查询失败不应拖垮整个 extras 聚合，分别回退默认值
            try:
                depth = f_depth.result()
            except Exception as e:
                log.warning("盘口获取失败: %s", e)
                depth = {"asks": [], "bids": []}
            try:
                boards = f_boards.result()
            except Exception as e:
                log.warning("板块信息获取失败: %s", e)
                boards = {"industry": "", "highlights": []}
            try:
                news = f_news.result()
            except Exception as e:
                log.warning("个股新闻获取失败: %s", e)
                news = []
        return {
            "code": sym,
            "exchange": exchange,
            "depth": depth,
            "boards": boards,
            "news": news,
        }

    return await asyncio.to_thread(_run)


def _realtime_quote_impl(code: str):
    sym, _ = normalize_stock_code(code)
    df = get_realtime_quote([sym])
    if not df.empty:
        row = df.iloc[0]
        return {
            "code": row.get("代码", sym),
            "name": row.get("名称", ""),
            "price": finite_float(row.get("最新价")),
            "change_pct": finite_float(row.get("涨跌幅")),
            "volume": finite_float(row.get("成交量")),
            "amount": finite_float(row.get("成交额")),
            "high": finite_float(row.get("最高")),
            "low": finite_float(row.get("最低")),
            "open": finite_float(row.get("今开")),
            "prev_close": finite_float(row.get("昨收")),
        }

    info = get_stock_info(sym)
    if info and (info.get("现价") or info.get("名称")):
        return {
            "code": str(info.get("代码", sym)),
            "name": str(info.get("名称", "")),
            "price": finite_float(info.get("现价")),
            "change_pct": finite_float(info.get("涨跌幅")),
            "volume": finite_float(info.get("成交量")),
            "amount": finite_float(info.get("成交额")),
            "high": finite_float(info.get("最高")),
            "low": finite_float(info.get("最低")),
            "open": finite_float(info.get("今开")),
            "prev_close": finite_float(info.get("昨收")),
        }
    raise HTTPException(status_code=404, detail="股票未找到")


@router.get("/api/stocks/{code}/quote", tags=["数据"])
async def realtime_quote(code: str, request: Request):
    check_kline_rate_limits(client_ip(request))
    return await asyncio.to_thread(_realtime_quote_impl, code)


def _stock_kline_impl(
    code: str,
    level: str,
    limit: int,
    start_date: Optional[str],
    end_date: Optional[str],
):
    period = level_to_period(level)
    df = get_kline_hist(code, period=period, adjust="qfq", limit=limit)
    if df.empty:
        return {"klines": [], "total": 0}

    if start_date:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["date"] <= pd.Timestamp(end_date) + pd.Timedelta(days=1)]

    df = df.tail(limit).reset_index(drop=True)

    klines = df_to_kline_dicts(df)
    return {"klines": klines, "total": len(klines)}


@router.get("/api/stocks/{code}/kline", tags=["数据"])
async def stock_kline(
    code: str,
    request: Request,
    level: str = Query(
        "daily",
        pattern="^(1min|5min|15min|30min|60min|daily|weekly|monthly)$",
    ),
    limit: int = Query(500, le=2000),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    check_kline_rate_limits(client_ip(request))
    return await asyncio.to_thread(
        _stock_kline_impl, code, level, limit, start_date, end_date
    )


def _export_stock_csv_impl(code: str, level: str, limit: int):
    period = level_to_period(level)
    df = get_kline_hist(code, period=period, adjust="qfq", limit=limit)
    if df.empty:
        raise HTTPException(status_code=404, detail="K线数据为空，无法导出")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日期", "开盘", "收盘", "最高", "最低", "成交量"])
    for _, r in df.iterrows():
        writer.writerow(
            [
                str(r["date"])[:10],
                f"{r['open']:.2f}",
                f"{r['close']:.2f}",
                f"{r['high']:.2f}",
                f"{r['low']:.2f}",
                f"{r.get('volume', 0):.0f}",
            ]
        )

    # 文件名来自路径参数，清洗掉换行/控制字符，避免注入 Content-Disposition 头
    safe_code = re.sub(r"[\r\n\"\\]", "_", code)
    filename = f"{safe_code}_{level}_{str(df['date'].iloc[-1])[:10]}.csv"
    output.seek(0)
    return output.getvalue(), filename


@router.get("/api/stocks/{code}/export", tags=["数据"])
async def export_stock_csv(
    code: str,
    request: Request,
    level: str = Query(
        "daily",
        pattern="^(1min|5min|15min|30min|60min|daily|weekly|monthly)$",
    ),
    limit: int = Query(500, le=2000),
):
    check_kline_rate_limits(client_ip(request))
    body, filename = await asyncio.to_thread(_export_stock_csv_impl, code, level, limit)
    return StreamingResponse(
        iter([body]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )
