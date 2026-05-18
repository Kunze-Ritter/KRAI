# ADR-001: Eigenes PM-Schema in PostgreSQL vs. Integration in krai_intelligence

**Status:** Accepted

**Date:** 2026-05-19

**Deciders:** PM Sprint 1 Team

---

## Problem Statement

Should predictive maintenance data be stored in a dedicated `krai_pm` schema or integrated into the existing `krai_intelligence` schema alongside documents and chunks?

## Decision

Create a **dedicated `krai_pm` schema** separate from `krai_intelligence`.

## Rationale

### 1. **Semantic Separation of Concerns**

- **krai_intelligence** is fundamentally document-centric: chunks, embeddings, and error codes are all extracted *from* service manuals and technical documentation
- **krai_pm** is device-centric: focused on operational metrics, lifecycle data, and device health tracking
- These represent two distinct semantic domains that happen to share some entities (e.g., error codes)

### 2. **Lifecycle Management**

- Intelligence data is ephemeral: chunks can be regenerated from documents, embeddings refreshed on model updates
- PM data is operational and long-lived: device lifecycle records are immutable once created, predictions accumulate over time
- Separate schemas allow independent retention policies and archival strategies

### 3. **Access Control and Compliance**

- Device serial numbers and operational metrics may be subject to different compliance rules than document content (e.g., GDPR, ISO 27001)
- Pseudonymization in `krai_pm.entity_mapping` is mandatory; document-level PII is handled differently
- Separate schema simplifies audit trails and access logging

### 4. **Query Performance**

- PM queries (time-series aggregations, device-cohort analysis) have different patterns than document-chunk queries
- Dedicated indexes (HNSW on ticket embeddings, composite on device lifecycle) can be optimized for PM workloads without interfering with document retrieval
- Future partitioning (e.g., by month or device model) is cleaner in isolation

### 5. **Data Lineage Clarity**

- PM data flows from **two independent sources**: service manuals (→ error codes) and operational systems (→ device metrics, parts usage)
- Keeping PM data separate makes this dual-source architecture explicit in the schema structure
- Easier to trace which predictions depend on which data sources

### 6. **Scalability Path**

- PM will eventually federate data from multiple OEMs and verticals (printers, copiers, MFPs, etc.)
- Dedicated schema allows multi-tenancy patterns (e.g., `krai_pm_kunze`, `krai_pm_ritter_custom`)
- Document schema remains single-tenant and focused on content retrieval

## Alternatives Considered

### A1: Integrate into krai_intelligence

**Pros:**
- Shared embedding infrastructure (both domains use vectors)
- Single schema to manage

**Cons:**
- Conflates document content with device operations
- Operational queries become cumbersome (filtering out chunks)
- Compliance complexity: mixing immutable device records with ephemeral document data
- Constraints become unclear: why would an error code belong to both a chunk *and* a device?

### A2: Create krai_pm but share core tables with krai_intelligence

**Pros:**
- Avoids duplication of error code table

**Cons:**
- Foreign key relationships become awkward (krai_pm.tickets → krai_intelligence.error_codes)
- Schema semantics are muddled: is error_codes document-centric or device-centric?
- Harder to version schemas independently

## Implementation

- **krai_pm schema** contains: `service_tickets`, `part_lifetimes`, `device_lifecycle`, `predictions`, `entity_mapping`
- **krai_intelligence schema** remains unchanged and continues to host: `chunks`, `error_codes`, `solutions`, `embeddings_v2`
- Cross-schema joins allowed where necessary (e.g., enriching PM error codes from intelligence error_codes table)

## Consequences

### Positive

- Clear, maintainable schema structure that reflects the business domain
- Easier to implement compliance controls and data retention policies
- PM team has autonomy over schema evolution without affecting document pipeline
- Supports future multi-tenant deployment patterns

### Negative

- Potential duplication of error code metadata (though `krai_intelligence.error_codes` remains the source of truth)
- Slightly more complex SQL for cross-domain queries (explicit JOIN across schemas)
- Team must manage two migration tracks instead of one

## Related Decisions

- **ADR-002**: Device serial number pseudonymization is mandatory in `krai_pm.entity_mapping` precisely because PM data is operational and long-lived
