"""
HP Solution Filter
==================
Extracts technician-specific solutions from HP error codes
HP has 3 levels: customers, call-agents, onsite technicians
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── HP section header patterns ───────────────────────────────────────────────
_CUSTOMER_HEADERS = [
    r"Recommended\s+action\s+for\s+customers?\b",
]
_AGENT_HEADERS = [
    r"Recommended\s+action\s+for\s+call[\-\s]center\s+agents?\b",
    r"Recommended\s+action\s+for\s+call[\-\s]agents?\b",
]
_TECHNICIAN_HEADERS = [
    r"Recommended\s+action\s+for\s+(?:onsite|on-site|service)\s+technicians?\b",
    r"Service\s+technician\s+action\b",
    r"Onsite\s+technician\b",
]
_COMBINED_AGENT_TECH_HEADERS = [
    r"Recommended\s+action\s+for\s+call[\-\s](?:center\s+)?agents?(?:\s*,\s*|\s+and\s+)(?:and\s+)?(?:onsite\s+)?technicians?\b",
]
_GENERIC_HEADER = r"Recommended\s+action\b"
_NEXT_CODE_STOP = re.compile(
    # Matches both pure-numeric (10.05.60) and x-placeholder (10.0x.60) HP section headings
    r"\n\d{2,3}[.\-][0-9x]{2}[.\-][0-9xa-fA-F]{2,}\s+\S",
    re.MULTILINE,
)

# ── Konica Minolta section headers ───────────────────────────────────────────
_KM_CUSTOMER_HEADERS = [
    r"Customer\s+recommended\s+action\b",
    r"Summary\s*:\s*",
]
_KM_AGENT_HEADERS = [
    r"Field\s+service\s+recommended\s+action\b",
    r"Agent\s+recommended\s+action\b",
    r"Call[\-\s]center\s+recommended\s+action\b",
]
_KM_TECHNICIAN_HEADERS = [
    r"Measures?\s*:\s*",
    r"Correction\s*:\s*",
    r"Service\s+action\b",
    r"Technician\s+recommended\s+action\b",
    r"Remedy\b",
]

# ── Xerox section headers ─────────────────────────────────────────────────────
_XEROX_CUSTOMER_HEADERS = [
    r"User\s+action\b",
    r"Customer\s+recommended\s+action\b",
    r"Initial\s+actions?\b",
]
_XEROX_AGENT_HEADERS = _AGENT_HEADERS  # reuse HP defaults
_XEROX_TECHNICIAN_HEADERS = [
    r"Service\s+technician\s+action\b",
    r"Technician\s+action\b",
    r"Field\s+replacement\b",
    r"Corrective\s+action\b",
]

# ── Canon/Ricoh/generic section headers ──────────────────────────────────────
_GENERIC_TECHNICIAN_HEADERS = [
    r"Corrective\s+action\b",
    r"Remedy\b",
    r"Solution\b",
    r"Measures?\s*:\s*",
    r"Correction\s*:\s*",
]


def _find_section(text: str, header_patterns: list) -> str | None:
    """Find the first matching section header and return text until next section."""
    flags = re.IGNORECASE | re.DOTALL
    for pat in header_patterns:
        m = re.search(pat, text, flags)
        if not m:
            continue
        start = m.end()
        # Require section stopper to begin on its own line to avoid matching
        # e.g. "onsite technicians" inside "agents and onsite technicians".
        next_section = re.search(
            r"(?:^|\n)\s*(?:Recommended\s+action|Service\s+technician\s+action|Onsite\s+technician)",
            text[start:],
            re.IGNORECASE | re.MULTILINE,
        )
        stop = next_section.start() if next_section else len(text[start:])
        code_stop = _NEXT_CODE_STOP.search(text[start : start + stop])
        if code_stop:
            stop = min(stop, code_stop.start())
        return text[start : start + stop].strip()
    return None


def extract_all_hp_levels(
    text: str,
    manufacturer: str | None = None,
) -> dict[str, str | None]:
    """
    Extract all three solution levels from a chunk/solution text.

    Supports HP, Konica Minolta, Xerox, Canon and generic formats by selecting
    the appropriate section-header patterns for each manufacturer.

    Returns a dict with keys:
        - 'customer'    : solution_customer_text  (Level 1 — basic steps)
        - 'agent'       : solution_agent_text      (Level 2 — call-center)
        - 'technician'  : solution_technician_text (Level 3 — on-site preferred)

    For single-level documents only 'technician' will be set.
    """
    result: dict[str, str | None] = {"customer": None, "agent": None, "technician": None}
    if not text:
        return result

    # Select header patterns based on manufacturer
    mfr_lower = (manufacturer or "").lower()
    if "konica" in mfr_lower or "minolta" in mfr_lower:
        customer_headers = _KM_CUSTOMER_HEADERS
        agent_headers = _KM_AGENT_HEADERS
        technician_headers = _KM_TECHNICIAN_HEADERS
    elif "xerox" in mfr_lower:
        customer_headers = _XEROX_CUSTOMER_HEADERS
        agent_headers = _XEROX_AGENT_HEADERS
        technician_headers = _XEROX_TECHNICIAN_HEADERS
    elif any(x in mfr_lower for x in ("canon", "ricoh", "sharp", "kyocera", "fuji")):
        customer_headers = _CUSTOMER_HEADERS
        agent_headers = _AGENT_HEADERS
        technician_headers = _GENERIC_TECHNICIAN_HEADERS
    else:
        # HP and unknown manufacturers — use HP-style headers
        customer_headers = _CUSTOMER_HEADERS
        agent_headers = _AGENT_HEADERS
        technician_headers = _TECHNICIAN_HEADERS

    # For HP: check for combined "agents and technicians" header FIRST to avoid
    # partial matches of agent_headers leaving " and onsite technicians" as prefix.
    if not mfr_lower or "hp" in mfr_lower or mfr_lower == "hewlett":
        combined = _find_section(text, _COMBINED_AGENT_TECH_HEADERS)
        if combined:
            agent_text = technician_text = combined
            customer_text = _find_section(text, customer_headers)
            if customer_text or agent_text or technician_text:
                result["customer"] = _clean_solution_text(customer_text)
                result["agent"] = _clean_solution_text(agent_text)
                result["technician"] = _clean_solution_text(technician_text)
                return result

    customer_text = _find_section(text, customer_headers)
    agent_text = _find_section(text, agent_headers)
    technician_text = _find_section(text, technician_headers)

    if customer_text or agent_text or technician_text:
        result["customer"] = _clean_solution_text(customer_text) if customer_text else None
        result["agent"] = _clean_solution_text(agent_text) if agent_text else None
        result["technician"] = _clean_solution_text(technician_text) if technician_text else None
        return result

    # No level headers — try generic "Recommended action"
    generic = _find_section(text, [_GENERIC_HEADER])
    if generic:
        result["technician"] = _clean_solution_text(generic)
        return result

    # Last fallback: full text as technician level
    result["technician"] = _clean_solution_text(text)
    return result


def extract_hp_technician_solution(solution_text: str) -> str:
    """
    Backward-compatible wrapper — extract only the technician-level solution.
    Prefer extract_all_hp_levels() for new code.
    """
    levels = extract_all_hp_levels(solution_text)
    return levels["technician"] or levels["agent"] or levels["customer"] or solution_text


def _clean_solution_text(text: str | None) -> str | None:
    """
    Clean up solution text: normalize whitespace and remove leading/trailing
    blank lines.  Returns None if input is None or empty.

    We deliberately do NOT truncate — the caller stores the full extracted
    section so that the chat response can show every step and note that
    appears in the service manual.
    """
    if not text or not text.strip():
        return None
    # Collapse runs of blank lines to a single blank line
    cleaned = re.sub(r"\n{3,}", "\n\n", text)
    return cleaned.strip()


def is_hp_multi_level_format(text: str) -> bool:
    """
    Check if text contains HP multi-level format
    (customers, call-agents, technicians)

    Returns:
        True if HP multi-level format detected
    """
    indicators = [
        r"Recommended\s+action\s+for\s+customers",
        r"Recommended\s+action\s+for\s+call-agents",
        r"Recommended\s+action\s+for\s+(?:onsite|service)\s+technicians",
    ]

    matches = sum(1 for pattern in indicators if re.search(pattern, text, re.IGNORECASE))

    # If we find at least 2 of the 3 sections, it's HP format
    return matches >= 2
