"""Prometheus metrics instrumentation for KR pipeline."""

from __future__ import annotations

import logging
import os
import statistics
import threading
import time
from collections import defaultdict, deque
from contextlib import ContextDecorator

try:
    from prometheus_client import CollectorRegistry, Counter, Histogram, push_to_gateway, start_http_server
except ImportError:  # pragma: no cover - prometheus optional at runtime
    CollectorRegistry = None  # type: ignore[assignment]
    Counter = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
    push_to_gateway = None  # type: ignore[assignment]
    start_http_server = None  # type: ignore[assignment]


class StageTimer(ContextDecorator):
    """Context manager to measure processing stage durations."""

    def __init__(
        self,
        metrics: PipelineMetrics,
        stage: str,
        manufacturer: str,
        document_type: str,
    ) -> None:
        self._metrics = metrics
        self._stage = stage
        self._manufacturer = manufacturer or "unknown"
        self._document_type = document_type or "unknown"
        self._start: float | None = None
        self._stopped = False
        self._lock = threading.Lock()

    def __enter__(self) -> StageTimer:
        self._start = time.perf_counter()
        return self

    def stop(self, success: bool, error_label: str | None = None) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True

        if self._start is None:
            duration = 0.0
        else:
            duration = max(0.0, time.perf_counter() - self._start)

        self._metrics.record_stage(
            stage=self._stage,
            manufacturer=self._manufacturer,
            document_type=self._document_type,
            duration=duration,
            success=success,
            error_label=error_label,
        )

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if not self._stopped:
            self.stop(success=exc is None, error_label=str(exc) if exc else None)


class PipelineMetrics:
    """Central metrics facade for pipeline and processor instrumentation."""

    _HISTOGRAM_BUCKETS = (
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
        30.0,
        60.0,
    )

    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_PROMETHEUS_METRICS", "1") != "0"
        self.registry = CollectorRegistry() if (self.enabled and CollectorRegistry is not None) else None

        if self.enabled and Counter is None:
            logging.getLogger(__name__).warning("Prometheus client library not available - disabling metrics export")
            self.enabled = False

        if self.enabled and self.registry:
            self.stage_success_counter = Counter(
                "krai_stage_success_total",
                "Number of successful stage executions",
                ("stage", "manufacturer", "document_type"),
                registry=self.registry,
            )
            self.stage_failure_counter = Counter(
                "krai_stage_failure_total",
                "Number of failed stage executions",
                ("stage", "manufacturer", "document_type", "error"),
                registry=self.registry,
            )
            self.stage_duration_histogram = Histogram(
                "krai_stage_duration_seconds",
                "Stage execution duration in seconds",
                ("stage", "manufacturer", "document_type"),
                buckets=self._HISTOGRAM_BUCKETS,
                registry=self.registry,
            )
            self.vision_success_counter = Counter(
                "krai_vision_success_total",
                "Number of successful vision inference calls",
                ("model",),
                registry=self.registry,
            )
            self.vision_failure_counter = Counter(
                "krai_vision_failure_total",
                "Number of failed vision inference calls",
                ("model", "error"),
                registry=self.registry,
            )
        else:  # Graceful fallbacks when metrics disabled
            self.stage_success_counter = None
            self.stage_failure_counter = None
            self.stage_duration_histogram = None
            self.vision_success_counter = None
            self.vision_failure_counter = None

        self.push_gateway_url = os.getenv("PROMETHEUS_PUSHGATEWAY_URL")
        self.push_job = os.getenv("PROMETHEUS_PUSH_JOB", "krai_pipeline")
        self._duration_samples: defaultdict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
        self._duration_lock = threading.Lock()

        if self.enabled and start_http_server is not None:
            try:
                port_env = os.getenv("PROMETHEUS_EXPORTER_PORT")
                if port_env:
                    start_http_server(int(port_env))
                    logging.getLogger(__name__).info("Prometheus exporter started on port %s", port_env)
            except Exception as exc:  # pragma: no cover - exporter start best effort
                logging.getLogger(__name__).warning("Unable to start Prometheus exporter: %s", exc)

    def stage_timer(self, stage: str, manufacturer: str, document_type: str) -> StageTimer:
        if not self.enabled:
            return StageTimer(metrics=self, stage=stage, manufacturer=manufacturer, document_type=document_type)
        return StageTimer(metrics=self, stage=stage, manufacturer=manufacturer, document_type=document_type)

    def record_stage(
        self,
        stage: str,
        manufacturer: str,
        document_type: str,
        duration: float,
        success: bool,
        error_label: str | None = None,
    ) -> None:
        label_stage = stage or "unknown"
        label_manufacturer = manufacturer or "unknown"
        label_doc_type = document_type or "unknown"

        if self.enabled and self.stage_duration_histogram is not None:
            self.stage_duration_histogram.labels(
                stage=label_stage,
                manufacturer=label_manufacturer,
                document_type=label_doc_type,
            ).observe(duration)

        with self._duration_lock:
            self._duration_samples[label_stage].append(duration)

        if self.enabled:
            if success and self.stage_success_counter is not None:
                self.stage_success_counter.labels(
                    stage=label_stage,
                    manufacturer=label_manufacturer,
                    document_type=label_doc_type,
                ).inc()
            elif not success and self.stage_failure_counter is not None:
                self.stage_failure_counter.labels(
                    stage=label_stage,
                    manufacturer=label_manufacturer,
                    document_type=label_doc_type,
                    error=error_label or "unknown",
                ).inc()

        self.push()

    def push(self) -> None:
        if not (self.enabled and self.push_gateway_url and self.registry and push_to_gateway):
            return
        try:
            push_to_gateway(self.push_gateway_url, job=self.push_job, registry=self.registry)
        except Exception as exc:  # pragma: no cover - push best effort
            logging.getLogger(__name__).warning("Failed to push metrics: %s", exc)

    def log_percentiles(self, logger: logging.Logger, batch_label: str) -> None:
        """Log p95/p99 latency derived from recent histogram samples."""
        with self._duration_lock:
            snapshot: dict[str, tuple[float, float]] = {}
            for stage, samples in self._duration_samples.items():
                if len(samples) < 5:
                    continue
                try:
                    p95 = statistics.quantiles(samples, n=100)[94]
                    p99 = statistics.quantiles(samples, n=100)[98]
                    snapshot[stage] = (p95, p99)
                except Exception:
                    continue

        for stage, (p95, p99) in snapshot.items():
            logger.info(
                "Metrics[%s] Stage '%s' latency percentiles: p95=%.3fs p99=%.3fs",
                stage,
                batch_label,
                p95,
                p99,
            )

    def record_vision_result(
        self,
        model: str | None,
        success: bool,
        error_label: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        model_label = model or "unknown"
        if success:
            if self.vision_success_counter is not None:
                self.vision_success_counter.labels(model=model_label).inc()
        else:
            if self.vision_failure_counter is not None:
                self.vision_failure_counter.labels(
                    model=model_label,
                    error=error_label or "unknown",
                ).inc()


metrics = PipelineMetrics()
