"""Feature extraction from service tickets for ML training."""

import logging

from backend.pm.models.ticket import ServiceTicketFeatures
from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Extract ML features from service ticket data."""

    def __init__(self, db_adapter: DatabaseAdapter) -> None:
        """Initialize feature engineer with database access."""
        self.db = db_adapter
        self._top10_error_codes: list[str] | None = None

    async def extract_features(self, ticket_id: str) -> ServiceTicketFeatures | None:
        """Extract features for a single ticket.

        Args:
            ticket_id: Service ticket ID

        Returns:
            ServiceTicketFeatures or None if ticket not found
        """
        ticket = await self.db.fetch_one(
            """
            SELECT id, problem_short, repair_time_minutes, error_codes,
                   replaced_parts, manufacturer_id
            FROM krai_pm.service_tickets
            WHERE id = %s
            """,
            ticket_id,
        )

        if not ticket:
            return None

        # Get frequency of this problem
        frequency_row = await self.db.fetch_one(
            """
            SELECT COUNT(*) as count FROM krai_pm.service_tickets
            WHERE problem_short = %s
            """,
            ticket["problem_short"],
        )
        problem_frequency = frequency_row["count"] if frequency_row else 0

        # Get error codes and encode top10
        error_codes = ticket.get("error_codes", []) or []
        if not error_codes:
            error_codes = []

        error_code_top10 = await self._encode_error_codes_top10(error_codes)

        return ServiceTicketFeatures(
            ticket_id=ticket["id"],
            repair_time_minutes=ticket.get("repair_time_minutes"),
            problem_frequency=problem_frequency,
            part_replacement_count=len(ticket.get("replaced_parts", []) or []),
            error_code_count=len(error_codes),
            manufacturer_encoded=self._encode_manufacturer(ticket.get("manufacturer_id")),
            error_code_top10=error_code_top10,
            device_age_months=None,
            page_count=None,
            service_history_count=None,
        )

    async def extract_features_batch(self, limit: int | None = None) -> list[ServiceTicketFeatures]:
        """Extract features for all tickets.

        Args:
            limit: Maximum number of tickets to process

        Returns:
            List of feature vectors
        """
        query = """
            SELECT id FROM krai_pm.service_tickets
            ORDER BY created_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        tickets = await self.db.fetch_all(query)

        features_list = []
        for ticket in tickets:
            try:
                features = await self.extract_features(ticket["id"])
                if features:
                    features_list.append(features)
            except Exception as e:
                logger.warning(f"Failed to extract features for {ticket['id']}: {e}")

        logger.info(f"Extracted features for {len(features_list)} tickets")
        return features_list

    async def get_top_problems(self, top_n: int = 20) -> list[str]:
        """Get most common problem types.

        Args:
            top_n: Number of top problems to return

        Returns:
            List of problem short descriptions
        """
        rows = await self.db.fetch_all(
            f"""
            SELECT problem_short, COUNT(*) as count
            FROM krai_pm.service_tickets
            WHERE problem_short IS NOT NULL AND problem_short != ''
            GROUP BY problem_short
            ORDER BY count DESC
            LIMIT {top_n}
            """
        )

        return [row["problem_short"] for row in rows]

    async def _get_top10_error_codes(self) -> list[str]:
        """Get the 10 most common error codes for One-Hot encoding.

        Returns:
            List of top 10 error code strings
        """
        if self._top10_error_codes is not None:
            return self._top10_error_codes

        # Using PostgreSQL unnest to flatten error_codes arrays
        rows = await self.db.fetch_all(
            """
            SELECT unnest(error_codes) as code, COUNT(*) as count
            FROM krai_pm.service_tickets
            WHERE error_codes IS NOT NULL AND array_length(error_codes, 1) > 0
            GROUP BY code
            ORDER BY count DESC
            LIMIT 10
            """
        )

        self._top10_error_codes = [row["code"] for row in rows]
        return self._top10_error_codes

    async def _encode_error_codes_top10(self, error_codes: list[str]) -> list[int]:
        """One-Hot encode error codes against top 10 list.

        Args:
            error_codes: List of error codes from ticket

        Returns:
            One-Hot encoded list of length 10 (0 or 1)
        """
        top10 = await self._get_top10_error_codes()
        return [1 if code in top10 else 0 for code in top10]

    @staticmethod
    def _encode_manufacturer(manufacturer_id: str | None) -> int:
        """Encode manufacturer ID to integer.

        Args:
            manufacturer_id: Manufacturer code from ticket

        Returns:
            Integer encoding (0 for unknown, 1+ for known manufacturers)
        """
        if not manufacturer_id:
            return 0

        manufacturer_map = {
            "KM": 1,
            "HP": 2,
            "XEROX": 3,
            "RICOH": 4,
            "CANON": 5,
            "BROTHER": 6,
            "LEXMARK": 7,
            "KYOCERA": 8,
            "SHARP": 9,
            "FUJIFILM": 10,
            "RISO": 11,
            "TOSHIBA": 12,
            "OKI": 13,
            "EPSON": 14,
        }

        return manufacturer_map.get(manufacturer_id.upper(), 0)
