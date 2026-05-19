"""
Part reliability analyzer for warranty analysis.

Quantifies mismatch between manufacturer-specified part lifespans and actual
field failures to identify early-failure patterns and warranty exposure.
"""

from datetime import datetime
from typing import Any

from backend.pm.models.ticket import PartReliabilityMetrics, WarrantyAnalysisSummary
from backend.services.database_adapter import DatabaseAdapter


class PartReliabilityAnalyzer:
    """
    Analyzes part reliability across manufacturers and categories.

    Queries krai_pm.vw_warranty_analysis and krai_pm.part_warranty_events
    to derive metrics for manufacturer negotiations.
    """

    def __init__(self, db_adapter: DatabaseAdapter) -> None:
        self.db = db_adapter

    async def analyze_by_manufacturer(self, manufacturer_name: str) -> list[PartReliabilityMetrics]:
        """
        Get reliability metrics for all part categories of a manufacturer.

        Args:
            manufacturer_name: e.g. 'Konica Minolta', 'HP', 'Ricoh'

        Returns:
            List of PartReliabilityMetrics, one per part_category for the manufacturer.
        """
        query = """
        SELECT
            manufacturer_name,
            part_category,
            total_replacements,
            avg_nominal_lifetime,
            avg_actual_runtime,
            avg_mismatch_ratio,
            warranty_eligible_count,
            warranty_rate_pct,
            total_repair_cost_eur
        FROM krai_pm.vw_warranty_analysis
        WHERE manufacturer_name = $1
        ORDER BY warranty_eligible_count DESC NULLS LAST, total_repair_cost_eur DESC NULLS LAST
        """
        rows = await self.db.fetch(query, manufacturer_name)

        metrics: list[PartReliabilityMetrics] = []
        for row in rows:
            warranty_rate = float(row["warranty_rate_pct"] or 0.0)
            risk = self.classify_risk(warranty_rate)
            metrics.append(
                PartReliabilityMetrics(
                    manufacturer_name=row["manufacturer_name"],
                    part_category=row["part_category"],
                    total_replacements=int(row["total_replacements"]),
                    nominal_lifetime_pages=row["avg_nominal_lifetime"],
                    actual_avg_runtime_pages=row["avg_actual_runtime"],
                    mismatch_ratio=row["avg_mismatch_ratio"],
                    warranty_eligible_count=int(row["warranty_eligible_count"] or 0),
                    warranty_rate_pct=warranty_rate,
                    risk_level=risk,
                    financial_impact_eur=row["total_repair_cost_eur"],
                )
            )

        return metrics

    async def analyze_all(self) -> WarrantyAnalysisSummary:
        """
        Get warranty analysis across all manufacturers.

        Returns:
            WarrantyAnalysisSummary with metrics grouped by manufacturer.
        """
        view_query = """
        SELECT
            manufacturer_name,
            part_category,
            total_replacements,
            avg_nominal_lifetime,
            avg_actual_runtime,
            avg_mismatch_ratio,
            warranty_eligible_count,
            warranty_rate_pct,
            total_repair_cost_eur
        FROM krai_pm.vw_warranty_analysis
        ORDER BY manufacturer_name, warranty_eligible_count DESC NULLS LAST
        """

        summary_query = """
        SELECT
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE is_in_warranty) as warranty_eligible,
            COUNT(DISTINCT manufacturer_id) as total_manufacturers
        FROM krai_pm.part_warranty_events
        """

        rows = await self.db.fetch(view_query)
        summary_row = await self.db.fetchrow(summary_query)

        by_manufacturer: dict[str, list[PartReliabilityMetrics]] = {}

        for row in rows:
            mfr_name = row["manufacturer_name"]
            if mfr_name not in by_manufacturer:
                by_manufacturer[mfr_name] = []

            warranty_rate = float(row["warranty_rate_pct"] or 0.0)
            risk = self.classify_risk(warranty_rate)

            metric = PartReliabilityMetrics(
                manufacturer_name=mfr_name,
                part_category=row["part_category"],
                total_replacements=int(row["total_replacements"]),
                nominal_lifetime_pages=row["avg_nominal_lifetime"],
                actual_avg_runtime_pages=row["avg_actual_runtime"],
                mismatch_ratio=row["avg_mismatch_ratio"],
                warranty_eligible_count=int(row["warranty_eligible_count"] or 0),
                warranty_rate_pct=warranty_rate,
                risk_level=risk,
                financial_impact_eur=row["total_repair_cost_eur"],
            )
            by_manufacturer[mfr_name].append(metric)

        return WarrantyAnalysisSummary(
            total_events=int(summary_row["total_events"] or 0),
            warranty_eligible=int(summary_row["warranty_eligible"] or 0),
            total_manufacturers=int(summary_row["total_manufacturers"] or 0),
            by_manufacturer=by_manufacturer,
            analysis_timestamp=datetime.utcnow(),
        )

    async def compute_replacement_frequency(self, manufacturer_name: str, part_category: str) -> dict[str, Any]:
        """
        Compute replacement frequency and lifetime statistics for a specific part.

        Args:
            manufacturer_name: e.g. 'Konica Minolta'
            part_category: e.g. 'drum'

        Returns:
            Dict with keys: replacement_count, nominal_lifetime_pages,
            avg_actual_runtime_pages, implied_lifetime_days
        """
        query = """
        SELECT
            COUNT(*) as replacement_count,
            AVG(pwe.nominal_lifetime_pages) as nominal_lifetime_pages,
            AVG(pwe.actual_runtime_pages) as avg_actual_runtime_pages,
            MIN(pwe.failure_date) as earliest_failure,
            MAX(pwe.failure_date) as latest_failure
        FROM krai_pm.part_warranty_events pwe
        JOIN krai_core.manufacturers m ON pwe.manufacturer_id = m.id
        WHERE m.name = $1 AND pwe.part_category = $2
        """

        row = await self.db.fetchrow(query, manufacturer_name, part_category)

        if not row or row["replacement_count"] == 0:
            return {
                "replacement_count": 0,
                "nominal_lifetime_pages": None,
                "avg_actual_runtime_pages": None,
                "implied_lifetime_days": None,
            }

        earliest = row["earliest_failure"]
        latest = row["latest_failure"]
        days_span = (latest - earliest).days if (latest and earliest) else None

        return {
            "replacement_count": int(row["replacement_count"] or 0),
            "nominal_lifetime_pages": row["nominal_lifetime_pages"],
            "avg_actual_runtime_pages": row["avg_actual_runtime_pages"],
            "implied_lifetime_days": days_span,
        }

    @staticmethod
    def classify_risk(warranty_rate_pct: float) -> str:
        """
        Classify risk level based on warranty event rate.

        Args:
            warranty_rate_pct: Percentage of events within warranty window (0-100)

        Returns:
            Risk level: 'critical', 'high', 'medium', 'low', or 'unknown'
        """
        if warranty_rate_pct is None:
            return "unknown"
        if warranty_rate_pct > 50.0:
            return "critical"
        if warranty_rate_pct > 30.0:
            return "high"
        if warranty_rate_pct > 15.0:
            return "medium"
        return "low"
