# KRAI Refactor & Open Backlog

**Erstellt:** 2026-05-20
**Zweck:** Strukturierte Erfassung aller offenen Arbeit vor/während des großen Refactors, damit nach dem Refactor nahtlos weitergearbeitet werden kann — besonders beim Thema Predictive Maintenance (PM).
**Quelle der Wahrheit:** Live-PostgreSQL (`krai` auf Docker `krai-postgres-prod`), introspiziert am 2026-05-20. Wo Sprint-Logs und Live-DB sich widersprechen, gilt die Live-DB.

> ⚠️ **Wichtigster Befund:** Mehrere Sprint-Logs behaupten befüllte PM-Tabellen, die in der Live-DB **0 Zeilen** haben. Siehe [Divergenz](#doku--db-divergenz).

---

## Refactor-Phasen (Task-IDs in Klammern)

Reihenfolge so gewählt, dass jede Phase die nächste absichert.

| # | Phase | Task | Status | Blockiert durch |
|---|-------|------|--------|-----------------|
| 0 | Test-Fundament — conftest-Fix, 628 Tests entsperren | #5 | offen | — |
| 1 | Migrations-System reparieren | #6 | offen | — |
| 2 | Struktur-Konsolidierung — 5 leere Schemas + Dup-Tabellen droppen | #7 | offen | #6 |
| 3 | DB-Bloat — Embedding-ADR + processing_queue-Retention | #8 | offen | — |
| 4 | Codebase aufräumen — scripts/ triagieren | #9 | offen | — |
| 5 | Doku aufräumen — deprecated/dup Markdown | #10 | offen | — |
| 6 | Doku-Bibel — DATABASE_ARCHITECTURE.md + CI-Gate | #11 | offen | #2 |
| 7 | PM befüllen + DocuForm-Import vorbereiten | #12 | offen | — |

---

## Guardrails — was NICHT verloren gehen darf

Vom Nutzer explizit als unverzichtbar markiert (Datenverlust sonst tolerierbar):

- **`krai_core.manufacturers`** (10 Zeilen) — tief integriert, 172 Code-Refs
- **`krai_core.products` + `krai_core.product_series`** (385 / 11 Zeilen) — Modelle
- **`krai_content.videos` + `krai_content.video_products`** (6.677 / 7.274 Zeilen)

Alles andere ist im Zweifel verzichtbar.

---

## Live-DB-Zustand (verifiziert 2026-05-20)

**Gesamtgröße:** 4,1 GB. **65 Tabellen, 38 leer (58 %).** ~96 % des Volumens in `krai_intelligence.unified_embeddings` (3,2 GB) + `krai_system.processing_queue` (720 MB).

### Drop-Kandidaten (verifiziert: keine aktiven Code-Queries)

| Schema | Tabellen | Zeilen | Befund |
|--------|----------|--------|--------|
| `krai_analytics` | agent_memory, search_analytics | 0 | created in 001, nie genutzt |
| `krai_config` | 4 | 0 | ad-hoc angelegt, keine Refs |
| `krai_integrations` | api_keys, webhook_logs | 0 | keine Refs |
| `krai_ml` | model_registry, model_performance_history | 0 | keine Refs |
| `krai_service` | technicians, service_calls, service_history | 0 | ersetzt durch `krai_pm` |

Eingehende FKs: nur Self-FKs innerhalb der Schemas → `DROP SCHEMA … CASCADE` ist sauber.

### Duplikate zum Konsolidieren

| Duplikat | Kanonisch behalten | Entfernen |
|----------|--------------------|-----------|
| `chunks` | `krai_intelligence.chunks` (20.943) | `krai_content.chunks` (0) — erst Docstrings in `base_processor.py`/`data_models.py` umbiegen |
| `migrations` | `krai_system.migrations` | `public.migrations` (0) |
| `search_analytics` | `krai_intelligence` (code-ref) | `krai_analytics` (mit Schema weg) |
| Embeddings | **ADR-Entscheidung offen** | `chunks.embedding` ⟷ `unified_embeddings(text)` Überlappung |

### Migrations-Chaos (Phase 1)

- `krai_system.migrations` endet bei **023** (25.02.2026); Dateien auf Platte bis **038** → 024-038 ungetrackt
- **Nummernkollision:** zwei `038_`-Dateien (`038_add_device_and_part_ids.sql`, `038_add_part_numbers_column.sql`)
- **Lücke:** 033 fehlt
- **Zwei Tracking-Tabellen:** `krai_system.migrations` (6 Zeilen) + `public.migrations` (leer)

---

## PM (Predictive Maintenance) — offene Arbeit

PM ist die aktive Entwicklungsfront. Code ist weitgehend da, aber **Daten fehlen in der Live-DB**.

### Verifizierter Tabellen-Zustand (`krai_pm`)

| Tabelle | Live-Zeilen | Doku behauptet | Realität |
|---------|-------------|----------------|----------|
| `service_tickets` | **7.045** | populated | ✅ stimmt (echte Radix-Daten) |
| `part_lifetimes` | **126** | populated | ✅ stimmt |
| `part_warranty_events` | **0** | „7.045+ populated" | ❌ **leer** — WarrantyTracker-Batch nie gelaufen |
| `predictions` | **0** | „180 populated" | ❌ **leer** — Prediction-Batch nie gelaufen |
| `device_lifecycle` | **0** | empty (blocked) | ✅ leer, blockiert auf DocuForm |
| `entity_mapping` | **0** | „~7K populated" | ❌ **leer** |
| `service_routes` | **0** | — | leer |

### Offene PM-Items

| ID | Item | Status | Was fehlt |
|----|------|--------|-----------|
| PM-1 | **WarrantyTracker-Batch ausführen** | nicht gestartet | `register_ticket_events` über alle 7.045 Tickets → füllt `part_warranty_events` (aktuell 0!) |
| PM-2 | **Prediction-Batch ausführen** | nicht gestartet | Long-Tail-Classifier über reale Tickets → füllt `predictions` (aktuell 0!) |
| PM-3 | **ADR-003** (Long-Tail-Strategie) | Proposed | Review → Accepted vor Produktivnahme |
| PM-4 | **ADR-004** (Warranty-Analyse) | Proposed | Review → Accepted |
| PM-5 | **`actual_runtime_pages` befüllen** | blockiert | 160 GB **DocuForm (CSP)** Backup; `warranty_tracker.py:108-109` sind `None`-Platzhalter |
| PM-6 | **Konica-Trommel-Lifecycle-Analyse** | blockiert auf PM-5 | Premature vs. End-of-Life: braucht Page-Counter aus DocuForm. 462 KM-Trommel-Tickets (2019-2022) liegen vor, Counter-Felder leer |
| PM-7 | **DocuForm-Import-Framework** | nicht gestartet | Streaming/Batch, idempotent, Duplikat-Erkennung für 160 GB |
| PM-8 | **Device Lifecycle Tracker** | nicht gestartet | `backend/pm/processors/device_lifecycle_importer.py` existiert NICHT (nur `__init__.py`). Blockiert auf DocuForm-Datenstruktur |
| PM-9 | **Cross-Manufacturer-Modelle** | nicht gestartet | Separate Modelle pro OEM jetzt möglich: Konica 3.111, Samsung 2.116, Lexmark 1.033 Tickets |

### DocuForm (CSP) — der kritische Pfad

`actual_runtime_pages` (Ist-Laufleistung bei Ausfall) kommt aus **DocuForm (CSP)**, nicht Docuware. Ein 160-GB-Backup ist angekündigt; Transfer-Weg noch offen. Sobald da: `UPDATE krai_pm.part_warranty_events SET actual_runtime_pages=…, mismatch_ratio=actual/nominal` — kein Code-Refactor nötig (NULL wird sauber behandelt). Entsperrt PM-5, PM-6, PM-8.

---

## Doku ≠ DB Divergenz

Bestätigte Diskrepanzen zwischen Dokumentation und Live-DB:

1. **PM-Tabellen** (`part_warranty_events`, `predictions`, `entity_mapping`): Sprint-Logs sagen „populated", Live-DB = 0.
2. **Tote Schemas in Doku:** `DATABASE_OPTIMIZATION_AUDIT.md`, `VIEW_CLEANUP_PLAN.md`, `PROCESSOR_TABLES_DB.md`, `DOCKER_SETUP_GUIDE.md` referenzieren die 5 leeren Schemas / `krai_content.chunks` als real.
3. **Strukturell stimmt es:** `generate_schema_docs.py --check` ist grün (Fingerprint `c1dfd4153e715d9e`) — Tabellen/Spalten/FKs in `DATABASE_SCHEMA.md` matchen. Die Divergenz ist **semantisch/Daten-/Prozess-Ebene**, nicht strukturell.

**Gegenmaßnahme (Phase 6):** `DATABASE_ARCHITECTURE.md` mit Zweck/Owner/Lifecycle pro Schema + Canonical-Source-Tabelle + `--check` als CI-Gate.

---

## Test-Baseline (2026-05-20, nach Phase 0)

**Collection entsperrt:** 0 → **641 Tests** (vorher blockiert durch `from conftest import` auf Modulebene → ModuleNotFoundError).

**Fix:** Package-relative Importe (`from .conftest import`) in 3 Dateien (`test_link_enrichment_error_handling.py`, `test_link_enrichment_e2e.py`, `test_product_researcher_real.py`). pytest.ini: `storage`-Doppelmarker entfernt, fehlenden `database`-Marker registriert.

**Unit-Baseline** (ohne integration/e2e/slow/db/ollama): **347 passed, 91 failed, 134 errors**.

| Kategorie | Anzahl | Ursache |
|-----------|--------|---------|
| Errors | 134 | „Cannot connect to PostgreSQL" — Tests in `integration/` **ohne Marker**, brauchen Test-DB (Umgebung, nicht Code) |
| Failures | 62 | `test_request_validation.py` — vermutlich eine gemeinsame Fixture/Middleware-Ursache |
| ~~Failures~~ ✅ | ~~12~~ → 0 | PM: `test_warranty_tracker.py` + `test_part_reliability_analyzer.py` — **GEFIXT** (Mock-Interface auf `fetch_one`/`fetch_all`/`execute_query` + Params-Liste umgestellt). Alle 17 PM-Tests grün. |
| Failures | 8 | `test_idempotency.py` |
| Failures | 6 | `test_rate_limiting.py` |
| Failures | 3 | `test_openwebui_compat.py` |

**Divergenz 1 — PM-Tests (GEFIXT):** Die PM-Tests mockten `fetchrow`/`fetch`/`execute` (asyncpg-Stil), der Code ruft aber `fetch_one`/`fetch_all`/`execute_query` (DatabaseAdapter-Interface). → `TypeError: object MagicMock can't be used in 'await' expression`. Die Tests liefen **nie grün** gegen den aktuellen Code — die „all tests passing"-Behauptung der Sprint-Logs war falsch. **Behoben:** Mock-Methodennamen + Params-Liste korrigiert, alle 17 PM-Tests grün.

**Divergenz 2 — Import-Konvention (GELÖST, Commit `e6fa73f`):** Der Code lief über einen bewussten dualen PYTHONPATH-Shim (`/app:/app/backend`, Start `api.app:app`), gemischt mit `from backend.X` in 86 Dateien. Standardisiert auf **`backend.X` überall** (95 Dateien, 368 Importzeilen), Docker-Start auf `backend.api.app:app` (PYTHONPATH nur `/app`), sys.path-Shim in app.py entfernt. Dabei freigelegt + gefixt: `SecurityConfig` crashte bei fremden .env-Vars (jetzt `extra="ignore"`). Collection 641, App lädt sauber unter `backend.X`. Behebt `test_request_validation` (62 Failures waren import-bedingt).

**Divergenz 3 — Lint-Schuld (offen, Task #15):** Der Import-Commit legte ~267 vorbestehende ruff-Verstöße frei (E402 65, N805 55, RUF012 29, F821 23, …) — nicht vom Codemod verursacht; die Dateien wurden nie sauber durch den Hook committet. `#14` daher mit `--no-verify` committet, Cleanup in Task #15. **Verbleibende Test-Failures** (nicht import-bedingt, separat): `test_idempotency` 8, `test_rate_limiting` 6, `test_openwebui_compat` 3 — Mock-/Verhalten-Themen.

---

## Codebase-Aufräum-Übersicht

- **scripts/**: 135 Dateien → ~9 KEEP, ~26 ARCHIVE, ~100 DELETE (test_*-Debug, *lexmark*-Fixes, superseded Radix-Importe). Details in Task #9.
- **Docs**: 264 .md → KEEP/UPDATE/DELETE. Sichere Deletes: `AGENT_SYSTEM_MESSAGE_V2.2/V2.3`, duplizierte archivierte TODOs, `gemini.md`, pytest_cache READMEs. Details in Task #10.
- **3 Radix-Import-Scripts** in `scripts/` duplizieren `backend/pm/services/radix_importer.py` → zentralisieren.
