# KRAI Master TODO
> Kompakte Projekt-Übersicht - Letzte Aktualisierung: 19.05.2026

---

## ⚡ Code Quality Optimization Blocks ✅ COMPLETE

Während auf Sprint 2 Docuware-Daten warten, haben wir 3 Optimierungsblöcke abgeschlossen:

- [x] **Block 1: Type Annotations** — MyPy kritische Paths verbessert (5 Core-Dateien)
  * Commit: `df2f960 [Backend] Improve type annotations in pipeline and processor critical paths`

- [x] **Block 2: Dashboard Links** — Verwandte Dokumente im Filament-Dashboard anzeigen
  * Commit: `535eaa2 [Dashboard] Add related documents panel using existing document_relationships table`

- [x] **Block 3: Foliant System** — Konica Minolta Foliant PDF-Import & Kompatibilitätsprüfung
  * Migrations: 036 (requires_accessory_id)
  * Commits: `25243d7 [Foliant] Add PDF import script and compatibility validation service`
  * Commit: `2dab34d [API] Add Foliant upload endpoint with compatibility check`
  * Tests: 19 Unit-Tests (9 Compatibility Service + 10 Import Script), 100% Pass Rate

---

## 📌 PM Sprint Status (Predictive Maintenance Initiative)

### Sprint 1: Datenfundament ✅ COMPLETE (19.05–01.06.2026)
**Status:** SHIPPED TO MASTER
- [x] DB Schema (krai_pm): 5 Tabellen + 4 Views (Migrations 034/035)
- [x] TicketIngestionProcessor: 180 Test-Tickets (OF/PP/SOL) + 10 Unit-Tests + 5 Integration-Tests
- [x] PartLifetimesImporter: 120+ Part-Einträge + 7 Unit-Tests + 6 Integration-Tests
- [x] Data Exploration Notebook: 9-Abschnitte, Long-Tail-Analyse validiert
- [x] ADR-001 (Eigenes PM-Schema): Accepted
- [x] ADR-002 (SHA-256 Pseudonymisierung): Accepted
- [x] Research Log (Kickoff + Closeout): Dokumentiert
- [x] Commits: 8x [KRAI-PM] Prefix, saubere History
- [x] GitHub: Auf master gepusht (commit 3f4cde7)

**Test-Ergebnisse:** 28 Total (17 Unit + 11 Integration), 100% Pass Rate

---

### Sprint 2: Modellgrundlagen ✅ CATEGORY A COMPLETE (02.06–15.06.2026)

#### ✅ Kategorie A — ABGESCHLOSSEN (Keine Datenverfügbarkeit nötig)
- [x] 2.1: ML Model v1 Architektur (XGBoost/LightGBM, Long-Tail Classification)
- [x] 2.2: Feature Engineering Framework (Problem-Häufigkeit, Error-Codes, Parts, Repair-Time)
- [x] 2.3: Long-Tail Klassifizierung (Training gegen 180 Test-Tickets, 5-fold CV)
- [x] 2.4: Error Pattern Analyzer (Pro-Hersteller Fehler-Cluster: HP/Konica/Ricoh)
- [x] 2.5: Model Evaluation Framework (Accuracy, Precision, Recall, F1, Ablation Testing)
- [x] 2.6: Prediction Service (Speichern von Predictions in krai_pm.predictions)
- [x] 2.7: ADR-003 (Long-Tail Classification Strategy): Proposed ✓
- [x] 2.8: Tests grün (64/64 passed) + Linting sauber
  - Feature Engineering: 6 tests ✓
  - Long-Tail Classifier: 13 tests ✓
  - Model Evaluator: 7 tests ✓
  - Error Pattern Analyzer: 6 tests ✓
  - Prediction Service: 5 tests ✓
  - Ticket Ingestion (Sprint 1): 10+5 tests ✓
  - Part Lifetimes (Sprint 1): 7+5 tests ✓

#### 🔴 Kategorie B — BLOCKIERT (Wartet auf Docuware/Radix Termin)
- [ ] 2.9: Device Lifecycle Tracker (Skeleton: bereit für Docuware-Integration)
- [ ] 2.10: Datenvolumen-Validierung (6.000+ echte Tickets, wenn Docuware verfügbar)
- [ ] 2.11: Cross-Manufacturer Model Validation (Pro-Hersteller Klassifizierer)

**Blockade:** ⏳ Docuware + Radix Datenverfügbarkeit — Termin wird intern abgestimmt
**Dokumentation:** `tasks/pm-sprint-02-modellgrundlagen.md` (mit Placeholders für Termin)

#### ✅ Kategorie C — ABGESCHLOSSEN (02.06–29.05.2026)
- [x] 2.C1: Migration 037 — part_warranty_events Schema + Bug-Fix predictions.metadata
- [x] 2.C2: PartReliabilityAnalyzer + WarrantyTracker + Pydantic-Modelle
- [x] 2.C3: ADR-004 (Part Warranty Analysis) + Tests (13/13 passing) + MASTER-TODO Update

**Tests:** 13 Total (7 analyzer + 6 tracker), 100% Pass Rate
**Linting:** Ruff clean (Core Category C modules)
**Status:** ✅ SPRINT 2 CATEGORY C COMPLETE

#### ✅ Kategorie D — WARRANTY DATA ANALYSIS (19.05.2026)
**Real Radix Warranty Analysis — Complete Device Lifecycle with Laufleistung**

- [x] **D.1: Device History Extraction** — Complete device replacement histories with page counters
  * Extracted: 3,068 unique devices | 8,071 service events
  * System IDs: Extracted from descriptions using regex
  * Page counters: 199 devices with Schwarzdruck/Farbdruck data
  * Part numbers: Article numbers and manufacturer part codes captured
  * Script: `build_device_part_history.py`
  * Output: `docs/device_part_replacement_history.json`

- [x] **D.2: Warranty Analysis Framework** — Calculated warranty eligibility and failure rates
  * Warranty failure rate: **92.3%** (4,620 of 5,003 parts fail within 365 days)
  * High-maintenance devices: 417 devices with 5+ service events per year
  * Part frequency analysis: Trommel (22.9%), Toner (16.5%), Transfer (14.8%)
  * Script: `analyze_warranty_from_device_history.py`
  * Output: `docs/warranty_analysis_detailed.json`

- [x] **D.3: Laufleistung Mismatch Analysis** — Actual page counts vs nominal specs
  * 226 part failures with actual page counter documentation
  * **133 critical failures** (<30% of nominal lifetime)
  * Trommel average: 27.9% of nominal | Fixier average: 24.9% of nominal
  * Kyocera most critical: Fusers failing at 44.2% of nominal
  * Script: `analyze_laufleistung_mismatch.py`
  * Output: `docs/laufleistung_mismatch_analysis.json`

- [x] **D.4: Warranty Claims Export** — Unsubmitted warranty claims with device serials
  * **EUR 3.37 million in unsubmitted warranty claims**
  * Breakdown: Konica Minolta EUR 1.39M (2,609 claims) | Samsung EUR 950k (1,660 claims)
  * Top device: Konica Minolta PRESS C1085 (Serial 14883) = EUR 30,450
  * CSV export: `warranty_claims_for_negotiation.csv` (6,053 records)
  * Script: `export_warranty_claims_for_negotiation.py`
  * Output: `docs/warranty_claims_detailed.json`

- [x] **D.5: Negotiation Brief** — Executive summary for manufacturer discussions
  * Brief: `docs/warranty_negotiation_brief.md`
  * Manufacturer strategy analysis (Konica Minolta, Samsung, Lexmark, HP, Kyocera)
  * Critical findings: 92.3% warranty failure rate, EUR 3.37M recovery opportunity
  * Schwarzdruck vs Farbdruck impact analysis
  * Recommended negotiation phases with timelines

**Data Quality & Traceability:**
- All findings linked to Radix ticket IDs
- Device serials and manufacturer serial numbers captured
- Page counter extraction from unstructured German/English text
- Counter types detected: Total (79 devices), Color/Farbdruck (54), BW/Schwarzdruck (20)

**Financial Impact Summary:**
```
Total unsubmitted warranty claims: EUR 3,377,500
- Konica Minolta: EUR 1,396,600 (41%)
- Samsung: EUR 950,450 (28%)
- Lexmark: EUR 344,450 (10%)
- Others: EUR 686,000 (21%)

Negotiation value: EUR 3.37M recovery + design review leverage
```

- [x] **D.6: Real Radix Tickets Import** — Import complete device history data into production database
  * Imported: **3,418 real service tickets** from `docs/device_part_replacement_history.json`
  * Replaced: 180 mock test tickets (MOCK* prefix) with real Radix data
  * Breakdown: Konica Minolta 1,760 | Lexmark 1,202 | Kyocera 455 | Canon 1
  * Data source: 8,071 events from 3,068 unique devices
  * Database: `krai_pm.service_tickets` with source_ticket_id indexing
  * Script: `scripts/import_device_history_tickets.py` (with --clear-mock flag)
  * Schema fix: Updated INSERT to match table structure (source_system, source_ticket_id, created_at_source)
  * Status: ✅ COMPLETE (0 errors, all tickets successfully imported)

**Status:** ✅ SPRINT 2 CATEGORY D COMPLETE (Ad-hoc warranty analysis + real ticket import)

---

## ✅ Erledigt (Kurzübersicht)

### Pipeline & Processing
- [x] 16-Stage Processing Pipeline
- [x] Safe Process mit Retry-Logic
- [x] Idempotency Checks
- [x] Stage Tracking mit WebSocket
- [x] Performance Metrics Collection
- [x] Retry Orchestrator mit Advisory Locks
- [x] SVG Processing (mit PDF Path Resolution)
- [x] Image Processing (mit PDF Path Resolution)
- [x] Link Extraction (mit PDF Path Resolution)
- [x] Live Status Dashboard mit Real-time Polling

### Datenbank & Suche
- [x] PostgreSQL + pgvector Embeddings
- [x] Error Code Hierarchy (Migration 018)
- [x] Chunks mit direkter embedding-Spalte
- [x] Full-Text Search
- [x] Similarity Search

### AI/ML
- [x] Ollama Integration (nomic-embed-text, llava)
- [x] Visual Embeddings
- [x] Error Code Extraction
- [x] Parts Extraction
- [x] Series Detection

### Infrastructure
- [x] Docker Compose (Production/Staging/Simple)
- [x] CUDA Support im Dockerfile
- [x] Redis Caching
- [x] MinIO Storage

### Testing & Quality
- [x] E2E Test Suite
- [x] Smoke Tests
- [x] Processor-spezifische Fixtures

---

## 🎯 Offene Tasks

### Hohe Priorität (Critical Path)

| # | Task | Beschreibung | Status |
|---|------|--------------|--------|
| 1 | **Unit-Tests für Fixed Stages** | Tests für SVG/Image/Link Processor erweitern | ✅ DONE |
| 2 | **Integration-Tests** | End-to-end Tests für alle 4 Stages zusammen | ✅ DONE |
| 3 | **Live Dashboard Monitoring** | Visuelle Fehler-Indikatoren in Timeline hinzufügen | ✅ DONE |

### Mittlere Priorität (Nice-to-Have)

| # | Task | Beschreibung | Status |
|---|------|--------------|--------|
| 4 | **Type Annotations** | MyPy konfigurieren, viele `Any` entfernen | ✅ DONE |
| 5 | **Performance Profiling** | Benchmark für Stage-Zeiten nach Fixes | ✅ DONE |
| 6 | **Fehler-Alerting** | Automatische Benachrichtigungen bei Stage-Fehlern | ✅ DONE |
| 7 | **Dashboard Verbindungen** | Visuelle Links zwischen verwandten Dokumenten | ✅ DONE |

### Niedrige Priorität (Nice-to-Have)

| # | Task | Beschreibung | Status |
|---|------|--------------|--------|
| 8 | **Foliant-System** | PDF-Import für Konica Minolta Produktdaten | ✅ DONE |
| 9 | **Product Accessories** | Siehe `TODO_PRODUCT_ACCESSORIES.md` | 📋 Backlog |
| 10 | **Documentation Audit** | DATABASE_SCHEMA.md, API-Docs aktualisieren | 📋 Backlog |

---

## 📊 Letzte Änderungen (13.05.2026)

### Testing & QA ✅ ERLEDIGT
- [x] **Unit-Tests für SVG/Image/Link Stages** — 18 comprehensive tests für file path resolution
  - test_svg_processor_file_path.py: 5 tests
  - test_image_processor_file_path.py: 6 tests
  - test_link_extraction_file_path.py: 7 tests
- [x] **Integration-Tests für File Path Flow** — 10 integration tests verifying all 4 stages together
  - test_file_path_resolution_pipeline.py: Tests für context consistency, sequence flow, error handling
  - Alle Tests erfolgreich (verified: test_all_stages_receive_resolved_file_path passes)
- [x] **Performance Benchmarking Suite** — 9 benchmark tests für processor initialization und context handling
  - benchmark_stages.py: Messungen für SVG, Image, Link Processor
  - Context creation time: ~1.9 microseconds (517.75 Kops/s)
  - Initialization & stage lookup performance baselines erfasst

### Dashboard Enhancements ✅ ERLEDIGT
- [x] **Stage Activity Log Visual Improvements** — Enhanced Blade template mit:
  - Error messages mit gradient background und warning icon
  - Color-coded status badges mit inline display
  - Pulsing indicator für "processing" status
  - Enhanced error ring indicators (red für failed stages)
  - Improved retry count display mit icon und background

### Pipeline Fixes ✅ KRITISCH ERLEDIGT
- [x] **File Path Resolution für SVG/Image/Link Stages** — PDF-Pfade wurden nur für TEXT/TABLE aufgelöst, jetzt für alle PDF-lesenden Stages
- [x] **SVG Processor** — Kann jetzt erfolgreich PDFs laden und SVGs extrahieren (369 SVGs getestet)
- [x] **Image Processor** — Empfängt jetzt korrekte Dateipfade
- [x] **Link Extraction** — Hinzugefügt zur Liste der Dateipfad-Stadien

### Error Alerting System ✅ ERLEDIGT
- [x] **StageAlertManager Service** — Intelligente Fehler-Benachrichtigungen für Stage-Ausfälle
  - stage_alert_manager.py: Service mit Severity-Escalation und Criticality-Mapping
  - Alerts on stage failures with context (error type, document, retry info)
  - Alerts on pipeline completion with summary (success/partial/failed)
  - 13 comprehensive test cases in test_stage_alert_manager.py
- [x] **Integration in master_pipeline.py** — Stage-Fehler triggern automatisch Alerts
  - Alert auf Stage-Fehler (success=False oder Exception)
  - Alert auf Pipeline-Completion mit Summary (completed/partial/failed stages)
  - Graceful degradation wenn AlertService unavailable
- [x] **ServiceLocator Registration** — AlertService und StageAlertManager in Service-Registry
  - Lazy loading via backend.services.alert_service.AlertService
  - Lazy loading via backend.services.stage_alert_manager.StageAlertManager
- [x] **Code Quality** — Linting und Formatting (ruff, black, isort, bandit) — alle Checks passing

### Infrastructure & Code Quality
- [x] Docker Container (krai-engine) neu gestartet und health-checks bestätigt
- [x] Git Merge-Conflict (version file) aufgelöst
- [x] Pre-commit Hooks (black, isort, ruff, bandit) konfiguriert und automatisch applied
- [x] Commits zu GitHub gepusht (9bb106e mit Error Alerting System)

---

## 📁 Detail-TODOs (für spezifische Bereiche)

| Datei | Bereich |
|-------|---------|
| `TODO.md` | Hauptsächliche Bug-Fixes |
| `docs/project_management/TODO.md` | E2E Tests |
| `docs/project_management/TODO_FOLIANT.md` | Foliant PDF-System |
| `docs/project_management/TODO_PRODUCT_ACCESSORIES.md` | Zubehör-System |
| `docs/project_management/TODO_PRODUCT_CONFIGURATION_DASHBOARD.md` | Dashboard |

---

## 🚀 Nächste Schritte (Priorität)

```
✅ 1. Integration-Tests für alle 4 Stage-Fixes schreiben (SVG/Image/Link/Visual)
✅ 2. Dashboard mit Fehler-Indikatoren erweitern (farbige Symbole)
✅ 3. Performance Profiling nach Fixes durchführen
✅ 5. Fehler-Alerting System implementieren für Stage-Fehler
🔄 4. Type Annotations in kritischen Paths verbessern
```

### Danach:
```
6. Dashboard-Links zwischen verwandten Dokumenten hinzufügen
7. Foliant-System Integration prüfen
8. Type Annotations finalisieren (MyPy vollständig)
```

## 📈 Metriken (seit März)

| Metrik | März | Jetzt | Status |
|--------|------|-------|--------|
| Pipeline-Stages | 2/4 funktional | 4/4 funktional ✅ | ERLEDIGT |
| Dashboard Features | minimal | Live-Status + Timeline | ERLEDIGT |
| Git Commits | 399778a | 221849f | 8 Commits hinzugefügt |
| Code Coverage | TBD | TBD | 🔄 Messung ausstehend |
