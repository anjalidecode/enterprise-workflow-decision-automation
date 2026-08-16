"""In-process LLM metrics with low-cardinality labels.

These counters are application-level observability, not a Prometheus deployment.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any

# Allowed label values only — never request ids, user ids, or prompts.
_OPERATIONS = frozenset({"understand", "respond"})
_PROVIDERS = frozenset({"gemini", "deterministic_fallback", "none"})
_STATUSES = frozenset({"success", "error", "timeout", "unavailable", "malformed", "skipped"})

_lock = Lock()
_requests_total: dict[tuple[str, str, str], int] = defaultdict(int)
_failures_total: dict[tuple[str, str], int] = defaultdict(int)
_latency_sum: dict[tuple[str, str], float] = defaultdict(float)
_latency_count: dict[tuple[str, str], int] = defaultdict(int)


def reset_llm_metrics() -> None:
    with _lock:
        _requests_total.clear()
        _failures_total.clear()
        _latency_sum.clear()
        _latency_count.clear()


def record_llm_call(
    *,
    operation: str,
    provider: str,
    status: str,
    duration_seconds: float,
) -> None:
    op = operation if operation in _OPERATIONS else "understand"
    prov = provider if provider in _PROVIDERS else "none"
    st = status if status in _STATUSES else "error"
    with _lock:
        _requests_total[(op, prov, st)] += 1
        _latency_sum[(op, prov)] += max(duration_seconds, 0.0)
        _latency_count[(op, prov)] += 1
        if st in {"error", "timeout", "unavailable", "malformed"}:
            _failures_total[(op, prov)] += 1


def llm_metrics_snapshot() -> dict[str, Any]:
    with _lock:
        requests = [
            {
                "operation": op,
                "provider": prov,
                "status": st,
                "value": value,
            }
            for (op, prov, st), value in sorted(_requests_total.items())
        ]
        failures = [
            {"operation": op, "provider": prov, "value": value}
            for (op, prov), value in sorted(_failures_total.items())
        ]
        latency = []
        for key, total in sorted(_latency_sum.items()):
            count = _latency_count.get(key) or 0
            latency.append(
                {
                    "operation": key[0],
                    "provider": key[1],
                    "count": count,
                    "sum_seconds": round(total, 6),
                    "avg_seconds": round(total / count, 6) if count else 0.0,
                }
            )
    return {
        "llm_requests_total": requests,
        "llm_failures_total": failures,
        "llm_latency_seconds": latency,
    }
