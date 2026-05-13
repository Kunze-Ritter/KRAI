# Structured Data Extraction Processor Tests

Comprehensive tests for the structured data extraction processors:

- **TableProcessor** – table extraction, classification, and embeddings
- **SVGProcessor** – vector graphics extraction and PNG conversion
- **ImageProcessor** – raster image extraction, filtering, OCR, Vision AI
- **VisualEmbeddingProcessor** – visual embeddings for images
- **Multi-modal integration** – combined processing of tables, SVGs, images, and visual embeddings

The suite focuses on realistic processor usage patterns using synthetic PDFs
constructed at test time, together with mock database, embedding, storage,
and AI services.

---

## Test Files

- **`test_table_processor_unit.py`**
  Unit tests for `TableProcessor` internals: table detection, validation,
  markdown generation, type detection, context extraction, and embedding
  generation via the mock embedding service.

- **`test_table_processor_e2e.py`**
  End-to-end tests for `TableProcessor`: extraction from PDFs, storage into
  `krai_intelligence.structured_tables` via `MockDatabaseAdapter`, and
  embedding creation in `krai_intelligence.chunks.embedding`.

- **`test_svg_processor_e2e.py`**
  E2E tests for `SVGProcessor`: SVG extraction from PDFs, conversion to PNG
  (svglib + reportlab), and queueing of images into the processing queue
  using a lightweight database shim.

- **`test_image_processor_e2e.py`**
  E2E tests for `ImageProcessor`: image extraction, basic filtering, and
  storage queueing using mock storage and AI services.

- **`test_visual_embedding_processor_e2e.py`**
  E2E tests for `VisualEmbeddingProcessor`: batch image embedding and
  storage of embeddings via `MockDatabaseAdapter`. Tests are tolerant of
  missing `colpali-engine` or heavy model loading, skipping where needed.

- **`test_multimodal_integration.py`**
  Integration tests for multi-modal processing: running table, SVG, image,
  and visual embedding processors together on a synthetic multimodal PDF and
  verifying that processors can operate in sequence without failures.

---

## Running Tests

Basic invocation for all processor tests:

```bash
pytest tests/processors/ -v
```

Run a specific file:

```bash
pytest tests/processors/test_table_processor_e2e.py -v
```

Run a specific test class:

```bash
pytest tests/processors/test_table_processor_e2e.py::TestTableExtractionE2E -v
```

Run a single test:

```bash
pytest tests/processors/test_table_processor_e2e.py::TestTableExtractionE2E::test_process_document_with_tables -v
```

Run by marker:

```bash
# TableProcessor tests
pytest tests/processors/ -m table -v

# SVGProcessor tests
pytest tests/processors/ -m svg -v

# ImageProcessor tests
pytest tests/processors/ -m image -v

# VisualEmbeddingProcessor tests
pytest tests/processors/ -m visual_embedding -v

# Multi-modal integration tests
pytest tests/processors/ -m multimodal -v

# Slow tests (if any are marked explicitly)
pytest tests/processors/ -m slow -v

# Skip slow tests
pytest tests/processors/ -m "not slow" -v
```

Parallel execution (requires `pytest-xdist`):

```bash
pytest tests/processors/ -n auto
```

Coverage report (example):

```bash
pytest tests/processors/ --cov=backend/processors --cov-report=html
```

---

## Fixtures

Key fixtures defined in `tests/processors/conftest.py` that support these tests:

- **`mock_database_adapter`**
  Mock `DatabaseAdapter` with in-memory stores for documents, chunks,
  structured tables (`structured_tables`) and `krai_intelligence.chunks.embedding`. Provides
  helper methods like `create_structured_table` and
  `create_embedding_v2` used by the processors.

- **`mock_embedding_service`**
  Deterministic, in-memory embedding service used by `TableProcessor` unit
  and E2E tests. Exposes `_generate_embedding(text)` which returns a
  768‑dimensional vector based on a SHA‑256 hash of the input text.

- **`mock_storage_service`**
  Lightweight mock of `ObjectStorageService` that stores uploaded image
  content in memory and returns predictable metadata for test assertions.

- **`mock_ai_service`**
  Simplified AI service for Vision/OCR‑style operations. Provides
  `analyze_image(image, description)` and `generate_embeddings(text)` with
  deterministic outputs suitable for tests without external dependencies.

- **`sample_pdf_files`**
  General PDF samples (valid, corrupted, empty, large, OCR‑like, multi‑lang).
  Used primarily by Upload/Text/Document tests but also helpful for
  negative paths here.

- **`sample_pdf_with_tables`**
  Synthetic multi‑page PDF containing specification, parts list, and error
  code tables, built with PyMuPDF where available.

- **`sample_pdf_with_images`**
  Synthetic PDF with several embedded raster images of varying aspect
  ratios and sizes.

- **`sample_pdf_with_svgs`**
  Synthetic PDF with basic vector graphics suitable for exercising
  `SVGProcessor` extraction and conversion.

- **`sample_pdf_multimodal`**
  Synthetic PDF containing a mix of tables, images, and vector drawings on
  multiple pages, used by the multi-modal integration tests.

- **`create_test_image`**
  Factory for generating small in‑memory Pillow images with configurable
  dimensions and colours.

- **`create_test_table_data`**
  Factory that returns a `pandas.DataFrame` with synthetic content for
  testing table‑related helpers.

- **`create_test_svg`**
  Factory that returns a simple SVG string containing configurable shapes
  (rectangles, circles, etc.).

---

## Test Patterns

Common patterns used across the structured data test suite:

- **Async tests**
  Many processor APIs are async. Tests use `@pytest.mark.asyncio` and
  await `processor.process(context)` directly or helper methods such as
  `process_document` where appropriate.

- **ProcessingContext construction**
  Tests construct `ProcessingContext` with at least `document_id`,
  `file_path`, and `document_type`. Additional fields like `pdf_path`,
  `page_texts`, or `images` are populated by processors or fixtures.

- **Mock services**
  Processors are initialised with mock services (database, embedding,
  storage, AI) to avoid network/IO and to allow deterministic assertions.

- **Database assertions**
  E2E tests verify that processors actually write to the mock adapter’s
  in‑memory stores (e.g. `structured_tables`, `krai_intelligence.chunks.embedding`) and that
  record counts line up with the `ProcessingResult` metadata.

- **Error handling paths**
  Negative tests deliberately provide invalid or missing inputs (e.g.
  missing `pdf_path`, non‑existent files) and assert that the processors
  return unsuccessful results without raising.

- **Stage tracking**
  Where practical, `mock_stage_tracker` is attached to processors and
  tests assert that successes and failures do not raise when stage
  tracking is in place.

---

## Test Categories

- **Unit Tests**
  `test_table_processor_unit.py` focuses on small helper methods and
  internal logic of `TableProcessor`.

- **E2E Tests**
  `test_table_processor_e2e.py`, `test_svg_processor_e2e.py`,
  `test_image_processor_e2e.py`, and
  `test_visual_embedding_processor_e2e.py` exercise real PDF parsing and
  end‑to‑end flows from context to storage.

- **Integration Tests**
  `test_multimodal_integration.py` composes multiple processors together
  on the same input document and verifies that contexts and storage
  behaviour are compatible.

- **Error Handling Tests**
  Each file includes negative tests for missing inputs, invalid PDFs, or
  dependency issues (such as missing models), asserting graceful failure
  instead of uncaught exceptions.

- **Performance / Slow Tests**
  Heavy tests that might be slow in CI can be marked with `@pytest.mark.slow`
  and filtered with `-m slow` or `-m "not slow"`. The current suite uses
  this sparingly to keep pipeline time reasonable.

---

## Markers

The following pytest markers are registered for structured data tests
(via `tests/processors/conftest.py` and `pytest.ini`):

- `@pytest.mark.processor` – All processor tests in this package.
- `@pytest.mark.table` – `TableProcessor` tests.
- `@pytest.mark.svg` – `SVGProcessor` tests.
- `@pytest.mark.image` – `ImageProcessor` tests.
- `@pytest.mark.visual_embedding` – `VisualEmbeddingProcessor` tests.
- `@pytest.mark.multimodal` – Multi‑modal integration tests.
- `@pytest.mark.slow` – Tests expected to take longer than ~10 seconds.

You can combine these markers with `-m` to include or exclude categories
as needed.

---

## Dependencies

The structured data test suite relies on the following dependencies in
addition to the core project requirements:

- **pytest**, **pytest-asyncio**, **pytest-cov**, **pytest-xdist** (optional,
  for async tests, coverage, and parallelisation).
- **PyMuPDF** (`pymupdf`) for PDF generation and parsing.
- **Pillow** (`PIL`) for image creation and inspection.
- **pandas** for table data manipulation.
- **svglib** and **reportlab** for SVG to PNG conversion in `SVGProcessor`.
- **pytesseract** and Tesseract OCR (optional) for OCR‑related image tests
  – some tests will skip or degrade gracefully if these are missing.
- **colpali-engine** (optional) for `VisualEmbeddingProcessor`. When
  absent, visual embedding tests skip rather than fail.

Ensure these are installed in your development environment when running
this subset of tests locally.

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'fitz'`**
  Install PyMuPDF: `pip install pymupdf`.

- **`ImportError: cannot import name 'ColQwen2_5'`**
  Install `colpali-engine` or skip the `visual_embedding` marker:

  ```bash
  pip install colpali-engine
  # or
  pytest tests/processors/ -m "not visual_embedding" -v
  ```

- **`pytesseract.TesseractNotFoundError`**
  Install Tesseract OCR binary and ensure it is on the system PATH, or
  disable OCR‑dependent tests by using markers or configuration
  variables.

- **File‑not‑found or permission errors**
  The synthetic PDFs are written to temporary directories using
  `tempfile.mkdtemp`. Ensure the process has permission to write to the
  system temp directory on your platform.

- **Slow test execution**
  Use `-n auto` for parallel execution and/or skip slow categories with
  markers as described above.

---

## Plan Coverage and Deferred Scenarios

The structured data test suite is designed to exercise the **core happy
paths and basic negative paths** for the Phase 4 multi‑modal embedding
architecture, without reproducing every scenario from the high‑level
design documents.

- **TableProcessor scenarios**
  Current tests cover realistic extraction, type detection, context
  JSON, and embedding/storage via:
  `test_table_processor_unit.py` and `test_table_processor_e2e.py`.
  **Deferred:** Very large or extremely wide tables, multi‑page tables,
  and performance/throughput benchmarks are intentionally left to the
  full pipeline and performance tests described in
  `docs/TESTING_GUIDE_PHASES_1_6.md` and `docs/PHASE_4_MULTIMODAL_EMBEDDINGS.md`.

- **SVGProcessor scenarios**
  `test_svg_processor_e2e.py` validates extraction and PNG conversion on
  clean synthetic PDFs plus basic error handling for missing PDFs.
  **Deferred:** Explicit failure paths for SVG‑>PNG conversion (e.g.
  missing `svglib`/`reportlab`, corrupted vector content) are treated as
  pipeline‑level concerns and are not duplicated here to keep runtime
  and dependency surface reasonable.

- **ImageProcessor and OCR/vision guardrails**
  `test_image_processor_e2e.py` focuses on raster image extraction,
  basic filtering and storage queueing with `enable_ocr=False` and
  `enable_vision=False` for determinism.
  **Deferred:** Heavy OCR and Vision AI scenarios (e.g. fully scanned
  PDFs, OCR fallbacks, and quality thresholds) are covered by higher‑
  level pipeline and search tests rather than this focused suite.

- **VisualEmbeddingProcessor GPU/CPU behavior**
  `test_visual_embedding_processor_e2e.py` runs the processor in CPU
  mode on small synthetic images and asserts on basic embedding/storage
  behavior, skipping cleanly when `colpali‑engine` or the model cannot
  be loaded.
  **Deferred:** GPU‑specific behaviour, out‑of‑memory handling, and
  adaptive batching are validated via manual runs and broader Phase 4
  integration testing, not per‑processor unit/E2E tests.

- **Multi‑modal pipeline integration depth**
  `test_multimodal_integration.py` composes table, SVG, image, and
  visual embedding processors on the `sample_pdf_multimodal` fixture
  using a minimal `ProcessingContext`. It deliberately **does not** run
  through the full Upload/Text pipeline, which is covered by the
  end‑to‑end integration and pipeline scripts under `tests/integration/`
  and `scripts/`. This keeps the structured‑data tests fast and avoids
  tight coupling to the complete pipeline wiring.

Future contributors can use this section as a guide when deciding where
to add new scenarios: edge‑case or performance tests that require heavy
dependencies or long runtimes should generally live in the broader
pipeline or performance suites, while small, deterministic behaviours
belong in this `tests/processors/` package.

## Contributing

When adding or extending structured data tests:

- Follow existing patterns for async tests and context creation.
- Use the existing fixtures in `conftest.py` rather than re‑creating
  mocks or sample PDFs.
- Mark tests appropriately (`table`, `svg`, `image`, `visual_embedding`,
  `multimodal`, `slow`).
- Add clear docstrings describing the purpose of each test and class.
- Prefer small, focused tests that assert on specific behaviours.
- Update this README with any new test files or major scenarios you add.

This keeps the suite maintainable and ensures consistent coverage across
all structured data processors.
