"""Part Lifetimes Importer for PM module.

Imports OEM nominal lifetimes for consumables from KM Excel v1.18 into krai_pm.part_lifetimes.
"""

import logging
from typing import Any, ClassVar

import openpyxl

from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class PartLifetimesImporter:
    """Import part lifetimes (consumables) from KM Excel file into PM schema."""

    EXPECTED_COLUMNS: ClassVar[list[str]] = [
        "Manufacturer",
        "ModelFamily",
        "PartCategory",
        "PartNumber",
        "NominalLifetimePages",
        "ColorChannel",
    ]

    PART_CATEGORIES: ClassVar[set[str]] = {
        "toner",
        "drum",
        "fuser",
        "transfer_belt",
        "pickup_roller",
        "developer",
        "image_unit",
        "separation_pad",
        "bypass_tray",
    }

    def __init__(self, db_adapter: DatabaseAdapter):
        self.db_adapter = db_adapter
        self.logger = logger

    async def ingest_file(self, excel_file: Any) -> int:
        """
        Process Excel file and ingest part lifetimes into database.

        Args:
            excel_file: bytes or file-like object

        Returns:
            Number of inserted entries
        """
        if not excel_file:
            raise ValueError("Missing excel_file")

        # Parse Excel
        workbook = openpyxl.load_workbook(excel_file, data_only=True)
        worksheet = workbook.active

        part_entries = await self._extract_part_lifetimes(worksheet)
        inserted_count = await self._insert_parts(part_entries)

        self.logger.info(f"Ingested {inserted_count} part lifetime entries")

        return inserted_count

    async def _extract_part_lifetimes(self, worksheet: openpyxl.worksheet.worksheet.Worksheet) -> list[dict]:
        """Extract part lifetime records from Excel worksheet."""
        entries = []

        # Get header row
        header_row = []
        for cell in worksheet[1]:
            if cell.value:
                header_row.append(cell.value)

        self.logger.debug(f"Found headers: {header_row}")

        # Map header names to indices
        col_indices = {col: idx for idx, col in enumerate(header_row) if col}

        # Extract data rows (skip header)
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=2, values_only=False), start=2):
            if not row[0].value:  # Skip empty rows
                continue

            try:
                entry = self._parse_part_row(row, col_indices)
                if entry:
                    entries.append(entry)
            except Exception as e:
                self.logger.warning(f"Failed to parse row {row_idx}: {e!s}")
                continue

        return entries

    def _parse_part_row(self, row: tuple, col_indices: dict) -> dict | None:
        """Parse a single Excel row into a part lifetime record."""
        try:
            manufacturer = self._get_cell_value(row, col_indices, "Manufacturer")
            model_family = self._get_cell_value(row, col_indices, "ModelFamily")
            part_category = self._get_cell_value(row, col_indices, "PartCategory")

            if not (manufacturer and part_category):
                return None

            # Normalize part category
            part_category_lower = part_category.lower().strip()
            if part_category_lower not in self.PART_CATEGORIES:
                self.logger.debug(f"Unknown part category: {part_category}")
                # Still include it, but log a warning

            part_number = self._get_cell_value(row, col_indices, "PartNumber")
            lifetime_str = self._get_cell_value(row, col_indices, "NominalLifetimePages")
            color_channel = self._get_cell_value(row, col_indices, "ColorChannel")

            # Parse lifetime as integer
            lifetime = None
            if lifetime_str:
                try:
                    lifetime = int(float(str(lifetime_str).strip()))
                except (ValueError, TypeError):
                    self.logger.debug(f"Could not parse lifetime: {lifetime_str}")
                    return None

            if not lifetime:
                return None

            return {
                "manufacturer": manufacturer.strip(),
                "model_family": model_family.strip() if model_family else None,
                "part_category": part_category_lower,
                "part_number": part_number.strip() if part_number else None,
                "nominal_lifetime_pages": lifetime,
                "color_channel": str(color_channel).strip() if color_channel else None,
                "source": "km_excel_v1.18",
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

    async def _insert_parts(self, entries: list[dict]) -> int:
        """Insert part entries into database."""
        if not entries:
            return 0

        # First, resolve manufacturer IDs
        sql_manufacturer_lookup = "SELECT id FROM krai_core.manufacturers WHERE name = %s LIMIT 1"
        sql_product_lookup = "SELECT id FROM krai_core.products WHERE name = %s LIMIT 1"

        sql_insert = """
        INSERT INTO krai_pm.part_lifetimes (
            manufacturer_id, product_id, part_category, part_number,
            nominal_lifetime_pages, color_channel, source, metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        count = 0
        for entry in entries:
            try:
                # Resolve manufacturer ID
                manufacturer_id = await self.db_adapter.fetch_one(sql_manufacturer_lookup, (entry["manufacturer"],))
                if not manufacturer_id:
                    self.logger.debug(f"Manufacturer not found: {entry['manufacturer']}")
                    continue

                manufacturer_id = manufacturer_id[0]

                # Resolve product ID (optional)
                product_id = None
                if entry["model_family"]:
                    product = await self.db_adapter.fetch_one(sql_product_lookup, (entry["model_family"],))
                    if product:
                        product_id = product[0]

                # Insert part entry
                await self.db_adapter.execute(
                    sql_insert,
                    (
                        manufacturer_id,
                        product_id,
                        entry["part_category"],
                        entry["part_number"],
                        entry["nominal_lifetime_pages"],
                        entry["color_channel"],
                        entry["source"],
                        {"model_family": entry["model_family"]} if entry["model_family"] else None,
                    ),
                )
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to insert part entry: {e!s}")
                continue

        return count
