"""
Lightweight custom observability decorator and reporter for agent workflow.
"""

import json
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List

# In-memory metrics log
_METRICS_LOG: List[Dict[str, Any]] = []

def track_agent(agent_name: str) -> Callable:
    """
    Decorator to track execution duration, call status, and state changes for agent nodes.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: Dict[str, Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
            start_time = time.perf_counter()
            start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            sendback_count_start = state.get("sendback_count", 0)
            status = "SUCCESS"
            error_message = None

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
                
                # Capture metrics
                metric_entry = {
                    "agent_name": agent_name,
                    "timestamp": start_timestamp,
                    "duration_seconds": duration_sec,
                    "status": status,
                    "error": error_message,
                    "sendback_count": state.get("sendback_count", sendback_count_start),
                }

                # Capture agent-specific verdicts/outputs if present
                if "qa_verdict" in state:
                    metric_entry["qa_verdict"] = state["qa_verdict"].get("passed")
                    metric_entry["next_agent"] = state["qa_verdict"].get("next_agent")

                _METRICS_LOG.append(metric_entry)

        return wrapper
    return decorator


def save_observability_report(report_dir: str = "report") -> Path:
    """
    Summarizes tracked agent metrics and saves the result to a local JSON file inside the specified folder.
    """
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_duration = sum(item["duration_seconds"] for item in _METRICS_LOG)
    total_calls = len(_METRICS_LOG)
    
    agent_summary: Dict[str, Dict[str, Any]] = {}
    for log in _METRICS_LOG:
        name = log["agent_name"]
        if name not in agent_summary:
            agent_summary[name] = {"calls": 0, "total_time_sec": 0.0, "failures": 0}
        agent_summary[name]["calls"] += 1
        agent_summary[name]["total_time_sec"] = round(
            agent_summary[name]["total_time_sec"] + log["duration_seconds"], 4
        )
        if log["status"] == "FAILED":
            agent_summary[name]["failures"] += 1

    report_payload = {
        "summary": {
            "total_execution_time_sec": round(total_duration, 4),
            "total_agent_calls": total_calls,
            "agent_breakdown": agent_summary,
        },
        "detailed_logs": _METRICS_LOG,
    }

    report_file = output_dir / f"agent_observability_{int(time.time())}.json"
    report_file.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    return report_file