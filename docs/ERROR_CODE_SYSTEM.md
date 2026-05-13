# Error Code System Documentation

## Overview

The KRAI Error Code System provides intelligent extraction, storage, and retrieval of manufacturer-specific error codes from technical documentation and videos.

## Table of Contents

1. [Architecture](#architecture)
2. [Error Code Extraction](#error-code-extraction)
3. [Multi-Source Search](#multi-source-search)
4. [Manufacturer-Specific Filters](#manufacturer-specific-filters)
5. [Product & Video Linking](#product--video-linking)
6. [Database Schema](#database-schema)
7. [API Usage](#api-usage)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Error Code System                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐     ┌──────────────┐    ┌──────────────┐  │
│  │  Extraction  │ ──> │   Storage    │ ─> │    Search    │  │
│  │              │     │              │    │              │  │
│  │ • Patterns   │     │ • Products   │    │ • Documents  │  │
│  │ • Filters    │     │ • Videos     │    │ • Videos     │  │
│  │ • Confidence │     │ • Documents  │    │ • Keywords   │  │
│  └──────────────┘     └──────────────┘    └──────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Error Code Extraction

### Supported Manufacturers

The system supports **17 manufacturers** with specific patterns:

| Manufacturer | Format | Example |
|-------------|--------|---------|
| HP | XX.XX.XX | 30.03.30 |
| Canon | E### | E826 |
| Lexmark | XXX.XX | 200.03 |
| Konica Minolta | C####, XX.XX | C2801, 10.20 |
| Ricoh | SC### | SC542 |
| Brother | ## or E## | 46, E52 |
| Xerox | XXX-XXX | 016-720 |
| Kyocera | C#### | C6000 |
| Sharp | H#-## | H5-01 |
| Fujifilm | XXX-XXX | 092-310 |
| Riso | ### | 123 |
| Toshiba | ### or E### | 456, E789 |
| OKI | ## or ### | 12, 345 |
| Epson | ### or E## | 678, E90 |

### Pattern Configuration

Patterns are defined in `backend/config/error_code_patterns.json`:

```json
{
  "hp": {
    "manufacturer_name": "HP",
    "format": "XX.XX.XX or XX.XXX.XX",
    "patterns": [
      "error\\s+code\\s+(\\d{2}\\.\\d{2,3}\\.\\d{2})",
      "\\b(\\d{2}\\.\\d{2,3}\\.\\d{2})\\b"
    ],
    "validation_regex": "^\\d{2}\\.\\d{1,3}[xX]?\\.\\d{2}$"
  }
}
```

### Extraction Process

1. **Pattern Matching**: Uses manufacturer-specific regex patterns
2. **Context Validation**: Checks for error-related keywords
3. **Description Extraction**: Extracts error description
4. **Solution Extraction**: Extracts troubleshooting steps
5. **Confidence Scoring**: Calculates extraction quality (0.0-1.0)
6. **Manufacturer Filtering**: Applies manufacturer-specific filters

### Confidence Scoring

```python
Base confidence: 0.3
+ Description > 30 chars: 0.2
+ Description > 100 chars: 0.1
+ Has solution: 0.2
+ Numbered steps: 0.1
+ Technical terms: 0.1-0.2
+ Multiple occurrences: 0.1
+ Reasonable context: 0.05

Minimum threshold: 0.60
```

---

## Multi-Source Search

### Search Function

`search_error_code_multi_source(error_code, manufacturer, product)`

Returns error codes from **3 sources**:

1. **Documents** (Service Manuals, CPMD - Control Panel Message Documents, Bulletins)
2. **Videos** (Direct error code match)
3. **Related Videos** (Keyword matching)

### Example Query

```sql
SELECT * FROM search_error_code_multi_source('30.03.30', 'HP', 'X580');
```

### Example Response

```json
[
  {
    "source_type": "document",
    "code": "30.03.30",
    "source_title": "HP_X580_Service_Manual.pdf",
    "error_description": "Scanner motor failure",
    "solution_text": "1. Check cable connections\n2. Test motor voltage...",
    "page_number": 325,
    "relevance_score": 1.0
  },
  {
    "source_type": "video",
    "code": "30.03.30",
    "source_title": "HP X580 Scanner Repair Tutorial",
    "video_url": "https://youtube.com/...",
    "video_duration": 323,
    "relevance_score": 1.0
  },
  {
    "source_type": "related_video",
    "code": "30.03.30",
    "source_title": "Scanner Replacement Guide",
    "video_url": "https://youtube.com/...",
    "relevance_score": 0.7
  }
]
```

### Relevance Scoring

- **Documents with error code**: 1.0
- **Videos with error code**: 1.0
- **Related videos (keyword match)**: 0.7

---

## Manufacturer-Specific Filters

### Purpose

Different manufacturers structure their error code solutions differently. Some provide multiple levels of troubleshooting (customer, call-agent, technician). We filter to extract only **technician-level** solutions.

### HP Solution Filter

**File**: `backend/utils/hp_solution_filter.py`

**HP Format**:
```
Recommended action for customers:
1. Turn the printer off, and then on.
2. Contact support at www.hp.com/support

Recommended action for call-agents:
1. Turn the printer off, and then on.
2. Replace the flatbed scanner assembly.
   Flatbed scanner - 6QN29-67005

Recommended action for onsite technicians:
1. Turn the printer off, and then on.
2. Dispatch a technician to check the following:
   - Check cable connections
   - Test motor voltage
   - Replace scanner assembly if needed
```

**Filtered Output** (Technician-only):
```
1. Turn the printer off, and then on.
2. Dispatch a technician to check the following:
   - Check cable connections
   - Test motor voltage
   - Replace scanner assembly if needed
```

### Adding New Manufacturer Filters

**Step 1**: Analyze manufacturer format
```
Example: Canon Service Mode
- User Action: (Basic troubleshooting)
- Service Mode: (Detailed repair)
```

**Step 2**: Create filter function
```python
def extract_canon_service_mode(solution_text: str) -> str:
    """Extract Canon Service Mode section"""
    pattern = r'Service\s+Mode\s*[:]\s*(.*?)(?=User\s+Action|\Z)'
    match = re.search(pattern, solution_text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return solution_text
```

**Step 3**: Integrate in extractor
```python
from utils.hp_solution_filter import extract_hp_technician_solution
from utils.canon_solution_filter import extract_canon_service_mode

# In _extract_solution():
if manufacturer == 'HP' and is_hp_multi_level_format(text):
    solution = extract_hp_technician_solution(solution)
elif manufacturer == 'Canon' and is_canon_service_format(text):
    solution = extract_canon_service_mode(solution)
```

### Supported Filters

| Manufacturer | Filter | Status |
|-------------|--------|--------|
| HP | Technician-only | ✅ Implemented |
| Canon | Service Mode | 📝 Planned |
| Lexmark | Field Service | 📝 Planned |
| Konica Minolta | Service Engineer | 📝 Planned |

---

## Product & Video Linking

### Product-Specific Error Codes

**Problem**: Same error code can have different solutions for different products.

**Solution**: Store error codes per product.

```sql
-- Same code, different products, different solutions
error_code: 30.03.30
├─ Product: HP LaserJet M479
│  └─ Solution: Replace scanner assembly (Part: ABC123)
└─ Product: HP OfficeJet X580
   └─ Solution: Clean scanner motor (Part: XYZ789)
```

### Video Linking

Error codes can be linked to:
1. **Direct videos**: Video specifically about this error code
2. **Related videos**: Videos with keywords matching the solution

```sql
-- Error code with video
error_code: 30.03.30
product_id: M479_uuid
video_id: youtube_uuid
solution: "See video for step-by-step repair"
```

---

## Database Schema

### error_codes Table

```sql
CREATE TABLE krai_intelligence.error_codes (
    id UUID PRIMARY KEY,
    error_code VARCHAR(20) NOT NULL,
    manufacturer_id UUID REFERENCES manufacturers(id),
    product_id UUID REFERENCES products(id),      -- NEW!
    document_id UUID REFERENCES documents(id),
    video_id UUID REFERENCES videos(id),          -- NEW!
    chunk_id UUID REFERENCES chunks(id),

    error_description TEXT,
    solution_text TEXT,
    page_number INTEGER,
    confidence_score DECIMAL(3,2),

    -- Unique constraint per source
    UNIQUE(error_code, manufacturer_id, product_id, document_id, video_id)
);
```

### Deduplication Logic

**Old**: `(error_code, manufacturer_id)`
**New**: `(error_code, manufacturer_id, product_id, document_id, video_id)`

This allows:
- ✅ Same code for different products
- ✅ Same code in different documents
- ✅ Same code with different videos

---

## API Usage

### N8N Tool: Error Code Search V6

**File**: `n8n/workflows/TOOL_Error_Code_Search_V6_MultiSource.json`

**Input**:
```json
{
  "error_code": "30.03.30",
  "manufacturer": "HP",
  "product": "X580"
}
```

**Output**:
```
🔧 ERROR CODE: 30.03.30
📝 Scanner motor failure

📖 DOKUMENTATION (2):
1. Service Manual (Seite 325)
   💡 Check cable connections, test motor voltage...
   🔧 Parts: ABC123, ABC124

2. CPMD (Seite 45)
   💡 Clean scanner motor
   🔧 Parts: XYZ789

🎬 VIDEOS (1):
1. HP X580 Scanner Repair (5:23)
   🔗 https://youtube.com/...

📺 VERWANDTE VIDEOS (2):
1. Scanner Replacement Tutorial (3:45)
   🔗 https://youtube.com/...

💡 Möchtest du mehr Details?
```

---

## Configuration Files

### Error Code Patterns

**File**: `backend/config/error_code_patterns.json`

Contains patterns for 17 manufacturers.

### Extraction Rules

```json
{
  "extraction_rules": {
    "min_confidence": 0.60,
    "max_codes_per_page": 15,
    "context_window_chars": 200,
    "require_context_keywords": [
      "error", "code", "fault", "failure", "alarm"
    ]
  }
}
```

---

## Migrations

### Migration 41: Product & Video Support

```sql
ALTER TABLE error_codes
ADD COLUMN product_id UUID,
ADD COLUMN video_id UUID;
```

### Migration 42: Multi-Source Search Function

```sql
CREATE FUNCTION search_error_code_multi_source(
  p_error_code TEXT,
  p_manufacturer_name TEXT,
  p_product_name TEXT
)
```

---

## Best Practices

### 1. Always Specify Manufacturer

```python
# ✅ Good
codes = extractor.extract_from_text(text, page=1, manufacturer_name="HP")

# ❌ Bad
codes = extractor.extract_from_text(text, page=1)  # No manufacturer!
```

### 2. Use Product-Specific Search

```sql
-- ✅ Good: Specific product
SELECT * FROM search_error_code_multi_source('30.03.30', 'HP', 'X580');

-- ⚠️ OK: All HP products
SELECT * FROM search_error_code_multi_source('30.03.30', 'HP', NULL);
```

### 3. Re-process After Filter Changes

When adding new manufacturer filters, re-process PDFs:
```bash
python backend/processors/document_processor.py path/to/document.pdf
```

---

## Troubleshooting

### Error Code Not Found

**Check**:
1. Is the manufacturer correct?
2. Is the pattern in `error_code_patterns.json`?
3. Is the confidence too low? (Check logs)
4. Is the context valid? (Has error keywords?)

### Wrong Solution Extracted

**Check**:
1. Is manufacturer filter applied?
2. Is the section pattern correct?
3. Re-process document after filter update

### Duplicate Error Codes

**Run deduplication**:
```bash
python scripts/deduplicate_error_codes.py
```

---

## Future Enhancements

- [ ] Add more manufacturer filters (Canon, Lexmark, etc.)
- [ ] Machine learning for confidence scoring
- [ ] Auto-detect manufacturer from document
- [ ] Parts extraction and linking
- [ ] Multi-language support
- [ ] Error code translation

---

## Support

For questions or issues:
- Check logs: `backend/logs/`
- Run debug scripts: `scripts/debug_extraction.py`
- Check database: `scripts/check_duplicate_error_codes.py`

---

**Last Updated**: 2025-10-07
**Version**: 2.0
