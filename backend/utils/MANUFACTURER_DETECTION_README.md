# Manufacturer Detection - Weighted Scoring System

## Overview

The manufacturer detection system uses a **weighted scoring approach** to accurately identify the manufacturer of a document, even when multiple manufacturers are mentioned in the text.

## Problem Solved

**Before**: A Lexmark document that mentions "Konica Minolta" in a compatibility note would be incorrectly detected as Konica Minolta.

**After**: The system prioritizes filename and title over text content, and counts occurrences to distinguish between the main manufacturer and passing mentions.

## Scoring System

### Weight Distribution

| Source | Weight | Reliability |
|--------|--------|-------------|
| **Filename** | 10 points | Highest - Most reliable indicator |
| **Author (Metadata)** | 8 points | Very High - Usually the actual manufacturer |
| **Title (Metadata)** | 5 points | Medium - Usually accurate |
| **Text Content** | 1-3 points | Lowest - Can contain mentions of other manufacturers |

### Text Content Scoring

Text matches are scored based on frequency:
- **3+ occurrences**: 3 points (likely main manufacturer)
- **2 occurrences**: 2 points (possibly main manufacturer)
- **1 occurrence**: 1 point (weak signal, might be just a mention)

## Confidence Levels

| Score | Confidence | Description |
|-------|------------|-------------|
| ≥18 | Excellent | All metadata sources (filename + author + title) |
| ≥15 | Very High | Multiple sources agree (filename + author or filename + title + text) |
| ≥10 | High | Filename match (most reliable) |
| ≥8 | High | Author metadata match (very reliable) |
| ≥5 | Medium | Title match |
| <5 | Low | Text only (weak signal) |

## Examples

### Example 1: Lexmark Document with Konica Mention (WITH Author Metadata)

```
Filename: lexmark_cs943_manual.pdf
Title: Lexmark CS943 Service Manual
Author: Lexmark International  ← NEW!
Text: "Lexmark CS943... compatible with Konica Minolta toner..."

Scoring:
- Lexmark: 10 (filename) + 8 (author) + 5 (title) + 1 (text) = 24 points ✅
- Konica Minolta: 0 (filename) + 0 (author) + 0 (title) + 2 (text) = 2 points

Result: Lexmark (score: 24, excellent confidence!)
```

### Example 2: Konica Minolta Document

```
Filename: bizhub_c454e_manual.pdf
Title: bizhub C454e User Guide
Text: "Konica Minolta bizhub C454e..."

Scoring:
- Konica Minolta: 0 (filename) + 5 (title: "bizhub") + 2 (text) = 7 points ✅

Result: Konica Minolta (score: 7, medium confidence)
```

### Example 3: HP Document

```
Filename: hp_m479_service.pdf
Title: HP LaserJet M479 Service Manual
Text: "HP LaserJet M479fdw..."

Scoring:
- HP: 10 (filename) + 5 (title) + 1 (text) = 16 points ✅

Result: HP Inc. (score: 16, very high confidence)
```

## Normalization Improvements

### Word Boundary Matching

The `normalize_manufacturer()` function now uses **word boundary matching** to prevent false positives:

```python
# Before (too aggressive)
if 'konica' in name_lower or 'minolta' in name_lower:
    return 'Konica Minolta'

# After (more precise)
if re.search(r'\bkonica\s+minolta\b', name_lower):
    return 'Konica Minolta'
```

### Strict Mode

New `strict` parameter for exact matching only:

```python
# Fuzzy matching (default)
normalize_manufacturer("This is a Lexmark document")  # → "Lexmark"

# Strict mode (exact match only)
normalize_manufacturer("This is a Lexmark document", strict=True)  # → None
normalize_manufacturer("Lexmark", strict=True)  # → "Lexmark"
```

## Manufacturer Aliases

### Lexmark
- lexmark, Lexmark, LEXMARK
- Lexmark International

### HP Inc.
- hp, HP, HP Inc, HP Inc.
- Hewlett Packard, Hewlett-Packard (legacy name)
- H-P, H P

### Konica Minolta
- konica minolta, Konica Minolta
- konica, Konica
- minolta, Minolta
- km, KM, K-M

### Canon
- canon, Canon, CANON
- Canon Inc, Canon Inc.

### Ricoh
- ricoh, Ricoh, RICOH
- Ricoh Company

### Xerox
- xerox, Xerox, XEROX
- Xerox Corporation

### Brother
- brother, Brother, BROTHER
- Brother Industries

### Kyocera
- kyocera, Kyocera, KYOCERA
- Kyocera Document Solutions

### Sharp
- sharp, Sharp, SHARP
- Sharp Corporation

### Epson
- epson, Epson, EPSON
- Seiko Epson

### OKI
- oki, Oki, OKI
- Oki Data, Okidata

## Integration

### In Document Processor

The document processor automatically uses weighted scoring:

```python
# Weighted validation: Filename > Title > Text
detection_scores = {}
for mfr_key, keywords in mfr_patterns.items():
    score = 0
    sources = []

    # Check filename (highest weight)
    if any(kw in filename_lower for kw in keywords):
        score += 10
        sources.append("filename")

    # Check title (medium weight)
    if any(kw in title_lower for kw in keywords):
        score += 5
        sources.append("title")

    # Check text (lowest weight, count occurrences)
    text_matches = sum(1 for kw in keywords if kw in first_pages_text)
    if text_matches >= 3:
        score += 3
        sources.append(f"text({text_matches}x)")
    elif text_matches >= 2:
        score += 2
        sources.append(f"text({text_matches}x)")
    elif text_matches >= 1:
        score += 1
        sources.append(f"text({text_matches}x)")

    if score > 0:
        detection_scores[mfr_key] = {'score': score, 'sources': sources}

# Select manufacturer with highest score
best_match = max(detection_scores.items(), key=lambda x: x[1]['score'])
```

## Logging

The system provides detailed logging:

```
🔍 Auto-detected manufacturer: Lexmark
   Confidence score: 16 (filename, title, text(2x))
   ✅ Very high confidence (multiple sources)
```

## False Positive Prevention

### Before
```
Document: "Lexmark CS943 manual... compatible with Konica Minolta toner"
Result: Konica Minolta ❌ (wrong - just mentioned in text)
```

### After
```
Document: "Lexmark CS943 manual... compatible with Konica Minolta toner"
Scores:
- Lexmark: 16 (filename + title + text)
- Konica Minolta: 2 (text only, single mention)
Result: Lexmark ✅ (correct - highest score)
```

## Best Practices

1. **Always provide filename and title** when available for best accuracy
2. **Use first 3 pages only** for text content to avoid false positives from appendices
3. **Count occurrences** to distinguish main manufacturer from mentions
4. **Log confidence scores** to identify low-confidence detections
5. **Review low-confidence detections** (score < 5) manually if needed

## Testing

Run tests:
```bash
python backend/utils/manufacturer_normalizer.py
```

## Notes

- **Filename is king**: A filename match (10 points) outweighs multiple text mentions
- **Title is reliable**: Title matches (5 points) are usually accurate
- **Text is noisy**: Text content can contain mentions of other manufacturers
- **Frequency matters**: Multiple text occurrences indicate main manufacturer
- **Word boundaries**: Prevents "Minolta camera" from matching "Konica Minolta printers"
