"""
Module: async_observability.py
Purpose: Asynchronous token and metrics tracking decorator for agent nodes.
Owner: Observability Lead
Depends on: observability
"""

import inspect
import json
import time
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List

# In-memory metrics log
_METRICS_LOG: List[Dict[str, Any]] = []

# Context variable to hold active token usage for the running agent node
_CURRENT_NODE_TOKENS: ContextVar[Dict[str, int]] = ContextVar(
    "_CURRENT_NODE_TOKENS",
    default={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
)

def record_token_usage(prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0) -> None:
    """Helper function to record token usage within the current agent run context."""
    current = _CURRENT_NODE_TOKENS.get().copy()
    current["prompt_tokens"] += prompt_tokens
    current["completion_tokens"] += completion_tokens
    current["total_tokens"] += total_tokens or (prompt_tokens + completion_tokens)
    _CURRENT_NODE_TOKENS.set(current)


def track_agent(agent_name: str) -> Callable:
    """
    Decorator supporting both sync and async agent nodes to track execution duration, 
    call status, state changes, and token usage.
    """
    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(state: Dict[str, Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
                start_time = time.perf_counter()
                start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                sendback_count_start = state.get("sendback_count", 0)
                status = "SUCCESS"
                error_message = None

                # Isolated token context for this async node run
                token_reset_token = _CURRENT_NODE_TOKENS.set(
                    {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                )

                try:
                    result = await func(state, *args, **kwargs)
                    return result
                except Exception as exc:
                    status = "FAILED"
                    error_message = str(exc)
                    raise exc
                finally:
                    end_time = time.perf_counter()
                    duration_sec = round(end_time - start_time, 4)
                    tokens_used = _CURRENT_NODE_TOKENS.get()

                    metric_entry = {
                        "agent_name": agent_name,
                        "timestamp": start_timestamp,
                        "duration_seconds": duration_sec,
                        "status": status,
                        "error": error_message,
                        "sendback_count": state.get("sendback_count", sendback_count_start),
                        "token_usage": tokens_used,
                    }

                    if "qa_verdict" in state:
                        metric_entry["qa_verdict"] = state["qa_verdict"].get("passed")
                        metric_entry["next_agent"] = state["qa_verdict"].get("next_agent")

                    _METRICS_LOG.append(metric_entry)
                    _CURRENT_NODE_TOKENS.reset(token_reset_token)

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(state: Dict[str, Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
                start_time = time.perf_counter()
                start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                sendback_count_start = state.get("sendback_count", 0)
                status = "SUCCESS"
                error_message = None

                token_reset_token = _CURRENT_NODE_TOKENS.set(
                    {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                )

                try:
                    result = func(state, *args, **kwargs)
                    return result
                except Exception as exc:
                    status = "FAILED"
                    error_message = str(exc)
                    raise exc
                finally:
                    end_time = time.perf_counter()
                    duration_sec = round(end_time - start_time, 4)
                    tokens_used = _CURRENT_NODE_TOKENS.get()

                    metric_entry = {
                        "agent_name": agent_name,
                        "timestamp": start_timestamp,
                        "duration_seconds": duration_sec,
                        "status": status,
                        "error": error_message,
                        "sendback_count": state.get("sendback_count", sendback_count_start),
                        "token_usage": tokens_used,
                    }

                    if "qa_verdict" in state:
                        metric_entry["qa_verdict"] = state["qa_verdict"].get("passed")
                        metric_entry["next_agent"] = state["qa_verdict"].get("next_agent")

                    _METRICS_LOG.append(metric_entry)
                    _CURRENT_NODE_TOKENS.reset(token_reset_token)

            return sync_wrapper

    return decorator


def save_observability_report(report_dir: str = "report") -> Path:
    """Summarizes tracked agent metrics including token usage and saves to JSON."""
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_duration = sum(item["duration_seconds"] for item in _METRICS_LOG)
    total_calls = len(_METRICS_LOG)
    total_tokens_used = sum(item["token_usage"]["total_tokens"] for item in _METRICS_LOG)
    total_prompt_tokens = sum(item["token_usage"]["prompt_tokens"] for item in _METRICS_LOG)
    total_completion_tokens = sum(item["token_usage"]["completion_tokens"] for item in _METRICS_LOG)

    agent_summary: Dict[str, Dict[str, Any]] = {}
    for log in _METRICS_LOG:
        name = log["agent_name"]
        if name not in agent_summary:
            agent_summary[name] = {
                "calls": 0,
                "total_time_sec": 0.0,
                "failures": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        agent_summary[name]["calls"] += 1
        agent_summary[name]["total_time_sec"] = round(
            agent_summary[name]["total_time_sec"] + log["duration_seconds"], 4
        )
        if log["status"] == "FAILED":
            agent_summary[name]["failures"] += 1
        
        agent_summary[name]["prompt_tokens"] += log["token_usage"]["prompt_tokens"]
        agent_summary[name]["completion_tokens"] += log["token_usage"]["completion_tokens"]
        agent_summary[name]["total_tokens"] += log["token_usage"]["total_tokens"]

    report_payload = {
        "summary": {
            "total_execution_time_sec": round(total_duration, 4),
            "total_agent_calls": total_calls,
            "total_tokens": {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens_used,
            },
            "agent_breakdown": agent_summary,
        },
        "detailed_logs": _METRICS_LOG,
    }

    report_file = output_dir / f"agent_observability_{int(time.time())}.json"
    report_file.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    return report_file