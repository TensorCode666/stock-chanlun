from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException, Query, Request

from ai.analysis_agent import SYSTEM_PROMPT, build_analysis_prompt, parse_llm_response
from ai.divergence import DivergenceDetector
from ai.llm_client import get_llm_client
from ai.strategy_engine import StrategyEngine
from ai.wave_classifier import WaveClassifier
from chanlun.elements import ChanlunAnalysis
from core.chanlun_analysis import (
    DEFAULT_KLINE_LIMIT,
    chanlun_cache_key,
    get_kline_df_for_ai,
    run_analysis,
)
from core.chanlun_response import serialize_chanlun_analysis
from deps import check_chanlun_rate_limits, client_ip
from utils import ai_signal_llm_cache, ai_signal_rule_cache, chanlun_cache, chanlun_multi_cache

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/api/chanlun/{code}", tags=["缠论"], summary="缠论完整分析")
async def analyze_chanlun(
    request: Request,
    code: str,
    level: str = Query(
        "daily",
        pattern="^(1min|5min|15min|30min|60min|daily|weekly|monthly)$",
    ),
):
    check_chanlun_rate_limits(client_ip(request))
    result = await asyncio.to_thread(run_analysis, code, level)
    return serialize_chanlun_analysis(result)


@router.get("/api/chanlun/{code}/multi-level", tags=["缠论"], summary="多级别并行缠论分析")
async def chanlun_multi_level(
    request: Request,
    code: str,
    levels: str = Query(
        "daily,weekly,30min",
        description="逗号分隔的分析级别，如 daily,weekly,30min",
    ),
):
    level_list = [l.strip() for l in levels.split(",") if l.strip()]
    level_list = list(dict.fromkeys(level_list))
    check_chanlun_rate_limits(client_ip(request), tokens=min(len(level_list), 4))

    cache_key = f"multi:{code}:{','.join(level_list)}"
    cached = chanlun_multi_cache.get(cache_key)
    if cached is not None:
        return cached

    t0 = time.time()

    def _serialize_result(result: ChanlunAnalysis) -> dict:
        return {
            "level": result.level,
            "trend": result.trend,
            "summary": result.summary,
            "bis_count": len(result.bis),
            "zhongshus_count": len(result.zhongshus),
            "signals_count": len(result.signals),
            "signals": [
                {
                    "type": s.type,
                    "price": s.price,
                    "datetime": str(s.datetime)[:19],
                    "confidence": s.confidence,
                    "description": s.description,
                }
                for s in result.signals[-3:]
            ],
            "supportResistance": [
                {
                    "type": lvl.type,
                    "price": lvl.price,
                    "datetime": str(lvl.datetime)[:19],
                    "strength": lvl.strength,
                }
                for lvl in result.support_resistance[-5:]
            ],
        }

    results: dict[str, dict | str] = {}

    def _safe_analyze(level: str) -> tuple[str, dict | str]:
        try:
            result = run_analysis(code, level, kline_limit=DEFAULT_KLINE_LIMIT)
            return level, _serialize_result(result)
        except HTTPException:
            return level, "数据不足"
        except Exception:
            log.debug("多级别缠论分析失败 code=%s level=%s", code, level, exc_info=True)
            return level, "数据不足"

    def _run_pool():
        with ThreadPoolExecutor(max_workers=min(len(level_list), 4)) as pool:
            futures = {pool.submit(_safe_analyze, lv): lv for lv in level_list}
            for future in as_completed(futures):
                lv, data = future.result(timeout=60)
                results[lv] = data

    await asyncio.to_thread(_run_pool)

    ordered = {lv: results.get(lv, "未知错误") for lv in level_list}
    t1 = time.time()
    payload = {
        "code": code,
        "levels": ordered,
        "count": len(level_list),
        "elapsed_ms": round((t1 - t0) * 1000, 1),
    }
    chanlun_multi_cache.set(cache_key, payload)
    return payload


def _ai_signal_cache_key(code: str, level: str, model: str, use_llm: bool) -> str:
    return f"ai:{code}:{level}:{model}:{'llm' if use_llm else 'rule'}"


def build_ai_signal_response(code: str, level: str, model: str, use_llm: bool) -> dict:
    """规则策略 + 可选 LLM；供线程池与缓存复用。"""
    df_for_ai, result = get_kline_df_for_ai(code, level)
    current_price = float(result.klines[-1].close) if result.klines else 0.0

    divergence = None
    if not df_for_ai.empty:
        try:
            div_detector = DivergenceDetector(df_for_ai.tail(200))
            divergence = div_detector.check_divergence(result.bis)
        except Exception:
            log.debug("背驰检测失败 code=%s", code, exc_info=True)

    classifier = WaveClassifier()
    wave_class = classifier.classify(result.xiangs, result.zhongshus, current_price)

    engine = StrategyEngine(
        signals=result.signals,
        trend=wave_class["trend"],
        current_price=current_price,
        current_level=level,
        zhongshus=result.zhongshus,
        divergence=divergence,
    )
    signal = engine.generate_signal()
    signal.stock_code = code

    resonance = None
    if level == "30min":
        try:
            daily_key = chanlun_cache_key(code, "daily", DEFAULT_KLINE_LIMIT)
            daily_result = chanlun_cache.get(daily_key)
            if daily_result is None:
                daily_result = run_analysis(code, "daily", kline_limit=DEFAULT_KLINE_LIMIT)
                chanlun_cache.set(daily_key, daily_result)
            if daily_result is not None:
                daily_cls = WaveClassifier().classify(
                    daily_result.xiangs,
                    daily_result.zhongshus,
                    float(daily_result.klines[-1].close) if daily_result.klines else 0.0,
                )
                resonance = classifier.multi_level_resonance(
                    [
                        {"trend": wave_class, "level": level},
                        {"trend": daily_cls, "level": "daily"},
                    ]
                )
        except Exception:
            log.debug("多级别共振计算失败 code=%s", code, exc_info=True)

    llm_result = None
    llm_error = None
    if use_llm:
        try:
            llm = get_llm_client(model)
            prompt = build_analysis_prompt(
                code=code,
                level=level,
                klines=[k.__dict__ for k in result.klines],
                trend=wave_class["trend"],
                divergence=divergence,
                signals=[s.__dict__ for s in result.signals],
                zhongshus=[z.__dict__ for z in result.zhongshus],
                bis=[b.__dict__ for b in result.bis],
            )
            raw = llm.chat(prompt, system=SYSTEM_PROMPT, temperature=0.3)
            llm_result = parse_llm_response(raw)
            if not isinstance(llm_result, dict):
                llm_result = None
                llm_error = "LLM 解析结果非对象"
        except Exception as e:
            llm_error = str(e)
            log.warning("LLM 策略生成失败 code=%s model=%s: %s", code, model, e)

    lr = llm_result if isinstance(llm_result, dict) else None

    return {
        "stock_code": signal.stock_code,
        "level": signal.level,
        "direction": (lr.get("direction") if lr else None) or signal.direction,
        "confidence": lr["confidence"] if lr and "confidence" in lr else signal.confidence,
        "risk_level": (lr.get("risk_level") if lr else None) or signal.risk_level,
        "entry_price": (lr.get("entry_price") if lr else None) or signal.entry_price,
        "stop_loss": (lr.get("stop_loss") if lr else None) or signal.stop_loss,
        "take_profit": (lr.get("take_profit") if lr else None) or signal.take_profit,
        "holding_period": (lr.get("holding_period") if lr else None) or signal.holding_period,
        "description": (lr.get("reasoning") if lr else None) or signal.description,
        "trend": wave_class["trend"],
        "divergence": divergence,
        "resonance": resonance,
        "llm": {
            "model": model,
            "used": lr is not None and llm_error is None,
            "error": llm_error,
            "skipped": not use_llm,
        },
    }


@router.get("/api/chanlun/{code}/ai", tags=["缠论"], summary="AI 策略信号（背驰 + 规则 + 可选 LLM）")
async def ai_signal(
    request: Request,
    code: str,
    level: str = Query("daily"),
    model: str = Query("deepseek", description="AI 模型：deepseek / gemini"),
    use_llm: bool = Query(
        False,
        description="为 true 时调用大模型增强；默认仅规则引擎，响应更快",
    ),
):
    check_chanlun_rate_limits(client_ip(request))

    cache_key = _ai_signal_cache_key(code, level, model, use_llm)
    cache = ai_signal_llm_cache if use_llm else ai_signal_rule_cache
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        payload = await asyncio.to_thread(build_ai_signal_response, code, level, model, use_llm)
        cache.set(cache_key, payload)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI 策略生成失败: {e!s}",
        ) from e
