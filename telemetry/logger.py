"""
Local Telemetry Logger for Mac-Control.
Persists structured traces to data/telemetry/traces.jsonl for analysis and agent improvisation.
"""

import os
import json
import threading
from typing import List, Dict, Any, Optional
from telemetry.models import TelemetryTrace

DEFAULT_TELEMETRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "telemetry", "traces.jsonl"
)

class TelemetryLogger:
    _instance: Optional["TelemetryLogger"] = None
    _lock = threading.Lock()

    def __init__(self, log_path: str = DEFAULT_TELEMETRY_PATH):
        self.log_path = log_path
        self._write_lock = threading.Lock()
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    @classmethod
    def get_instance(cls, log_path: str = DEFAULT_TELEMETRY_PATH) -> "TelemetryLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = TelemetryLogger(log_path=log_path)
            return cls._instance

    def log_trace(self, trace: TelemetryTrace) -> None:
        """Appends a single structured trace to JSONL file."""
        data = trace.to_dict()
        line = json.dumps(data) + "\n"
        with self._write_lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception as e:
                print(f"[TelemetryLogger Error] Failed to write trace: {e}")

    def read_traces(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Reads all traces from disk, optionally limited to the most recent 'limit' records."""
        if not os.path.exists(self.log_path):
            return []
        traces = []
        with self._write_lock:
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            traces.append(json.loads(line))
            except Exception as e:
                print(f"[TelemetryLogger Error] Failed to read traces: {e}")
        if limit and len(traces) > limit:
            return traces[-limit:]
        return traces

    def get_summary(self) -> Dict[str, Any]:
        """Calculates high-level telemetry statistics including SLA and Cost determination."""
        traces = self.read_traces()
        total = len(traces)
        if total == 0:
            return {"total_traces": 0, "status": "no_data"}

        success_count = sum(1 for t in traces if t.get("status") in ["executed", "executed_from_memory", "awake_ready", "chat_answered"])
        rejected_count = sum(1 for t in traces if t.get("status") == "rejected")
        unresolved_count = sum(1 for t in traces if t.get("status") == "unresolved")
        confirmation_count = sum(1 for t in traces if t.get("status") in ["confirmation_requested", "confirmation_processed"])
        sleeping_count = sum(1 for t in traces if t.get("status") == "sleeping")

        latencies = sorted([t.get("latency_ms", {}).get("total", 0.0) for t in traces if t.get("latency_ms", {}).get("total", 0.0) > 0])
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
        p99 = latencies[-1] if latencies else 0.0

        # SLA Compliance (<2000ms target, <1000ms sub-second target)
        sla_compliant = sum(1 for lat in latencies if lat <= 2000.0)
        sub_second = sum(1 for lat in latencies if lat <= 1000.0)
        sla_pct = round((sla_compliant / len(latencies)) * 100, 2) if latencies else 100.0
        sub_second_pct = round((sub_second / len(latencies)) * 100, 2) if latencies else 100.0

        # Cost & Token Accounting
        total_tokens = sum(t.get("cost", {}).get("tokens_total", 0) for t in traces)
        total_cost_usd = sum(t.get("cost", {}).get("cost_usd", 0.0) for t in traces)
        total_saved_usd = sum(t.get("cost", {}).get("estimated_cloud_cost_saved_usd", 0.0) for t in traces)

        # Tier breakdown
        tier_counts = {}
        for t in traces:
            tier_name = t.get("tier_name", "unknown")
            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

        return {
            "total_traces": total,
            "success_count": success_count,
            "rejected_count": rejected_count,
            "unresolved_count": unresolved_count,
            "confirmation_count": confirmation_count,
            "sleeping_count": sleeping_count,
            "success_rate_pct": round((success_count / total) * 100, 2) if total else 0.0,
            "latency": {
                "average_ms": round(avg_latency, 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
                "sla_target_ms": 2000.0,
                "sla_compliant_pct": sla_pct,
                "sub_second_pct": sub_second_pct
            },
            "cost_metrics": {
                "total_tokens_processed": total_tokens,
                "actual_cost_usd": round(total_cost_usd, 6),
                "estimated_cloud_cost_saved_usd": round(total_saved_usd, 6),
                "free_tier_enforced": True
            },
            "tier_distribution": tier_counts
        }
