# ADR-004: Part Warranty Analysis Strategy

**Status:** Proposed
**Date:** 2026-06-02
**Owner:** Predictive Maintenance Team

---

## Context

Manufacturers specify nominal lifespans for spare parts (e.g., drum = 500,000 pages, fuser = 200,000 pages). However, field data shows that many parts fail significantly earlier than these specifications suggest. The company calculates maintenance intervals and warranty obligations based on manufacturer claims, but actual part failures often occur within warranty windows (typically 1 year), resulting in:

1. Unexpected warranty repair costs
2. Lower actual part lifespans driving more frequent replacements
3. Discrepancies that can be leveraged in manufacturer negotiations

**Current state:** 180 test service tickets in `krai_pm.service_tickets` with `replaced_part_categories` and `completed_date`. Nominal lifespans available in `krai_pm.part_lifetimes` (sourced from manufacturer datasheets).

**Future state:** When Docuware/Radix integration is available, `actual_runtime_pages` will be populated from device page counters, enabling precise calculation of `mismatch_ratio` (actual/nominal).

---

## Decision

Implement **event-driven part warranty tracking** with the following architecture:

### 1. Schema: `krai_pm.part_warranty_events`

Track each part replacement as a discrete event linked to the service ticket:

```sql
CREATE TABLE krai_pm.part_warranty_events (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(255) REFERENCES krai_pm.service_tickets(id),
    manufacturer_id UUID REFERENCES krai_core.manufacturers(id),
    part_category VARCHAR(50),                    -- drum, fuser, toner, etc.
    failure_date TIMESTAMP,                       -- When part failed (=completed_date)
    warranty_expiry_date TIMESTAMP,               -- failure_date + warranty_days (365)
    is_in_warranty BOOLEAN,                       -- Did failure occur before expiry?
    nominal_lifetime_pages INTEGER,               -- From part_lifetimes
    actual_runtime_pages INTEGER,                 -- Placeholder: Docuware/Radix
    mismatch_ratio DECIMAL(10,4),                 -- actual/nominal (< 1.0 = early failure)
    estimated_repair_cost_eur DECIMAL(10,2),
    warranty_status VARCHAR(50),                  -- unchecked, submitted, accepted, rejected
    metadata JSONB,                               -- Extensibility
    created_at TIMESTAMP
);
```

### 2. Analysis View: `krai_pm.vw_warranty_analysis`

Aggregate metrics by manufacturer + part_category:

```sql
CREATE VIEW krai_pm.vw_warranty_analysis AS
SELECT
    m.name AS manufacturer_name,
    pwe.part_category,
    COUNT(*) AS total_replacements,
    COUNT(*) FILTER (WHERE is_in_warranty) AS warranty_eligible_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_in_warranty)
          / NULLIF(COUNT(*), 0), 2) AS warranty_rate_pct,
    AVG(nominal_lifetime_pages)::INT AS avg_nominal_lifetime,
    AVG(actual_runtime_pages)::INT AS avg_actual_runtime,
    ROUND(AVG(mismatch_ratio)::NUMERIC, 4) AS avg_mismatch_ratio,
    ROUND(SUM(estimated_repair_cost_eur)::NUMERIC, 2) AS total_repair_cost_eur
FROM krai_pm.part_warranty_events pwe
JOIN krai_core.manufacturers m ON pwe.manufacturer_id = m.id
GROUP BY m.name, pwe.part_category;
```

### 3. Service Classes

**PartReliabilityAnalyzer:**
- `analyze_by_manufacturer(mfr_name)` → List[PartReliabilityMetrics]
- `analyze_all()` → WarrantyAnalysisSummary
- `compute_replacement_frequency(mfr, category)` → Dict (replacement count, frequency, lifetime stats)
- `classify_risk(warranty_rate_pct)` → str ("critical", "high", "medium", "low")

**WarrantyTracker:**
- `register_ticket_events(ticket_id)` → int (count of events registered)
- `run_batch_registration(limit)` → Dict (registered, skipped, errors)
- `get_summary()` → Dict (total_events, warranty_eligible, avg_warranty_rate_pct)

---

## Placeholder Pattern: `actual_runtime_pages`

Until Docuware/Radix integration is available, `actual_runtime_pages` remains `NULL`. This follows the same pattern as `device_age_months` in Feature Engineering:

1. **Test Phase (now):** Features and metrics compute correctly with NULL placeholders
2. **Integration Phase:** When Docuware/Radix data arrives, a simple UPDATE populates the column
3. **No refactoring needed:** PartReliabilityAnalyzer already handles NULL values gracefully

```python
actual_avg_runtime_pages: float | None = Field(None, ge=0)
mismatch_ratio: float | None = Field(None, ge=0.0)
```

Consumers can display "Data unavailable until device page counts integrated" without changing logic.

---

## Risk Thresholds

Warranty event rate (events within warranty window / total replacements):

| Rate | Risk Level | Action |
|------|------------|--------|
| > 50% | **critical** | Immediate manufacturer escalation required |
| > 30% | **high** | Monitor closely, escalate if trend continues |
| > 15% | **medium** | Track for next contract negotiation |
| ≤ 15% | **low** | Acceptable alignment with supplier |

---

## Alternatives Considered

### 1. No event tracking (baseline)
Only aggregate failures in a view without individual events. **Rejected:** Loses granularity needed for litigation/audits.

### 2. Simpler schema (part_failures table with one row per part type, not per ticket)
Aggregate at ingest time. **Rejected:** Loses ticket traceability needed for audits.

### 3. Direct calculation in FeatureEngineer
Include warranty metrics as features for ML model. **Rejected:** Warranty analysis is independent of prediction; mixes concerns.

---

## Consequences

### Positive
1. **Quantifiable business impact:** Warranty rates by manufacturer provide leverage in contract renegotiations
2. **Audit trail:** Each event linked to specific ticket, repairable, and date
3. **Extensible:** metadata JSONB allows future enrichment (claim status, adjuster notes, etc.)
4. **Future-proof:** `actual_runtime_pages` placeholder requires no refactor when Docuware arrives

### Negative
1. **Placeholder dependency:** Mismatch_ratio is NULL until Docuware integration
2. **Latency:** Events only registered when tickets complete; historical backfill may be needed for older data
3. **Estimated costs:** `estimated_repair_cost_eur` is a placeholder calculation

---

## Implementation Notes

### Migration 037: Schema + Bug Fix
- Creates `part_warranty_events` table with indexes
- Creates `vw_warranty_analysis` view
- **Critical:** Fixes `predictions.metadata JSONB` bug (migration 037, line 5-6)
  - `prediction_service.py` already references `metadata` field but column never existed
  - Would cause PostgreSQL errors at runtime without this fix

### Batch Registration
- `WarrantyTracker.run_batch_registration()` processes tickets without existing events
- Idempotent: re-running same batch does not duplicate events (ON CONFLICT DO NOTHING)
- Supports `limit` parameter for incremental processing

### Test Coverage
- 7 PartReliabilityAnalyzer unit tests (analyze_by_manufacturer, analyze_all, compute_replacement_frequency, classify_risk)
- 6 WarrantyTracker unit tests (register_ticket_events, batch registration, idempotency, summary)

---

## Future Work (Category B+)

1. **Docuware/Radix integration:** Populate `actual_runtime_pages` from device page counters
2. **Cross-manufacturer models:** Train separate classifiers per manufacturer (Sprint 2.11)
3. **Automated escalation:** Queue alerts when warranty_rate_pct exceeds thresholds
4. **Dashboard visualization:** Timeline of warranty events by manufacturer + part category
5. **Legal workflow:** Integration with claim submission system for warranty_status tracking

---

## References

- Migration 037: `database/migrations_postgresql/037_part_warranty_events.sql`
- Backend: `backend/pm/models/part_reliability_analyzer.py`, `backend/pm/services/warranty_tracker.py`
- Models: `backend/pm/models/ticket.py` (PartReliabilityMetrics, WarrantyAnalysisSummary)
- Tests: 13 unit tests (7 analyzer + 6 tracker)
- Related ADRs: ADR-001 (PM schema), ADR-002 (pseudonymization), ADR-003 (long-tail classification)
