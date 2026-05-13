# Optimization Recommendations - HP E877 Extraction Failures

## Scope
This plan targets the failed production run documented in:
- `file:docs/quality/PRODUCTION_TEST_BASELINE_20260213.md`
- `file:test_results/production_test_20260213_172656.json`
- `file:docs/quality/sql_diagnostics_20260213.json`

## Priority 0 (Immediate): Fix Manufacturer Linkage at Document Level

### Problem
Documents store `manufacturer = 'HP Inc.'` but `manufacturer_id = NULL`. This blocks downstream joins and pattern routing.

### Change
In metadata/manufacturer resolution pipeline, always normalize `manufacturer` text to `krai_core.manufacturers.id` and persist `documents.manufacturer_id`.

Target code paths to update:
- `file:backend/processors/product_extractor.py`
- `file:backend/processors/error_code_extractor.py`
- `file:backend/processors/parts_extractor.py`
- Manufacturer detection/normalization utilities:
  - `file:backend/utils/manufacturer_utils.py`
  - `file:backend/utils/MANUFACTURER_DETECTION_README.md` (doc update)

### Validation SQL
```sql
SELECT id, filename, manufacturer, manufacturer_id
FROM krai_core.documents
WHERE id = ANY(ARRAY[
  'becd5a67-3008-4d60-82ee-aa24f666b8c9'::uuid,
  'b557ec67-52db-4863-9e3a-b0d48e330b2e'::uuid
]);
```
Success criteria:
- `manufacturer_id` non-null for both documents.

## Priority 1: Guarantee Product Linking Before Parts Extraction

### Problem
`krai_parts.parts_catalog` is product-linked (`product_id`) and not document-linked (`document_id`). If document-product linking fails, parts count remains zero regardless of part extraction capability.

### Change
Enforce ordered dependency:
1. Product extraction/linking creates `krai_core.document_products` rows.
2. Parts extraction runs only after product links exist, or emits explicit warning/failure state.

### Validation SQL
```sql
SELECT dp.document_id, COUNT(*) AS linked_products
FROM krai_core.document_products dp
WHERE dp.document_id = ANY(ARRAY[
  'becd5a67-3008-4d60-82ee-aa24f666b8c9'::uuid,
  'b557ec67-52db-4863-9e3a-b0d48e330b2e'::uuid
])
GROUP BY dp.document_id;
```
Success criteria:
- At least one product link per document.

## Priority 2: Add Explicit Zero-Extraction Failure Signals

### Problem
Stages 11-15 complete successfully while extraction outputs remain zero. This is a silent quality failure mode.

### Change
Add stage-level guardrails:
- If `product_count == 0` after product stage, mark stage metadata warning/error.
- If `error_code_count == 0` for error-code-rich docs, add quality alert.
- If parts stage runs with no linked products, mark stage as skipped-with-reason.

Target:
- `file:backend/pipeline/master_pipeline.py`
- `file:scripts/quality_validator.py`

### Validation SQL
```sql
SELECT document_id, stage_number, stage_name, status, error_message, metadata
FROM krai_system.stage_tracking
WHERE document_id = ANY(ARRAY[
  'becd5a67-3008-4d60-82ee-aa24f666b8c9'::uuid,
  'b557ec67-52db-4863-9e3a-b0d48e330b2e'::uuid
])
ORDER BY document_id, stage_number;
```
Success criteria:
- Quality-relevant zero outputs are visible in stage metadata/error fields.

## Priority 3: Make SQL Diagnostics Schema-Aware

### Problem
Three ticket SQL statements failed due to outdated column assumptions:
- `document_products.confidence_score`
- `error_codes.manufacturer_name`
- `parts_catalog.document_id` and `parts_catalog.manufacturer_name`

### Change
Store canonical, schema-compatible quality SQL in one location and reuse in scripts.

Target:
- `file:scripts/quality_validator.py`
- optional helper under `file:scripts/` for shared diagnostics

### Validation
- Execute diagnostics without manual query edits.
- Ensure 8-query run returns `status=ok` (except intentionally optional checks).

## Priority 4: Improve Error-Code Extraction Recall for HP Format

### Problem
Chunk corpus contains many HP-style error tokens, but table `krai_intelligence.error_codes` is empty.

### Change
- Verify and tighten regex application over chunk text for HP:
  - `\b\d{2}\.\d{2,3}\.\d{2}\b`
- Add unit/integration tests with real CPMD snippets.
- Persist extraction provenance in `extraction_method`.

Target configs:
- `file:backend/config/error_code_patterns.json`

Target tests:
- Add tests under `file:tests/processors/` or existing extractor test suites.

### Validation SQL
```sql
SELECT document_id, COUNT(*) AS error_count
FROM krai_intelligence.error_codes
WHERE document_id = ANY(ARRAY[
  'becd5a67-3008-4d60-82ee-aa24f666b8c9'::uuid,
  'b557ec67-52db-4863-9e3a-b0d48e330b2e'::uuid
])
GROUP BY document_id;
```
Success criteria:
- Non-zero error codes for at least CPMD.

## Priority 5: Expand Observability for Image Semantic Steps

### Problem
`images_with_context_embedding = 0` for both docs despite successful image processing counts.

### Change
- Decide if image context embeddings are optional or required.
- If required: enforce generation and track failure reason per image batch.
- If optional: mark explicitly in quality report to avoid false expectations.

Target:
- image pipeline components in `file:backend/processors/`
- quality reporting in `file:scripts/quality_validator.py`

## Effort Estimate
- P0: 0.5-1 day
- P1: 0.5 day
- P2: 0.5 day
- P3: 0.5 day
- P4: 1-2 days
- P5: 0.5-1 day

Total: ~3.5 to 5.5 engineering days.

## Recommended Execution Order
1. Implement P0 manufacturer FK linkage.
2. Implement P1 dependency enforcement on product links.
3. Implement P2 zero-extraction signals.
4. Fix diagnostics for schema-awareness (P3).
5. Tune extraction recall and tests (P4).
6. Clarify image semantic behavior (P5).

## Exit Criteria
- Production test rerun shows:
  - `products_count >= 1`
  - `error_codes >= 5` (threshold)
  - `manufacturer_detected = true`
  - `linked_products >= 1`
  - no silent zero-extraction stages
