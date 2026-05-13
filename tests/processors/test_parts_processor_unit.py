"""
Unit tests for PartsProcessor components.

Covers:
- Deterministic unit tests for the parts extractor helper (via mock_parts_extractor)
- Direct unit tests for PartsProcessor helper methods:
  - _extract_part_name
  - _extract_description_and_category
  - _extract_and_link_parts_from_text
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.processors.parts_processor import PartsProcessor


@pytest.mark.parts
class TestPartsExtractor:
    """Test parts extraction functionality with deterministic mocks."""

    def test_extract_hp_parts(self, mock_parts_extractor):
        """Test extraction of HP parts from text."""
        extractor = mock_parts_extractor

        text = "Replace part 6QN29-67005 - Fuser Unit. Install RM1-1234-000 - Transfer Roller."
        parts = extractor(text, manufacturer="HP")

        assert len(parts) == 2
        part_numbers = [p["part"] for p in parts]
        assert "6QN29-67005" in part_numbers
        assert "RM1-1234-000" in part_numbers

        # Verify HP part details
        fuser_part = next(p for p in parts if p["part"] == "6QN29-67005")
        assert fuser_part["pattern_name"] == "hp_main_part"
        assert fuser_part["confidence"] == 0.9
        assert fuser_part["manufacturer"] == "HP"
        assert "Fuser Unit" in fuser_part["context"]

    def test_extract_konica_minolta_parts(self, mock_parts_extractor):
        """Test extraction of Konica Minolta parts from text."""
        extractor = mock_parts_extractor

        text = "A1DU-R750-00 - Developer Unit. Replace 4062-R750-01 - Drum Unit."
        parts = extractor(text, manufacturer="Konica Minolta")

        assert len(parts) == 2
        part_numbers = [p["part"] for p in parts]
        assert "A1DU-R750-00" in part_numbers
        assert "4062-R750-01" in part_numbers

        developer_part = next(p for p in parts if p["part"] == "A1DU-R750-00")
        assert developer_part["pattern_name"] == "konica_developer"
        assert developer_part["confidence"] == 0.95
        assert developer_part["manufacturer"] == "Konica Minolta"
        assert "Developer Unit" in developer_part["context"]

    def test_extract_canon_parts(self, mock_parts_extractor):
        """Test extraction of Canon parts from text."""
        extractor = mock_parts_extractor

        text = "Canon: FM3-5945-000 - Fuser Film replacement required."
        parts = extractor(text, manufacturer="Canon")

        assert len(parts) == 1
        part = parts[0]
        assert part["part"] == "FM3-5945-000"
        assert part["pattern_name"] == "canon_fuser"
        assert part["confidence"] == 0.92
        assert part["manufacturer"] == "Canon"
        assert "Fuser Film" in part["context"]

    def test_extract_lexmark_parts(self, mock_parts_extractor):
        """Test extraction of Lexmark parts from text."""
        extractor = mock_parts_extractor

        text = "Install 40X5852 - Toner Cartridge in Lexmark printer."
        parts = extractor(text, manufacturer="Lexmark")

        assert len(parts) == 1
        part = parts[0]
        assert part["part"] == "40X5852"
        assert part["pattern_name"] == "lexmark_consumable"
        assert part["confidence"] == 0.9
        assert part["manufacturer"] == "Lexmark"
        assert "Toner Cartridge" in part["context"]

    def test_extract_consumables(self, mock_parts_extractor):
        """Test extraction of consumable parts."""
        extractor = mock_parts_extractor

        text = "Use CE285A Black Toner. High yield Q7553X available."
        parts = extractor(text, manufacturer="HP")

        assert len(parts) == 2
        part_numbers = [p["part"] for p in parts]
        assert "CE285A" in part_numbers
        assert "Q7553X" in part_numbers

        toner_part = next(p for p in parts if p["part"] == "CE285A")
        assert toner_part["pattern_name"] == "hp_consumable"
        assert toner_part["confidence"] == 0.95
        assert "Black Toner" in toner_part["context"]

    def test_extract_no_parts(self, mock_parts_extractor):
        """Test extraction from text with no parts."""
        extractor = mock_parts_extractor

        text = "This document contains no part numbers or technical information."
        parts = extractor(text, manufacturer="AUTO")

        assert len(parts) == 0

    def test_extract_multiple_manufacturers(self, mock_parts_extractor):
        """Test extraction with multiple manufacturer parts in same text."""
        extractor = mock_parts_extractor

        text = (
            "HP: Replace 6QN29-67005 Fuser Unit. "
            "Konica Minolta: Install A1DU-R750-00 Developer Unit. "
            "Canon: Use FM3-5945-000 Fuser Film. "
            "Lexmark: Install 40X5852 Toner Cartridge."
        )
        parts = extractor(text, manufacturer="AUTO")

        assert len(parts) >= 4
        part_numbers = [p["part"] for p in parts]
        assert "6QN29-67005" in part_numbers
        assert "A1DU-R750-00" in part_numbers
        assert "FM3-5945-000" in part_numbers
        assert "40X5852" in part_numbers


@pytest.mark.parts
class TestPartsProcessorHelpers:
    """Direct unit tests for PartsProcessor helper methods."""

    def _make_processor(self) -> PartsProcessor:
        adapter = MagicMock()
        return PartsProcessor(database_adapter=adapter)

    # _extract_part_name -------------------------------------------------

    @pytest.mark.parametrize(
        "context, part_number, expected",
        [
            ("Replace the Fuser Unit - 6QN29-67005 immediately.", "6QN29-67005", "Fuser Unit"),
            ("Install the Transfer Roller - RM1-1234-000 carefully.", "RM1-1234-000", "Transfer Roller"),
            ("Use the maintenance kit: 6QN29-67005 for regular service.", "6QN29-67005", "maintenance kit"),
            ("Fuser Unit: 6QN29-67005 must be replaced.", "6QN29-67005", "Fuser Unit"),
            ("component: Transfer Roller - RM1-1234-000 should be inspected.", "RM1-1234-000", "Transfer Roller"),
            ("assembly: paper feed unit - 1234-ABC is optional.", "1234-ABC", "paper feed unit"),
            ("REPLACE THE FUSER UNIT - 6QN29-67005 when needed.", "6QN29-67005", "fuser unit"),
            (
                "Replace the Fuser Unit - 6QN29-67005. Fuser Unit: 6QN29-67005.",
                "6QN29-67005",
                "Fuser Unit",
            ),
            ("Order the maintenance kit - KIT-0001 for preventive replacement.", "KIT-0001", "maintenance kit"),
            ("Use High Capacity Cartridge - CE285X for extended printing.", "CE285X", "High Capacity Cartridge"),
        ],
    )
    def test_extract_part_name_patterns(self, context: str, part_number: str, expected: str):
        """Verify that common context patterns yield the correct short part name.

        Covers command-style, label-style, and component: name - part forms,
        including case-insensitive matches and multiple patterns in one string.
        """
        processor = self._make_processor()

        name = processor._extract_part_name(context, part_number)
        assert name is not None
        assert name.lower() == expected.lower()
        assert len(name) <= 100

    def test_extract_part_name_no_match_returns_none(self):
        """If no known pattern is present, helper must return None."""
        processor = self._make_processor()
        context = "Check part 6QN29-67005 only by number without label."

        name = processor._extract_part_name(context, "6QN29-67005")
        assert name is None

    def test_extract_part_name_truncates_to_max_length(self):
        """Very long names are truncated to at most 100 characters."""
        processor = self._make_processor()
        # Construct a very long descriptive name before the part number.
        long_name = "very long maintenance assembly kit " * 10
        context = f"replace the {long_name}- 6QN29-67005"

        name = processor._extract_part_name(context, "6QN29-67005")
        # Helper always returns at most 100 chars by design.
        assert name is not None
        assert len(name) <= 100

    # _extract_description_and_category ----------------------------------

    @pytest.mark.parametrize(
        "context, part_number, expected_category",
        [
            ("Install toner cartridge CE285A in the printer.", "CE285A", "consumable"),
            ("Replace the fuser assembly 6QN29-67005 for better performance.", "6QN29-67005", "assembly"),
            ("Check the sensor board RM1-1234-000 for faults.", "RM1-1234-000", "component"),
            ("Inspect the transfer roller gear inside the printer.", "RM1-0000-000", "mechanical"),
            ("Disconnect the power harness cable before servicing.", "CABLE-01", "electrical"),
            ("Developer unit and toner cartridge should be replaced.", "DEV-01", "consumable"),
            ("This is a general note without any part keywords.", "GEN-01", None),
            ("Install new ink cartridge 953XL before printing.", "953XL", "consumable"),
            ("Replace the finisher unit assembly 1234-UNIT for stapling issues.", "1234-UNIT", "assembly"),
            ("Check motor and sensor board on part MOTOR-01 for noise.", "MOTOR-01", "component"),
            ("Lubricate all gears and roller surfaces for part GEAR-01.", "GEAR-01", "mechanical"),
            ("Route the LVDS cable and harness behind the frame.", "LVDS-01", "electrical"),
            ("Replace the PCB control board PWB-123; this circuit board fails often.", "PWB-123", "component"),
            ("Check belt tension on transfer belt BELT-01 before operation.", "BELT-01", "mechanical"),
            ("Connector on harness lead may be damaged for part CONN-01.", "CONN-01", "electrical"),
        ],
    )
    def test_extract_description_and_category_keywords(
        self, context: str, part_number: str, expected_category: str | None
    ):
        """Map keyword-containing context to the correct category and description."""
        processor = self._make_processor()

        description, category = processor._extract_description_and_category(context, part_number)

        assert isinstance(description, str)
        # Description should preserve the original content (modulo whitespace).
        assert description.startswith(context.split()[0])
        assert len(description) <= 500
        assert category == expected_category

    def test_extract_description_truncates_long_context(self):
        """Description is a cleaned version of context limited to 500 characters."""
        processor = self._make_processor()
        base = "This is a long description about a fuser unit and toner cartridge. "
        context = base * 50  # > 500 characters

        description, category = processor._extract_description_and_category(context, "6QN29-67005")

        assert category == "consumable"  # contains "toner" / "cartridge" keywords
        assert isinstance(description, str)
        assert len(description) == 500

    def test_extract_description_strips_whitespace(self):
        """Newlines and repeated spaces are normalized in the description."""
        processor = self._make_processor()
        context = "Install  CE285A  toner\n\ncartridge   in  the printer."

        description, category = processor._extract_description_and_category(context, "CE285A")

        assert "  " not in description
        assert "\n" not in description
        assert description.startswith("Install CE285A toner cartridge")
        assert category == "consumable"

    # _extract_and_link_parts_from_text ----------------------------------

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_basic_success(self, mock_database_adapter):
        """Parts are looked up and links created with correct payload fields."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            mock_extract.return_value = [
                {"part": "6QN29-67005", "confidence": 0.9},
                {"part": "RM1-1234-000", "confidence": 0.75},
            ]

            mock_database_adapter.get_part_by_number = AsyncMock(
                side_effect=lambda pn: {"id": f"part-{pn}", "part_number": pn}
            )
            mock_database_adapter.create_error_code_part_link = AsyncMock()

            logger_adapter = MagicMock()

            linked = await processor._extract_and_link_parts_from_text(
                text="dummy text", error_code_id="ec-1", source="solution_text", adapter=logger_adapter
            )

            assert linked == 2
            assert mock_database_adapter.create_error_code_part_link.await_count == 2

            calls = mock_database_adapter.create_error_code_part_link.await_args_list
            payloads = [c.args[0] for c in calls]
            assert {p["part_id"] for p in payloads} == {"part-6QN29-67005", "part-RM1-1234-000"}
            assert {p["error_code_id"] for p in payloads} == {"ec-1"}
            assert {p["extraction_source"] for p in payloads} == {"solution_text"}
            assert any(p["relevance_score"] == 0.9 for p in payloads)
            assert any(p["relevance_score"] == 0.75 for p in payloads)

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_no_parts_found(self, mock_database_adapter):
        """If extractor returns no parts, no links are created."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            mock_extract.return_value = []

            mock_database_adapter.get_part_by_number = AsyncMock(return_value=None)
            mock_database_adapter.create_error_code_part_link = AsyncMock()

            linked = await processor._extract_and_link_parts_from_text(
                text="no parts here", error_code_id="ec-2", source="chunk", adapter=MagicMock()
            )

            assert linked == 0
            mock_database_adapter.create_error_code_part_link.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_skips_missing_parts(self, mock_database_adapter):
        """Parts not present in the catalog are skipped."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            mock_extract.return_value = [
                {"part": "KNOWN-1", "confidence": 0.8},
                {"part": "UNKNOWN-2", "confidence": 0.9},
            ]

            async def fake_get_part(pn: str) -> dict[str, Any] | None:
                if pn == "KNOWN-1":
                    return {"id": "part-known-1", "part_number": pn}
                return None

            mock_database_adapter.get_part_by_number = AsyncMock(side_effect=fake_get_part)
            mock_database_adapter.create_error_code_part_link = AsyncMock()

            linked = await processor._extract_and_link_parts_from_text(
                text="dummy", error_code_id="ec-3", source="chunk", adapter=MagicMock()
            )

            assert linked == 1
            mock_database_adapter.create_error_code_part_link.assert_awaited_once()
            payload = mock_database_adapter.create_error_code_part_link.await_args[0][0]
            assert payload["part_id"] == "part-known-1"

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_link_creation_error_is_ignored(self, mock_database_adapter):
        """Database errors during link creation must not abort processing."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            mock_extract.return_value = [
                {"part": "P1", "confidence": 0.8},
                {"part": "P2", "confidence": 0.9},
            ]

            mock_database_adapter.get_part_by_number = AsyncMock(side_effect=lambda pn: {"id": pn, "part_number": pn})

            async def fake_create_link(payload: dict[str, Any]) -> None:
                if payload["part_id"] == "P1":
                    raise Exception("duplicate link")
                return

            mock_database_adapter.create_error_code_part_link = AsyncMock(side_effect=fake_create_link)

            linked = await processor._extract_and_link_parts_from_text(
                text="dummy", error_code_id="ec-4", source="chunk", adapter=MagicMock()
            )

            # One link fails, the other succeeds.
            assert linked == 1
            assert mock_database_adapter.create_error_code_part_link.await_count == 2

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_empty_text(self, mock_database_adapter):
        """Empty input text results in zero links and no database calls."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            mock_extract.return_value = []

            mock_database_adapter.get_part_by_number = AsyncMock(return_value=None)
            mock_database_adapter.create_error_code_part_link = AsyncMock()

            linked = await processor._extract_and_link_parts_from_text(
                text="", error_code_id="ec-5", source="solution_text", adapter=MagicMock()
            )

            assert linked == 0
            mock_database_adapter.create_error_code_part_link.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_ignores_invalid_items(self, mock_database_adapter):
        """Robust against extractor returning malformed items (no crash, zero links)."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            # Missing "part" key will trigger the outer try/except and return 0.
            mock_extract.return_value = [{"foo": "bar"}]

            mock_database_adapter.get_part_by_number = AsyncMock(return_value=None)
            mock_database_adapter.create_error_code_part_link = AsyncMock()

            linked = await processor._extract_and_link_parts_from_text(
                text="dummy", error_code_id="ec-6", source="chunk", adapter=MagicMock()
            )

            assert linked == 0
            mock_database_adapter.create_error_code_part_link.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_handles_extractor_exception(self, mock_database_adapter):
        """Extractor errors are caught and surfaced as zero linked parts."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            mock_extract.side_effect = Exception("boom")

            mock_database_adapter.get_part_by_number = AsyncMock(return_value=None)
            mock_database_adapter.create_error_code_part_link = AsyncMock()

            linked = await processor._extract_and_link_parts_from_text(
                text="dummy", error_code_id="ec-7", source="chunk", adapter=MagicMock()
            )

            assert linked == 0
            mock_database_adapter.create_error_code_part_link.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extract_and_link_parts_handles_get_part_exception(self, mock_database_adapter):
        """Exceptions during part lookup should not bubble out of the helper."""
        processor = PartsProcessor(database_adapter=mock_database_adapter)

        with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
            mock_extract.return_value = [{"part": "P1", "confidence": 0.9}]

            async def boom(_pn: str):
                raise Exception("db down")

            mock_database_adapter.get_part_by_number = AsyncMock(side_effect=boom)
            mock_database_adapter.create_error_code_part_link = AsyncMock()

            linked = await processor._extract_and_link_parts_from_text(
                text="dummy", error_code_id="ec-8", source="chunk", adapter=MagicMock()
            )

            assert linked == 0
            mock_database_adapter.create_error_code_part_link.assert_not_awaited()
