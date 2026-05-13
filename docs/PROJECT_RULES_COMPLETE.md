---
trigger: always_on
---

# KRAI Project Rules

**This document contains CRITICAL project rules that MUST be followed at all times.**

---

## 📋 TODO Management (CRITICAL!)

**Bei JEDER Änderung am Code oder System MUSS TODO.md aktualisiert werden!**

### 1. Erledigte Tasks markieren

Format:
```markdown
- [x] **Task Name** ✅ (HH:MM)
  - Details was gemacht wurde
  - **File:** path/to/file.py
  - **Result:** Was wurde erreicht
```

Beispiel:
```markdown
- [x] **OEM Sync Reactivated** ✅ (08:37)
  - Fixed: OEM sync was disabled (TEMPORARY WORKAROUND comment)
  - Changed: Use `schema('krai_core').table('products')` instead of vw_products
  - **File:** `backend/utils/oem_sync.py`
  - **Result:** OEM info will now be saved!
```

### 2. Neue TODOs hinzufügen

Format:
```markdown
- [ ] **Task Name** 🔥 HIGH PRIORITY
  - **Task:** Was muss gemacht werden
  - **Example:** Konkretes Beispiel
  - **Implementation:** Code-Snippet oder Pseudo-Code
  - **Files to modify:** Liste der Dateien
  - **Priority:** HIGH/MEDIUM/LOW
  - **Effort:** X hours
  - **Status:** TODO
```

Beispiel:
```markdown
- [ ] **Agent Search with OEM Integration** 🔥 HIGH PRIORITY
  - **Task:** Expand search to include OEM manufacturers
  - **Example:** User searches "Lexmark CS920 error 900.01"
    - Also search: Konica Minolta (CS920 = Konica Engine!)
  - **Files to modify:**
    - `backend/api/agent_api.py`
    - `backend/api/search_api.py`
  - **Priority:** HIGH
  - **Effort:** 2-3 hours
  - **Status:** TODO
```

### 3. Priority Emojis

- 🔥 **HIGH PRIORITY** - Kritisch, muss bald gemacht werden
- 🔍 **MEDIUM PRIORITY** - Wichtig, aber nicht dringend
- 📌 **LOW PRIORITY** - Nice to have

### 4. Session Statistics aktualisieren

Am Ende jeder Session:
```markdown
### 📊 Session Statistics (YYYY-MM-DD)

**Time:** HH:MM-HH:MM (X minutes/hours)
**Commits:** X+ commits
**Files Changed:** X+ files
**Migrations Created:** X (numbers)
**Bugs Fixed:** X (list)
**Features Added:** X (list)

**Key Achievements:**
1. ✅ Achievement 1
2. ✅ Achievement 2
3. ✅ Achievement 3

**Next Focus:** What to do next 🎯
```

### 5. Mehrere TODO-Dateien

Checke und synchronisiere:
- `TODO.md` - Haupt-TODO (IMMER aktualisieren!)
- `TODO_PRODUCT_ACCESSORIES.md` - Accessory System
- `AGENT_TODO.md` - Agent Features
- `DB_FIXES_CHECKLIST.md` - Database Fixes

Bei größeren Features: Wichtigste TODOs in TODO.md zusammenfassen mit Referenz!

### 6. Last Updated Timestamp

IMMER am Ende von TODO.md aktualisieren:

```markdown
**Last Updated:** YYYY-MM-DD (HH:MM)
**Current Focus:** Was gerade gemacht wird
**Next Session:** Was als nächstes kommt
```

---

## 🗄️ Database Schema (CRITICAL!)

**IMMER DATABASE_SCHEMA.md als Referenz nutzen!**

Die Datei `DATABASE_SCHEMA.md` im Root-Verzeichnis (`c:\Users\haast\Docker\KRAI-minimal\DATABASE_SCHEMA.md`) enthält die ECHTE, aktuelle Datenbankstruktur direkt aus PostgreSQL.

### Regeln

1. **IMMER** `DATABASE_SCHEMA.md` lesen bevor du Annahmen über Tabellen/Spalten machst
2. **NIEMALS** raten welche Spalten existieren - IMMER in der Doku nachsehen
3. **NIEMALS** annehmen dass Tabellen in bestimmten Schemas sind - IMMER prüfen

### Bei DB-Änderungen

1. Änderungen in PostgreSQL durchführen (via pgAdmin, DBeaver, oder SQL-Script)

2. Neue CSV exportieren:

   ```sql
   SELECT table_schema, table_name, column_name, data_type,
          character_maximum_length, is_nullable, column_default, udt_name
   FROM information_schema.columns
   WHERE table_schema LIKE 'krai_%'
   ORDER BY table_schema, table_name, ordinal_position;
   ```

3. CSV als "PostgreSQL_Columns.csv" im Root speichern

4. Script ausführen: `cd scripts && python generate_db_doc_from_csv.py`

5. Neue DATABASE_SCHEMA.md committen

### Wichtige Fakten

**Embeddings:**

- Embeddings sind IN `krai_intelligence.chunks` (Spalte: `embedding`, Typ: `vector(768)`)
- Es gibt KEIN separates `krai_embeddings` Schema
- View: `public.vw_embeddings` ist ein ALIAS für `public.vw_chunks`

**Schemas:**

- `krai_content` - Images, Links, Videos, Print Defects, Tables (5 Tabellen)
- `krai_core` - Documents, Products, Manufacturers, Series (11 Tabellen)
- `krai_intelligence` - Chunks, Error Codes, Solutions (13 Tabellen)
- `krai_parts` - Parts Catalog, Accessories (2 Tabellen)
- `krai_system` - System-Tabellen (5 Tabellen)
- `krai_users` - User-Tabellen (2 Tabellen)

**Views:**

- Alle Views nutzen `vw_` Prefix und sind im `public` Schema
- Views werden automatisch via Migration `002_views.sql` erstellt

**Wichtige Tabellen:**

- `krai_core.products` - Hat Spalten: `specifications`, `urls`, `metadata` (alle JSONB)
- `krai_core.manufacturers` - Hersteller (z.B. "Hewlett Packard", "Brother", "Canon")
- `krai_core.product_accessories` - Zubehör-Beziehungen
- `krai_core.oem_relationships` - OEM-Beziehungen zwischen Herstellern
- `krai_intelligence.chunks` - Text-Chunks mit `embedding` Spalte
- `krai_parts.parts_catalog` - Ersatzteile

**Datei-Pfad:** `c:\Users\haast\Docker\KRAI-minimal\DATABASE_SCHEMA.md`
**Update-Script:** `scripts/generate_db_doc_from_csv.py`

---

## 🏭 Manufacturer Name Mapping (CRITICAL!)

**Problem:** Verschiedene Namen für denselben Hersteller!

### Mapping Rules

**IMMER** diese Mappings verwenden:

- `HP Inc.` → `Hewlett Packard` (DB-Name)
- `HP` → `Hewlett Packard`
- `Hewlett-Packard` → `Hewlett Packard`
- `Brother Industries` → `Brother`
- `Konica Minolta Business Solutions` → `Konica Minolta`

### Implementation

1. **In `ManufacturerVerificationService`:**
   - `manufacturer_name_mapping` Dictionary nutzen
   - Mapping in `discover_product_page()` anwenden

2. **In `ClassificationProcessor`:**
   - Erkannten Manufacturer-Namen mappen bevor DB-Lookup

3. **Bei neuen Herstellern:**
   - Zuerst in `krai_core.manufacturers` checken welcher Name in DB ist
   - Mapping hinzufügen falls nötig

**Beispiel:**
```python
manufacturer_name_mapping = {
    'HP Inc.': 'Hewlett Packard',
    'HP': 'Hewlett Packard',
}

# Apply mapping
if manufacturer in manufacturer_name_mapping:
    manufacturer = manufacturer_name_mapping[manufacturer]
```

---

## 🔍 Product Discovery Integration

**Automatische Product Page Discovery nach Classification**

### Wann wird Product Discovery ausgeführt

1. **Automatisch nach Classification:**
   - Wenn `manufacturer_verification_service` vorhanden
   - Wenn Manufacturer erkannt wurde
   - Wenn Models extrahiert werden konnten

2. **Model-Extraktion:**
   - Aus Context (wenn vorhanden)
   - Aus Filename via Regex-Patterns
   - Patterns: `E877`, `M454dn`, `HL-L8360CDW`, etc.

### save_to_db Parameter

**IMMER `save_to_db=True` in Production:**

- In `ClassificationProcessor.process()`
- In Pipeline-Integration

**`save_to_db=False` nur für:**

- Unit Tests
- Debugging
- Lokale Entwicklung mit Schema-Mismatch

### Discovery Strategies (in Reihenfolge)

1. **URL Patterns** - Schnell, zuverlässig
2. **Perplexity AI** - KI-basiert mit Citations (95% Confidence)
3. **Google Custom Search API** - Falls konfiguriert
4. **Web Scraping** - Fallback

### Logging

```python
self.logger.info(f"🔍 Starting product discovery for {len(models)} model(s)")
self.logger.info(f"   Discovering: {manufacturer} {model}")
self.logger.success(f"   ✅ Found: {result['url']}")
self.logger.warning(f"   ⚠️  No product page found for {model}")
```

### Return Format

```python
{
    'model': 'E877',
    'url': 'https://support.hp.com/...',
    'confidence': 0.95,
    'product_id': 'uuid'  # Wenn saved to DB
}
```

---

## 🔧 Code Style & Best Practices

### 1. Immer minimal & focused edits

- Nutze `edit` oder `multi_edit` tools
- Halte Änderungen klein und fokussiert
- Folge existierendem Code-Style

### 2. Keine Code-Ausgabe an User

- **NIEMALS** Code im Chat ausgeben (außer explizit angefragt)
- Stattdessen: Code-Edit-Tools nutzen
- User sieht Änderungen direkt in IDE

### 3. Imports immer am Anfang

- Imports MÜSSEN am Anfang der Datei sein
- Bei Edits: Separater Edit für Imports
- Niemals Imports in der Mitte des Codes

### 4. Runnable Code

- Code MUSS sofort lauffähig sein
- Alle Dependencies hinzufügen
- Alle Imports hinzufügen
- Bei Web Apps: Laravel/Filament (existing dashboard)

---

## 🐛 Debugging Discipline

### 1. Root Cause First

- Adressiere die Ursache, nicht die Symptome
- Verstehe das Problem bevor du fixst

### 2. Logging hinzufügen

- Descriptive logging statements
- Error messages mit Context
- Track variable states

### 3. Tests hinzufügen

- Test functions um Problem zu isolieren
- Reproduzierbare Test Cases

### 4. Nur fixen wenn sicher

- Nur Code ändern wenn du die Lösung kennst
- Sonst: Debug-Logging hinzufügen und testen

---

## 📝 Documentation

### 1. Code Comments

- Erkläre WARUM, nicht WAS
- Komplexe Logik dokumentieren
- TODOs mit Context

### 2. Commit Messages

- Beschreibend und präzise
- Format: `[Component] What was changed`
- Beispiel: `[OEM] Reactivate OEM sync - fix PostgREST cache issue`

### 3. Migration Comments

- Jede Migration braucht klaren Comment
- Erkläre WARUM die Änderung nötig ist
- Beispiel: `-- Remove content_text (1.17 MB per document - wasteful!)`

---

## ⚠️ NEVER DO

1. ❌ Code im Chat ausgeben (außer explizit angefragt)
2. ❌ Raten welche DB-Spalten existieren
3. ❌ TODO.md nicht aktualisieren
4. ❌ Imports in der Mitte des Codes
5. ❌ Ungetesteten Code als "funktioniert" markieren
6. ❌ Große Edits (>300 lines) - aufteilen!
7. ❌ Tests löschen oder schwächen ohne Erlaubnis
8. ❌ Implement custom retry logic (use BaseProcessor.safe_process())
9. ❌ Send emails/Slack directly (use AlertService)
10. ❌ Run benchmarks in production
11. ❌ Process without idempotency checks
12. ❌ Acquire locks without try-finally
13. ❌ Log without correlation IDs
14. ❌ Retry permanent errors (HTTP 4xx)
15. ❌ Hardcode retry policies in code
16. ❌ Use time.sleep() for retry delays
17. ❌ Catch generic exceptions without re-raising
18. ❌ Insert data without checking completion markers

---

## ✅ ALWAYS DO

1. ✅ TODO.md nach jeder Änderung aktualisieren inkl. timestamp
2. ✅ DATABASE_SCHEMA.md checken vor DB-Queries
3. ✅ Code-Edit-Tools nutzen statt Output
4. ✅ Minimal & focused edits
5. ✅ Tests hinzufügen für neue Features
6. ✅ Logging für Debugging
7. ✅ Session Statistics aktualisieren
8. ✅ Use `BaseProcessor.safe_process()` for all processing
9. ✅ Check `stage_completion_markers` before processing
10. ✅ Generate correlation IDs in format `req_{uuid}.stage_{name}.retry_{n}`
11. ✅ Use PostgreSQL advisory locks in try-finally blocks
12. ✅ Queue alerts via `AlertService.queue_alert()`
13. ✅ Run benchmarks in staging environment only
14. ✅ Classify errors as transient or permanent
15. ✅ Set completion markers after successful processing
16. ✅ Include correlation_id in ALL log entries
17. ✅ Compute data hash for idempotency checks
18. ✅ Release advisory locks in finally blocks

---

## 🧪 Testing & Quality Assurance

### 1. Test-Typen

**Unit Tests:**
- Einzelne Funktionen/Methoden testen
- Mocks für externe Dependencies
- Schnell und isoliert

**Integration Tests:**
- Mehrere Komponenten zusammen testen
- Echte DB-Verbindung (Test-DB)
- Pipeline-Stages testen

**End-to-End Tests:**
- Komplette Pipeline mit echten Dokumenten
- Alle Services integriert
- Längere Laufzeit

### 2. Test-Dateien Naming

- `test_*.py` - Unit/Integration Tests
- `test_*_integration.py` - Explizite Integration Tests
- `test_*_e2e.py` - End-to-End Tests
- `check_*.py` - Verification Scripts (keine echten Tests)

### 3. Test-Daten

**Kleine Test-Dokumente:**

- `Brother_HL-L8360CDW_UM_ENG.pdf` (~50 Seiten)
- Schnelle Tests

**Große Test-Dokumente:**

- `HP_E877_CPMD.pdf` (1116 Seiten)
- Performance Tests
- Vollständige Pipeline-Tests

### 4. Assertions

```python
# Good
assert result.success, f"Expected success but got: {result.message}"
assert len(products) > 0, "No products found"

# Bad
assert result.success  # Keine Info bei Fehler
```

### 5. Test-Isolation

- Jeder Test muss unabhängig laufen
- Setup/Teardown für DB-Änderungen
- Keine Abhängigkeiten zwischen Tests

---

## 🚀 Deployment & Production

### 1. Environment Variables

**IMMER** `.env` Datei nutzen:
```bash
POSTGRES_URL=postgresql://...
PERPLEXITY_API_KEY=...
GOOGLE_API_KEY=...
OLLAMA_HOST=http://localhost:11434
```

### 2. Database Migrations

**Reihenfolge:**

1. `001_schema.sql` - Schemas und Tabellen
2. `002_views.sql` - Views erstellen
3. `003_indexes.sql` - Indexes und Performance

**Location:** `database/migrations_postgresql/`

### 3. Production Checklist

- [ ] Alle Environment Variables gesetzt
- [ ] PostgreSQL 15+ mit pgvector Extension
- [ ] Ollama mit Embedding Models
- [ ] MinIO für Object Storage
- [ ] Redis für Caching
- [ ] Backup Strategy aktiv

---

## 🔄 Error Handling & Retry Architecture (FUTURE WORK)

**⚠️ IMPORTANT: The features documented in this section are PLANNED but NOT YET IMPLEMENTED!**

**Current State:**
- `BaseProcessor.safe_process()` provides basic error handling and logging
- No automatic retry logic implemented
- No idempotency checks via completion markers
- No advisory lock management
- No correlation ID propagation
- No alert service integration

**When implementing these features, remove the "FUTURE WORK" marker and update this section with actual usage examples.**

---

### Rule 1: ALWAYS use BaseProcessor.safe_process()

**NEVER implement custom retry logic in processors!**

All retry logic is centralized in `BaseProcessor.safe_process()` method. This ensures:
- Consistent error handling across all processors
- Centralized retry orchestration
- Proper correlation ID tracking
- Idempotency checks
- Advisory lock management

**✅ CORRECT:**
```python
class MyProcessor(BaseProcessor):
    def process(self, context: ProcessingContext) -> ProcessingResult:
        # Your processing logic here
        # No try/except needed - safe_process() handles it
        result = self.do_work(context)
        return ProcessingResult(success=True, data=result)
```

**❌ WRONG:**
```python
class MyProcessor(BaseProcessor):
    def process(self, context: ProcessingContext) -> ProcessingResult:
        # NEVER implement custom retry loops!
        for attempt in range(3):
            try:
                result = self.do_work(context)
                return ProcessingResult(success=True, data=result)
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)  # ❌ WRONG!
                    continue
                raise
```

---

### Rule 2: Error Classification

**Errors MUST be classified as transient or permanent!**

Use `ErrorClassifier` to determine retry behavior:

**Transient Errors (WILL be retried):**
- HTTP 5xx (500, 502, 503, 504)
- `ConnectionError`, `TimeoutError`
- `requests.exceptions.Timeout`
- `requests.exceptions.ConnectionError`
- Database connection errors
- Rate limit errors (429)

**Permanent Errors (NO retry):**
- HTTP 4xx (400, 401, 403, 404)
- `ValidationError`
- `AuthenticationError`
- `PermissionError`
- Malformed input data
- Missing required fields

**✅ CORRECT:**
```python
from backend.core.error_classifier import ErrorClassifier

classifier = ErrorClassifier()

try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    error_type = classifier.classify(e)
    if error_type == "transient":
        # Will be retried by safe_process()
        raise ProcessingError(f"Transient HTTP error: {e}", processor_name=self.name)
    else:
        # Permanent error - no retry
        raise ProcessingError(f"Permanent HTTP error: {e}", processor_name=self.name)
```

**❌ WRONG:**
```python
try:
    response = requests.get(url)
except Exception as e:
    # ❌ WRONG: No error classification!
    # ❌ WRONG: Catching all exceptions!
    raise ProcessingError(str(e))
```

---

### Rule 3: Exception Handling

**ALWAYS raise `ProcessingError` with descriptive messages!**

**✅ CORRECT:**
```python
from backend.processors.exceptions import ProcessingError

try:
    result = external_api.call(data)
except requests.exceptions.Timeout as e:
    raise ProcessingError(
        f"API timeout after 30s for document {context.document_id}",
        processor_name=self.name,
        original_exception=e
    )
except ValueError as e:
    raise ProcessingError(
        f"Invalid data format: {e}",
        processor_name=self.name,
        original_exception=e
    )
```

**❌ WRONG:**
```python
try:
    result = external_api.call(data)
except Exception as e:
    # ❌ WRONG: Generic exception catch
    # ❌ WRONG: No processor name
    # ❌ WRONG: No context
    raise Exception(str(e))
```

---

### Rule 4: Hybrid Retry Approach

**First retry synchronous, subsequent retries asynchronous!**

- **Retry 1:** Synchronous with 1s wait (fast recovery for transient blips)
- **Retry 2+:** Asynchronous background tasks (exponential backoff: 2s, 4s, 8s)

This is handled automatically by `BaseProcessor.safe_process()` - you don't need to implement it!

**Flow:**
1. First attempt fails with transient error
2. Wait 1 second
3. Retry synchronously (attempt 2)
4. If still fails, schedule async retry with 2s delay
5. Background worker picks up retry task
6. Exponential backoff for subsequent retries

---

### Rule 5: Idempotency - Check-Before-Write Pattern

**NEVER process without checking `stage_completion_markers` first!**

**✅ CORRECT:**
```python
from backend.core.idempotency_checker import IdempotencyChecker

class MyProcessor(BaseProcessor):
    def process(self, context: ProcessingContext) -> ProcessingResult:
        checker = IdempotencyChecker(self.db_adapter)

        # Check if already processed
        is_complete, data_hash = checker.check_completion_marker(
            document_id=context.document_id,
            stage_name=self.name
        )

        if is_complete:
            # Compute current data hash
            current_hash = checker.compute_data_hash(context.data)

            if current_hash == data_hash:
                # Same data - skip processing
                self.logger.info(f"Stage {self.name} already completed with same data")
                return ProcessingResult(success=True, skipped=True)
            else:
                # Data changed - cleanup and re-process
                self.logger.info(f"Data changed - cleaning up old data")
                self.cleanup_old_data(context.document_id)

        # Process the data
        result = self.do_work(context)

        # Set completion marker
        checker.set_completion_marker(
            document_id=context.document_id,
            stage_name=self.name,
            data_hash=checker.compute_data_hash(context.data)
        )

        return ProcessingResult(success=True, data=result)
```

**❌ WRONG:**
```python
class MyProcessor(BaseProcessor):
    def process(self, context: ProcessingContext) -> ProcessingResult:
        # ❌ WRONG: No idempotency check!
        # This will create duplicate data on retries!
        result = self.do_work(context)
        return ProcessingResult(success=True, data=result)
```

**Database Table:** `krai_system.stage_completion_markers`

```sql
CREATE TABLE krai_system.stage_completion_markers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES krai_core.documents(id),
    stage_name VARCHAR(100) NOT NULL,
    completed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    data_hash VARCHAR(64) NOT NULL,  -- SHA256 hash
    metadata JSONB,
    UNIQUE(document_id, stage_name)
);
```

---

### Rule 6: Correlation ID & Tracing

**EVERY log entry MUST include correlation_id!**

**Hierarchical format:** `req_{uuid}.stage_{name}.retry_{n}`

**Examples:**
- Request ID: `req_a3f2e8d1-4b2c-4a5e-8f3d-9c1e2b3a4d5e`
- Stage ID: `req_a3f2e8d1.stage_image_processing`
- Retry ID: `req_a3f2e8d1.stage_image_processing.retry_2`

**✅ CORRECT:**
```python
def safe_process(self, context: ProcessingContext) -> ProcessingResult:
    # Generate correlation ID
    correlation_id = f"req_{context.request_id}.stage_{self.name}"
    if context.retry_attempt > 0:
        correlation_id += f".retry_{context.retry_attempt}"

    # Add to context
    context.correlation_id = correlation_id

    self.logger.info(f"[{correlation_id}] Starting {self.name} processing")
    self.logger.debug(f"[{correlation_id}] Extracted {len(chunks)} chunks")
    self.logger.error(f"[{correlation_id}] Failed to process: {error}")
```

**❌ WRONG:**
```python
# ❌ WRONG: No correlation ID
self.logger.info(f"Processing document {document_id}")
self.logger.error(f"Failed to process: {error}")
```

**Grep logs by correlation_id to trace request flow:**

```bash
# Trace entire request
grep "req_a3f2e8d1" logs/pipeline.log

# Trace specific stage
grep "req_a3f2e8d1.stage_image_processing" logs/pipeline.log

# Trace specific retry
grep "req_a3f2e8d1.stage_image_processing.retry_2" logs/pipeline.log
```

---

### Rule 7: PostgreSQL Advisory Locks

**ALWAYS use try-finally block to ensure locks are released!**

**Purpose:** Prevent concurrent retries of the same stage for the same document!

Without advisory locks:
- Retry 1 starts processing
- Retry 2 starts processing (race condition!)
- Both create duplicate data

With advisory locks:
- Retry 1 acquires lock and processes
- Retry 2 tries to acquire lock, fails, and skips (another retry in progress)

**✅ CORRECT:**
```python
def safe_process(self, context: ProcessingContext) -> ProcessingResult:
    lock_id = self.compute_lock_id(context.document_id, self.name)
    lock_acquired = False

    try:
        # Try to acquire lock (non-blocking)
        lock_acquired = self.db_adapter.execute_scalar(
            "SELECT pg_try_advisory_lock(%s)",
            (lock_id,)
        )

        if not lock_acquired:
            if context.retry_attempt > 0:
                # Another retry is in progress
                self.logger.info(f"Lock not acquired - another retry in progress")
                return ProcessingResult(success=True, skipped=True)
            else:
                # First attempt - should always get lock
                raise ProcessingError("Failed to acquire lock on first attempt")

        # Process with lock held
        result = self.process(context)
        return result

    finally:
        # ALWAYS release lock
        if lock_acquired:
            self.db_adapter.execute(
                "SELECT pg_advisory_unlock(%s)",
                (lock_id,)
            )
```

**❌ WRONG:**
```python
def safe_process(self, context: ProcessingContext) -> ProcessingResult:
    lock_id = self.compute_lock_id(context.document_id, self.name)

    # ❌ WRONG: No try-finally - lock may not be released!
    lock_acquired = self.db_adapter.execute_scalar(
        "SELECT pg_try_advisory_lock(%s)",
        (lock_id,)
    )

    result = self.process(context)

    # ❌ WRONG: If exception occurs, lock is never released!
    self.db_adapter.execute(
        "SELECT pg_advisory_unlock(%s)",
        (lock_id,)
    )

    return result
```

**Lock ID Computation:**
```python
def compute_lock_id(self, document_id: str, stage_name: str) -> int:
    """Compute PostgreSQL advisory lock ID."""
    # Combine document_id and stage_name
    lock_key = f"{document_id}:{stage_name}"

    # Hash to 32-bit integer (PostgreSQL advisory lock range)
    hash_value = int(hashlib.sha256(lock_key.encode()).hexdigest(), 16)

    # Modulo to fit in 32-bit signed integer range
    return hash_value % (2**31)
```

---

### Rule 8: Alert-Service Integration

**NEVER send emails/Slack directly from processors!**

**ALWAYS use `AlertService.queue_alert()`!**

**✅ CORRECT:**
```python
from backend.services.alert_service import AlertService

alert_service = AlertService(db_adapter)

# Queue alert - will be aggregated and sent by background worker
alert_service.queue_alert(
    alert_type="processing_error",
    severity="high",
    title=f"Processing failed for {self.name}",
    message=f"Document {document_id} failed after {retry_attempt} retries",
    metadata={
        "document_id": document_id,
        "stage_name": self.name,
        "error_message": str(error),
        "retry_attempt": retry_attempt
    }
)
```

**❌ WRONG:**
```python
import smtplib

# ❌ WRONG: Sending email directly from processor!
# This bypasses aggregation and rate limiting!
msg = f"Processing failed for {document_id}"
smtp.sendmail("alerts@example.com", ["admin@example.com"], msg)
```

**Alert Aggregation:**

Background worker processes queue every 1 minute and aggregates alerts by:
- Alert type
- Time window (5 minutes)
- Severity

**Example aggregation:**
- 10 "processing_error" alerts in 5 minutes
- Aggregated into 1 email: "10 processing errors in the last 5 minutes"

**Database Tables:**

```sql
CREATE TABLE krai_system.alert_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,  -- low, medium, high, critical
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    sent_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending'  -- pending, aggregated, sent, failed
);

CREATE TABLE krai_system.alert_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT true,
    threshold INT NOT NULL DEFAULT 1,  -- Min count to trigger alert
    time_window_minutes INT NOT NULL DEFAULT 5,
    channels JSONB NOT NULL,  -- ["email", "slack"]
    recipients JSONB NOT NULL,  -- {"email": [...], "slack": [...]}
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

### Rule 9: Performance Measurement

**NEVER run benchmarks in production!**

**Use staging environment only!**

**Why:**
- Benchmarks consume resources
- May impact production performance
- Can cause timeouts or errors
- Skews production metrics

**✅ CORRECT:**
```bash
# Run benchmarks in staging
docker-compose -f docker-compose.staging.yml up -d
python scripts/run_benchmark.py --env staging
```

**❌ WRONG:**
```bash
# ❌ WRONG: Running benchmarks in production!
python scripts/run_benchmark.py --env production
```

**Fixed test documents:**

```python
# Fixed test documents for benchmarking
BENCHMARK_DOCUMENTS = [
    "Brother_HL-L8360CDW_UM_ENG.pdf",  # Small: 50 pages
    "HP_E877_CPMD.pdf",  # Large: 1116 pages
    "Canon_MF644Cdw_UM.pdf"  # Medium: 200 pages
]

# Run benchmark with same documents
for doc in BENCHMARK_DOCUMENTS:
    result = run_pipeline(doc)
    store_baseline(doc, result.metrics)
```

**Database Table:** `krai_system.performance_baselines`

```sql
CREATE TABLE krai_system.performance_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_name VARCHAR(100) NOT NULL,
    document_name VARCHAR(200) NOT NULL,
    git_commit VARCHAR(40) NOT NULL,
    environment VARCHAR(20) NOT NULL,  -- staging, production
    metrics JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(test_name, document_name, git_commit)
);
```

---

### Anti-Patterns to Avoid

**Common mistakes to avoid in error handling and retry logic:**

1. **❌ Custom Retry Loops**
   - Custom retry loops bypass centralized error handling, correlation IDs, idempotency checks, and advisory locks
   - Use `BaseProcessor.safe_process()` instead

2. **❌ Sleeping in Sync Code**
   - `time.sleep()` blocks the entire thread, prevents other work, doesn't scale
   - Let `safe_process()` handle retry scheduling

3. **❌ Ignoring Error Classification**
   - Wastes resources retrying permanent errors (404, 401, etc.)
   - Classify errors as transient or permanent first

4. **❌ Missing Idempotency Checks**
   - Retries create duplicate data (chunks, images, etc.)
   - Always check completion markers before processing

5. **❌ Direct Alert Sending**
   - Floods inboxes with duplicate alerts, no aggregation, no rate limiting
   - Queue alerts for aggregation via `AlertService`

6. **❌ Hardcoded Retry Policies**
   - Requires code changes to adjust retry behavior, not configurable per environment
   - Load retry policies from database

7. **❌ Missing Correlation IDs**
   - Impossible to trace request flow across stages and retries
   - Include correlation ID in all log entries

8. **❌ Locks Without Finally**
   - Locks may never be released, causing deadlocks
   - Always use try-finally blocks

9. **❌ Production Benchmarks**
   - Consumes resources, impacts performance, skews metrics
   - Always use staging environment

10. **❌ Catching Generic Exceptions**
    - Catches system exceptions, prevents proper error handling
    - Catch specific exception types only

---

### Database Schema - New Tables

**6 new tables for error handling and retry architecture:**

1. **`krai_system.stage_completion_markers`** - Track idempotency with data hashing
2. **`krai_system.pipeline_errors`** - Error tracking for dashboard and analytics
3. **`krai_system.alert_queue`** - Alert aggregation queue
4. **`krai_system.alert_configurations`** - Database-first alert configuration
5. **`krai_system.retry_policies`** - Configurable retry policies per service/stage
6. **`krai_system.performance_baselines`** - Performance measurement baselines

---

### Components to Implement

**When implementing error handling architecture, create these components:**

1. **ErrorClassifier** (`backend/core/error_classifier.py`)
   - Error classification logic
   - Classify as transient or permanent

2. **RetryOrchestrator** (`backend/core/retry_orchestrator.py`)
   - Retry scheduling and orchestration
   - Hybrid retry approach (sync first, then async)

3. **IdempotencyChecker** (`backend/core/idempotency_checker.py`)
   - Completion marker management
   - Data hash computation

4. **AlertService** (`backend/services/alert_service.py`)
   - Alert queueing and aggregation
   - Background worker for alert processing

5. **BenchmarkSuite** (`scripts/benchmark_suite.py`)
   - Performance measurement tools
   - Baseline comparison

---

## 📚 Key Files Reference

**Core Architecture:**
- `backend/core/base_processor.py` - Base processor with safe_process()
- `backend/core/data_models.py` - ProcessingContext, ProcessingResult
- `backend/processors/exceptions.py` - ProcessingError class
- `backend/processors/logger.py` - ProcessorLogger implementation

**Error Handling (to be implemented):**
- `backend/core/error_classifier.py` - Error classification logic
- `backend/core/retry_orchestrator.py` - Retry scheduling
- `backend/core/idempotency_checker.py` - Completion marker management
- `backend/services/alert_service.py` - Alert queueing and aggregation

**Database:**
- `DATABASE_SCHEMA.md` - Complete database schema documentation
- `database/migrations_postgresql/` - PostgreSQL migrations

**Configuration:**
- `.env` - Environment variables
- `backend/config/` - Application configuration

**Testing:**
- `tests/processors/` - Processor tests
- `tests/api/` - API tests
- `pytest.ini` - Test configuration

---

**Last Updated:** 2026-01-12 (15:15)
**Version:** 3.0 - Complete rules with full error-handling architecture details
**Status:** Ready for implementation - Remove "FUTURE WORK" markers when features are implemented
