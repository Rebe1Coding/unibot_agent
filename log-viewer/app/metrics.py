from prometheus_client import Counter, Gauge, Histogram

requests_total = Counter(
    "logviewer_requests_total",
    "Total HTTP requests handled by log-viewer",
    ["method", "endpoint", "status"],
)

request_latency = Histogram(
    "logviewer_request_latency_seconds",
    "Log-viewer request latency",
    ["method", "endpoint"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

active_streams = Gauge(
    "logviewer_active_streams",
    "Number of active SSE log streams",
)

streamed_lines_total = Counter(
    "logviewer_streamed_lines_total",
    "Total log lines streamed to clients",
    ["container", "stream"],
)

docker_errors_total = Counter(
    "logviewer_docker_errors_total",
    "Total errors encountered while talking to Docker daemon",
    ["operation"],
)
