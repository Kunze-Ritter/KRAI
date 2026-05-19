"""
Warranty tracker service for batch registration of warranty events.

Processes service tickets to register part warranty events, tracking
failures relative to warranty windows (typically 365 days).
"""

from datetime import datetime, timedelta
from typing import Any

from backend.services.database_adapter import DatabaseAdapter


class WarrantyTracker:
    """
    Batch registers warranty events from service tickets.

    Tracks part replacements against warranty windows and nominal lifespans
    to quantify early failures and warranty exposure.
    """

    WARRANTY_DAYS_DEFAULT = 365

    def __init__(self, db_adapter: DatabaseAdapter) -> None:
        self.db = db_adapter

    async def register_ticket_events(self, ticket_id: str, warranty_days: int = WARRANTY_DAYS_DEFAULT) -> int:
        """
        Register warranty events for all parts replaced in a ticket.

        Args:
            ticket_id: Service ticket ID
            warranty_days: Warranty window (default 365 days)

        Returns:
            Number of warranty events created (0 if already registered)
        """
        fetch_ticket_query = """
        SELECT
            st.id,
            st.completed_date,
            st.manufacturer_id,
            st.replaced_part_categories,
            m.id as mfr_id,
            m.name as mfr_name
        FROM krai_pm.service_tickets st
        LEFT JOIN krai_core.manufacturers m ON st.manufacturer_id = m.id
        WHERE st.id = $1
        """

        ticket = await self.db.fetchrow(fetch_ticket_query, ticket_id)
        if not ticket:
            return 0

        completed_date = ticket["completed_date"]
        if not completed_date:
            return 0

        mfr_id = ticket["mfr_id"]
        part_categories = ticket["replaced_part_categories"] or []

        if not part_categories:
            return 0

        count = 0
        warranty_expiry = completed_date + timedelta(days=warranty_days)
        is_in_warranty = completed_date <= datetime.utcnow()

        for part_category in part_categories:
            part_lifetimes_query = """
            SELECT nominal_lifetime_pages FROM krai_pm.part_lifetimes
            WHERE manufacturer_id = $1 AND part_category = $2
            LIMIT 1
            """

            part_row = await self.db.fetchrow(part_lifetimes_query, mfr_id, part_category)
            nominal_lifetime = part_row["nominal_lifetime_pages"] if part_row else None

            check_existing = """
            SELECT id FROM krai_pm.part_warranty_events
            WHERE ticket_id = $1 AND part_category = $2
            """

            existing = await self.db.fetchrow(check_existing, ticket_id, part_category)
            if existing:
                continue

            insert_query = """
            INSERT INTO krai_pm.part_warranty_events (
                ticket_id, manufacturer_id, part_category, failure_date,
                warranty_expiry_date, is_in_warranty, nominal_lifetime_pages,
                actual_runtime_pages, mismatch_ratio, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT DO NOTHING
            """

            await self.db.execute(
                insert_query,
                ticket_id,
                mfr_id,
                part_category,
                completed_date,
                warranty_expiry,
                is_in_warranty,
                nominal_lifetime,
                None,  # actual_runtime_pages placeholder
                None,  # mismatch_ratio placeholder
                "{}",  # metadata
            )
            count += 1

        return count

    async def run_batch_registration(
        self, limit: int | None = None, warranty_days: int = WARRANTY_DAYS_DEFAULT
    ) -> dict[str, int]:
        """
        Register warranty events for all tickets without existing events.

        Args:
            limit: Max tickets to process (None = all)
            warranty_days: Warranty window (default 365 days)

        Returns:
            Dict with keys: registered, skipped, errors
        """
        get_tickets_query = """
        SELECT DISTINCT st.id FROM krai_pm.service_tickets st
        LEFT JOIN krai_pm.part_warranty_events pwe ON st.id = pwe.ticket_id
        WHERE pwe.id IS NULL
        AND st.replaced_part_categories IS NOT NULL
        AND array_length(st.replaced_part_categories, 1) > 0
        """

        if limit:
            get_tickets_query += f"\nLIMIT {limit}"

        ticket_ids = await self.db.fetch(get_tickets_query)

        registered = 0
        skipped = 0
        errors = 0

        for row in ticket_ids:
            try:
                ticket_id = row["id"]
                events = await self.register_ticket_events(ticket_id, warranty_days)
                if events > 0:
                    registered += events
                else:
                    skipped += 1
            except Exception:
                errors += 1

        return {
            "registered": registered,
            "skipped": skipped,
            "errors": errors,
        }

    async def get_summary(self) -> dict[str, Any]:
        """
        Get summary statistics of registered warranty events.

        Returns:
            Dict with: total_events, warranty_eligible, avg_warranty_rate_pct
        """
        query = """
        SELECT
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE is_in_warranty) as warranty_eligible,
            COUNT(DISTINCT manufacturer_id) as total_manufacturers,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_in_warranty)
                  / NULLIF(COUNT(*), 0), 2) as avg_warranty_rate_pct
        FROM krai_pm.part_warranty_events
        """

        row = await self.db.fetchrow(query)

        return {
            "total_events": int(row["total_events"] or 0),
            "warranty_eligible": int(row["warranty_eligible"] or 0),
            "total_manufacturers": int(row["total_manufacturers"] or 0),
            "avg_warranty_rate_pct": float(row["avg_warranty_rate_pct"] or 0.0),
        }
