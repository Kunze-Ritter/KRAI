"""Route calculation and reconstruction from service ticket timestamps and addresses."""

import logging
from datetime import datetime
from typing import Any

from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class RouteCalculator:
    """Calculate service routes from activity timestamps and addresses."""

    def __init__(self, db_adapter: DatabaseAdapter) -> None:
        """Initialize route calculator."""
        self.db = db_adapter

    async def calculate_daily_routes(self, employee_id: str, service_date: str) -> int:
        """
        Calculate routes for all activities by employee on specific date.

        Reconstructs routes by:
        1. Fetching all completed activities for the employee on that date
        2. Sorting by completion time
        3. Calculating travel time as gap between activities
        4. Estimating distance if addresses are available

        Args:
            employee_id: Employee/technician ID
            service_date: Date in YYYY-MM-DD format

        Returns:
            Number of routes calculated
        """
        logger.info(f"Calculating routes for employee {employee_id} on {service_date}")

        # Fetch all activities for this employee on this date
        activities = await self.db.fetch_all(
            """
            SELECT
                st.id, st.completed_date, st.repair_time_minutes,
                st.customer_address, st.service_location_address,
                st.metadata->>'radix_customer' as customer_name,
                st.metadata->>'radix_device_model' as device_model
            FROM krai_pm.service_tickets st
            WHERE st.employee_id = %s
                AND DATE(st.completed_date) = %s
                AND st.completed_date IS NOT NULL
            ORDER BY st.completed_date ASC
            """,
            (employee_id, service_date),
        )

        if not activities:
            logger.info(f"No activities found for employee {employee_id} on {service_date}")
            return 0

        logger.info(f"Found {len(activities)} activities")

        # Calculate routes between activities
        routes_count = 0
        for idx, activity in enumerate(activities):
            try:
                # Determine from and to addresses
                from_address = activities[idx - 1]["service_location_address"] if idx > 0 else None
                to_address = activity["service_location_address"] or activity["customer_address"]

                # Calculate travel time (gap between previous activity end and this one start)
                departure_time = None
                arrival_time = activity["completed_date"]

                if idx > 0 and activities[idx - 1]["completed_date"]:
                    prev_end = activities[idx - 1]["completed_date"]
                    curr_start = arrival_time
                    if isinstance(curr_start, str):
                        curr_start = datetime.fromisoformat(curr_start)
                    if isinstance(prev_end, str):
                        prev_end = datetime.fromisoformat(prev_end)

                    departure_time = prev_end

                # Insert route record
                query = """
                    INSERT INTO krai_pm.service_routes (
                        activity_id, route_sequence, employee_id,
                        from_address, to_address,
                        departure_time, arrival_time,
                        duration_minutes, distance_km,
                        route_calculation_method, metadata
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s
                    )
                    ON CONFLICT DO NOTHING
                """

                duration_minutes = None
                if departure_time and arrival_time:
                    if isinstance(arrival_time, str):
                        arrival_time = datetime.fromisoformat(arrival_time)
                    duration_minutes = int((arrival_time - departure_time).total_seconds() / 60)

                metadata = {
                    "customer_name": activity["customer_name"],
                    "device_model": activity["device_model"],
                }

                params = (
                    activity["id"],
                    idx,
                    employee_id,
                    from_address,
                    to_address,
                    departure_time,
                    arrival_time,
                    duration_minutes,
                    None,  # distance_km - would be calculated via Maps API
                    "reconstructed_from_timestamps",
                    metadata,
                )
                await self.db.execute_query(query, params)

                routes_count += 1

            except Exception as e:
                logger.error(f"Failed to calculate route for activity {activity['id']}: {e}")

        logger.info(f"✓ Calculated {routes_count} routes for employee {employee_id} on {service_date}")
        return routes_count

    async def calculate_all_routes(self, limit_days: int = 30) -> dict[str, Any]:
        """
        Calculate routes for all employees for the last N days.

        Args:
            limit_days: Number of recent days to process

        Returns:
            Summary with employee count, route count, date range
        """
        logger.info(f"Calculating all routes for the last {limit_days} days")

        # Get unique employees with completed activities
        employees = await self.db.fetch_all(
            """
            SELECT DISTINCT employee_id
            FROM krai_pm.service_tickets
            WHERE completed_date IS NOT NULL
                AND completed_date >= NOW() - INTERVAL '1 day' * %s
                AND employee_id IS NOT NULL
            ORDER BY employee_id
            """,
            limit_days,
        )

        logger.info(f"Found {len(employees)} employees with activities")

        total_routes = 0
        employee_routes = {}

        for emp in employees:
            employee_id = emp["employee_id"]
            if not employee_id:
                continue

            # Get date range for this employee
            dates = await self.db.fetch_all(
                """
                SELECT DISTINCT DATE(completed_date) as service_date
                FROM krai_pm.service_tickets
                WHERE employee_id = %s
                    AND completed_date IS NOT NULL
                ORDER BY service_date DESC
                LIMIT %s
                """,
                (employee_id, limit_days),
            )

            routes_for_employee = 0
            for date_row in dates:
                routes = await self.calculate_daily_routes(employee_id, date_row["service_date"].isoformat())
                routes_for_employee += routes

            employee_routes[employee_id] = routes_for_employee
            total_routes += routes_for_employee

        logger.info(f"✓ Calculated {total_routes} total routes for {len(employee_routes)} employees")

        return {
            "total_routes": total_routes,
            "employee_count": len(employee_routes),
            "employees": employee_routes,
            "days_processed": limit_days,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def calculate_efficiency_metrics(self) -> dict[str, Any]:
        """
        Calculate service efficiency metrics per employee.

        Returns:
            Efficiency metrics aggregated by employee
        """
        metrics = await self.db.fetch_all(
            """
            SELECT
                st.employee_id,
                st.employee_name,
                COUNT(*) as total_tickets,
                ROUND(AVG(st.repair_time_minutes)::numeric, 2) as avg_repair_minutes,
                ROUND(AVG(st.total_travel_time_minutes)::numeric, 2) as avg_travel_minutes,
                ROUND(
                    AVG(COALESCE(st.total_travel_time_minutes, 0) +
                        COALESCE(st.repair_time_minutes, 0))::numeric, 2
                ) as avg_total_service_minutes,
                MIN(st.completed_date) as first_service_date,
                MAX(st.completed_date) as last_service_date
            FROM krai_pm.service_tickets st
            WHERE st.completed_date IS NOT NULL
                AND st.employee_id IS NOT NULL
            GROUP BY st.employee_id, st.employee_name
            ORDER BY total_tickets DESC
            """
        )

        return {
            "employees": [dict(m) for m in metrics],
            "metric_timestamp": datetime.utcnow().isoformat(),
        }
