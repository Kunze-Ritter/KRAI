# Link, Chunk Preprocessing, and Classification Processor Tests

This test suite exercises the mid‑pipeline processors responsible for
link extraction, chunk preprocessing, and document classification.

- **LinkExtractor** and **LinkExtractionProcessorAI**
- **ChunkPreprocessor**
- **DocumentTypeDetector**
- **ClassificationProcessor**
- **LinkEnrichmentService** integration
- **End‑to‑end flow** from link → chunk → classification

---

## Test Files

- **`test_link_extractor_unit.py`**
  Unit tests for `LinkExtractor` internals:
  - URL and placeholder detection
  - YouTube ID and duration parsing
  - Direct video URL detection and metadata
  - Link type/category classification
  - Link deduplication and description extraction

- **`test_link_extraction_processor_e2e.py`**
  E2E tests for `LinkExtractionProcessorAI`:
  - Extraction of HTTP(S), YouTube, and direct video links from PDFs
  - Handling of multi‑page documents
  - Error paths (missing document ID, missing file, missing page texts)
  - Persistence helpers for links and videos using a lightweight PostgreSQL-style client

- **`test_chunk_preprocessor_unit.py`**
  Unit tests for `ChunkPreprocessor` internals:
  - Header/footer removal
  - Whitespace normalisation and empty‑line cleanup
  - Chunk type detection (error_code, parts_list, procedure, specification, table, text, empty)

- **`test_chunk_preprocessor_e2e.py`**
  E2E tests for `ChunkPreprocessor`:
  - Loading chunks from a mocked `chunks` table
  - Updating cleaned content, metadata, and `char_count`
  - Behaviour when no chunks are found
  - Graceful handling of update failures while still reporting progress

- **`test_document_type_detector_unit.py`**
  Unit tests for `DocumentTypeDetector`:
  - Document type detection for service manuals, parts catalogs, user guides, and installation guides
  - Version detection from titles, filenames, creation dates, and document codes (e.g. `A93E`)
  - Date‑based versions (e.g. `August 2025` for Konica Minolta parts catalogs)

- **`test_classification_processor_e2e.py`**
  E2E tests for `ClassificationProcessor`:
  - Manufacturer detection from filenames and titles
  - Fallback AI‑based manufacturer detection using `mock_ai_service`
  - Document type and version detection using `DocumentTypeDetector`
  - Database update of `documents.manufacturer`, `documents.document_type`, and `documents.version`

- **`test_link_enrichment_integration.py`**
  Integration tests joining `LinkExtractionProcessorAI` with
  `LinkEnrichmentService`:
  - Verifies that enrichment is called when `ENABLE_LINK_ENRICHMENT=true`
  - Verifies that enrichment is skipped when disabled
  - Optionally triggers structured extraction for enriched links when
    `ENABLE_STRUCTURED_EXTRACTION=true`

- **`test_link_chunk_classification_flow_e2e.py`**
  End‑to‑end flow test chaining:
  - `LinkExtractionProcessorAI` (links only, no DB persistence)
  - `ChunkPreprocessor` (via `MockDatabaseAdapter` + Supabase‑like client)
  - `ClassificationProcessor` (using content statistics from the same
    mock client)
  This validates that a single `document_id` can move through link →
  chunk → classification stages with consistent database state.

---

## Fixtures

Key fixtures added to `tests/processors/conftest.py` for this suite:

- **`mock_link_extractor`** – `MagicMock` spec for `LinkExtractor` that
  returns deterministic links and videos.
- **`mock_context_extraction_service`** – mocked
  `ContextExtractionService` for predictable link/video context data.
- **`mock_document_type_detector`** – mocked `DocumentTypeDetector`
  returning fixed `(document_type, version)` tuples when direct unit
  testing is not desired.
- **`sample_chunks_for_preprocessing`** – list of chunk dictionaries
  covering headers/footers, error codes, parts lists, procedures,
  specifications, tables, and plain text.
- **`sample_document_metadata_for_classification`** – example
  `documents` rows for HP, Canon, and Konica Minolta manuals and
  catalogs.
- **`create_test_link` / `create_test_video` / `create_test_chunk`** –
  factories for building minimal, strongly‑typed dictionaries for links,
  videos, and chunks.
- **`sample_pdf_with_links` / `sample_pdf_with_videos` /
  `sample_pdf_multipage_links`** – small synthetic PDFs (PyMuPDF when
  available, otherwise text‑based) used in link and video tests.
- **`link_enrichment_service_with_mock_scraper`** – real
  `LinkEnrichmentService` wired to a pure‑Python `MockScraper` and a
  Supabase‑like client that operates on the in‑memory `MockDatabaseAdapter`.

All new tests rely exclusively on these fixtures and avoid external
network or database calls.

---

## Running Tests

Run all processor tests:

```bash
pytest tests/processors/ -v
```

Run only link / chunk / classification suites via markers:

```bash
# Link extraction (unit + E2E)
pytest tests/processors/ -m link -v

# Chunk preprocessing (unit + E2E)
pytest tests/processors/ -m chunk_prep -v

# Classification (DocumentTypeDetector + ClassificationProcessor)
pytest tests/processors/ -m classification -v

# Link enrichment integration
pytest tests/processors/ -m link_enrichment -v

# Full link → chunk → classification flow
pytest tests/processors/ -m pipeline -v
```

You can combine markers, for example:

```bash
pytest tests/processors/ -m "link and e2e" -v
```

---

## Design Notes and Scope

- Tests are **async‑first** and follow existing patterns from
  `test_table_processor_e2e.py` and the legacy pipeline flow tests.
- All database interactions use `MockDatabaseAdapter` with a minimal
  Supabase‑style `.client.table(...).select().eq().execute()` shim.
- Network‑bound operations (YouTube API, web scraping, structured
  extraction) are **fully mocked** to keep the suite deterministic and
  fast.
- The link → chunk → classification flow test intentionally focuses on a
  happy‑path scenario with a single document ID and a small chunk set,
  deferring heavy edge‑case and performance coverage to the broader
  pipeline tests under `tests/processors/test_pipeline_flow_e2e.py` and
  related integration suites.

When adding new scenarios, keep tests small, deterministic, and focused
on specific behaviours, and update this README with any additional test
files or major flows.
