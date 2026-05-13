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
| 1 | **Unit-Tests für Fixed Stages** | Tests für SVG/Image/Link Processor erweitern | 📝 TODO |
| 2 | **Integration-Tests** | End-to-end Tests für alle 4 Stages zusammen | 📝 TODO |
| 3 | **Live Dashboard Monitoring** | Visuelle Fehler-Indikatoren in Timeline hinzufügen | 📝 TODO |

### Mittlere Priorität (Nice-to-Have)

| # | Task | Beschreibung | Status |
|---|------|--------------|--------|
| 4 | **Type Annotations** | MyPy konfigurieren, viele `Any` entfernen | 🔄 In Progress |
| 5 | **Performance Profiling** | Benchmark für Stage-Zeiten nach Fixes | 📝 TODO |
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

### Pipeline Fixes ✅ KRITISCH ERLEDIGT
- [x] **File Path Resolution für SVG/Image/Link Stages** — PDF-Pfade wurden nur für TEXT/TABLE aufgelöst, jetzt für alle PDF-lesenden Stages
- [x] **SVG Processor** — Kann jetzt erfolgreich PDFs laden und SVGs extrahieren (369 SVGs getestet)
- [x] **Image Processor** — Empfängt jetzt korrekte Dateipfade
- [x] **Link Extraction** — Hinzugefügt zur Liste der Dateipfad-Stadien

### Dashboard Features ✅ ERLEDIGT
- [x] **Live Status Dashboard** — Real-time Auto-Refresh alle 5 Sekunden während Verarbeitung
- [x] **Activity Timeline** — Chronologische Übersicht aller Stage-Events mit Timestamps
- [x] **Error Tracking** — Fehler und Retry-Counts im Activity-Log sichtbar
- [x] **Stage Activity Log View** — Neue Blade-Template mit Status-Icons (✓/⏳/✗/◯)
- [x] **Database Integration** — getStageActivityLog() Methode auf Document-Modell hinzugefügt

### Infrastructure & Code Quality
- [x] Docker Container (krai-engine) neu gestartet und health-checks bestätigt
- [x] Git Merge-Conflict (version file) aufgelöst
- [x] Commits zu GitHub gepusht (221849f + a2e77ef)

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
1. Integration-Tests für alle 4 Stage-Fixes schreiben (SVG/Image/Link/Visual)
2. Dashboard mit Fehler-Indikatoren erweitern (farbige Symbole)
3. Performance Profiling nach Fixes durchführen
4. Type Annotations in kritischen Paths verbessern
```

## 📈 Metriken (seit März)

| Metrik | März | Jetzt | Status |
|--------|------|-------|--------|
| Pipeline-Stages | 2/4 funktional | 4/4 funktional ✅ | ERLEDIGT |
| Dashboard Features | minimal | Live-Status + Timeline | ERLEDIGT |
| Git Commits | 399778a | 221849f | 8 Commits hinzugefügt |
| Code Coverage | TBD | TBD | 🔄 Messung ausstehend |
