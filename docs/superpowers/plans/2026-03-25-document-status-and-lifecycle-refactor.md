# Document Status And Lifecycle Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make document upload, processing status, stage status, monitoring, and delete behavior consistent so the admin UI reflects real pipeline activity and lifecycle actions reliably.

**Architecture:** Keep `krai_system.stage_tracking` as the execution log, but explicitly project it into `krai_core.documents.processing_status` and `krai_core.documents.stage_status`, because Laravel already reads those fields everywhere. Refactor Laravel to consume one normalized status contract from `KraiEngineService`, move delete through the backend API only, and make the Pipeline Status page show pipeline-specific activity from backend-supported data instead of stitching together partially stale sources.

**Tech Stack:** FastAPI, asyncpg, KRMasterPipeline, Laravel 12, Filament 5, PHPUnit, pytest, Docker Compose

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `backend/pipeline/master_pipeline.py` | **Modify** | Persist stage-tracking updates into document projection fields and define lifecycle rules |
| `backend/api/routes/document_processing.py` | **Modify** | Return richer normalized status and stage payloads |
| `backend/api/routes/documents.py` | **Modify** | Make delete cleanup authoritative and idempotent |
| `backend/api/routes/monitoring.py` or existing monitoring route module | **Modify** | Add pipeline-activity/log endpoint that reflects real processing events |
| `backend/services/object_storage_service.py` | **Modify** | Keep storage download helper for processors needing local files |
| `backend/services/metrics_service.py` | **Modify** | Remove stale `krai_core.stage_status` / missing-view assumptions |
| `backend/tests/test_document_processing_routes.py` | **Modify** | Backend contract tests for status projection and stage responses |
| `backend/tests/...monitoring...py` | **Create/Modify** | Backend tests for pipeline activity endpoint |
| `laravel-admin/app/Services/KraiEngineService.php` | **Modify** | Single normalization layer for document status, stage status, reprocess, and delete |
| `laravel-admin/app/Filament/Resources/Documents/Pages/ListDocuments.php` | **Modify** | Upload action semantics and status refresh after upload |
| `laravel-admin/app/Filament/Resources/Documents/Pages/EditDocument.php` | **Modify** | Replace generic “processing” toast with structured status, working delete, and stage summary |
| `laravel-admin/app/Filament/Resources/Documents/Schemas/DocumentForm.php` | **Modify** | Show real per-stage status on the edit form |
| `laravel-admin/app/Filament/Resources/Documents/Tables/DocumentsTable.php` | **Modify** | Show compact, trustworthy processing/stage state in listing |
| `laravel-admin/app/Filament/Pages/PipelineStatusPage.php` | **Modify** | Consume new backend activity/status data instead of improvised queue/error merge |
| `laravel-admin/resources/views/filament/pages/pipeline-status.blade.php` | **Modify** | Render pipeline activity, current documents, and terminal-like log lines clearly |
| `laravel-admin/app/Services/MonitoringService.php` | **Modify** | Fetch normalized pipeline activity endpoint with cache discipline |
| `laravel-admin/tests/Feature/KraiEngineServiceFixesTest.php` | **Modify** | Service contract tests for status and delete |
| `laravel-admin/tests/Feature/ListDocumentsUploadActionTest.php` | **Modify** | Upload starts processing and surfaces status |
| `laravel-admin/tests/Feature/PipelineStatusPageTest.php` | **Modify** | Pipeline page renders real activity payload |
| `laravel-admin/tests/Feature/DocumentLifecycleActionsTest.php` | **Create** | Edit-page status and delete regression coverage |

---

## Refactor Decision

This should be a bounded refactor, not more spot fixes.

Why:
- The real execution truth currently lands in `krai_system.stage_tracking`, but the UI reads `krai_core.documents.stage_status` and `processing_status`.
- The Pipeline Status page currently assembles queue items and errors from separate sources that are not guaranteed to represent one live document lifecycle.
- Delete is only trustworthy if every UI path uses the backend API cleanup path.
- The current “Status prüfen” action only echoes a top-level string and hides the stage-level truth the user actually needs.

The refactor boundary is intentionally narrow:
- Do **not** redesign the whole pipeline engine.
- Do **not** introduce a new status store.
- Do **not** replace Filament resources wholesale.
- Do unify the data contract and lifecycle behavior end-to-end.

---

## UX Direction

Implementation must follow the approved UX in [2026-03-26-document-status-ux-design.md](/C:/Users/haast/Docker/KRAI-minimal/docs/superpowers/specs/2026-03-26-document-status-ux-design.md).

Key rules:
- Document detail page uses a guided grouped pipeline view with expandable groups.
- All stages stay visible, not only failures.
- Failed stages show technical error text directly.
- Pipeline Status page follows the grouped operational overview direction, not a flat metrics board.
- Technical logs on the Pipeline Status page are expandable per group, not always-on global noise.

---

## Task 1: Define the status source of truth and project it onto documents

**Files:**
- Modify: `backend/pipeline/master_pipeline.py`
- Modify: `backend/tests/test_document_processing_routes.py`
- Modify: backend integration test file that already covers master pipeline stage tracking

### Background

Execution is already tracked in `krai_system.stage_tracking`. Laravel mostly reads `krai_core.documents.processing_status` and `stage_status`. The backend must therefore update the document row whenever a stage moves to `processing`, `completed`, `failed`, or is skipped.

The document projection rules should be:
- `processing_status = pending` only before any real processing starts
- `processing_status = processing` when at least one stage is running or some stages are completed while more remain
- `processing_status = completed` when all required stages for the selected flow are complete
- `processing_status = failed` when a stage fails and the document is not automatically recovered

`stage_status` should become a structured JSON object per stage, not a bare string map:

```json
{
  "text_extraction": {
    "status": "completed",
    "started_at": "2026-03-25T12:00:00Z",
    "completed_at": "2026-03-25T12:01:30Z",
    "processing_time": 90.0,
    "message": null
  }
}
```

- [ ] **Step 1: Write a failing backend test for status projection**

Add a test that simulates `track_stage_status(document_id, "text_extraction", "completed", ...)` and expects the document row update SQL to include both `stage_status` and `processing_status`.

```python
assert "UPDATE krai_core.documents" in executed_sql
assert "stage_status" in executed_sql
assert "processing_status" in executed_sql
```

- [ ] **Step 2: Run the backend test and confirm failure**

Run: `cd backend && python -m pytest tests/test_document_processing_routes.py -k status_projection -v`

Expected: FAIL because projection is incomplete or still string-based.

- [ ] **Step 3: Refactor `track_stage_status()` to own document projection**

Implement structured projection in `backend/pipeline/master_pipeline.py`:

```python
stage_payload = {
    "status": status,
    "started_at": started_at_iso,
    "completed_at": completed_at_iso,
    "processing_time": processing_time,
    "message": error_message,
}
```

Then merge it into `krai_core.documents.stage_status` and derive `processing_status` with one helper:

```python
def derive_document_processing_status(stage_status: dict[str, dict[str, Any]]) -> str:
    ...
```

- [ ] **Step 4: Add one integration-level test for real lifecycle transitions**

Cover:
- upload only -> `pending`
- first active stage -> `processing`
- all required stages complete -> `completed`
- one failed stage -> `failed`

- [ ] **Step 5: Run focused backend tests**

Run: `cd backend && python -m pytest tests/test_document_processing_routes.py tests/integration/test_full_pipeline_integration.py -k "status or stage_tracking" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/master_pipeline.py backend/tests/test_document_processing_routes.py backend/tests/integration/test_full_pipeline_integration.py
git commit -m "[Pipeline] Project stage tracking into document status fields"
```

---

## Task 2: Normalize the backend document status and stage-status contracts

**Files:**
- Modify: `backend/api/routes/document_processing.py`
- Modify: `backend/api/routes/response_models.py` if needed
- Modify: `backend/tests/test_document_processing_routes.py`

### Background

Laravel should not need to guess between:
- bare `stage_status`
- legacy `data.stages`
- UUID objects vs strings
- string status values vs structured stage objects

The backend routes must always return a single normalized payload shape.

- [ ] **Step 1: Write failing contract tests for status and stage-status payloads**

Add tests asserting:

```python
assert body["data"] == {
    "document_id": "doc-123",
    "status": "processing",
    "current_stage": "text_extraction",
    "progress": 0.2,
    "queue_position": 1,
    "total_queue_items": 3,
}
```

and:

```python
assert body["data"]["stage_status"]["text_extraction"]["status"] == "completed"
assert isinstance(body["data"]["document_id"], str)
```

- [ ] **Step 2: Run the route tests and verify failure**

Run: `cd backend && python -m pytest tests/test_document_processing_routes.py -k "document_status or stage_status" -v`

Expected: FAIL on legacy/malformed payload shape.

- [ ] **Step 3: Refactor route serialization**

In `backend/api/routes/document_processing.py`:
- always cast `document_id` to `str`
- always return structured `stage_status`
- derive `current_stage` from the first active or last incomplete stage
- derive `progress` from completed stages over total selected stages

Use one serializer helper instead of duplicating route logic:

```python
def serialize_stage_status(raw_stage_status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ...
```

- [ ] **Step 4: Preserve backward compatibility only inside the serializer**

Handle old values like:

```python
{"embedding": "completed"}
```

by converting them to:

```python
{"embedding": {"status": "completed"}}
```

- [ ] **Step 5: Run backend status route tests**

Run: `cd backend && python -m pytest tests/test_document_processing_routes.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/document_processing.py backend/api/routes/response_models.py backend/tests/test_document_processing_routes.py
git commit -m "[API] Normalize document and stage status payloads"
```

---

## Task 3: Make Laravel use one normalized status service contract

**Files:**
- Modify: `laravel-admin/app/Services/KraiEngineService.php`
- Modify: `laravel-admin/tests/Feature/KraiEngineServiceFixesTest.php`

### Background

UI code should not parse raw backend responses directly. `KraiEngineService` should return one predictable array shape for:
- `getDocumentStatus()`
- `getStageStatus()`
- `reprocessDocument()`
- `processMultipleStages()`
- `deleteDocument()`

The service return for `getDocumentStatus()` should be:

```php
[
    'success' => true,
    'status' => 'processing',
    'current_stage' => 'text_extraction',
    'progress' => 0.2,
    'queue_position' => 1,
    'total_queue_items' => 3,
    'stage_summary' => [
        'completed' => 2,
        'processing' => 1,
        'failed' => 0,
        'pending' => 11,
    ],
    'stage_status' => [...],
]
```

- [ ] **Step 1: Write failing PHPUnit tests for normalized status output**

Add tests asserting:

```php
$this->assertSame('processing', $result['status']);
$this->assertSame('text_extraction', $result['current_stage']);
$this->assertSame(1, $result['queue_position']);
$this->assertSame(2, $result['stage_summary']['completed']);
```

- [ ] **Step 2: Run the service tests and confirm failure**

Run: `cd laravel-admin && php artisan test --compact tests/Feature/KraiEngineServiceFixesTest.php`

Expected: FAIL because summary/current stage are not fully normalized.

- [ ] **Step 3: Refactor `KraiEngineService` normalization helpers**

Create private helpers like:

```php
private function normalizeDocumentStatusPayload(array $payload): array
private function summarizeStageStatus(array $stageStatus): array
private function normalizeErrorMessage(mixed $error): ?string
```

Keep every UI caller dependent on these helpers, not raw response arrays.

- [ ] **Step 4: Make service methods idempotent around missing data**

Missing `stage_status` should become `[]`.
Missing `progress` should become `0.0`.
Missing `current_stage` should become `null`.

- [ ] **Step 5: Run Laravel service tests**

Run: `cd laravel-admin && php artisan test --compact tests/Feature/KraiEngineServiceFixesTest.php`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add laravel-admin/app/Services/KraiEngineService.php laravel-admin/tests/Feature/KraiEngineServiceFixesTest.php
git commit -m "[Laravel] Normalize document status service contract"
```

---

## Task 4: Refactor the document UI around real status and working lifecycle actions

**Files:**
- Modify: `laravel-admin/app/Filament/Resources/Documents/Pages/ListDocuments.php`
- Modify: `laravel-admin/app/Filament/Resources/Documents/Pages/EditDocument.php`
- Modify: `laravel-admin/app/Filament/Resources/Documents/Schemas/DocumentForm.php`
- Modify: `laravel-admin/app/Filament/Resources/Documents/Tables/DocumentsTable.php`
- Create: `laravel-admin/tests/Feature/DocumentLifecycleActionsTest.php`
- Modify: `laravel-admin/tests/Feature/ListDocumentsUploadActionTest.php`

### Background

The current document UX has three problems:
- upload success does not clearly surface whether processing actually started
- “Status prüfen” only shows `processing`
- delete behavior is not proven end-to-end in the UI

The UI should expose:
- top-level status
- current stage
- progress percentage
- counts of completed/processing/failed/pending stages
- delete via backend API only
- grouped accordion sections for the pipeline
- technical stage error text inline for failed stages
- visible successful stages to preserve trust/context

- [ ] **Step 1: Write failing UI-focused tests**

Cover:
- upload without selected stages triggers reprocess and shows a “Pipeline gestartet” style message
- `Status prüfen` renders current stage and progress
- delete action calls backend API service and redirects away from edit page

- [ ] **Step 2: Run the focused Laravel tests**

Run: `cd laravel-admin && php artisan test --compact tests/Feature/ListDocumentsUploadActionTest.php tests/Feature/DocumentLifecycleActionsTest.php`

Expected: FAIL

- [ ] **Step 3: Refactor the upload success path**

In `ListDocuments.php`, when upload succeeds:
- if no stages are chosen, call `reprocessDocument()`
- surface the returned status contract in the notification

Example body:

```php
'Dokument hochgeladen. Pipeline gestartet. Aktuelle Stage: '.$result['current_stage']
```

- [ ] **Step 4: Refactor `EditDocument` status actions**

Replace the flat notification with a structured summary:

```php
$lines = [
    'Dokumentenstatus: '.$result['status'],
    'Aktuelle Stage: '.($result['current_stage'] ?? 'keine'),
    'Fortschritt: '.number_format($result['progress'] * 100, 1).'%',
];
```

Also ensure `Stage Status anzeigen` uses the structured stage object contract, not raw strings.

- [ ] **Step 5: Refactor the stage-status layout**

Update the document detail/status Blade components so the view matches the approved UX:
- grouped accordions by pipeline block
- header summary with current stage and progress
- stage rows with inline technical error text
- completed stages remain visible

Avoid the current dense badge-grid layout.

- [ ] **Step 6: Refactor delete UI to one backend-backed path**

Use only `KraiEngineService::deleteDocument()` in Filament actions and list views. Remove any remaining raw Eloquent delete usage for documents.

- [ ] **Step 7: Run document lifecycle tests**

Run: `cd laravel-admin && php artisan test --compact tests/Feature/ListDocumentsUploadActionTest.php tests/Feature/DocumentLifecycleActionsTest.php`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add laravel-admin/app/Filament/Resources/Documents/Pages/ListDocuments.php laravel-admin/app/Filament/Resources/Documents/Pages/EditDocument.php laravel-admin/app/Filament/Resources/Documents/Schemas/DocumentForm.php laravel-admin/app/Filament/Resources/Documents/Tables/DocumentsTable.php laravel-admin/tests/Feature/ListDocumentsUploadActionTest.php laravel-admin/tests/Feature/DocumentLifecycleActionsTest.php
git commit -m "[Filament] Refactor document lifecycle status and delete actions"
```

---

## Task 5: Make backend delete authoritative and idempotent

**Files:**
- Modify: `backend/api/routes/documents.py`
- Add/Modify: backend delete-route tests
- Modify: `laravel-admin/tests/Feature/KraiEngineServiceFixesTest.php`

### Background

Delete should succeed whether or not queue, scraping, chunks, or stage-tracking records already exist. The backend route should own the cleanup order and be safe to call more than once.

- [ ] **Step 1: Write failing backend delete tests**

Add tests for:
- document with queue rows
- document with link scraping rows
- document already partially cleaned up
- second delete call returns a safe “not found / already deleted” response contract

- [ ] **Step 2: Run delete tests**

Run: `cd backend && python -m pytest -k delete_document -v`

Expected: FAIL

- [ ] **Step 3: Refactor delete cleanup sequence**

Cleanup order should look like:

```python
DELETE FROM krai_system.processing_queue WHERE document_id = $1
DELETE FROM krai_system.link_scraping_jobs WHERE document_id = $1
DELETE FROM krai_system.stage_tracking WHERE document_id = $1
DELETE FROM krai_intelligence.chunks WHERE document_id = $1
DELETE FROM krai_core.documents WHERE id = $1
```

Only include tables that actually exist in this schema and are safe to own here.

- [ ] **Step 4: Return a predictable delete contract**

Example:

```python
{"success": True, "deleted": True, "document_id": "..."}
```

- [ ] **Step 5: Run backend and Laravel delete tests**

Run:
- `cd backend && python -m pytest -k delete_document -v`
- `cd laravel-admin && php artisan test --compact tests/Feature/KraiEngineServiceFixesTest.php`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/documents.py laravel-admin/tests/Feature/KraiEngineServiceFixesTest.php
git commit -m "[Documents] Make backend delete cleanup authoritative"
```

---

## Task 6: Rebuild the Pipeline Status page around real pipeline activity

**Files:**
- Modify: backend monitoring route module that serves `/api/v1/monitoring/pipeline`
- Modify: `backend/services/metrics_service.py`
- Modify: `laravel-admin/app/Services/MonitoringService.php`
- Modify: `laravel-admin/app/Filament/Pages/PipelineStatusPage.php`
- Modify: `laravel-admin/resources/views/filament/pages/pipeline-status.blade.php`
- Modify: `laravel-admin/tests/Feature/PipelineStatusPageTest.php`

### Background

The page should answer:
- which documents are running right now?
- which stage is active?
- what failed recently?
- what pipeline-specific log lines exist?

It should **not** depend on missing relations/views like `krai_core.stage_status` or `vw_*_aggregated` if they are not present.

Define a normalized backend response shape:

```json
{
  "pipeline_metrics": {...},
  "active_documents": [
    {
      "document_id": "doc-123",
      "filename": "manual.pdf",
      "status": "processing",
      "current_stage": "text_extraction",
      "progress": 0.2
    }
  ],
  "recent_activity": [
    {
      "timestamp": "2026-03-25T12:34:56Z",
      "type": "stage",
      "document_id": "doc-123",
      "stage_name": "text_extraction",
      "status": "processing",
      "message": "Stage started"
    }
  ],
  "recent_failures": [...]
}
```

The Laravel page implementation must follow the approved UX:
- grouped operational overview
- active documents surfaced inside the relevant group
- recent failures visible in context
- expandable technical logs per group

- [ ] **Step 1: Write failing tests for the backend pipeline activity payload**

Assert the response includes:
- `active_documents`
- `recent_activity`
- `recent_failures`
- no dependency on nonexistent views

- [ ] **Step 2: Write failing PHPUnit test for the Filament page**

Update `PipelineStatusPageTest.php` so it asserts:

```php
$this->assertArrayHasKey('active_documents', $data);
$this->assertArrayHasKey('recent_activity', $data);
$this->assertStringContainsString('text_extraction', implode("\n", $data['terminal_lines']));
```

- [ ] **Step 3: Refactor backend monitoring aggregation**

Use only tables that exist now:
- `krai_core.documents`
- `krai_system.stage_tracking`
- `krai_system.processing_queue`
- `krai_system.pipeline_errors`

Build pipeline activity from those tables instead of `krai_core.stage_status` or missing materialized views.

- [ ] **Step 4: Refactor Laravel monitoring service and page**

`MonitoringService` should fetch one endpoint and cache it for a short TTL.
`PipelineStatusPage` should stop merging queue/errors ad hoc and instead render the normalized backend payload.

- [ ] **Step 5: Update the Blade view**

Render:
- summary cards
- active documents table
- recent failures block
- terminal-like log lines from `recent_activity`
- grouped accordion sections with per-group expandable technical traces

- [ ] **Step 6: Run backend and Laravel monitoring tests**

Run:
- `cd backend && python -m pytest -k "monitoring and pipeline" -v`
- `cd laravel-admin && php artisan test --compact tests/Feature/PipelineStatusPageTest.php`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/metrics_service.py laravel-admin/app/Services/MonitoringService.php laravel-admin/app/Filament/Pages/PipelineStatusPage.php laravel-admin/resources/views/filament/pages/pipeline-status.blade.php laravel-admin/tests/Feature/PipelineStatusPageTest.php
git commit -m "[Monitoring] Rebuild pipeline status around real activity data"
```

---

## Task 7: Verify end-to-end in Docker and clean up user-facing text

**Files:**
- Modify: any touched files that still expose stale wording
- Optionally update a docs note if workflow changed materially

### Background

Before considering this done, verify the actual user workflow:
- upload document
- observe status move beyond `pending`
- inspect edit page
- inspect pipeline page
- delete document

- [ ] **Step 1: Rebuild the relevant containers**

Run: `docker compose up -d --build krai-engine laravel-admin nginx`

Expected: containers healthy.

- [ ] **Step 2: Upload one PDF through the UI or through the Laravel-side workflow test helper**

Verify:
- document row exists
- `processing_status` becomes `processing`
- `stage_status` is not empty

- [ ] **Step 3: Query the database directly**

Run SQL checks for the uploaded document:

```sql
SELECT processing_status, stage_status FROM krai_core.documents WHERE id = '<doc-id>';
SELECT stage_name, status FROM krai_system.stage_tracking WHERE document_id = '<doc-id>' ORDER BY started_at;
```

Expected: document projection matches tracking rows.

- [ ] **Step 4: Verify the Pipeline Status page**

Confirm it shows:
- active document
- current stage
- recent activity lines
- no SQL/view errors

- [ ] **Step 5: Delete the same document**

Verify:
- backend delete returns success
- edit page redirects
- related queue/tracking rows are gone

- [ ] **Step 6: Run focused regression suites**

Run:
- `cd backend && python -m pytest tests/test_document_processing_routes.py -v`
- `cd laravel-admin && php artisan test --compact tests/Feature/KraiEngineServiceFixesTest.php tests/Feature/ListDocumentsUploadActionTest.php tests/Feature/DocumentLifecycleActionsTest.php tests/Feature/PipelineStatusPageTest.php`
- `cd laravel-admin && vendor/bin/pint --dirty`

Expected: PASS and clean formatting.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "[Refactor] Align document lifecycle status, monitoring, and delete behavior"
```

---

## Notes For Execution

- Prefer small commits per task. Do not batch the whole refactor into one commit.
- Do not remove backward-compatibility parsing from Laravel until backend route tests are green.
- Keep `upload` excluded from manual stage selection.
- Treat `krai_system.stage_tracking` as the operational log and `krai_core.documents.*status*` as the UI projection.
- If a missing DB object is discovered during monitoring refactor, either stop depending on it or add it in a dedicated migration task; do not silently hard-code around it.

## Open Questions Resolved By This Plan

- **Should we refactor?** Yes, but bounded to status, monitoring, and delete lifecycle consistency.
- **Should Pipeline Status show raw container logs?** No. It should show pipeline-specific activity derived from pipeline tables and normalized backend responses.
- **Should upload without explicit stage selection start processing automatically?** Yes, and the UI should display that clearly.
