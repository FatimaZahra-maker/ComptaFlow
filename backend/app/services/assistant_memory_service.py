"""Mémoire conversationnelle bornée, isolée par cabinet et utilisateur."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any

from app.core.config import settings


TTL_SECONDS = 1800
MAX_CONVERSATIONS = 500
MAX_RESULT_IDS = 50
_lock = threading.Lock()
_fallback: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_redis_client = None


def _key(cabinet_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID) -> str:
    return f"assistant:conversation:{cabinet_id}:{user_id}:{conversation_id}"


def _redis():
    global _redis_client
    if _redis_client is False:
        return None
    if _redis_client is None:
        try:
            import redis
            client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=0.15, socket_connect_timeout=0.15)
            client.ping()
            _redis_client = client
        except Exception:
            _redis_client = False
    return _redis_client or None


def load(cabinet_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID) -> dict[str, Any]:
    key = _key(cabinet_id, user_id, conversation_id)
    client = _redis()
    if client:
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else {}
        except Exception:
            pass
    now = time.monotonic()
    with _lock:
        value = _fallback.get(key)
        if not value or now - value[0] > TTL_SECONDS:
            _fallback.pop(key, None)
            return {}
        _fallback.move_to_end(key)
        return dict(value[1])


def save(cabinet_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID,
         context: dict[str, Any]) -> None:
    key = _key(cabinet_id, user_id, conversation_id)
    safe = dict(context)
    safe["result_ids"] = [str(value) for value in safe.get("result_ids", [])[:MAX_RESULT_IDS]]
    client = _redis()
    if client:
        try:
            client.setex(key, TTL_SECONDS, json.dumps(safe, default=str))
            return
        except Exception:
            pass
    with _lock:
        _fallback[key] = (time.monotonic(), safe)
        _fallback.move_to_end(key)
        while len(_fallback) > MAX_CONVERSATIONS:
            _fallback.popitem(last=False)
