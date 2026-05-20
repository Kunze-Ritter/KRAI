"""Error Code Patterns Module

Contains all regex patterns, constants, and configuration loading
for error code extraction. Separated from main extractor for better maintainability.
"""

import json
import re
from pathlib import Path
from typing import Any

# Words that are NOT error codes (reject these!)
REJECT_CODES = {
    "descriptions",
    "information",
    "lookup",
    "troubleshooting",
    "specify",
    "displays",
    "field",
    "system",
    "file",
    "page",
    "section",
    "chapter",
    "table",
    "figure",
    "error",
    "code",
    "manual",
    "document",
    "version",
    "revision",
    "contents",
}

# Technical terms that indicate real error context
TECHNICAL_TERMS = {
    "fuser",
    "sensor",
    "motor",
    "cartridge",
    "drum",
    "roller",
    "replace",
    "check",
    "clean",
    "reset",
    "calibrate",
    "inspect",
    "toner",
    "paper",
    "jam",
    "feed",
    "pickup",
    "transfer",
    "formatter",
    "engine",
    "scanner",
    "adf",
    "duplex",
    "tray",
    "thermistor",
    "heater",
    "solenoid",
    "clutch",
    "gear",
    "belt",
}

# PERFORMANCE: Pre-compile regex patterns (avoid recompilation in hot loops)
RECOMMENDED_ACTION_PATTERN = re.compile(
    r"(?:recommended\s+action|corrective\s+action|troubleshooting\s+steps?|service\s+procedure|procedure|remedy|repair\s+procedure|measures\s+to\s+take|correction|^action$)"
    r"(?:\s+for\s+(?:customers?|technicians?|agents?|users?|when\s+an\s+alert\s+occurs)?)?"
    r"\s*[\n:]+((?:(?:\d+[\.\)]|\d+\s+(?=[A-Z])|•|-|\*|step\s+\d+)\s*[^\n\r]{5,500}[\n\r]?){1,})",
    re.IGNORECASE | re.MULTILINE,
)

SOLUTION_KEYWORDS_PATTERN = re.compile(
    r"(?:solution|fix|remedy|resolution|procedure|action|steps?)" r"\s*[:]\s*(.{50,1500}?)", re.IGNORECASE
)

# Matches numbered steps with period/paren (1. step) OR digit-space-uppercase (1 Check)
NUMBERED_STEPS_PATTERN = re.compile(
    r"((?:(?:\d+[\.\)]\s+|\d+\s+(?=[A-Z])).{15,500}?[\n\r]?){2,})", re.MULTILINE | re.IGNORECASE
)

BULLET_PATTERN = re.compile(
    r"((?:(?:•|-|\*|–)\s+.{15,500}?[\n\r]?){2,})",  # en-dash is a legitimate bullet char in PDFs
    re.MULTILINE,
)

# Additional pre-compiled patterns for _extract_solution
# Matches: "1. ", "1) ", "a. ", "a) " AND Lexmark "1 " followed by uppercase (e.g. "1 Check")
STEP_LINE_PATTERN = re.compile(r"^(?:\s{0,4}\d+[\.\)]\s+|\s{0,4}\d+\s+(?=[A-Z])|•|-|\*|[a-z][\.\)])\s*", re.MULTILINE)
STEP_MATCH_PATTERN = re.compile(r"(?:\d+[\.\)]|Step\s+\d+|\d+\s+(?=[A-Z]))", re.IGNORECASE)
SECTION_END_NOTE = re.compile(r"\n\s*(?:note|warning|caution|important|tip)", re.IGNORECASE)
SECTION_END_TITLE = re.compile(r"\n\s*[A-Z][a-z]+\s+[A-Z]")
SECTION_END_NUMBERED = re.compile(r"\n\s*\d+(?:\.\d+)+\s")  # matches 3.7.2, 3.7.1.1, etc.
CLASSIFICATION_PATTERN = re.compile(
    r"Classification\s*\n\s*(.+?)(?:\n\s*Cause|\n\s*Measures|$)", re.IGNORECASE | re.DOTALL
)
SENTENCE_END_PATTERN = re.compile(r"[.!?\n]{1,2}")

MAX_BATCH_CODE_LENGTH = 128


def load_error_code_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load error code patterns configuration from JSON file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "error_code_patterns.json"

    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"extraction_rules": {}}
    except json.JSONDecodeError:
        return {"extraction_rules": {}}


def slugify_error_code(name: str) -> str:
    """Convert manufacturer name to slug format."""
    return re.sub(r"[^a-z0-9]", "", name.lower())
