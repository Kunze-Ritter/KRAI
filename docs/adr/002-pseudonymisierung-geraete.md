# ADR-002: SHA-256-Pseudonymisierung von Geräte-Seriennummern

**Status:** Accepted

**Date:** 2026-05-19

**Deciders:** PM Sprint 1 Team

---

## Problem Statement

How should device serial numbers be handled in the predictive maintenance system? Should they be:
1. Stored in plaintext and protected only by database access controls?
2. Stored as one-way hashes with a mapping table for reversal?
3. Encrypted reversibly and stored with key material?

Device serial numbers are sensitive operational data that link devices to specific customers, locations, and failure patterns.

## Decision

Implement **SHA-256-based pseudonymization** with a cryptographically secure mapping table in `krai_pm.entity_mapping`:

```sql
-- Stored in service_tickets
device_serial_hash = SHA-256(device_serial_number)

-- Stored in entity_mapping (zugriffsbeschränkt)
entity_mapping: device_serial_hash -> HMAC-SHA256(device_serial_number, secret_key)
```

## Rationale

### 1. **Compliance and Data Protection**

- Device serial numbers identify specific devices owned by specific customers → personally identifiable information (PII) under GDPR
- One-way hashing ensures device-level analytics cannot accidentally expose individual customer identities to unauthorized users
- Mapping table is "zugriffsbeschränkt" (restricted access) and audited separately

### 2. **Operational Anonymity with Recovery Path**

- PM analysts can aggregate failure rates *by device model* without seeing which customers experienced failures
- Authorized staff (customer success, support) can reverse-map hashes to contact affected customers
- Audit trail shows who accessed the mapping table and when

### 3. **Cross-Organization Safety**

- Kunze-Ritter can share anonymized failure telemetry with OEMs (Konica Minolta, HP, Ricoh) without revealing customer identities
- OEMs can identify device model trends without customer data exposure
- Competitive risk is eliminated: a Kunze-Ritter salesperson cannot use failure data to target competitors' customers

### 4. **Scalability to Third-party Integrations**

- When device telemetry eventually comes from Docuform or Radix (future sprints), those systems will provide their own device identifiers
- SHA-256 hash can be seeded with provider-specific salts (e.g., SHA-256(docuform_device_id + provider_salt))
- Single mapping table can ingest identifiers from multiple sources

### 5. **Predictive Model Integrity**

- Models trained on anonymized device hashes are more likely to generalize across customer bases
- Prevents overfitting to specific customer environments or locations
- If models are shared with OEMs or partners, they never see raw customer data

## Alternatives Considered

### A1: Plaintext Storage with Database Access Control

**Pros:**
- Simpler queries (no JOIN to mapping table)
- Easier debugging during development

**Cons:**
- Violates GDPR privacy-by-design principle
- Single database breach exposes customer device data
- Cannot safely share anonymized telemetry with OEMs
- Insider threats: anyone with SELECT permission sees customer identities

### A2: AES-256 Reversible Encryption

**Pros:**
- Reversible (can recover original serial number for direct customer contact)

**Cons:**
- Key management complexity: where is the encryption key stored?
- Performance overhead on every query (decrypt → filter → encrypt → return)
- All users who can query PM data can potentially access the key
- Not truly anonymized: only obfuscated

### A3: Customer ID Lookup Instead of Device Serial

**Pros:**
- Customer ID is non-sensitive
- Already exists in Kunze-Ritter systems

**Cons:**
- Fails when device telemetry comes from OEM directly (no customer ID context)
- Cannot federate to multi-OEM scenarios
- Future device data from Docuform/Radix will not have customer ID

## Implementation

### 1. **Hash Strategy**

```python
import hashlib

def hash_device_serial(serial_number: str) -> str:
    """One-way SHA-256 hash of device serial."""
    return hashlib.sha256(serial_number.encode()).hexdigest()
```

- Hash is deterministic: same serial number always produces same hash
- Hash is uniform: no correlation between serial and hash (unlike simple checksums)
- Collision resistance: SHA-256 has 2^256 possible outputs (negligible collision risk in practice)

### 2. **Mapping Table (krai_pm.entity_mapping)**

```sql
CREATE TABLE krai_pm.entity_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_serial_hash CHAR(64) NOT NULL UNIQUE,
    encrypted_serial BYTEA NOT NULL,  -- AES-256-GCM encrypted
    provider VARCHAR(50) NOT NULL,     -- 'docuform', 'radix', 'km_service', etc.
    provider_device_id VARCHAR(255),   -- Original ID from provider
    created_at TIMESTAMP DEFAULT NOW(),
    last_accessed_at TIMESTAMP,
    access_log_id UUID,
    CONSTRAINT unique_provider_id UNIQUE (provider, provider_device_id)
);
```

- `encrypted_serial`: AES-256-GCM encrypted for rare reversal scenarios (customer contact, disputes)
- `access_log_id`: Links to audit log (zugriffsbeschränkt)
- Key material for decryption stored in secure vault (AWS Secrets Manager, HashiCorp Vault), not in database

### 3. **Audit Trail**

```sql
CREATE TABLE krai_pm.entity_mapping_access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_id UUID NOT NULL REFERENCES krai_pm.entity_mapping(id),
    accessed_by VARCHAR(255) NOT NULL,  -- User ID or service principal
    accessed_at TIMESTAMP DEFAULT NOW(),
    operation VARCHAR(50),  -- 'lookup', 'export', etc.
    reason VARCHAR(500),
    ip_address INET,
    CONSTRAINT immutable UNIQUE (mapping_id, accessed_at, accessed_by)
);
```

- Every access to the mapping table is logged
- Compliance team periodically reviews logs for unusual patterns

### 4. **Usage in Analytics**

```sql
-- PM analysts can see failure patterns WITHOUT customer identity
SELECT
    device_serial_hash,  -- Only the hash
    COUNT(*) as failure_count,
    device_lifecycle.model_family,
    device_lifecycle.counter_pages
FROM krai_pm.service_tickets
JOIN krai_pm.device_lifecycle USING (device_serial_hash)
GROUP BY device_serial_hash, model_family
ORDER BY failure_count DESC;

-- Customer success can reverse-map only when authorized
SELECT
    st.device_serial_hash,
    entity_mapping.encrypted_serial,  -- Must decrypt with vault key
    COUNT(*) as recent_failures
FROM krai_pm.service_tickets st
JOIN krai_pm.entity_mapping USING (device_serial_hash)
WHERE st.created_at_source > NOW() - INTERVAL '30 days'
GROUP BY st.device_serial_hash
-- Decrypt happens in application layer with proper audit logging
```

## Consequences

### Positive

- GDPR compliant by design: device serial numbers are pseudonymized by default
- Safe to share failure telemetry with OEMs and partners
- Prevents accidental exposure of customer device identities
- Clear audit trail for regulatory compliance
- Supports future multi-provider device data federation

### Negative

- Additional table join for any customer-facing query that needs the original serial
- Key management complexity: encryption key must be secured separately
- Small performance overhead for hash computation (negligible for current scale)
- Data reversal is intentionally difficult (requires vault access + audit approval)

## Related Decisions

- **ADR-001**: Dedicated `krai_pm` schema houses `entity_mapping` with restricted access controls
- Pseudonymization applies only to device serial numbers; other device metadata (model, manufacturer) remains plaintext
- Integration with Docuform and Radix (future) will extend this mapping table to support provider-specific device IDs

## Future Enhancements

- Explore differential privacy for aggregate statistics before sharing with OEMs
- Implement automatic key rotation (recommend annual or per compliance requirement)
- Add PII detection system to flag any sensitive data that accidentally makes it into PM tables
