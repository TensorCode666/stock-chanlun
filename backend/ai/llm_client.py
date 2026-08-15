"""
统一 LLM 客户端 — 支持 DeepSeek 和 Gemini，自动降级
"""
import os
import threading

import httpx
from typing import Optional

from config import DEEPSEEK_MODEL_ID

_llm_http_client: httpx.Client | None = None
_llm_http_lock = threading.RLock()


def _get_llm_http_client() -> httpx.Client:
    global _llm_http_client
    with _llm_http_lock:
        if _llm_http_client is None:
            _llm_http_client = httpx.Client(timeout=60.0)
        return _llm_http_client


class LLMClient:
    """
    DeepSeek（https://platform.deepseek.com） / Gemini（https://ai.google.dev）
    环境变量：
      DEEPSEEK_API_KEY   — DeepSeek API Key
      GEMINI_API_KEY      — Gemini API Key
    """

    def __init__(self, model: str = "deepseek"):
        self.model = model

    # ── DeepSeek ───────────────────────────────────────────────────────────────

    def _deepseek(self, messages: list[dict], **kwargs) -> str:
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请检查 .env 文件")

        body = {
            "model": kwargs.get("model", DEEPSEEK_MODEL_ID),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        client = _get_llm_http_client()
        resp = client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    # ── Gemini ─────────────────────────────────────────────────────────────────

    def _gemini(self, messages: list[dict], **kwargs) -> str:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY 未设置，请检查 .env 文件")

        # 把 messages 转成 Gemini 格式（仅支持 user + model 交替）
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        parts = []
        for m in messages:
            if m["role"] == "system":
                continue
            parts.append({"text": m["content"]})

        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.3),
                "maxOutputTokens": kwargs.get("max_tokens", 1024),
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        # Gemini 模型名映射
        model_map = {
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
        }
        model_id = model_map.get(self.model, "gemini-2.0-flash")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
        client = _get_llm_http_client()
        # 密钥走请求头，避免写入 URL 被代理/访问日志/异常信息捕获
        resp = client.post(url, json=body, headers={"x-goog-api-key": key})
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # ── 统一入口 ───────────────────────────────────────────────────────────────

    def chat(self,
             prompt: str,
             system: str = "",
             **kwargs) -> str:
        """
        发送对话，返回模型原始回复文本。
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            if self.model.startswith("deepseek"):
                return self._deepseek(messages, **kwargs)
            elif self.model.startswith("gemini"):
                return self._gemini(messages, **kwargs)
            else:
                raise ValueError(f"不支持的模型: {self.model}")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LLM HTTP 错误 {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            raise RuntimeError(f"LLM 调用失败: {e}")


# ── 全局单例（按需重新创建）───────────────────────────────────────────────────

_current_model: Optional[str] = None
_llm_client: Optional[LLMClient] = None
_llm_client_lock = threading.RLock()


def get_llm_client(model: Optional[str] = None) -> LLMClient:
    global _current_model, _llm_client
    with _llm_client_lock:
        if model and model != _current_model:
            _llm_client = LLMClient(model=model)
            _current_model = model
        if _llm_client is None:
            _llm_client = LLMClient(model="deepseek")
            _current_model = "deepseek"
        return _llm_client


def set_llm_model(model: str):
    global _current_model, _llm_client
    with _llm_client_lock:
        _llm_client = LLMClient(model=model)
        _current_model = model
