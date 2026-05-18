# Document Processor V2

Clean, modular rewrite of document processing pipeline with strict validation.

## Features

✅ **Type-safe** - Pydantic models with built-in validation
✅ **Beautiful logging** - Rich console output with progress bars
✅ **Unified processor base** - Shared `BaseProcessor` with centralized Stage enum + contextual logging
✅ **Strict validation** - No filenames as products, no random words as error codes
✅ **Real confidence** - Context-based scoring, not fake values
✅ **Modular design** - Easy to test and extend
✅ **Smart chunking** - Overlap for context preservation

---

## Installation

```bash
cd backend
pip install -r requirements.txt
```

**Dependencies:**
- PyMuPDF (PDF extraction)
- rich (beautiful logging)
- pydantic (type safety)
- sentence-transformers (embeddings)

---

## Quick Start

### Test with single PDF:

```bash
python test_processor.py /path/to/manual.pdf
```

### With options:

```bash
# Canon document
python test_processor.py manual.pdf --manufacturer Canon

# Custom chunk size
python test_processor.py manual.pdf --chunk-size 1500

# Save results to JSON
python test_processor.py manual.pdf --output results.json
```

---

## Active Processors in Master Pipeline

1. `upload_processor.py` – UploadProcessor (Document ingestion & deduplication)
2. `text_processor_optimized.py` – OptimizedTextProcessor (Smart chunking with AI)
3. `image_processor.py` – ImageProcessor (OCR, AI vision, SVG support)
4. `classification_processor.py` – ClassificationProcessor (Manufacturer/product detection)
5. `chunk_preprocessor.py` – ChunkPreprocessor (Chunk preparation)
6. `link_extraction_processor_ai.py` – LinkExtractionProcessorAI (Link extraction)
7. `metadata_processor_ai.py` – MetadataProcessorAI (Error codes, version extraction)
8. `storage_processor.py` – StorageProcessor (MinIO object storage)
9. `embedding_processor.py` – EmbeddingProcessor (Vector embeddings)
10. `search_processor.py` – SearchProcessor (Search analytics)

Diese Liste spiegelt die aktive Pipeline in `backend/pipeline/master_pipeline.py` wider.

---

## Archived Processors

Legacy-Varianten und historische Implementierungen liegen jetzt in `backend/processors/archive/`. So bleiben Referenzen erhalten, ohne die aktive Pipeline zu verwirren.

---

## Test Files

Alle Processor-bezogenen Tests wurden nach `tests/processors/` verschoben. Verwende dieses Verzeichnis für Integration- und Regressionstests der Pipeline.

---

## Utility Scripts

- `scripts/` enthält Hilfs- und Wartungsskripte (z.B. `auto_processor.py`, `pipeline_processor.py`).
- `examples/` bündelt Demonstrationen wie `example_pipeline_usage.py` zur schnellen Orientierung.

---

## Modules

### 1. `text_extractor.py`
Extracts text from PDFs using PyMuPDF (primary) or pdfplumber (fallback).

**Features:**
- Document metadata extraction
- Type classification (service_manual, parts_catalog, etc.)
- Clean text normalization

```python
from backend.processors.text_extractor import extract_text_from_pdf

page_texts, metadata, structured_texts_by_page = extract_text_from_pdf(pdf_path, document_id)

if structured_texts_by_page:
    # Prefilter enrichment search to pages that actually contain dense error tables
    candidate_pages = [
        page for page, structured in structured_texts_by_page.items()
        if structured and "13.20" in structured
    ]
    print(f"Pages with structured error references: {candidate_pages}")

    # Example: Only send those pages into a downstream enrichment run
    enrichment_targets = {
        page: page_texts[page]
        for page in candidate_pages
        if page in page_texts
    }
    # enrichment_pipeline.process(enrichment_targets)
```

> Tipp: `structured_texts_by_page` ist bewusst schlank (tabellarische Ausschnitte). Damit lassen sich Enrichment- oder QA-Pipelines gezielt auf relevante Seiten begrenzen – besonders hilfreich bei sehr großen Service-Handbüchern.

### Enrichment Usage

The `text_extractor` module can be used to prefilter pages for enrichment pipelines. By analyzing the structured text extracted from each page, you can identify pages that contain dense error tables or other relevant information. These pages can then be sent to a downstream enrichment pipeline for further processing.

```python
enrichment_targets = {
    page: page_texts[page]
    for page in candidate_pages
    if page in page_texts
}
# enrichment_pipeline.process(enrichment_targets)
```

### 2. `product_extractor.py`
Extracts product models with strict validation.

**Patterns:**
- HP: LaserJet, OfficeJet, DesignJet, PageWide, simple models (E877, M455)
- Canon: imageRUNNER, PIXMA

**Validation:**
- ✅ Must have letters AND numbers
- ❌ NO filenames (., _, /)
- ❌ NO all-caps patterns (COLORLJM480M)
- ❌ NOT reject words (page, chapter, etc.)

```python
from backend.processors.product_extractor import extract_products_from_text

products = extract_products_from_text(text, manufacturer="HP")
```

**Example:**
```python
# ✅ ACCEPTED:
"LaserJet Pro M404dn"
"Color LaserJet Enterprise E877"
"OfficeJet Pro 9015"

# ❌ REJECTED:
"COLORLJE47528M"  # All-caps filename
"AAJN007"         # No pattern match
"SP00"            # Too short
```

---

### 3. `error_code_extractor.py`
Extracts error codes with STRICT numeric validation.

**Patterns:**
- HP Standard: `13.20.01` (XX.XX.XX)
- HP Short: `49.38` (XX.XX)
- HP Events: `12345-6789`

**Validation:**
- ✅ Must match manufacturer-specific numeric regex
- ❌ NO random words ("descriptions", "information")
- ✅ Description > 20 chars
- ❌ NOT generic phrases
- ⚠️ Confidence < 0.6 is marked with a `quality_flag` instead of being dropped

**Confidence factors:**
- Proper description: +0.3
- Solution steps: +0.2
- Technical terms: +0.2
- Multiple appearances: +0.1

```python
from backend.processors.error_code_extractor import extract_error_codes_from_text

error_codes = extract_error_codes_from_text(text, page_number=5)
```

**Example:**
```python
# ✅ ACCEPTED:
"13.20.01" with "Fuser temperature error - thermistor failure"

# ❌ REJECTED:
"descriptions"  # Not numeric
"information"   # Not numeric
"10.22.15" with "Refer to manual"  # Generic description
```

---

### 4. `chunker.py`
Smart text chunking with overlap and context preservation.

**Features:**
- Paragraph-aware splitting
- Overlap for context (default 100 chars)
- Chunk type detection (error_code_section, troubleshooting, etc.)
- Fingerprinting for deduplication

```python
from backend.processors.chunker import chunk_document_text

chunks = chunk_document_text(page_texts, document_id, chunk_size=1000, overlap=100)
```

---

### 5. `document_processor.py`
Main orchestrator - coordinates everything.

**Pipeline:**
1. Extract text from PDF
2. Extract products (first page + scan)
3. Extract error codes (all pages)
4. Create chunks with overlap
5. Validate & calculate statistics

```python
from backend.processors.document_processor import process_pdf

result = process_pdf(pdf_path, manufacturer="HP")

if result.success:
    print(f"Chunks: {len(result.chunks)}")
    print(f"Products: {len(result.products)}")
    print(f"Error Codes: {len(result.error_codes)}")
```

---

## Data Models

### ExtractedProduct
```python
ExtractedProduct(
    model_number="LaserJet Pro M404dn",
    model_name="LaserJet Pro M404dn",
    product_type="laser_printer",  # siehe ALLOWED_PRODUCT_TYPES in backend/constants/product_types.py
    manufacturer_name="HP",
    confidence=0.85,
    source_page=1,
    extraction_method="regex_laserjet"
)
```

### ExtractedErrorCode
```python
ExtractedErrorCode(
    error_code="13.20.01",
    error_description="Fuser temperature error - thermistor failure",
    solution_text="1. Check fuser connections\n2. Test thermistor...",
    context_text="...",
    confidence=0.82,
    page_number=137,
    extraction_method="hp_standard",
    severity_level="medium"  # low, medium, high, critical
)
```

### TextChunk
```python
TextChunk(
    chunk_id=UUID(...),
    document_id=UUID(...),
    text="...",
    chunk_index=5,
    page_start=10,
    page_end=11,
    chunk_type="error_code_section",
    metadata={"has_error_codes": True, "word_count": 245},
    fingerprint="abc123..."
)
```

---

## Quality Checks

### After processing, check quality:

```sql
-- 1. Error codes should be numeric only
SELECT error_code, COUNT(*)
FROM krai_intelligence.error_codes
WHERE error_code !~ '^\d{2}\.\d{2}(\.\d{2})?$'
GROUP BY error_code;
-- Should return 0 rows!

-- 2. Products should not be filenames
SELECT model_number, COUNT(*)
FROM krai_core.products
WHERE model_number LIKE '%_%' OR model_number LIKE '%.%'
GROUP BY model_number;
-- Should return 0 rows!

-- 3. Confidence distribution
SELECT
    CASE
        WHEN confidence_score >= 0.9 THEN 'High (0.9+)'
        WHEN confidence_score >= 0.7 THEN 'Medium (0.7-0.9)'
        ELSE 'Low (<0.7)'
    END as confidence_range,
    COUNT(*) as count
FROM krai_intelligence.error_codes
GROUP BY confidence_range;
-- Should have mostly High/Medium!
```

---

## Comparison: V1 vs V2

| Feature | V1 | V2 |
|---------|----|----|
| **Product Extraction** | ❌ Filenames accepted | ✅ Strict validation |
| **Error Codes** | ❌ Random words | ✅ Numeric only |
| **Confidence** | ❌ Fake (0.75) | ✅ Real scoring |
| **Validation** | ❌ Minimal | ✅ Comprehensive |
| **Logging** | ❌ Basic | ✅ Beautiful (rich) |
| **Type Safety** | ❌ None | ✅ Pydantic models |
| **Chunking** | ✅ Basic | ✅ Smart with overlap |

**V1 Example (BAD):**
```json
{
  "model_number": "COLORLJE47528M",  // ❌ Filename!
  "error_code": "descriptions",       // ❌ Not a code!
  "confidence": 0.75                  // ❌ Fake!
}
```

**V2 Example (GOOD):**
```json
{
  "model_number": "Color LaserJet Enterprise E475",  // ✅ Real model!
  "error_code": "13.20.01",                          // ✅ Numeric!
  "confidence": 0.82                                 // ✅ Real!
}
```

---

## Development

### Run tests:
```bash
python test_processor.py test_manual.pdf --output results.json
```

### Check results:
```bash
cat results.json | jq '.products'
cat results.json | jq '.error_codes'
cat results.json | jq '.statistics'
```

### Add new manufacturer:
1. Add patterns to `product_extractor.py`
2. Test with sample PDF
3. Validate results

---

## Troubleshooting

### "No text extracted"
- Check PDF is not scanned image
- Try pdfplumber: `--pdf-engine pdfplumber`
- OCR needed for image PDFs

### "No products found"
- Check first page has model number
- Try different manufacturer
- Check patterns in `product_extractor.py`

### "Low confidence scores"
- Check context quality
- Review extracted descriptions
- Tune confidence thresholds

---

## Next Steps

1. ✅ Test with real PDFs
2. ⏳ Add embedding generation
3. ⏳ Database integration
4. ⏳ Batch processing
5. ⏳ API endpoints

---

## License

Part of KRAI Manual2Vector project.
