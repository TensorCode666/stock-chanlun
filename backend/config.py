"""Runtime configuration from environment (loaded before HTTP patches)."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _truthy(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if v == "":
        return default
    return v in ("1", "true", "yes", "on")


# Comma-separated origins, or "*" for any origin (browser credentials disabled)
CORS_ORIGINS_RAW: str = os.environ.get("CORS_ORIGINS", "*").strip()

# When True: disable TLS verification for patched finance HTTP (legacy Windows/proxy setups)
FINANCE_TLS_RELAXED: bool = _truthy("FINANCE_TLS_RELAXED", default=False)

# When True: trust the X-Forwarded-For header for client IP (rate limiting).
# Only enable behind a trusted reverse proxy (e.g. Railway/nginx) that overwrites it;
# otherwise any client can spoof the header to bypass per-IP rate limits.
TRUST_X_FORWARDED_FOR: bool = _truthy("TRUST_X_FORWARDED_FOR", default=False)

# DeepSeek Chat Completions 模型 ID（诊股 SSE、策略 LLM 等）
# https://api.deepseek.com — 当前推荐 deepseek-v4-pro
DEEPSEEK_MODEL_ID: str = os.environ.get("DEEPSEEK_MODEL_ID", "deepseek-v4-pro").strip() or "deepseek-v4-pro"

# 选股缠论并发（默认 12，可通过环境变量调低以减轻行情源压力）
SCREENING_WORKERS: int = max(1, min(32, int(os.environ.get("SCREENING_WORKERS", "12") or "12")))

# 后端默认监听端口（run_server.py 与 python main.py 均读取）
PORT: int = max(1, min(65535, int(os.environ.get("PORT", "8010") or "8010")))


def cors_allow_origins() -> list[str]:
    if CORS_ORIGINS_RAW == "*":
        return ["*"]
    parts = [p.strip() for p in CORS_ORIGINS_RAW.split(",") if p.strip()]
    return parts if parts else ["*"]


def cors_allow_credentials() -> bool:
    # Browsers reject credentials with wildcard origins
    return cors_allow_origins() != ["*"]
