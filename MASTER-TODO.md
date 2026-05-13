# KRAI Master TODO
> Kompakte Projekt-Übersicht - Letzte Aktualisierung: 13.05.2026

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
| 4 | **Type Annotations** | MyPy konfigurieren, viele `Any` entfernen | 🔄 In Progress |
| 5 | **Performance Profiling** | Benchmark für Stage-Zeiten nach Fixes | ✅ DONE |
| 6 | **Fehler-Alerting** | Automatische Benachrichtigungen bei Stage-Fehlern | 📝 TODO |
| 7 | **Dashboard Verbindungen** | Visuelle Links zwischen verwandten Dokumenten | 📝 TODO |

### Niedrige Priorität (Nice-to-Have)

| # | Task | Beschreibung | Status |
|---|------|--------------|--------|
| 8 | **Foliant-System** | Siehe `TODO_FOLIANT.md` | 📋 Backlog |
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

### Infrastructure & Code Quality
- [x] Docker Container (krai-engine) neu gestartet und health-checks bestätigt
- [x] Git Merge-Conflict (version file) aufgelöst
- [x] Pre-commit Hooks (black, isort, ruff, bandit) konfiguriert und automatisch applied
- [x] Commits zu GitHub gepusht (29e4d63, de49f25)

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
🔄 4. Type Annotations in kritischen Paths verbessern
```

### Danach:
```
5. Fehler-Alerting System aktivieren für kritische Stage-Fehler
6. Dashboard-Links zwischen verwandten Dokumenten hinzufügen
7. Foliant-System Integration prüfen
```

## 📈 Metriken (seit März)

| Metrik | März | Jetzt | Status |
|--------|------|-------|--------|
| Pipeline-Stages | 2/4 funktional | 4/4 funktional ✅ | ERLEDIGT |
| Dashboard Features | minimal | Live-Status + Timeline | ERLEDIGT |
| Git Commits | 399778a | 221849f | 8 Commits hinzugefügt |
| Code Coverage | TBD | TBD | 🔄 Messung ausstehend |
