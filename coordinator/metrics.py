"""
Prometheus Observability Exporter — Fault-Tolerant Storage System
Exporting standardized metrics on /metrics endpoint.
"""

import time
import threading
from typing import Dict

class MetricsRegistry:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.lock = threading.Lock()
        self.counters: Dict[str, float] = {
            "http_requests_total": 0.0,
            "files_stored_total": 0.0,
            "files_downloaded_total": 0.0,
            "encryption_ops_total": 0.0,
            "erasure_reconstructions_total": 0.0,
            "security_blocks_total": 0.0,
            "ai_anomalies_total": 0.0,
            "active_nodes_count": 3.0
        }
        self.start_time = time.time()

    def inc(self, metric_name: str, amount: float = 1.0):
        with self.lock:
            if metric_name in self.counters:
                self.counters[metric_name] += amount
            else:
                self.counters[metric_name] = amount

    def set(self, metric_name: str, value: float):
        with self.lock:
            self.counters[metric_name] = value

    def generate_prometheus_exposition(self) -> str:
        with self.lock:
            uptime = time.time() - self.start_time
            lines = [
                f"# HELP fts_uptime_seconds Total runtime in seconds for service {self.service_name}",
                f"# TYPE fts_uptime_seconds counter",
                f'fts_uptime_seconds{{service="{self.service_name}"}} {uptime:.2f}'
            ]
            for name, val in self.counters.items():
                lines.append(f"# HELP fts_{name} Metric {name} for {self.service_name}")
                lines.append(f"# TYPE fts_{name} counter")
                lines.append(f'fts_{name}{{service="{self.service_name}"}} {val}')
            return "\n".join(lines) + "\n"

coordinator_metrics = MetricsRegistry("coordinator")
