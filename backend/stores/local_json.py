"""
自选、笔记、系统设置的 JSON 持久化。
单进程内用 RLock 保护读改写；写入使用临时文件 + os.replace 尽量原子化。
多 worker / 多机部署时各进程状态不一致——仅适合单机或文档化约束下的部署。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

_WATCHLIST_FILE = _BACKEND_ROOT / "watchlist.json"
_COMMENTS_FILE = _BACKEND_ROOT / "comments.json"
_SETTINGS_FILE = _BACKEND_ROOT / "settings.json"

_watchlist_lock = threading.RLock()
_comments_lock = threading.RLock()
_settings_lock = threading.RLock()

_watchlist: dict[str, str] = {}
_comments: dict[str, list[dict]] = {}


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_watchlist_from_disk() -> dict[str, str]:
    try:
        if _WATCHLIST_FILE.exists():
            data = json.loads(_WATCHLIST_FILE.read_text(encoding="utf-8"))
            return {str(k).zfill(6): str(v) for k, v in data.items() if str(k).strip()}
    except Exception as e:
        log.warning("自选股加载失败: %s", e)
    return {}


def _load_comments_from_disk() -> dict[str, list[dict]]:
    try:
        if _COMMENTS_FILE.exists():
            return json.loads(_COMMENTS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("评论加载失败: %s", e)
    return {}


def init_stores() -> None:
    """模块导入后初始化内存缓存（main 启动时也可再次调用）。"""
    global _watchlist, _comments
    with _watchlist_lock:
        _watchlist = _load_watchlist_from_disk()
    with _comments_lock:
        _comments = _load_comments_from_disk()


def get_watchlist_map() -> dict[str, str]:
    with _watchlist_lock:
        return dict(_watchlist)


def watchlist_add(sym: str) -> tuple[str, bool]:
    """返回 (iso_time, was_new)."""
    from datetime import datetime

    with _watchlist_lock:
        if sym in _watchlist:
            return _watchlist[sym], False
        _watchlist[sym] = datetime.now().isoformat()
        _atomic_write_json(_WATCHLIST_FILE, _watchlist)
        return _watchlist[sym], True


def watchlist_remove(sym: str) -> bool:
    with _watchlist_lock:
        if sym not in _watchlist:
            return False
        del _watchlist[sym]
        _atomic_write_json(_WATCHLIST_FILE, _watchlist)
        return True


def comments_get(sym: str) -> list[dict]:
    with _comments_lock:
        return list(_comments.get(sym, []))


def comments_add(sym: str, comment: dict) -> None:
    with _comments_lock:
        if sym not in _comments:
            _comments[sym] = []
        _comments[sym].append(comment)
        _atomic_write_json(_COMMENTS_FILE, _comments)


def comments_update(sym: str, comment_id: str, new_content: str, updated_iso: str) -> bool:
    with _comments_lock:
        items = _comments.get(sym, [])
        for c in items:
            if c.get("id") == comment_id:
                c["content"] = new_content
                c["updatedAt"] = updated_iso
                _atomic_write_json(_COMMENTS_FILE, _comments)
                return True
        return False


def comments_delete(sym: str, comment_id: str) -> bool:
    with _comments_lock:
        items = _comments.get(sym, [])
        n = len(items)
        items = [c for c in items if c.get("id") != comment_id]
        if len(items) == n:
            return False
        _comments[sym] = items
        _atomic_write_json(_COMMENTS_FILE, _comments)
        return True


def load_settings() -> dict:
    with _settings_lock:
        try:
            if _SETTINGS_FILE.exists():
                return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("设置加载失败: %s", e)
        return {"ai_model": "deepseek"}


def save_settings(s: dict) -> None:
    with _settings_lock:
        _atomic_write_json(_SETTINGS_FILE, s)


def apply_startup_ai_model() -> None:
    from ai.llm_client import set_llm_model

    try:
        settings = load_settings()
        model = settings.get("ai_model", "deepseek")
        set_llm_model(model)
        log.info("AI 模型已恢复: %s", model)
    except Exception:
        log.debug("启动时恢复 AI 模型失败", exc_info=True)


init_stores()
