"""
Custom exceptions for document processing
"""


class ProcessingError(Exception):
    """Base exception for processing errors"""

    pass


class ManufacturerPatternNotFoundError(ProcessingError):
    """
    Raised when no error code patterns are configured for a manufacturer

    This prevents false positives from generic patterns matching part numbers,
    model numbers, or other non-error-code identifiers.
    """

    def __init__(self, manufacturer: str, stage: str = "Error Code Extraction"):
        self.manufacturer = manufacturer
        self.stage = stage

        message = self._build_error_message()
        super().__init__(message)

    def _build_error_message(self) -> str:
        """Build comprehensive error message with solutions"""

        # Box drawing characters
        box_top = "╔" + "═" * 63 + "╗"
        box_mid = "╠" + "═" * 63 + "╣"
        box_bot = "╚" + "═" * 63 + "╝"

        def box_line(text):
            return f"║ {text:<61} ║"

        lines = [
            "",
            box_top,
            box_line("❌ ERROR: Manufacturer Pattern Not Found"),
            box_mid,
            box_line(""),
            box_line(f"Manufacturer: {self.manufacturer}"),
            box_line(f"Stage: {self.stage}"),
            box_line(""),
            box_line("📋 REASON:"),
            box_line(f"No error code patterns configured for '{self.manufacturer}' in:"),
            box_line("backend/config/error_code_patterns.json"),
            box_line(""),
            box_line("🔧 SOLUTIONS:"),
            box_line(""),
            box_line("Option 1: Use existing patterns (if rebrand)"),
            box_line("─" * 61),
            box_line(f"{self.manufacturer} might be a rebrand. Common rebrands:"),
            box_line("  • UTAX/TA Triumph-Adler → Kyocera"),
            box_line("  • Olivetti → Konica Minolta"),
            box_line("  • Develop → Konica Minolta"),
            box_line("  • Muratec → Brother"),
            box_line(""),
            box_line("Try:"),
            box_line("  python scripts/create_manufacturer_patterns.py \\"),
            box_line(f"    --name {self.manufacturer} \\"),
            box_line("    --based-on <manufacturer>"),
            box_line(""),
            box_line("Option 2: Create new patterns from scratch"),
            box_line("─" * 61),
            box_line("  python scripts/create_manufacturer_patterns.py \\"),
            box_line(f"    --name {self.manufacturer} \\"),
            box_line("    --interactive"),
            box_line(""),
            box_line("Option 3: Manual configuration"),
            box_line("─" * 61),
            box_line("  1. Edit: backend/config/error_code_patterns.json"),
            box_line(f"  2. Add '{self.manufacturer.lower()}' section"),
            box_line("  3. Test: python scripts/test_error_code_extraction.py"),
            box_line(""),
            box_line("📚 DOCUMENTATION:"),
            box_line("  • Pattern Guide: backend/docs/ERROR_CODE_PATTERNS.md"),
            box_line("  • Testing Guide: backend/scripts/ERROR_CODE_TESTING.md"),
            box_line("  • Examples: See HP, Konica Minolta in patterns.json"),
            box_line(""),
            box_bot,
            "",
            f"⚠️  Processing stopped at stage: {self.stage}",
            "",
            "💡 TIP: After adding patterns, you can resume processing with:",
            "   python scripts/reprocess_document.py --document-id <id>",
            "",
        ]

        return "\n".join(lines)


class ManufacturerNotFoundError(ProcessingError):
    """Raised when manufacturer cannot be found or created in database"""

    def __init__(self, manufacturer: str, reason: str = ""):
        self.manufacturer = manufacturer
        self.reason = reason
        message = f"Manufacturer '{manufacturer}' not found in database"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class SeriesNotFoundError(ProcessingError):
    """Raised when product series cannot be found in database"""

    def __init__(self, series: str, manufacturer: str = ""):
        self.series = series
        self.manufacturer = manufacturer
        message = f"Series '{series}' not found"
        if manufacturer:
            message += f" for manufacturer '{manufacturer}'"
        super().__init__(message)


class ProductNotFoundError(ProcessingError):
    """Raised when product cannot be found in database"""

    def __init__(self, product: str, series: str = ""):
        self.product = product
        self.series = series
        message = f"Product '{product}' not found"
        if series:
            message += f" in series '{series}'"
        super().__init__(message)
