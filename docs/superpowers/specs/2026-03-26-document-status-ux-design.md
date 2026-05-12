# Document Status UX Design
**Date:** 2026-03-26
**Status:** Approved
**Scope:** Laravel Admin UX for document detail status and pipeline status monitoring

## Background

The current document processing UX exposes too little useful truth and too much raw noise at the same time:

- the document detail page reduces status to a flat top-level string like `processing`
- the stage view is visually noisy and hard to scan
- failed stages dominate the view without explaining where the document currently is in the pipeline
- the pipeline status page does not build trust because it does not clearly answer what is running, what is blocked, and what has already succeeded

The chosen direction is to make both views trustworthy, stage-aware, and operationally useful without turning them into a raw debug console.

---

## UX Goals

1. A user should immediately understand where a document currently is in the pipeline.
2. A user should be able to see all stages, not only failures, so successful work remains visible.
3. Technical errors should be visible directly where they matter.
4. The document detail page and the global pipeline page should feel related, but not identical.
5. The pipeline page should be readable for operations, not just engineers.

---

## Chosen Direction

### Document Detail Page

Use a **guided grouped pipeline view** with expandable groups.

The page should have:

- a summary header with:
  - overall document status
  - current stage
  - progress percentage
  - failed-stage count
- grouped pipeline sections such as:
  - Initialization
  - Extraction
  - Processing
  - Enrichment
  - Finalization
- groups expanded/collapsed as accordions
- all stages visible inside the groups
- direct technical error text on failed stages
- successful stages kept visible, not hidden

This page is document-centric. It should answer:
- What is happening to this document right now?
- What already succeeded?
- What failed exactly?
- What is likely next?

### Pipeline Status Page

Use the visual direction corresponding to **Option 2** from the mockups.

The page should be a **grouped operational overview** across multiple documents, with:

- summary cards at the top
- grouped pipeline blocks showing what is active, idle, or blocked
- active document highlights per group
- recent failures surfaced in context
- technical logs available as **expandable sections per group**

This page is system-centric. It should answer:
- Which pipeline groups are active right now?
- Which documents are currently moving?
- Which groups are blocked or failing?
- What technical events explain the current state?

---

## Information Hierarchy

### Document Detail Page Hierarchy

1. **Current truth**
   - overall status
   - current stage
   - progress
2. **Pipeline map**
   - grouped stage blocks
   - active vs completed vs failed vs pending stages
3. **Technical detail**
   - raw error reason for failed stages
   - timestamps / processing time where available

### Pipeline Status Page Hierarchy

1. **System summary**
   - active flows
   - blocked groups
   - failed stages
   - health / throughput summary
2. **Grouped live activity**
   - Extraction / Processing / Enrichment / Finalization blocks
3. **Expandable technical traces**
   - per-group event/log section

---

## Visual Rules

### Document Detail Page

- Prefer grouped accordions over flat multi-column badge grids.
- Highlight the currently active group first.
- Use status color sparingly:
  - green for completed
  - amber for active / in progress
  - red for failed
  - neutral gray/slate for pending / idle
- Do not render all failed stages as equally dominant if one active stage is the real current bottleneck.
- Each stage row should show:
  - stage label
  - short machine-readable status
  - optional timing
  - technical error text if failed

### Pipeline Status Page

- Prefer grouped operational blocks over one giant document table.
- Keep the page readable without opening every detail section.
- Logs are secondary and should stay collapsed until requested.
- Recent failures belong near the affected group, not only in a separate distant error list.

---

## Content Rules

### Failed Stages

Show the technical error directly.

Example:

```text
image_processing
Failed
File missing in object storage: documents/abc123.pdf
```

Do not replace the technical error with vague text like:
- `Verarbeitung fehlgeschlagen`
- `Bitte Support kontaktieren`

### Successful Stages

Keep successful stages visible so users can see progress and build trust.

Example:

```text
metadata_extraction
Completed
finished in 1.2s
```

### Active Stage

Always surface the active stage both:
- in the summary header
- inside the relevant group block

---

## Data Contract Implications

This UX requires structured stage status, not plain strings.

Each stage should ideally provide:

```json
{
  "status": "pending|processing|completed|failed",
  "message": "technical error or informational detail",
  "started_at": "ISO timestamp or null",
  "completed_at": "ISO timestamp or null",
  "processing_time": 12.3
}
```

The Laravel UI should not assemble this ad hoc from multiple inconsistent payloads. The normalized contract must come from the service layer.

---

## Out Of Scope

- full redesign of all Filament document resources
- custom charts or heavy analytics widgets
- container-wide raw log streaming
- replacing Filament with a bespoke frontend

---

## Success Criteria

The UX is successful when:

1. `Status prüfen` reveals materially more than the string `processing`.
2. A user can open a document and immediately understand its stage progression.
3. The pipeline page clearly shows live grouped activity across documents.
4. Failed stages show actionable technical causes.
5. Successful stages remain visible so the UI feels trustworthy, not opaque.
