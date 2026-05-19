"""
Feature extraction from PM database for ML model training.

Converts raw service tickets and maintenance data into normalized feature vectors
for consumption by ML models.
"""

from backend.pm.models.ticket import ServiceTicketFeatures
from backend.services.database_adapter import DatabaseAdapter


class FeatureEngineer:
    """
    Extracts features from PM database for model training and prediction.

    Loads service tickets, parts data, and error codes; normalizes and encodes them
    into feature vectors compatible with XGBoost/LightGBM.
    """

    def __init__(self, db_adapter: DatabaseAdapter) -> None:
        """
        Initialize feature engineer.

        Args:
            db_adapter: Database adapter for querying PM schema
        """
        self.db = db_adapter
        self._top_problems: list[str] | None = None
        self._top_error_codes: list[str] | None = None
        self._manufacturer_map: dict[str, int] | None = None

    async def extract_features(self, ticket_id: str) -> ServiceTicketFeatures:
        """
        Extract feature vector for a single service ticket.

        Args:
            ticket_id: UUID of the service ticket

        Returns:
            ServiceTicketFeatures with all computed fields

        Raises:
            ValueError: If ticket not found or incomplete data
        """
        # Fetch ticket from database
        query = """
            SELECT id, problem_short, problem_long, error_codes, replaced_parts,
                   repair_time_minutes, manufacturer_id, metadata
            FROM krai_pm.service_tickets
            WHERE id = %s
        """
        ticket = await self.db.fetch_one(query, (ticket_id,))
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Ensure caches loaded
        if self._top_problems is None:
            self._top_problems = await self.get_top_problems()
        if self._top_error_codes is None:
            self._top_error_codes = await self._get_top10_error_codes()
        if self._manufacturer_map is None:
            self._manufacturer_map = await self._get_manufacturer_map()

        # Extract problem frequency
        problem_frequency = await self._get_problem_frequency(ticket["problem_short"])

        # Extract error codes one-hot encoding
        error_codes = ticket.get("error_codes") or []
        error_code_top10 = self._encode_error_codes(error_codes)

        # Extract manufacturer encoding
        manufacturer_encoded = self._manufacturer_map.get(ticket.get("manufacturer_id"), 0)

        return ServiceTicketFeatures(
            ticket_id=ticket_id,
            repair_time_minutes=ticket.get("repair_time_minutes"),
            problem_frequency=problem_frequency,
            part_replacement_count=len(ticket.get("replaced_parts") or []),
            error_code_count=len(error_codes),
            manufacturer_encoded=manufacturer_encoded,
            error_code_top10=error_code_top10,
            device_age_months=None,  # Docuware placeholder
            page_count=None,  # Docuware placeholder
            service_history_count=None,  # Docuware placeholder
        )

    async def extract_features_batch(self, limit: int | None = None) -> list[ServiceTicketFeatures]:
        """
        Extract feature vectors for all service tickets.

        Args:
            limit: Max tickets to process (None = all)

        Returns:
            List of ServiceTicketFeatures, one per ticket
        """
        # Ensure caches loaded
        if self._top_problems is None:
            self._top_problems = await self.get_top_problems()
        if self._top_error_codes is None:
            self._top_error_codes = await self._get_top10_error_codes()
        if self._manufacturer_map is None:
            self._manufacturer_map = await self._get_manufacturer_map()

        # Fetch all tickets
        query = """
            SELECT id FROM krai_pm.service_tickets
            ORDER BY created_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        tickets = await self.db.fetch_all(query, ())
        features_list = []

        for row in tickets:
            try:
                features = await self.extract_features(row["id"])
                features_list.append(features)
            except (ValueError, KeyError):
                # Skip tickets with incomplete data
                continue

        return features_list

    async def get_top_problems(self, top_n: int = 20) -> list[str]:
        """
        Get most frequent problem_short values.

        Args:
            top_n: Number of top problems to return

        Returns:
            List of problem_short strings, sorted by frequency descending
        """
        query = """
            SELECT problem_short, COUNT(*) as cnt
            FROM krai_pm.service_tickets
            WHERE problem_short IS NOT NULL
            GROUP BY problem_short
            ORDER BY cnt DESC
            LIMIT %s
        """
        rows = await self.db.fetch_all(query, (top_n,))
        return [row["problem_short"] for row in rows]

    async def _get_problem_frequency(self, problem_short: str) -> int:
        """
        Count how many tickets have the same problem_short.

        Args:
            problem_short: Problem short description

        Returns:
            Count of tickets with this problem
        """
        query = """
            SELECT COUNT(*) as cnt FROM krai_pm.service_tickets
            WHERE problem_short = %s
        """
        result = await self.db.fetch_one(query, (problem_short,))
        return result["cnt"] if result else 0

    async def _get_top10_error_codes(self) -> list[str]:
        """
        Get top-10 most frequent error codes across all tickets.

        Returns:
            List of error code strings
        """
        query = """
            SELECT DISTINCT(unnest(error_codes)) as code, COUNT(*) as cnt
            FROM krai_pm.service_tickets
            WHERE error_codes IS NOT NULL AND array_length(error_codes, 1) > 0
            GROUP BY code
            ORDER BY cnt DESC
            LIMIT 10
        """
        rows = await self.db.fetch_all(query, ())
        return [row["code"] for row in rows]

    async def _get_manufacturer_map(self) -> dict[str, int]:
        """
        Get mapping from manufacturer_id to encoded integer.

        Returns:
            Dict mapping manufacturer_id to integer (1-10)
        """
        query = """
            SELECT DISTINCT manufacturer_id FROM krai_pm.service_tickets
            WHERE manufacturer_id IS NOT NULL
            ORDER BY manufacturer_id
        """
        rows = await self.db.fetch_all(query, ())
        return {row["manufacturer_id"]: i + 1 for i, row in enumerate(rows)}

    def _encode_error_codes(self, error_codes: list[str]) -> list[int]:
        """
        One-hot encode error codes against top-10 list.

        Args:
            error_codes: List of error code strings from ticket

        Returns:
            List of 10 integers (0 or 1), one per top-10 error code
        """
        if self._top_error_codes is None:
            return [0] * 10

        encoding = []
        for top_code in self._top_error_codes:
            encoding.append(1 if top_code in error_codes else 0)
        return encoding
