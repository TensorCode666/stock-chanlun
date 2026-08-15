"""FastAPI dependencies: client IP and rate-limit guards."""
from __future__ import annotations

from fastapi import HTTPException, Request

from config import TRUST_X_FORWARDED_FOR
from utils import (
    ai_diagnosis_global_limiter,
    ai_diagnosis_ip_limiter,
    chanlun_global_limiter,
    chanlun_ip_limiter,
    kline_global_limiter,
    kline_ip_limiter,
    light_global_limiter,
    light_ip_limiter,
)


def client_ip(request: Request) -> str:
    # 仅在可信反向代理之后（TRUST_X_FORWARDED_FOR=1）才信任 XFF 头，
    # 否则客户端可伪造该头绕过每 IP 限流。
    if TRUST_X_FORWARDED_FOR:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def check_chanlun_rate_limits(ip: str, tokens: int = 1) -> None:
    """Global + per-IP limits for 缠论 / AI 策略 / 选股等重计算接口."""
    tokens = max(1, min(tokens, 8))
    if not chanlun_global_limiter.try_acquire("global", tokens):
        raise HTTPException(status_code=429, detail="服务繁忙，请稍后重试")
    if not chanlun_ip_limiter.try_acquire(ip, tokens):
        raise HTTPException(
            status_code=429,
            detail="缠论分析请求过于频繁，请稍后再试",
        )


def check_screening_rate_limits(ip: str) -> None:
    """选股接口：消耗更多令牌（与并发缠论分析成本对齐）。"""
    check_chanlun_rate_limits(ip, tokens=3)


def check_kline_rate_limits(ip: str) -> None:
    """Global + per-IP limits for K 线 / 导出等行情拉取接口."""
    if not kline_global_limiter.try_acquire("global"):
        raise HTTPException(status_code=429, detail="行情服务繁忙，请稍后重试")
    if not kline_ip_limiter.try_acquire(ip):
        raise HTTPException(
            status_code=429,
            detail="K 线请求过于频繁，请稍后再试",
        )


def check_light_api_rate_limits(ip: str) -> None:
    """搜索 / 热门 / 新闻 / 评论等轻量读接口。"""
    if not light_global_limiter.try_acquire("global"):
        raise HTTPException(status_code=429, detail="服务繁忙，请稍后重试")
    if not light_ip_limiter.try_acquire(ip):
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试",
        )


def check_ai_diagnosis_rate_limits(ip: str) -> None:
    if not ai_diagnosis_global_limiter.try_acquire("global"):
        raise HTTPException(status_code=429, detail="AI 诊股服务繁忙，请稍后重试")
    if not ai_diagnosis_ip_limiter.try_acquire(ip):
        raise HTTPException(
            status_code=429,
            detail="AI 诊股请求过于频繁，请稍后再试",
        )
