"""Low-cardinality notification metrics (mirrors LLM metrics style)."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any

_EVENT_TYPES = frozenset(
    {
        "USER_REGISTERED",
        "USER_INVITED",
        "WORKFLOW_PENDING_APPROVAL",
        "WORKFLOW_APPROVED",
        "WORKFLOW_REJECTED",
        "WORKFLOW_COMPLETED",
        "WORKFLOW_BLOCKED",
    }
)
_PROVIDERS = frozenset({"console", "smtp", "none"})
_STATUSES = frozenset({"sent", "generated", "failed", "skipped", "pending"})

_lock = Lock()
_sent_total: dict[tuple[str, str, str], int] = defaultdict(int)
_failed_total: dict[tuple[str, str], int] = defaultdict(int)
_latency_sum: dict[tuple[str, str], float] = defaultdict(float)
_latency_count: dict[tuple[str, str], int] = defaultdict(int)


def reset_notification_metrics() -> None:
    with _lock:
        _sent_total.clear()
        _failed_total.clear()
        _latency_sum.clear()
        _latency_count.clear()


def record_notification(
    *,
    provider: str,
    event_type: str,
    status: str,
    duration_seconds: float = 0.0,
) -> None:
    prov = provider if provider in _PROVIDERS else "none"
    et = event_type if event_type in _EVENT_TYPES else "USER_REGISTERED"
    st = status if status in _STATUSES else "failed"
    with _lock:
        _sent_total[(prov, et, st)] += 1
        _latency_sum[(prov, et)] += max(duration_seconds, 0.0)
        _latency_count[(prov, et)] += 1
        if st == "failed":
            _failed_total[(prov, et)] += 1


def notification_metrics_snapshot() -> dict[str, Any]:
    with _lock:
        sent = [
            {"provider": p, "event_type": e, "status": s, "value": v}
            for (p, e, s), v in sorted(_sent_total.items())
        ]
        failed = [
            {"provider": p, "event_type": e, "value": v}
            for (p, e), v in sorted(_failed_total.items())
        ]
        latency = []
        for key, total in sorted(_latency_sum.items()):
            count = _latency_count.get(key) or 0
            latency.append(
                {
                    "provider": key[0],
                    "event_type": key[1],
                    "count": count,
                    "sum_seconds": round(total, 6),
                    "avg_seconds": round(total / count, 6) if count else 0.0,
                }
            )
    return {
        "notification_sent_total": sent,
        "notification_failed_total": failed,
        "notification_latency_seconds": latency,
    }
