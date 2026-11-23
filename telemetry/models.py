"""
Telemetry & Distributed Tracing Data Models for Mac-Control.
Provides OpenTelemetry-style Trace Spans, Latency SLA Auditing, and Cost Metric Determination.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
import time
import uuid

@dataclass
class TraceSpan:
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:6])
    name: str = "unnamed_span"
    start_time: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    status: str = "ok"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "ok", extra_metadata: Optional[Dict[str, Any]] = None):
        self.duration_ms = (time.time() - self.start_time) * 1000
        self.status = status
        if extra_metadata:
            self.metadata.update(extra_metadata)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class CostMetrics:
    tokens_prompt: int = 0
    tokens_completion: int = 0
    tokens_total: int = 0
    model_name: str = "local"
    compute_provider: str = "local_apple_silicon"  # "local_apple_silicon", "openrouter_free"
    cost_usd: float = 0.000000                     # USD cost (strictly $0.00 for free/local)
    is_free_tier: bool = True
    estimated_cloud_cost_saved_usd: float = 0.0    # What commercial APIs (e.g. GPT-4o) would have cost

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str, provider: str = "local"):
        self.tokens_prompt = prompt_tokens
        self.tokens_completion = completion_tokens
        self.tokens_total = prompt_tokens + completion_tokens
        self.model_name = model
        self.compute_provider = provider

        # Strict policy: local and :free models are $0.000000
        if provider == "local" or model.endswith(":free"):
            self.cost_usd = 0.000000
            self.is_free_tier = True
            # Estimated commercial savings ($2.50 per 1M prompt, $10.00 per 1M completion)
            self.estimated_cloud_cost_saved_usd = (prompt_tokens * 2.50 / 1_000_000) + (completion_tokens * 10.0 / 1_000_000)
        else:
            # Theoretical paid rate if user deliberately unlocked a paid tier
            self.is_free_tier = False
            self.cost_usd = (prompt_tokens * 2.50 / 1_000_000) + (completion_tokens * 10.0 / 1_000_000)
            self.estimated_cloud_cost_saved_usd = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class TelemetryTrace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    iso_time: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    raw_input: str = ""
    normalized_input: str = ""
    agent_state_before: str = "sleeping"
    agent_state_after: str = "sleeping"
    wake_word_detected: bool = False
    conversational_followup: bool = False
    intent_tier: Optional[float] = None
    tier_name: str = "unknown"
    action_name: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None
    safety_verdict: str = "allowed"
    status: str = "pending"
    spoken_feedback: Optional[str] = None
    latency_ms: Dict[str, float] = field(default_factory=dict)
    sla_target_ms: float = 2000.0   # SLA target: 2000ms max latency
    sla_violated: bool = False
    error: Optional[str] = None
    spans: List[Dict[str, Any]] = field(default_factory=list)
    cost: Dict[str, Any] = field(default_factory=lambda: CostMetrics().to_dict())

    def start_span(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> TraceSpan:
        span = TraceSpan(name=name, metadata=metadata or {})
        return span

    def record_span(self, span: TraceSpan):
        self.spans.append(span.to_dict())

    def finalize(self):
        total = self.latency_ms.get("total", 0.0)
        self.sla_violated = total > self.sla_target_ms

    def to_dict(self) -> Dict[str, Any]:
        self.finalize()
        return asdict(self)
