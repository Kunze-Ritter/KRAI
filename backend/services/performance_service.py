import logging
import statistics
from typing import Any

from backend.core.types import ProcessingResult
from backend.services.database_adapter import DatabaseAdapter


class PerformanceCollector:
    """
    Service for collecting, aggregating, and storing pipeline performance metrics.

    This service collects processing times from pipeline stages, calculates statistical
    aggregates (avg, p50, p95, p99), stores baseline metrics, and tracks performance
    improvements over time.

    Usage Example:
        ```python
        # Initialize the collector
        collector = PerformanceCollector(db_adapter, logger)

        # Collect metrics during pipeline execution
        await collector.collect_stage_metrics("classification", processing_result)

        # Aggregate and store baseline after benchmark run
        aggregated = await collector.flush_metrics_buffer()
        await collector.store_baseline(
            "classification",
            aggregated["classification"],
            test_document_ids=["uuid1", "uuid2"],
            notes="Baseline after optimization"
        )

        # Update current metrics for comparison
        await collector.update_current_metrics("classification", current_metrics)

        # Calculate improvement
        improvement = await collector.calculate_improvement("classification")
        print(f"Performance improved by {improvement['overall_improvement_percent']}%")
        ```

    Attributes:
        db_adapter: PostgreSQL database adapter for storing metrics
        logger: Logger instance for tracking operations
        _metrics_buffer: In-memory buffer for collecting stage metrics before aggregation
    """

    def __init__(self, db_adapter: DatabaseAdapter, logger: logging.Logger | None = None):
        """
        Initialize the PerformanceCollector.

        Args:
            db_adapter: PostgreSQL adapter instance for database operations
            logger: Optional logger instance (creates default if not provided)
        """
        self.db_adapter = db_adapter
        self.logger = logger or logging.getLogger(__name__)
        self._metrics_buffer: dict[str, list[float]] = {}
        self._outcomes_buffer: dict[str, list[bool]] = {}  # success/failure for rate calculation
        self._db_buffer: dict[str, list[float]] = {}
        self._api_buffer: dict[str, list[float]] = {}

    async def collect_stage_metrics(
        self,
        stage_name: str,
        processing_result: ProcessingResult,
        success: bool | None = None,
        error_message: str | None = None,
        resource_metrics: dict[str, float] | None = None,
    ) -> None:
        """
        Extract timing data from ProcessingResult and buffer it for aggregation.

        Records both success and failure paths so success/error rates can be derived.
        Call this after each pipeline stage completes (success or failure).

        Args:
            stage_name: Name of the pipeline stage (e.g., "classification", "chunking")
            processing_result: Result object containing processing time and metadata
            success: Whether the stage completed successfully. Defaults to processing_result.success
            error_message: Optional error message if failed
            resource_metrics: Optional dict with cpu_percent, ram_mb, gpu_mb for resource usage

        Returns:
            None
        """
        try:
            processing_time = processing_result.processing_time or 0.0
            is_success = success if success is not None else getattr(processing_result, "success", True)

            # Buffer processing time (including failures - time spent before failure)
            if stage_name not in self._metrics_buffer:
                self._metrics_buffer[stage_name] = []
            self._metrics_buffer[stage_name].append(processing_time)

            # Buffer success/failure for rate calculation
            if stage_name not in self._outcomes_buffer:
                self._outcomes_buffer[stage_name] = []
            self._outcomes_buffer[stage_name].append(is_success)

            document_id = processing_result.metadata.get("document_id", "unknown")
            correlation_id = processing_result.metadata.get("correlation_id", "N/A")

            self.logger.debug(
                f"Collected metric for stage '{stage_name}': {processing_time:.3f}s "
                f"success={is_success} (document_id={document_id}, correlation_id={correlation_id})"
            )

            if resource_metrics:
                self.logger.debug(f"Resource metrics for stage '{stage_name}': {resource_metrics}")

        except Exception as e:
            self.logger.error(f"Error collecting metrics for stage '{stage_name}': {e}", exc_info=True)

    async def collect_db_query_metrics(self, query_type: str, duration: float) -> None:
        """
        Collect database query timing metrics for performance tracking.

        This method buffers DB query durations for later aggregation and baseline storage.
        Wrap DB calls with timing to capture metrics:

        Args:
            query_type: Type of query (e.g., 'get_chunks', 'insert_document', 'update_product')
            duration: Query execution time in seconds

        Returns:
            None

        Example:
            ```python
            start = time.time()
            result = await db.fetch_one(query, params)
            await collector.collect_db_query_metrics('get_chunks', time.time() - start)
            ```
        """
        try:
            if duration is None or duration < 0:
                self.logger.warning(f"Invalid DB query duration for '{query_type}': {duration}")
                return

            if query_type not in self._db_buffer:
                self._db_buffer[query_type] = []

            self._db_buffer[query_type].append(duration)

            self.logger.debug(f"Collected DB metric for query '{query_type}': {duration:.3f}s")

        except Exception as e:
            self.logger.error(f"Error collecting DB metrics for query '{query_type}': {e}", exc_info=True)

    async def collect_api_response_metrics(self, endpoint: str, duration: float) -> None:
        """
        Collect API response timing metrics for performance tracking.

        This method buffers API call durations for later aggregation and baseline storage.
        Wrap API calls with timing to capture metrics:

        Args:
            endpoint: API endpoint identifier (e.g., 'ollama_embed', 'perplexity_search')
            duration: API call duration in seconds

        Returns:
            None

        Example:
            ```python
            start = time.time()
            response = await http_client.post(url, json=payload)
            await collector.collect_api_response_metrics('ollama_embed', time.time() - start)
            ```
        """
        try:
            if duration is None or duration < 0:
                self.logger.warning(f"Invalid API response duration for '{endpoint}': {duration}")
                return

            if endpoint not in self._api_buffer:
                self._api_buffer[endpoint] = []

            self._api_buffer[endpoint].append(duration)

            self.logger.debug(f"Collected API metric for endpoint '{endpoint}': {duration:.3f}s")

        except Exception as e:
            self.logger.error(f"Error collecting API metrics for endpoint '{endpoint}': {e}", exc_info=True)

    async def store_baseline(
        self, stage_name: str, metrics: dict[str, float], test_document_ids: list[str], notes: str | None = None
    ) -> bool:
        """
        Store baseline metrics to krai_system.performance_baselines table.

        This method stores or updates baseline performance metrics for a pipeline stage,
        DB query, or API endpoint. Supports prefixed stage names for DB/API metrics.
        If a baseline already exists for the same stage and date, it will be updated.

        Args:
            stage_name: Pipeline stage name (e.g., "classification", "chunking"),
                       DB query type (e.g., "db__get_chunks"), or
                       API endpoint (e.g., "api__ollama_embed")
            metrics: Dictionary with keys: avg_seconds, p50_seconds, p95_seconds, p99_seconds
            test_document_ids: List of document IDs used for measurement
            notes: Optional notes about the baseline (e.g., "After optimization X")

        Returns:
            True on success, False on failure

        Example:
            ```python
            # Store pipeline stage baseline
            metrics = {
                'avg_seconds': 1.234,
                'p50_seconds': 1.100,
                'p95_seconds': 2.500,
                'p99_seconds': 3.200
            }
            success = await collector.store_baseline(
                "classification",
                metrics,
                ["uuid1", "uuid2", "uuid3"],
                notes="Baseline after GPU optimization"
            )

            # Store DB query baseline
            await collector.store_baseline(
                "db__get_chunks",
                db_metrics,
                test_doc_ids,
                notes="DB query baseline"
            )

            # Store API endpoint baseline
            await collector.store_baseline(
                "api__ollama_embed",
                api_metrics,
                test_doc_ids,
                notes="API baseline"
            )
            ```
        """
        try:
            if not self._validate_metrics(metrics):
                self.logger.error(f"Invalid metrics format for stage '{stage_name}'")
                return False

            query = """
                INSERT INTO krai_system.performance_baselines (
                    stage_name, baseline_avg_seconds, baseline_p50_seconds,
                    baseline_p95_seconds, baseline_p99_seconds,
                    test_document_ids, measurement_date, notes
                ) VALUES (%(stage_name)s, %(avg_seconds)s, %(p50_seconds)s, %(p95_seconds)s, %(p99_seconds)s, %(test_document_ids)s, CURRENT_TIMESTAMP, %(notes)s)
                ON CONFLICT (stage_name, DATE(measurement_date))
                DO UPDATE SET
                    baseline_avg_seconds = EXCLUDED.baseline_avg_seconds,
                    baseline_p50_seconds = EXCLUDED.baseline_p50_seconds,
                    baseline_p95_seconds = EXCLUDED.baseline_p95_seconds,
                    baseline_p99_seconds = EXCLUDED.baseline_p99_seconds,
                    test_document_ids = EXCLUDED.test_document_ids,
                    notes = EXCLUDED.notes
                RETURNING id
            """

            result = await self.db_adapter.execute_query(
                query,
                {
                    "stage_name": stage_name,
                    "avg_seconds": metrics["avg_seconds"],
                    "p50_seconds": metrics["p50_seconds"],
                    "p95_seconds": metrics["p95_seconds"],
                    "p99_seconds": metrics["p99_seconds"],
                    "test_document_ids": test_document_ids,
                    "notes": notes,
                },
            )

            if result:
                self.logger.info(
                    f"Stored baseline for stage '{stage_name}': "
                    f"avg={metrics['avg_seconds']:.3f}s, "
                    f"p50={metrics['p50_seconds']:.3f}s, "
                    f"p95={metrics['p95_seconds']:.3f}s, "
                    f"p99={metrics['p99_seconds']:.3f}s"
                )
                return True
            self.logger.warning(f"No result returned when storing baseline for '{stage_name}'")
            return False

        except Exception as e:
            self.logger.error(f"Error storing baseline for stage '{stage_name}': {e}", exc_info=True)
            return False

    async def update_current_metrics(self, stage_name: str, metrics: dict[str, float]) -> bool:
        """
        Update current performance metrics for comparison with baseline.

        This method updates the current metrics for the most recent baseline record
        and automatically calculates the improvement percentage. Supports pipeline stages,
        DB queries (prefixed with 'db__'), and API endpoints (prefixed with 'api__').

        Args:
            stage_name: Pipeline stage name (e.g., "classification"),
                       DB query type (e.g., "db__get_chunks"), or
                       API endpoint (e.g., "api__ollama_embed")
            metrics: Dictionary with keys: avg_seconds, p50_seconds, p95_seconds, p99_seconds

        Returns:
            True if updated, False if no baseline exists or on error

        Example:
            ```python
            # Update pipeline stage metrics
            current_metrics = {
                'avg_seconds': 0.987,
                'p50_seconds': 0.900,
                'p95_seconds': 1.800,
                'p99_seconds': 2.100
            }
            updated = await collector.update_current_metrics("classification", current_metrics)

            # Update DB query metrics
            await collector.update_current_metrics("db__get_chunks", db_metrics)

            # Update API metrics
            await collector.update_current_metrics("api__ollama_embed", api_metrics)
            ```
        """
        try:
            if not self._validate_metrics(metrics):
                self.logger.error(f"Invalid metrics format for stage '{stage_name}'")
                return False

            query = """
                UPDATE krai_system.performance_baselines
                SET
                    current_avg_seconds = %(avg_seconds)s,
                    current_p50_seconds = %(p50_seconds)s,
                    current_p95_seconds = %(p95_seconds)s,
                    current_p99_seconds = %(p99_seconds)s,
                    improvement_percentage = (
                        (baseline_avg_seconds - %(avg_seconds)s) / NULLIF(baseline_avg_seconds, 0) * 100
                    )
                WHERE id = (
                    SELECT id
                    FROM krai_system.performance_baselines
                    WHERE stage_name = %(stage_name)s
                    ORDER BY measurement_date DESC
                    LIMIT 1
                )
                RETURNING id
            """

            result = await self.db_adapter.execute_query(
                query,
                {
                    "stage_name": stage_name,
                    "avg_seconds": metrics["avg_seconds"],
                    "p50_seconds": metrics["p50_seconds"],
                    "p95_seconds": metrics["p95_seconds"],
                    "p99_seconds": metrics["p99_seconds"],
                },
            )

            if result:
                self.logger.info(
                    f"Updated current metrics for stage '{stage_name}': "
                    f"avg={metrics['avg_seconds']:.3f}s, "
                    f"p50={metrics['p50_seconds']:.3f}s, "
                    f"p95={metrics['p95_seconds']:.3f}s, "
                    f"p99={metrics['p99_seconds']:.3f}s"
                )
                return True
            self.logger.warning(
                f"No baseline found for stage '{stage_name}' on current date. "
                f"Create a baseline first using store_baseline()."
            )
            return False

        except Exception as e:
            self.logger.error(f"Error updating current metrics for stage '{stage_name}': {e}", exc_info=True)
            return False

    async def calculate_improvement(self, stage_name: str) -> dict[str, Any] | None:
        """
        Calculate percentage improvement between baseline and current metrics.

        This method retrieves the latest baseline and current metrics for a stage
        and calculates improvement percentages for all metrics (avg, p50, p95, p99).

        Args:
            stage_name: Pipeline stage name

        Returns:
            Dictionary with improvement data, or None if no baseline exists:
            {
                'stage_name': str,
                'baseline_avg': float,
                'current_avg': float,
                'improvement_avg_percent': float,
                'baseline_p50': float,
                'current_p50': float,
                'improvement_p50_percent': float,
                'baseline_p95': float,
                'current_p95': float,
                'improvement_p95_percent': float,
                'baseline_p99': float,
                'current_p99': float,
                'improvement_p99_percent': float,
                'overall_improvement_percent': float
            }

        Example:
            ```python
            improvement = await collector.calculate_improvement("classification")
            if improvement:
                print(f"Overall improvement: {improvement['overall_improvement_percent']:.2f}%")
                print(f"P95 improvement: {improvement['improvement_p95_percent']:.2f}%")
            ```
        """
        try:
            query = """
                SELECT
                    baseline_avg_seconds, current_avg_seconds,
                    baseline_p50_seconds, current_p50_seconds,
                    baseline_p95_seconds, current_p95_seconds,
                    baseline_p99_seconds, current_p99_seconds,
                    improvement_percentage
                FROM krai_system.performance_baselines
                WHERE stage_name = %(stage_name)s
                ORDER BY measurement_date DESC
                LIMIT 1
            """

            result = await self.db_adapter.fetch_one(query, {"stage_name": stage_name})

            if not result:
                self.logger.warning(f"No baseline found for stage '{stage_name}'")
                return None

            def calc_improvement(baseline: float | None, current: float | None) -> float:
                if baseline is None or current is None or baseline == 0:
                    return 0.0
                return ((baseline - current) / baseline) * 100

            improvement_data = {
                "stage_name": stage_name,
                "baseline_avg": result.get("baseline_avg_seconds"),
                "current_avg": result.get("current_avg_seconds"),
                "improvement_avg_percent": calc_improvement(
                    result.get("baseline_avg_seconds"), result.get("current_avg_seconds")
                ),
                "baseline_p50": result.get("baseline_p50_seconds"),
                "current_p50": result.get("current_p50_seconds"),
                "improvement_p50_percent": calc_improvement(
                    result.get("baseline_p50_seconds"), result.get("current_p50_seconds")
                ),
                "baseline_p95": result.get("baseline_p95_seconds"),
                "current_p95": result.get("current_p95_seconds"),
                "improvement_p95_percent": calc_improvement(
                    result.get("baseline_p95_seconds"), result.get("current_p95_seconds")
                ),
                "baseline_p99": result.get("baseline_p99_seconds"),
                "current_p99": result.get("current_p99_seconds"),
                "improvement_p99_percent": calc_improvement(
                    result.get("baseline_p99_seconds"), result.get("current_p99_seconds")
                ),
                "overall_improvement_percent": result.get("improvement_percentage", 0.0),
            }

            self.logger.info(
                f"Calculated improvement for stage '{stage_name}': "
                f"{self._format_improvement_percent(improvement_data['overall_improvement_percent'])}"
            )

            return improvement_data

        except Exception as e:
            self.logger.error(f"Error calculating improvement for stage '{stage_name}': {e}", exc_info=True)
            return None

    async def aggregate_metrics(self, stage_name: str, durations: list[float]) -> dict[str, float]:
        """
        Calculate statistical aggregates (avg, p50, p95, p99) from a list of durations.

        This method computes percentile-based performance metrics from raw timing data.
        It handles edge cases like empty lists or insufficient samples gracefully.

        Args:
            stage_name: Name of the pipeline stage (used for logging)
            durations: List of processing times in seconds

        Returns:
            Dictionary with keys: avg_seconds, p50_seconds, p95_seconds, p99_seconds
            Returns zeros if durations is empty or on calculation errors

        Example:
            ```python
            durations = [1.2, 1.5, 1.1, 2.3, 1.8, 1.4, 1.6, 1.3, 1.7, 1.9]
            metrics = await collector.aggregate_metrics("classification", durations)
            print(f"Average: {metrics['avg_seconds']:.3f}s")
            print(f"P95: {metrics['p95_seconds']:.3f}s")
            ```
        """
        try:
            if not durations:
                self.logger.warning(f"No durations provided for stage '{stage_name}'")
                return {"avg_seconds": 0.0, "p50_seconds": 0.0, "p95_seconds": 0.0, "p99_seconds": 0.0}

            sorted_durations = sorted(durations)
            n_samples = len(sorted_durations)

            avg = statistics.mean(sorted_durations)
            p50 = statistics.median(sorted_durations)

            if n_samples < 5:
                self.logger.warning(
                    f"Only {n_samples} samples for stage '{stage_name}'. " f"Using max value for p95 and p99."
                )
                p95 = max(sorted_durations)
                p99 = max(sorted_durations)
            elif n_samples < 100:
                quantiles = statistics.quantiles(sorted_durations, n=n_samples)
                p95_idx = int(0.95 * len(quantiles))
                p99_idx = int(0.99 * len(quantiles))
                p95 = quantiles[min(p95_idx, len(quantiles) - 1)]
                p99 = quantiles[min(p99_idx, len(quantiles) - 1)]
            else:
                quantiles = statistics.quantiles(sorted_durations, n=100)
                p95 = quantiles[94]
                p99 = quantiles[98]

            metrics = {
                "avg_seconds": round(avg, 3),
                "p50_seconds": round(p50, 3),
                "p95_seconds": round(p95, 3),
                "p99_seconds": round(p99, 3),
            }

            self.logger.debug(
                f"Aggregated {n_samples} samples for stage '{stage_name}': "
                f"avg={metrics['avg_seconds']:.3f}s, "
                f"p50={metrics['p50_seconds']:.3f}s, "
                f"p95={metrics['p95_seconds']:.3f}s, "
                f"p99={metrics['p99_seconds']:.3f}s"
            )

            return metrics

        except Exception as e:
            self.logger.error(f"Error aggregating metrics for stage '{stage_name}': {e}", exc_info=True)
            return {"avg_seconds": 0.0, "p50_seconds": 0.0, "p95_seconds": 0.0, "p99_seconds": 0.0}

    async def flush_db_buffer(self, query_type: str | None = None) -> dict[str, dict[str, float]]:
        """
        Aggregate buffered DB query metrics and clear the buffer.

        This method processes the in-memory DB metrics buffer, calculates aggregates,
        and clears the buffer. It can process a single query type or all buffered queries.

        Args:
            query_type: Optional query type to flush. If None, flushes all query types.

        Returns:
            Dictionary mapping query_type to aggregated metrics:
            {
                'get_chunks': {
                    'avg_seconds': float,
                    'p50_seconds': float,
                    'p95_seconds': float,
                    'p99_seconds': float
                }
            }

        Example:
            ```python
            # Flush all DB queries
            all_db_metrics = await collector.flush_db_buffer()

            # Flush specific query type
            chunk_metrics = await collector.flush_db_buffer("get_chunks")
            ```
        """
        try:
            aggregated = {}

            if query_type:
                if query_type in self._db_buffer:
                    durations = self._db_buffer[query_type]
                    aggregated[query_type] = await self.aggregate_metrics(f"db__{query_type}", durations)
                    del self._db_buffer[query_type]
                    self.logger.info(f"Flushed {len(durations)} DB metrics for query '{query_type}'")
                else:
                    self.logger.warning(f"No buffered DB metrics for query '{query_type}'")
            else:
                for query, durations in list(self._db_buffer.items()):
                    aggregated[query] = await self.aggregate_metrics(f"db__{query}", durations)
                    self.logger.info(f"Flushed {len(durations)} DB metrics for query '{query}'")
                self._db_buffer.clear()

            return aggregated

        except Exception as e:
            self.logger.error(f"Error flushing DB metrics buffer: {e}", exc_info=True)
            return {}

    async def flush_api_buffer(self, endpoint: str | None = None) -> dict[str, dict[str, float]]:
        """
        Aggregate buffered API response metrics and clear the buffer.

        This method processes the in-memory API metrics buffer, calculates aggregates,
        and clears the buffer. It can process a single endpoint or all buffered endpoints.

        Args:
            endpoint: Optional endpoint to flush. If None, flushes all endpoints.

        Returns:
            Dictionary mapping endpoint to aggregated metrics:
            {
                'ollama_embed': {
                    'avg_seconds': float,
                    'p50_seconds': float,
                    'p95_seconds': float,
                    'p99_seconds': float
                }
            }

        Example:
            ```python
            # Flush all API endpoints
            all_api_metrics = await collector.flush_api_buffer()

            # Flush specific endpoint
            embed_metrics = await collector.flush_api_buffer("ollama_embed")
            ```
        """
        try:
            aggregated = {}

            if endpoint:
                if endpoint in self._api_buffer:
                    durations = self._api_buffer[endpoint]
                    aggregated[endpoint] = await self.aggregate_metrics(f"api__{endpoint}", durations)
                    del self._api_buffer[endpoint]
                    self.logger.info(f"Flushed {len(durations)} API metrics for endpoint '{endpoint}'")
                else:
                    self.logger.warning(f"No buffered API metrics for endpoint '{endpoint}'")
            else:
                for ep, durations in list(self._api_buffer.items()):
                    aggregated[ep] = await self.aggregate_metrics(f"api__{ep}", durations)
                    self.logger.info(f"Flushed {len(durations)} API metrics for endpoint '{ep}'")
                self._api_buffer.clear()

            return aggregated

        except Exception as e:
            self.logger.error(f"Error flushing API metrics buffer: {e}", exc_info=True)
            return {}

    async def flush_metrics_buffer(self, stage_name: str | None = None) -> dict[str, dict[str, Any]]:
        """
        Aggregate buffered metrics and optionally store them.

        Includes success_count and failure_count for success/error rate derivation.

        Args:
            stage_name: Optional stage name to flush. If None, flushes all stages.

        Returns:
            Dictionary mapping stage_name to aggregated metrics:
            {
                'stage_name': {
                    'avg_seconds': float,
                    'p50_seconds': float,
                    'p95_seconds': float,
                    'p99_seconds': float,
                    'success_count': int,
                    'failure_count': int,
                    'success_rate': float
                }
            }
        """
        try:
            aggregated = {}

            async def flush_one(sname: str) -> None:
                durations = self._metrics_buffer.get(sname, [])
                outcomes = self._outcomes_buffer.get(sname, [])
                metrics = await self.aggregate_metrics(sname, durations)
                success_count = sum(1 for o in outcomes if o)
                failure_count = len(outcomes) - success_count
                total = len(outcomes)
                metrics["success_count"] = success_count
                metrics["failure_count"] = failure_count
                metrics["success_rate"] = success_count / total if total else 0.0
                aggregated[sname] = metrics
                if sname in self._metrics_buffer:
                    del self._metrics_buffer[sname]
                if sname in self._outcomes_buffer:
                    del self._outcomes_buffer[sname]
                self.logger.info(
                    f"Flushed {len(durations)} metrics for stage '{sname}' "
                    f"(success={success_count}, failure={failure_count})"
                )

            if stage_name:
                if stage_name in self._metrics_buffer or stage_name in self._outcomes_buffer:
                    await flush_one(stage_name)
                else:
                    self.logger.warning(f"No buffered metrics for stage '{stage_name}'")
            else:
                stages = set(self._metrics_buffer.keys()) | set(self._outcomes_buffer.keys())
                for sname in list(stages):
                    await flush_one(sname)

            return aggregated

        except Exception as e:
            self.logger.error(f"Error flushing metrics buffer: {e}", exc_info=True)
            return {}

    async def get_baseline(self, stage_name: str) -> dict[str, Any] | None:
        """
        Retrieve the latest baseline for a stage.

        This method fetches the most recent baseline record for a pipeline stage,
        including all baseline and current metrics, improvement percentage, and metadata.

        Args:
            stage_name: Pipeline stage name

        Returns:
            Dictionary with all baseline fields, or None if not found:
            {
                'id': str,
                'stage_name': str,
                'baseline_avg_seconds': float,
                'baseline_p50_seconds': float,
                'baseline_p95_seconds': float,
                'baseline_p99_seconds': float,
                'current_avg_seconds': float,
                'current_p50_seconds': float,
                'current_p95_seconds': float,
                'current_p99_seconds': float,
                'improvement_percentage': float,
                'test_document_ids': List[str],
                'measurement_date': datetime,
                'notes': str,
                'created_at': datetime
            }

        Example:
            ```python
            baseline = await collector.get_baseline("classification")
            if baseline:
                print(f"Baseline avg: {baseline['baseline_avg_seconds']:.3f}s")
                print(f"Measured on: {baseline['measurement_date']}")
            ```
        """
        try:
            query = """
                SELECT
                    id, stage_name,
                    baseline_avg_seconds, baseline_p50_seconds,
                    baseline_p95_seconds, baseline_p99_seconds,
                    current_avg_seconds, current_p50_seconds,
                    current_p95_seconds, current_p99_seconds,
                    improvement_percentage, test_document_ids,
                    measurement_date, notes, created_at
                FROM krai_system.performance_baselines
                WHERE stage_name = %(stage_name)s
                ORDER BY measurement_date DESC
                LIMIT 1
            """

            result = await self.db_adapter.fetch_one(query, {"stage_name": stage_name})

            if result:
                self.logger.debug(f"Retrieved baseline for stage '{stage_name}'")
                return dict(result)
            self.logger.warning(f"No baseline found for stage '{stage_name}'")
            return None

        except Exception as e:
            self.logger.error(f"Error retrieving baseline for stage '{stage_name}': {e}", exc_info=True)
            return None

    async def get_all_baselines(self) -> list[dict[str, Any]]:
        """
        Retrieve latest baselines for all stages.

        This method fetches the most recent baseline record for each pipeline stage,
        useful for dashboard displays and performance monitoring.

        Returns:
            List of dictionaries with baseline data (same structure as get_baseline)
            Returns empty list on errors

        Example:
            ```python
            all_baselines = await collector.get_all_baselines()
            for baseline in all_baselines:
                print(f"{baseline['stage_name']}: {baseline['baseline_avg_seconds']:.3f}s")
            ```
        """
        try:
            query = """
                SELECT DISTINCT ON (stage_name)
                    id, stage_name,
                    baseline_avg_seconds, baseline_p50_seconds,
                    baseline_p95_seconds, baseline_p99_seconds,
                    current_avg_seconds, current_p50_seconds,
                    current_p95_seconds, current_p99_seconds,
                    improvement_percentage, test_document_ids,
                    measurement_date, notes, created_at
                FROM krai_system.performance_baselines
                ORDER BY stage_name, measurement_date DESC
            """

            results = await self.db_adapter.fetch_all(query)

            baselines = [dict(row) for row in results]

            self.logger.info(f"Retrieved {len(baselines)} baselines")

            return baselines

        except Exception as e:
            self.logger.error(f"Error retrieving all baselines: {e}", exc_info=True)
            return []

    def _validate_metrics(self, metrics: dict[str, float]) -> bool:
        """
        Validate that metrics dictionary has all required keys.

        Args:
            metrics: Dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        required_keys = {"avg_seconds", "p50_seconds", "p95_seconds", "p99_seconds"}

        if not isinstance(metrics, dict):
            self.logger.error("Metrics must be a dictionary")
            return False

        missing_keys = required_keys - set(metrics.keys())
        if missing_keys:
            self.logger.error(f"Missing required metric keys: {missing_keys}")
            return False

        for key, value in metrics.items():
            if key in required_keys and (not isinstance(value, int | float) or value < 0):
                self.logger.error(f"Invalid value for '{key}': {value}")
                return False

        return True

    def _format_improvement_percent(self, percent: float | None) -> str:
        """
        Format improvement percentage with sign (+/-) and 2 decimal places.

        Args:
            percent: Improvement percentage (positive = improvement, negative = regression)

        Returns:
            Formatted string like "+15.23%" or "-5.67%"
        """
        if percent is None:
            return "N/A"

        sign = "+" if percent >= 0 else ""
        return f"{sign}{percent:.2f}%"

    def clear_buffer(self) -> None:
        """
        Clear all metrics buffers (stage, DB, API, outcomes).

        Example:
            ```python
            collector.clear_buffer()
            ```
        """
        stage_count = sum(len(durations) for durations in self._metrics_buffer.values())
        outcome_count = sum(len(o) for o in self._outcomes_buffer.values())
        db_count = sum(len(durations) for durations in self._db_buffer.values())
        api_count = sum(len(durations) for durations in self._api_buffer.values())

        self._metrics_buffer.clear()
        self._outcomes_buffer.clear()
        self._db_buffer.clear()
        self._api_buffer.clear()

        self.logger.info(
            f"Cleared all buffers (stage: {stage_count}, outcomes: {outcome_count}, "
            f"DB: {db_count}, API: {api_count} samples)"
        )

    async def store_stage_metric(
        self,
        document_id: str,
        stage_name: str,
        processing_time: float,
        success: bool,
        error_message: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """
        Store individual stage metric to krai_system.stage_metrics table.

        Use this when the optional stage_metrics table is created via migration
        009_add_stage_metrics_table.sql. Does nothing if the table does not exist.

        Args:
            document_id: Document UUID
            stage_name: Pipeline stage name
            processing_time: Duration in seconds
            success: Whether the stage completed successfully
            error_message: Optional error message if failed
            correlation_id: Optional correlation ID

        Returns:
            True if stored successfully, False on error or missing table
        """
        try:
            query = """
                INSERT INTO krai_system.stage_metrics (
                    document_id, stage_name, processing_time, success,
                    error_message, correlation_id
                ) VALUES (%(document_id)s, %(stage_name)s, %(processing_time)s, %(success)s, %(error_message)s, %(correlation_id)s)
            """
            await self.db_adapter.execute_query(
                query,
                {
                    "document_id": document_id,
                    "stage_name": stage_name,
                    "processing_time": round(processing_time, 3),
                    "success": success,
                    "error_message": error_message,
                    "correlation_id": correlation_id,
                },
            )
            self.logger.debug(f"Stored stage_metric: {stage_name} doc={document_id} time={processing_time:.3f}s")
            return True
        except Exception as e:
            self.logger.debug(f"Could not store stage_metric (table may not exist): {e}")
            return False
