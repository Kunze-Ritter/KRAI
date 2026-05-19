"""
Error pattern analysis service for manufacturing and maintenance.

Analyzes error code distributions per manufacturer to identify patterns,
failure modes, and dominant issue categories.
"""

from typing import Any

from backend.services.database_adapter import DatabaseAdapter


class ErrorPatternAnalyzer:
    """
    Analyzes error code patterns per manufacturer.

    Computes frequency distributions, co-occurrence matrices, and identifies
    dominant failure modes for predictive maintenance modeling.
    """

    def __init__(self, db_adapter: DatabaseAdapter) -> None:
        """
        Initialize error pattern analyzer.

        Args:
            db_adapter: Database adapter for querying PM schema
        """
        self.db = db_adapter

    async def analyze_by_manufacturer(self, manufacturer_name: str, top_n: int = 15) -> dict[str, Any]:
        """
        Analyze error patterns for a specific manufacturer.

        Args:
            manufacturer_name: Manufacturer name or ID
            top_n: Number of top error codes to return

        Returns:
            Dict with keys:
            - top_error_codes: List of (code, count) tuples
            - total_tickets: Total tickets for manufacturer
            - distribution_type: 'skewed' or 'uniform' based on entropy
            - cooccurrence_matrix: Dict of co-occurring error codes
        """
        # Fetch all error codes for this manufacturer
        query = """
            SELECT DISTINCT(unnest(error_codes)) as code, COUNT(*) as cnt
            FROM krai_pm.service_tickets
            WHERE manufacturer_id = %s AND error_codes IS NOT NULL
            GROUP BY code
            ORDER BY cnt DESC
            LIMIT %s
        """
        error_codes = await self.db.fetch_all(query, (manufacturer_name, top_n))

        # Get total ticket count for this manufacturer
        total_query = """
            SELECT COUNT(*) as cnt FROM krai_pm.service_tickets
            WHERE manufacturer_id = %s
        """
        total_result = await self.db.fetch_one(total_query, (manufacturer_name,))
        total_tickets = total_result["cnt"] if total_result else 0

        # Compute co-occurrence matrix
        cooccurrence = await self._compute_cooccurrence(manufacturer_name, [row["code"] for row in error_codes])

        # Classify distribution
        distribution_type = self._classify_distribution(error_codes, total_tickets)

        return {
            "manufacturer": manufacturer_name,
            "total_tickets": total_tickets,
            "top_error_codes": [(row["code"], row["cnt"]) for row in error_codes],
            "distribution_type": distribution_type,
            "cooccurrence_matrix": cooccurrence,
        }

    async def analyze_all_manufacturers(self) -> dict[str, dict[str, Any]]:
        """
        Analyze error patterns for all manufacturers in the database.

        Returns:
            Dict mapping manufacturer names to their analysis results
        """
        # Get list of all manufacturers
        query = """
            SELECT DISTINCT manufacturer_id FROM krai_pm.service_tickets
            WHERE manufacturer_id IS NOT NULL
        """
        manufacturers = await self.db.fetch_all(query, ())

        results = {}
        for row in manufacturers:
            manufacturer_id = row["manufacturer_id"]
            analysis = await self.analyze_by_manufacturer(manufacturer_id)
            results[manufacturer_id] = analysis

        return results

    async def _compute_cooccurrence(self, manufacturer_name: str, error_codes: list[str]) -> dict[str, dict[str, int]]:
        """
        Compute co-occurrence matrix for error codes.

        Which error codes appear together in the same ticket.

        Args:
            manufacturer_name: Manufacturer to analyze
            error_codes: List of error codes to analyze

        Returns:
            Dict mapping error code to dict of co-occurrence counts
        """
        cooccurrence: dict[str, dict[str, int]] = {}

        for code in error_codes:
            cooccurrence[code] = {}

            # Find all tickets with this error code
            query = """
                SELECT error_codes FROM krai_pm.service_tickets
                WHERE manufacturer_id = %s AND %s = ANY(error_codes)
            """
            tickets = await self.db.fetch_all(query, (manufacturer_name, code))

            # Count co-occurrences
            for ticket in tickets:
                for other_code in ticket.get("error_codes") or []:
                    if other_code != code:
                        cooccurrence[code][other_code] = cooccurrence[code].get(other_code, 0) + 1

        return cooccurrence

    def _classify_distribution(self, error_codes: list[dict[str, Any]], total_tickets: int) -> str:
        """
        Classify whether error distribution is skewed or uniform.

        Skewed: Top 20% of codes account for 80%+ of tickets.
        Uniform: More balanced distribution.

        Args:
            error_codes: List of (code, count) tuples
            total_tickets: Total number of tickets

        Returns:
            'skewed' or 'uniform'
        """
        if not error_codes or total_tickets == 0:
            return "uniform"

        # Sum top 20% of error codes
        top_count = int(len(error_codes) * 0.2) or 1
        top_count_sum = sum(row["cnt"] for row in error_codes[:top_count])

        # If top 20% accounts for 80%+, it's skewed
        if top_count_sum / total_tickets >= 0.8:
            return "skewed"
        return "uniform"
