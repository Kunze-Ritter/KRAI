"""Ticket Ingestion Processor for PM module.

Imports service tickets from KM Excel sources (OF, PP, SOL) into krai_pm.service_tickets.
"""

import contextlib
import json
import logging
from datetime import datetime
from typing import Any, ClassVar

import openpyxl

from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class TicketIngestionProcessor:
    """Import service tickets from KM Excel files into PM schema."""

    SUPPORTED_SOURCES: ClassVar[dict[str, str]] = {
        "km_anfragen_of": "Office",
        "km_anfragen_pp": "Production",
        "km_anfragen_sol": "Solutions",
    }

    EXPECTED_COLUMNS: ClassVar[list[str]] = [
        "TicketID",
        "Erstellt",
        "Gerät/Modell",
        "Problem Kurz",
        "Problem Lang",
        "Lösung",
        "Fehlercodes",
        "Ersatzteile",
        "Reparaturzeit (min)",
    ]

    def __init__(self, db_adapter: DatabaseAdapter):
        self.db_adapter = db_adapter
        self.logger = logger

    async def ingest_file(self, excel_file: Any, source_system: str) -> int:
        """
        Process Excel file and ingest tickets into database.

        Args:
            excel_file: bytes or file-like object
            source_system: one of km_anfragen_of, km_anfragen_pp, km_anfragen_sol

        Returns:
            Number of inserted tickets
        """
        if not source_system or source_system not in self.SUPPORTED_SOURCES:
            raise ValueError(f"Invalid source_system. Expected one of {list(self.SUPPORTED_SOURCES.keys())}")

        if not excel_file:
            raise ValueError("Missing excel_file")

        # Parse Excel
        workbook = openpyxl.load_workbook(excel_file, data_only=True)
        worksheet = workbook.active

        tickets = await self._extract_tickets(worksheet, source_system)
        inserted_count = await self._insert_tickets(tickets)

        self.logger.info(f"Ingested {inserted_count} tickets from {source_system}")

        return inserted_count

    async def _extract_tickets(
        self, worksheet: openpyxl.worksheet.worksheet.Worksheet, source_system: str
    ) -> list[dict]:
        """Extract ticket records from Excel worksheet."""
        tickets = []

        # Get header row
        header_row = []
        for cell in worksheet[1]:
            if cell.value:
                header_row.append(cell.value)

        self.logger.debug(f"Found headers: {header_row}")

        # Validate headers (case-insensitive)
        header_lower = [h.lower() if h else None for h in header_row]
        expected_lower = [h.lower() for h in self.EXPECTED_COLUMNS]

        # Check if at least the first few columns match
        if not all(expected_lower[i] == header_lower[i] for i in range(min(3, len(header_lower)))):
            self.logger.warning(f"Headers don't match expected format. Got: {header_row}")

        # Map header names to indices
        col_indices = {col: idx for idx, col in enumerate(header_row) if col}

        # Extract data rows (skip header)
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=2, values_only=False), start=2):
            if not row[0].value:  # Skip empty rows
                continue

            try:
                ticket = self._parse_row(row, col_indices, source_system)
                if ticket:
                    tickets.append(ticket)
            except Exception as e:
                self.logger.warning(f"Failed to parse row {row_idx}: {e!s}")
                continue

        return tickets

    def _parse_row(self, row: tuple, col_indices: dict, source_system: str) -> dict | None:
        """Parse a single Excel row into a ticket record."""
        try:
            ticket_id = self._get_cell_value(row, col_indices, "TicketID")
            if not ticket_id:
                return None

            created_str = self._get_cell_value(row, col_indices, "Erstellt")
            created_at = self._parse_date(created_str) if created_str else None

            model_string = self._get_cell_value(row, col_indices, "Gerät/Modell")
            problem_short = self._get_cell_value(row, col_indices, "Problem Kurz")
            problem_long = self._get_cell_value(row, col_indices, "Problem Lang")
            solution = self._get_cell_value(row, col_indices, "Lösung")
            error_codes_str = self._get_cell_value(row, col_indices, "Fehlercodes")
            parts_str = self._get_cell_value(row, col_indices, "Ersatzteile")
            repair_time_str = self._get_cell_value(row, col_indices, "Reparaturzeit (min)")

            # Parse arrays from semicolon-separated strings
            error_codes = [e.strip() for e in error_codes_str.split(";") if e.strip()] if error_codes_str else []
            parts = [p.strip() for p in parts_str.split(";") if p.strip()] if parts_str else []

            repair_time = None
            if repair_time_str:
                with contextlib.suppress(ValueError, TypeError):
                    repair_time = int(repair_time_str)

            return {
                "source_system": source_system,
                "source_ticket_id": str(ticket_id),
                "model_string_raw": model_string,
                "created_at_source": created_at,
                "problem_short": problem_short,
                "problem_long": problem_long,
                "solution_text": solution,
                "error_codes": error_codes,
                "replaced_parts": parts,
                "repair_time_minutes": repair_time,
            }
        except Exception as e:
            self.logger.debug(f"Error parsing row: {e!s}")
            return None

    def _get_cell_value(self, row: tuple, col_indices: dict, col_name: str) -> Any:
        """Safely get cell value from row."""
        if col_name not in col_indices:
            return None
        idx = col_indices[col_name]
        if idx >= len(row):
            return None
        cell = row[idx]
        return cell.value if cell else None

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse date string to datetime."""
        if not date_str:
            return None
        if isinstance(date_str, datetime):
            return date_str
        # Try common formats
        formats = ["%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"]
        for fmt in formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except (ValueError, TypeError):
                continue
        return None

    async def _insert_tickets(self, tickets: list[dict]) -> int:
        """Insert tickets into database."""
        if not tickets:
            return 0

        # Prepare bulk insert
        sql = """
        INSERT INTO krai_pm.service_tickets (
            source_system, source_ticket_id, model_string_raw,
            created_at_source, problem_short, problem_long,
            solution_text, error_codes, replaced_parts, repair_time_minutes,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_system, source_ticket_id) DO NOTHING
        """

        count = 0
        for ticket in tickets:
            try:
                metadata = json.dumps({"ingestion_source": "excel"})
                await self.db_adapter.execute_query(
                    sql,
                    (
                        ticket["source_system"],
                        ticket["source_ticket_id"],
                        ticket["model_string_raw"],
                        ticket["created_at_source"],
                        ticket["problem_short"],
                        ticket["problem_long"],
                        ticket["solution_text"],
                        ticket["error_codes"],
                        ticket["replaced_parts"],
                        ticket["repair_time_minutes"],
                        metadata,
                    ),
                )
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to insert ticket {ticket['source_ticket_id']}: {e!s}")
                continue

        return count
