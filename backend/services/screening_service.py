"""
选股服务 — 按基础指标、缠论买卖点、MACD+SKDJ 双金叉筛选股票。
"""
import logging
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from chanlun.elements import BuySellPoint
from core.chanlun_analysis import SCREENING_KLINE_LIMIT, run_analysis
from core.kline_serialize import analysis_klines_to_df
from services.akshare_service import (
    get_daily_hot_stocks,
    get_realtime_quote,
    get_stock_boards_em,
    get_stock_info,
)
from config import SCREENING_WORKERS
from core.indicators import calc_macd_lists, calc_skdj_lists, find_latest_dual_cross_bar

log = logging.getLogger(__name__)


def _dual_cross_info(klines_df: pd.DataFrame):
    """计算 MACD+SKDJ 双金叉共振，返回 (has_dual_cross, dual_cross_date_str)。"""
    if len(klines_df) < 30:
        return False, None

    closes = klines_df["close"].tolist()
    highs = klines_df["high"].tolist()
    lows = klines_df["low"].tolist()
    dif, dea = calc_macd_lists(closes)
    sk, sd = calc_skdj_lists(highs, lows, closes)
    best_hi = find_latest_dual_cross_bar(dif, dea, sk, sd)
    if best_hi is None:
        return False, None

    d = klines_df.iloc[best_hi]["date"]
    date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
    return True, date_str


# ─── 单只股票分析 ─────────────────────────────────────────────────────────────

def _analyze_stock(code: str, level: str) -> dict | None:
    """
    对单只股票执行选股分析。
    返回字典或 None（分析失败时跳过）。
    """
    try:
        result = run_analysis(code, level, kline_limit=SCREENING_KLINE_LIMIT)
        df = analysis_klines_to_df(result.klines)
        if df.empty or len(df) < 20:
            return None

        latest_signal: BuySellPoint | None = None
        if result.signals:
            sorted_sigs = sorted(result.signals, key=lambda s: s.datetime, reverse=True)
            latest_signal = sorted_sigs[0]

        has_dual_cross, dual_cross_date = _dual_cross_info(df)

        return {
            "code": code,
            "trend": result.trend,
            "latest_signal": latest_signal,
            "has_dual_cross": has_dual_cross,
            "dual_cross_date": dual_cross_date,
        }
    except Exception:
        log.debug("单只股票选股分析失败 code=%s level=%s", code, level, exc_info=True)
        return None


# ─── 实时行情 & 基本面 ────────────────────────────────────────────────────────

def _normalize_code(code: str) -> str:
    """统一转换为纯6位数字码，便于跨数据源匹配"""
    code = str(code).strip()
    if code.startswith("sh") or code.startswith("sz") or code.startswith("bj"):
        code = code[2:]
    return code.zfill(6)


def _parse_pe_pb(info: dict) -> tuple[float | None, float | None]:
    pe = info.get("市盈率")
    pb = info.get("市净率")
    try:
        pe_f = float(pe) if pe not in (None, "", 0) else None
    except (TypeError, ValueError):
        pe_f = None
    try:
        pb_f = float(pb) if pb not in (None, "", 0) else None
    except (TypeError, ValueError):
        pb_f = None
    return pe_f, pb_f


def _quotes_from_hot(hot_list: list[dict]) -> dict[str, dict]:
    """从热门池种子行情，避免重复拉全量实时报价。"""
    out: dict[str, dict] = {}
    for item in hot_list:
        code = _normalize_code(str(item.get("code") or ""))
        if not code:
            continue
        out[code] = {
            "price": float(item.get("price") or 0),
            "change_pct": float(item.get("change_pct") or 0),
            "volume": float(item.get("volume") or 0),
            "amount": float(item.get("amount") or 0),
            "name": item.get("name") or code,
            "industry": None,
            "pe": None,
            "pb": None,
        }
    return out


def _quote_map_from_seed(candidates: list[str], seed: dict[str, dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for code in candidates:
        nc = _normalize_code(code)
        base = seed.get(nc, {})
        result[code] = {
            "price": float(base.get("price") or 0),
            "change_pct": float(base.get("change_pct") or 0),
            "volume": float(base.get("volume") or 0),
            "amount": float(base.get("amount") or 0),
            "name": base.get("name") or code,
            "industry": None,
            "pe": None,
            "pb": None,
        }
    return result


def _get_quote_and_info(
    codes: list[str],
    *,
    need_industry_name: bool = False,
    need_pe_pb: bool = False,
    quote_seed: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """
    批量获取实时行情 + 基本面信息。

    need_industry_name: 拉取行业（东方财富板块接口）
    need_pe_pb: 拉取市盈率/市净率（腾讯行情 info 字段）
    quote_seed: 热门池等已有行情时跳过全量实时报价拉取
    """
    result = {}

    if quote_seed is not None:
        for code in codes:
            nc = _normalize_code(code)
            base = quote_seed.get(nc, {})
            result[code] = {
                "price": float(base.get("price") or 0),
                "change_pct": float(base.get("change_pct") or 0),
                "volume": float(base.get("volume") or 0),
                "amount": float(base.get("amount") or 0),
                "name": base.get("name") or code,
                "industry": None,
                "pe": None,
                "pb": None,
            }
    else:
        quotes_df = get_realtime_quote(codes)
        quotes_records = quotes_df.to_dict("records") if not quotes_df.empty else []

        qmap = {}
        for q in quotes_records:
            code_key = _normalize_code(q.get("代码") or q.get("code") or "")
            qmap[code_key] = q

        for code in codes:
            norm_code = _normalize_code(code)
            q = qmap.get(norm_code, {})
            price = float(q.get("最新价") or q.get("price") or 0)
            prev_close = float(q.get("昨收") or q.get("prev_close") or 0)
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0

            result[code] = {
                "price": price,
                "change_pct": round(change_pct, 2),
                "volume": float(q.get("成交量") or q.get("volume") or 0),
                "amount": float(q.get("成交额") or q.get("amount") or 0),
                "name": q.get("名称") or q.get("name") or code,
                "industry": None,
                "pe": None,
                "pb": None,
            }

    if (need_industry_name or need_pe_pb) and codes:
        def fetch_one(code: str) -> tuple[str, str | None, float | None, float | None]:
            industry = None
            pe = pb = None
            try:
                if need_industry_name:
                    boards = get_stock_boards_em(code)
                    industry = boards.get("industry")
                if need_pe_pb:
                    info = get_stock_info(code)
                    pe, pb = _parse_pe_pb(info)
            except Exception:
                log.debug("股票基本面获取失败 code=%s", code, exc_info=True)
            return code, industry, pe, pb

        workers = min(30, len(codes))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for code, ind, pe, pb in pool.map(fetch_one, codes):
                if code in result:
                    if need_industry_name:
                        result[code]["industry"] = ind
                    if need_pe_pb:
                        result[code]["pe"] = pe
                        result[code]["pb"] = pb

    return result


# ─── 主选股函数（生成器版）────────────────────────────────────────────────

def screen_stocks_stream(
    change_pct_min: float | None = None,
    change_pct_max: float | None = None,
    volume_min: float | None = None,
    volume_max: float | None = None,
    industry: str | None = None,
    pe_max: float | None = None,
    pb_max: float | None = None,
    signal_types: list[str] | None = None,
    require_dual_cross: bool = False,
    level: str = "daily",
    pool_size: int = 100,
    max_results: int = 50,
):
    """
    选股主入口（生成器版）。yield 每条符合条件的结果，前端可边算边展示。

    yield dict:
        type: "progress" → { done, total }  进度
        type: "result"   → 选股结果 dict
        type: "done"     → None（全部完成）
    """
    t0 = time.time()

    hot_list = get_daily_hot_stocks(pool_size)
    t1 = time.time()
    log.info("选股候选池获取 count=%s elapsed=%.1fs", len(hot_list), t1 - t0)
    if not hot_list:
        yield {"type": "done", "total": 0}
        return

    candidates = [item["code"] for item in hot_list]
    total = len(candidates)

    need_industry_name = industry is not None
    need_pe_pb = pe_max is not None or pb_max is not None
    seed = _quotes_from_hot(hot_list)
    quote_map = _quote_map_from_seed(candidates, seed)

    # 先用热门池行情做涨跌幅/成交量预过滤，缩小行业/PE 拉取范围
    prefiltered_basic = []
    for code in candidates:
        q = quote_map.get(code, {})
        pct = q.get("change_pct", 0)
        vol = q.get("volume", 0)
        if change_pct_min is not None and pct < change_pct_min:
            continue
        if change_pct_max is not None and pct > change_pct_max:
            continue
        if volume_min is not None and vol < volume_min:
            continue
        if volume_max is not None and vol > volume_max:
            continue
        prefiltered_basic.append(code)

    if (need_industry_name or need_pe_pb) and prefiltered_basic:
        extra = _get_quote_and_info(
            prefiltered_basic,
            need_industry_name=need_industry_name,
            need_pe_pb=need_pe_pb,
            quote_seed=seed,
        )
        for code in prefiltered_basic:
            quote_map[code] = {**quote_map.get(code, {}), **extra.get(code, {})}
    t2 = time.time()
    log.info("选股行情和基本面完成 elapsed=%.1fs", t2 - t1)

    prefiltered = []
    for code in prefiltered_basic:
        q = quote_map.get(code, {})
        if industry is not None and industry not in (q.get("industry") or ""):
            continue
        if pe_max is not None and q.get("pe") is not None and q["pe"] > pe_max:
            continue
        if pb_max is not None and q.get("pb") is not None and q["pb"] > pb_max:
            continue
        prefiltered.append(code)

    if not prefiltered:
        yield {"type": "done", "total": 0}
        return

    yield {"type": "progress", "done": 0, "total": len(prefiltered)}
    t3 = time.time()
    log.info("选股预过滤完成 remaining=%s elapsed=%.1fs", len(prefiltered), t3 - t2)

    workers = min(SCREENING_WORKERS, max(1, len(prefiltered)))
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = {pool.submit(_analyze_stock, c, level): c for c in prefiltered}
    done_count = 0
    emitted_count = 0
    from concurrent.futures import as_completed

    try:
        for future in as_completed(futures):
            code = futures[future]
            done_count += 1
            if done_count % 50 == 0 or done_count == len(prefiltered):
                yield {"type": "progress", "done": done_count, "total": len(prefiltered)}

            try:
                analysis = future.result()
            except Exception:
                log.exception("选股任务执行失败 code=%s level=%s", code, level)
                analysis = None

            if analysis is None:
                continue

            if emitted_count >= max_results:
                continue

            if signal_types:
                if analysis["latest_signal"] is None:
                    continue
                if analysis["latest_signal"].type not in signal_types:
                    continue

            has_dual_cross = analysis["has_dual_cross"]
            dual_cross_date = analysis["dual_cross_date"]
            if require_dual_cross and not has_dual_cross:
                continue

            q = quote_map.get(code, {})
            sig = analysis["latest_signal"]
            sig_date_str = None
            sig_conf = None
            if sig is not None:
                sig_date_str = str(sig.datetime)[:10]
                sig_conf = round(sig.confidence, 2)

            emitted_count += 1
            yield {
                "type": "result",
                "data": {
                    "code": code,
                    "name": q.get("name", code),
                    "price": q.get("price", 0),
                    "change_pct": q.get("change_pct", 0),
                    "volume": q.get("volume", 0),
                    "amount": q.get("amount", 0),
                    "industry": q.get("industry"),
                    "pe": q.get("pe"),
                    "pb": q.get("pb"),
                    "latest_signal": sig.type if sig else None,
                    "latest_signal_date": sig_date_str,
                    "latest_signal_conf": sig_conf,
                    "has_dual_cross": has_dual_cross,
                    "dual_cross_date": dual_cross_date,
                    "trend": analysis["trend"],
                },
            }
            if emitted_count >= max_results:
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
                break
    finally:
        for future in futures:
            future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)

    t4 = time.time()
    log.info("选股完成 done=%s elapsed=%.1fs", done_count, t4 - t3)
    yield {"type": "done", "total": done_count}


def screen_stocks(
    change_pct_min: float | None = None,
    change_pct_max: float | None = None,
    volume_min: float | None = None,
    volume_max: float | None = None,
    industry: str | None = None,
    pe_max: float | None = None,
    pb_max: float | None = None,
    signal_types: list[str] | None = None,
    require_dual_cross: bool = False,
    level: str = "daily",
    pool_size: int = 100,
    max_results: int = 50,
) -> list[dict]:
    """选股主入口（兼容版）。内部调用生成器，等全部算完返回列表。"""
    output = []
    for item in screen_stocks_stream(
        change_pct_min=change_pct_min,
        change_pct_max=change_pct_max,
        volume_min=volume_min,
        volume_max=volume_max,
        industry=industry,
        pe_max=pe_max,
        pb_max=pb_max,
        signal_types=signal_types,
        require_dual_cross=require_dual_cross,
        level=level,
        pool_size=pool_size,
        max_results=max_results,
    ):
        if item["type"] == "result":
            output.append(item["data"])
            if len(output) >= max_results:
                break
    return output
