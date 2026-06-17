"""Prometheus metrics for the University Agent service.

All metrics are declared here and imported by main.py and react_agent.py
to keep a single source of truth.
"""

from prometheus_client import Counter, Gauge, Histogram

# ── Counters ────────────────────────────────────────────────────────────────

chat_requests_total = Counter(
    "unibot_chat_requests_total",
    "Total chat requests",
    ["status"],  # "success" | "error"
)

tool_calls_total = Counter(
    "unibot_tool_calls_total",
    "Agent tool invocations",
    ["tool_name"],
)

voice_requests_total = Counter(
    "unibot_voice_requests_total",
    "Voice upload requests",
    ["status"],  # "success" | "error"
)

token_usage_total = Counter(
    "unibot_token_usage_total",
    "Total LLM tokens consumed",
    ["type"],  # "prompt" | "completion"
)

# ── Histograms ──────────────────────────────────────────────────────────────

chat_latency = Histogram(
    "unibot_chat_latency_seconds",
    "Chat request end-to-end latency",
    buckets=[0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0],
)

# ── Gauges ──────────────────────────────────────────────────────────────────

active_requests = Gauge(
    "unibot_active_requests",
    "Currently in-flight requests",
)
