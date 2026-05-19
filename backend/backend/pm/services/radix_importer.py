"""
Import service tickets from Radix RxPlusService API into krai_pm.service_tickets.

Maps Radix activities + spare parts + work times to KRAI schema.
"""

import logging
from datetime import datetime
from typing import Any

from backend.pm.models.radix_models import RadixActivity, RadixSparePart, RadixWorkTime
from backend.pm.services.radix_data_client import RadixDataClient
from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class RadixImporter:
    """Import service activities from Radix into KRAI database."""

    def __init__(
        self,
        db_adapter: DatabaseAdapter,
        radix_client: RadixDataClient,
    ) -> None:
        """
        Initialize Radix importer.

        Args:
            db_adapter: Database adapter for KRAI
            radix_client: Radix API client with valid Bearer token
        """
        self.db = db_adapter
        self.radix = radix_client

    async def import_activities(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 1000,
        skip_duplicates: bool = True,
    ) -> dict[str, int]:
        """
        Import Radix activities as service tickets.

        Args:
            filters: Radix API filters (optional)
            limit: Max activities to fetch
            skip_duplicates: Check for existing tickets before insert

        Returns:
            Dict with counts: imported, skipped, errors
        """
        logger.info(f"Starting Radix activity import (limit={limit}, filters={filters})")

        # Fetch all activities
        try:
            activities_data = await self.radix.get_activities(filters=filters, limit=limit)
        except Exception as e:
            logger.error(f"Failed to fetch Radix activities: {e}")
            return {"imported": 0, "skipped": 0, "errors": 1}

        logger.info(f"Fetched {len(activities_data)} activities from Radix")

        # Parse and validate
        activities = []
        for activity_data in activities_data:
            try:
                activity = RadixActivity.model_validate(activity_data)
                activities.append(activity)
            except Exception as e:
                logger.warning(f"Failed to parse activity {activity_data.get('id')}: {e}")

        # Import each activity
        imported_count = 0
        skipped_count = 0
        error_count = 0

        for activity in activities:
            try:
                result = await self._import_single_activity(activity, skip_duplicates)
                if result:
                    imported_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Error importing activity {activity.id}: {e}")
                error_count += 1

        logger.info(f"Import complete: {imported_count} imported, {skipped_count} skipped, {error_count} errors")

        return {"imported": imported_count, "skipped": skipped_count, "errors": error_count}

    async def _import_single_activity(self, activity: RadixActivity, skip_duplicates: bool = True) -> bool:
        """
        Import single Radix activity to database.

        Args:
            activity: Parsed RadixActivity
            skip_duplicates: Skip if ticket with same ID already exists

        Returns:
            True if imported, False if skipped
        """
        # Check for duplicate
        if skip_duplicates:
            existing = await self.db.fetch_one(
                "SELECT id FROM krai_pm.service_tickets WHERE id = %s",
                activity.id,
            )
            if existing:
                logger.debug(f"Activity {activity.id} already exists, skipping")
                return False

        # Fetch related data (spare parts, work times)
        spare_parts = []
        total_repair_time = 0.0

        try:
            spare_parts_data = await self.radix.get_activity_spare_parts(activity.id)
            spare_parts = [RadixSparePart.model_validate(sp) for sp in spare_parts_data]
        except Exception as e:
            logger.warning(f"Failed to fetch spare parts for {activity.id}: {e}")

        try:
            work_times_data = await self.radix.get_activity_work_times(activity.id)
            work_times = [RadixWorkTime.model_validate(wt) for wt in work_times_data]
            total_repair_time = sum((wt.duration_minutes or 0.0) for wt in work_times)
        except Exception as e:
            logger.warning(f"Failed to fetch work times for {activity.id}: {e}")

        # Map to KRAI schema
        replaced_parts = [sp.part_name for sp in spare_parts if sp.part_name]
        error_codes = []  # Radix doesn't have error codes; would need to extract from notes

        metadata = {
            "radix_id": activity.id,
            "radix_customer": activity.customer_name,
            "radix_device_model": activity.device_model,
            "radix_device_serial": activity.device_serial,
            "radix_state": activity.state,
            "radix_type": activity.activity_type,
            "radix_code": activity.code,
            "source_system": "Radix",
        }

        # Insert ticket
        query = """
            INSERT INTO krai_pm.service_tickets (
                id, problem_short, problem_long, error_codes, replaced_parts,
                repair_time_minutes, manufacturer_id, created_at, updated_at, metadata
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """

        await self.db.execute(
            query,
            activity.id,
            activity.problem_short or "Unknown",
            activity.problem_description or "",
            error_codes,
            replaced_parts,
            total_repair_time if total_repair_time > 0 else None,
            activity.code,  # Radix "code" is location/branch; map to manufacturer_id if available
            activity.created_date or datetime.utcnow(),
            activity.modified_date or datetime.utcnow(),
            metadata,
        )

        logger.info(f"Imported activity {activity.id} ({len(spare_parts)} parts, {total_repair_time}min)")
        return True

    async def get_activity_summary(self) -> dict[str, Any]:
        """Fetch summary statistics from Radix."""
        try:
            # This is exploratory — adjust based on actual Radix response format
            activities = await self.radix.get_activities(limit=1)
            states = await self.radix.get_activity_states()
            types = await self.radix.get_activity_types()

            return {
                "sample_activity": activities[0] if activities else None,
                "states": states,
                "types": types,
            }
        except Exception as e:
            logger.error(f"Failed to fetch activity summary: {e}")
            return {"error": str(e)}
