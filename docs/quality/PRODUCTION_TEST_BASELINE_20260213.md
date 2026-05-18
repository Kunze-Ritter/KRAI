# Production Test Quality Baseline - February 13, 2026

## Executive Summary
- Test Run ID: `test_20260213_072532`
- Result: `FAIL`
- Start: `2026-02-13T07:25:32.699812`
- End: `2026-02-13T17:26:56.754430`
- Duration: `36,084.05s` (`10.02h`)
- Documents:
  - `becd5a67-3008-4d60-82ee-aa24f666b8c9` (`HP_E877_CPMD.pdf`)
  - `b557ec67-52db-4863-9e3a-b0d48e330b2e` (`HP_E877_SM.pdf`)
- Critical quality failures:
  - Products extracted: `0`
  - Error codes extracted: `0`
  - Parts linked to target documents: `0`

This baseline is data-backed from:
- `file:test_results/production_test_20260213_172656.json`
- `file:docs/quality/sql_diagnostics_20260213.json`

## Test Configuration
- PDFs:
  - `C:\Firmwares\HP\HP_E877_CPMD.pdf`
  - `C:\Firmwares\HP\HP_E877_SM.pdf`
- Thresholds from `file:config/production_test_thresholds.json`:
  - `min_chunks: 100`
  - `min_images: 10`
  - `min_error_codes: 5`
  - `min_embedding_coverage: 0.95`
  - `min_products: 1`
  - `min_parts: 0`

## Quality Metrics Summary

### Completeness
- Chunks: `5,159` vs threshold `100` -> `PASS`
- Images: `2,062` vs threshold `10` -> `PASS`
- Error codes: `0` vs threshold `5` -> `FAIL`
- Parts: `0` vs threshold `0` -> `PASS`
- Overall completeness: `FAIL`

### Correctness
- Products: `0` vs threshold `1` -> `FAIL`
- Model detected (`E877`): `false` -> `FAIL`
- Manufacturer detected (`HP`): `false` -> `FAIL`
- Overall correctness: `FAIL`

### Embeddings
- Coverage: `5,159 / 5,159 = 1.0` -> `PASS`

### Relationships
- Linked documents in `krai_core.document_products`: `0`
- Linked products in `krai_core.document_products`: `0`
- Relationship integrity result: `FAIL`

### Stage Tracking
- Stage records: `30/30`
- Completed stages: `30/30`
- Stage status: `PASS`

## SQL Diagnostic Results

Eight diagnostic SQL checks were executed. Original query set from ticket was run first; where schema mismatches existed, equivalent schema-compatible query variants were executed and documented.

### Query 1: Document Metadata Analysis
Result:
- Both documents have `manufacturer = 'HP Inc.'`
- Both documents have `manufacturer_id = NULL`
- `extracted_metadata = {}`
- Joined manufacturer row is `NULL` due to missing FK

Evidence:
- `HP_E877_CPMD.pdf`: `processing_status = failed`
- `HP_E877_SM.pdf`: `processing_status = pending`

### Query 2: Product Extraction Analysis
Original query status:
- Failed: `column dp.confidence_score does not exist`

Schema-compatible result (`relevance_score` used):
- `0` rows in `krai_core.document_products` for both document IDs

### Query 3: Error Code Extraction Analysis
Original query status:
- Failed: `column ec.manufacturer_name does not exist`

Schema-compatible result (`error_description`, `solution_text`, `severity_level`, `confidence_score`):
- `0` error code rows for both documents

### Query 4: Parts Extraction Analysis
Original query status:
- Failed: `column pc.manufacturer_name does not exist` (and table has no `document_id`)

Schema-compatible result:
- `krai_parts.parts_catalog` links via `product_id`, not `document_id`
- No parts linked via document products (`0` rows), because no products are linked

### Query 5: Chunk Content Sampling
Result:
- Sampled first 20 early-page chunks
- Expected semantic signals present in raw text:
  - `E877` appears in chunk corpus
  - HP style error-code patterns like `10.23.35`, `10.31.60` appear in chunk text
- Embedding exists on sampled rows (`has_embedding = true`)

Pattern probe (whole corpus):
- `HP_E877_SM.pdf`: `chunks_with_e877 = 30`, `chunks_with_hp_error_pattern = 11`
- `HP_E877_CPMD.pdf`: `chunks_with_e877 = 15`, `chunks_with_hp_error_pattern = 250`

### Query 6: Stage Tracking Analysis
Result:
- All 15 stages completed for both documents
- No stage-level `error_message` values in stage rows for target documents

Interpretation:
- Pipeline orchestration completed, but semantic extraction outputs stayed empty.

### Query 7: Image Processing Verification
Result:
- `HP_E877_CPMD.pdf`: `1708` images, OCR on `67`, AI descriptions on `43`, context embeddings `0`
- `HP_E877_SM.pdf`: `354` images, OCR on `56`, AI descriptions on `13`, context embeddings `0`

Interpretation:
- Image ingestion happened at scale; context embedding for images appears disabled or not populated.

### Query 8: Manufacturer Configuration Check
Result:
- HP manufacturer exists:
  - `id: e7680b1c-d4f8-45fb-934a-3be603c29cac`
  - `name: HP Inc.`
  - `short_name: HP`

Interpretation:
- Configuration data exists, but target documents were not linked to this manufacturer by `manufacturer_id`.

## Root Cause Analysis

### Primary Root Cause (Confirmed): Manufacturer Linkage Missing
Evidence chain:
1. Documents have manufacturer string (`HP Inc.`) but `manufacturer_id = NULL`.
2. Manufacturer table contains valid HP row.
3. No rows in `krai_core.document_products`.
4. Error/parts extraction outputs are empty despite relevant patterns in chunks.

Impact:
- Extractors that rely on normalized manufacturer context / FK-based joins do not activate correctly.

### Secondary Issue (Confirmed): Schema Drift vs Diagnostic SQL
Evidence:
- Ticket-provided Query 2/3/4 fail on missing columns (`confidence_score`, `manufacturer_name`, `document_id` in parts context).

Impact:
- Diagnostics can report false negatives or fail outright unless schema-compatible queries are used.

### Tertiary Observation (Likely): Extraction Selection Logic Not Entering Positive Paths
Evidence:
- Chunk text clearly contains model and error-pattern tokens.
- Stage completion is 100%.
- Yet product/error extraction tables remain empty.

Likely explanation:
- Manufacturer linkage is prerequisite for pattern activation and/or product linking stage.

## Baseline Snapshot (Per Document)

| Document | Chunks | Images | Error Codes | Products | Parts via Product Link | Embedding Coverage |
|---|---:|---:|---:|---:|---:|---:|
| `HP_E877_CPMD.pdf` | 1189 | 1708 | 0 | 0 | 0 | 1.0 |
| `HP_E877_SM.pdf` | 3970 | 354 | 0 | 0 | 0 | 1.0 |

## Evidence Files
- Raw production report: `file:test_results/production_test_20260213_172656.json`
- SQL diagnostics full output: `file:docs/quality/sql_diagnostics_20260213.json`
- Threshold config: `file:config/production_test_thresholds.json`

## Baseline Conclusion
The pipeline is operational for ingestion, chunking, embedding, and stage progression, but fails semantically at extraction/linking. The highest-confidence failure point is missing `manufacturer_id` linkage on documents despite existing HP manufacturer records and obvious HP/E877/error-pattern content in chunks.
