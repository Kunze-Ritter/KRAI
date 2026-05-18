# Test Setup & Ausführung

Schnellstart-Anleitung für die Integration Tests.

## 🚀 Schnellstart

### Option 1: Interaktives Setup (Empfohlen)

```powershell
.\setup_tests.ps1
```

Das Script:
- ✅ Prüft Python Installation
- ✅ Erstellt/aktiviert Virtual Environment
- ✅ Installiert alle Dependencies
- ✅ Zeigt verfügbare Test-Optionen
- ✅ Führt Tests nach deiner Wahl aus

### Option 2: Quick Runner

```powershell
# Alle Tests
.\run_tests.ps1 all

# Nur LinkEnrichmentService
.\run_tests.ps1 link

# Nur ProductResearcher
.\run_tests.ps1 product

# Schnelle Tests (ohne slow)
.\run_tests.ps1 fast

# Ohne Firecrawl
.\run_tests.ps1 no-firecrawl

# Hilfe anzeigen
.\run_tests.ps1 help
```

### Option 3: Batch File (Doppelklick)

```cmd
run_tests.bat all
run_tests.bat link
run_tests.bat fast
```

### Option 4: Direkt mit Python

```powershell
# Virtual Environment aktivieren (falls vorhanden)
.\venv\Scripts\Activate.ps1

# Tests ausführen
python -m pytest backend/tests/integration/ -v -m integration
```

---

## 📋 Verfügbare Test-Suites

### Alle Integration Tests
```powershell
python -m pytest backend/tests/integration/ -v -m integration
```

### LinkEnrichmentService Tests
```powershell
# E2E Tests (Single + Batch)
python -m pytest backend/tests/integration/test_link_enrichment_e2e.py -v

# Error Handling Tests
python -m pytest backend/tests/integration/test_link_enrichment_error_handling.py -v

# Beide zusammen
python -m pytest backend/tests/integration/test_link_enrichment*.py -v
```

### ProductResearcher Tests
```powershell
python -m pytest backend/tests/integration/test_product_researcher_real.py -v
```

### Nach Kategorie
```powershell
# Nur Database Tests
python -m pytest backend/tests/integration/ -v -m "integration and database"

# Nur Benchmark Tests
python -m pytest backend/tests/integration/ -v -m "integration and benchmark"

# Ohne Firecrawl
python -m pytest backend/tests/integration/ -v -m "integration and not firecrawl"

# Ohne langsame Tests
python -m pytest backend/tests/integration/ -v -m "integration and not slow"
```

### Einzelne Test-Klassen
```powershell
# Single Link Workflows
python -m pytest backend/tests/integration/test_link_enrichment_e2e.py::TestLinkEnrichmentRealE2E -v

# Batch Processing
python -m pytest backend/tests/integration/test_link_enrichment_e2e.py::TestLinkEnrichmentBatchProcessing -v

# Error Handling
python -m pytest backend/tests/integration/test_link_enrichment_error_handling.py::TestLinkEnrichmentErrorHandling -v
```

---

## ⚙️ Manuelle Einrichtung

Falls du die Scripts nicht verwenden möchtest:

### 1. Virtual Environment erstellen
```powershell
python -m venv venv
```

### 2. Virtual Environment aktivieren
```powershell
.\venv\Scripts\Activate.ps1
```

Falls Fehler "Ausführung von Skripts ist auf diesem System deaktiviert":
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. Dependencies installieren
```powershell
pip install --upgrade pip
pip install pytest pytest-asyncio pytest-benchmark
pip install -r requirements.txt

# Optional: Firecrawl SDK
pip install firecrawl-py

# Optional: Tavily SDK
pip install tavily-python
```

### 4. Environment konfigurieren
Erstelle `.env.test` oder verwende `.env`:
```bash
# PostgreSQL Test Database
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:password@localhost:5432/krai_test
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=krai_test

# AI Services
OLLAMA_URL=http://krai-ollama:11434

# Web Scraping (Optional)
FIRECRAWL_API_URL=http://krai-firecrawl-api:3002
FIRECRAWL_API_KEY=your-api-key

# Note: Supabase support removed (November 2024, KRAI-002)
# Use PostgreSQL-only configuration above
```

### 5. Tests ausführen
```powershell
python -m pytest backend/tests/integration/ -v -m integration
```

---

## 🔧 Troubleshooting

### "pytest" nicht gefunden
**Lösung**: Verwende `python -m pytest` statt `pytest`

### Virtual Environment Aktivierung fehlgeschlagen
**Fehler**: "Ausführung von Skripts ist auf diesem System deaktiviert"

**Lösung**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Import Errors
**Lösung**: Virtual Environment aktivieren und Dependencies installieren:
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Firecrawl Tests schlagen fehl
**Lösung**: Tests werden automatisch übersprungen wenn Firecrawl nicht verfügbar ist.
Alternativ: Tests ohne Firecrawl ausführen:
```powershell
python -m pytest backend/tests/integration/ -v -m "integration and not firecrawl"
```

### Database Connection Errors
**Lösung**:
1. Prüfe ob Docker Container laufen: `docker ps`
2. Prüfe `.env.test` oder `.env` Konfiguration
3. Teste DB-Verbindung: `psql -h localhost -U postgres -d krai_test`

### Ollama Connection Errors
**Lösung**:
1. Prüfe Ollama Container: `docker ps | grep ollama`
2. Prüfe Models: `docker exec krai-ollama ollama list`
3. Teste Ollama: `curl http://localhost:11434/api/tags`

---

## 📊 Test Output

### Erfolgreiche Tests
```
test_real_link_enrichment_firecrawl_success PASSED        [10%]
test_real_batch_enrichment_concurrent_links PASSED        [20%]
...
======================== 25 passed in 45.2s ========================
```

### Übersprungene Tests
```
test_real_link_enrichment_firecrawl_success SKIPPED       [10%]
Reason: Firecrawl not available
```

### Fehlgeschlagene Tests
```
test_real_link_enrichment_timeout FAILED                  [30%]
AssertionError: Expected timeout error
```

---

## 🎯 Best Practices

### Vor dem Commit
```powershell
# Schnelle Tests
python -m pytest backend/tests/integration/ -v -m "integration and not slow"
```

### Vollständige Test-Suite
```powershell
# Alle Tests (kann 5-10 Minuten dauern)
python -m pytest backend/tests/integration/ -v -m integration
```

### Performance Tests
```powershell
# Nur Benchmark Tests
python -m pytest backend/tests/integration/ -v -m "integration and benchmark"
```

### Debugging
```powershell
# Mit ausführlichem Output
python -m pytest backend/tests/integration/ -v -s -m integration

# Einzelner Test mit Debug
python -m pytest backend/tests/integration/test_link_enrichment_e2e.py::TestLinkEnrichmentRealE2E::test_real_link_enrichment_firecrawl_success -v -s
```

---

## 📚 Weitere Dokumentation

- **Detaillierte Test-Dokumentation**: `backend/tests/integration/README.md`
- **Test-Struktur**: Siehe README für vollständige Test-Matrix
- **CI Integration**: GitHub Actions Beispiele in README

---

**Erstellt**: 2024-12-07
**Zuletzt aktualisiert**: 2024-12-07
