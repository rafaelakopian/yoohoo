"""Prometheus metrics for HTTP requests and background jobs."""

from prometheus_client import Counter, Histogram, Info

# --- HTTP Metrics ---

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path_template"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP errors (4xx and 5xx)",
    ["method", "path_template", "status_code"],
)

# --- Background Job Metrics ---

job_started_total = Counter(
    "job_started_total",
    "Background jobs started",
    ["job_name"],
)

job_completed_total = Counter(
    "job_completed_total",
    "Background jobs completed successfully",
    ["job_name"],
)

job_failed_total = Counter(
    "job_failed_total",
    "Background jobs failed (including retries)",
    ["job_name"],
)

job_dead_letter_total = Counter(
    "job_dead_letter_total",
    "Background jobs that exhausted all retries",
    ["job_name"],
)

# --- App Info ---

app_info = Info("yoohoo", "Yoohoo SaaS platform info")
