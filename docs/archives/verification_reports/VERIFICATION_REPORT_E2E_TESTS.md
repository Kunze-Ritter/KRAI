# KRAI Pipeline Verification Report – E2E Tests

**Datum:** 2026-02-08
**Gültig für:** Plan „Verification Steps“ (Master Pipeline E2E, Processor E2E, Error Recovery, Integration, Performance, Coverage)

---

## 1. Zusammenfassung

| Kategorie              | Status | Bestanden | Fehlgeschlagen | Übersprungen | Fehler |
|------------------------|--------|-----------|----------------|--------------|--------|
| Master Pipeline E2E    | ⚠️     | 2         | 1              | 0            | 0      |
| Processor E2E (15 Dateien) | ⚠️ | 66        | 39             | 57           | 0      |
| Error Recovery         | ⚠️     | 1         | 2              | 0            | 0      |
| Integration (Real Services) | ❌ | –         | –              | –            | Import |
| Test Coverage (processors) | ⚠️ | 363       | 107            | 93           | 6      |

**Umgebung:** Windows 11, Python 3.13.7, pytest 7.4.3. PostgreSQL-Verbindungstest (verify_database_connection.py) Timeout (Dienst vermutlich nicht erreichbar). Tests nutzen MockDatabaseAdapter.

---

## 2. Testumgebung (Schritt 1)

- **pytest.ini:** testpaths = backend/tests, tests/processors, tests/verification; Marker (e2e, integration, error_recovery, …) registriert; asyncio_mode = auto; timeout 600s.
- **conftest.py (tests/processors):** MockDatabaseAdapter mit allen vom DatabaseAdapter-ABC geforderten Methoden ergänzt (disconnect, fetch_one, fetch_all, insert_chunk, insert_table, create_unified_embedding, insert_link, insert_part, start_stage, complete_stage, fail_stage, skip_stage, get_stage_status).
- **Datenbank:** `verify_database_connection.py` lief ins Timeout (PostgreSQL nicht erreichbar). Migrationen und RPC-Funktionen wurden nicht gegen eine laufende DB geprüft.
- **Code-Anpassung:** In `backend/services/performance_service.py` wurde in `flush_metrics_buffer()` die innere Hilfsfunktion `flush_one` zu `async def` geändert und Aufrufe mit `await flush_one(...)`, damit `await self.aggregate_metrics(...)` korrekt in einer async-Funktion verwendet wird (SyntaxError behoben).

---

## 3. Master Pipeline E2E (Schritt 2)

**Befehl:** `pytest tests/processors/test_master_pipeline_e2e.py -v --tb=short`

| Test | Ergebnis |
|------|----------|
| TestFullPipelineSmartProcessing::test_full_pipeline_new_document_runs_all_stages | ✅ PASSED |
| TestFullPipelineSmartProcessing::test_full_pipeline_duplicate_document_uses_smart_processing | ✅ PASSED |
| TestProcessDocumentSmartStages::test_smart_stages_only_runs_missing_stages | ❌ FAILED |

**Fehler Smart Stages:**
`assert 'svg' in result["completed_stages"]` – Tatsächlich wurden nur `['classification', 'storage', 'embedding']` als completed_stages gemeldet. Smart Processing hat nicht alle fehlenden Stages (svg, image, chunk_prep, links, metadata, search) ausgeführt, sondern nur einen Teil. Entweder Testannahme oder Pipeline-Logik für „nur fehlende Stages“ weicht ab.

---

## 4. Individual Processor E2E (Schritt 3)

**Befehl:** `pytest tests/processors/test_upload_e2e.py test_text_processor_e2e.py … test_search_processor_e2e.py -v -k e2e` (15 im Plan genannte Dateien).

- **Upload (test_upload_e2e.py):** Mehrere Fehler (z. B. `ProcessingError` is not iterable, AssertionError bei document_creation/processing_queue_creation, KeyError 'file_size_bytes', AttributeError 'ProcessingError' object has no attribute 'lower').
- **Text (test_text_processor_e2e.py):** Alle getesteten Szenarien **skipped** (z. B. PyMuPDF/PDF-Plumber-bedingt).
- **Table (test_table_processor_e2e.py):** test_process_document_with_tables / no_tables / stage_tracking PASSED; test_store_tables_and_embeddings FAILED (async_generator object is not iterable).
- **SVG (test_svg_processor_e2e.py):** Alle 4 Tests PASSED.
- **Image (test_image_processor_e2e.py):** 4 Tests PASSED.
- **Visual Embedding (test_visual_embedding_processor_e2e.py):** 2 Tests PASSED.
- **Link Extraction (test_link_extraction_processor_e2e.py):** Mehrere PASSED; 3 FAILED (Context/Database-Persistence, z. B. coroutine not awaited, len(coroutine)).
- **Chunk Preprocessor (test_chunk_preprocessor_e2e.py):** 2 PASSED, 1 FAILED (test_process_no_chunks_found_returns_failure).
- **Classification (test_classification_processor_e2e.py):** 4 PASSED, 1 FAILED (test_detect_manufacturer_from_ai).
- **Metadata (test_metadata_processor_e2e.py):** Viele SKIPPED; 2 FAILED (test_safe_process_persists_error_codes_and_version, test_db_errors_do_not_break_safe_process).
- **Parts (test_parts_processor_e2e.py):** Alle 18 Tests PASSED.
- **Series (test_series_processor_e2e.py):** 5 PASSED, 1 FAILED (test_process_product_detects_series_and_links).
- **Storage (test_storage_processor_e2e.py):** 2 PASSED, 4 FAILED (persists_all_artifact_types, skips_unsupported_artifact_type, upload_failure_records, invalid_json_payload).
- **Embedding (test_embedding_processor_e2e.py):** 2 FAILED (test_process_creates_embeddings_and_populates_adapter, test_partial_failure_reports_failed_chunks – Ollama/Adapter-Erwartungen).
- **Search (test_search_processor_e2e.py):** test_end_to_end_indexing_with_analytics_stub PASSED.

**Sammlung:** 66 passed, 39 failed, 57 skipped (ohne fehlerhafte Module document_processor, create_database_adapter).

---

## 5. Error Recovery (Schritt 4)

**Befehl:** `pytest tests/processors/test_master_pipeline_error_recovery.py -v -m error_recovery`

| Test | Ergebnis |
|------|----------|
| TestRunSingleStageErrorHandling::test_run_single_stage_processor_exception_returns_error_dict | ❌ FAILED |
| TestFullPipelineErrorHandling::test_full_pipeline_upload_failure_returns_clean_error | ❌ FAILED |
| TestFullPipelineErrorHandling::test_full_pipeline_mid_stage_exception_returns_error | ✅ PASSED |

**Fehler:**
- Ein Test erwartet Fehlertext `'processor boom'`, erhält `"ProcessingContext.__init__() got an unexpected keyword argument 'chunks'"`.
- Ein Test erwartet `'Upload failed'`, erhält `"'NoneType' object has no attribute 'get'"`.
Hinweis: Retry, Idempotenz und Advisory Locks wurden nicht separat ausgeführt (scripts/test_transient_errors.py, test_advisory_locks.py); bei Bedarf manuell mit laufender DB ausführen.

---

## 6. Integration Tests mit Real Services (Schritt 5)

**Befehl:** `pytest backend/tests/integration/test_full_pipeline_integration.py -v -m integration --tb=short`

**Ergebnis:** Conftest-Importfehler – `ModuleNotFoundError: No module named 'services.database_service'` (backend/tests/integration/conftest.py importiert `services.database_service`). Integrationstests wurden nicht ausgeführt. Korrektur: Import auf `backend.services`-Pfad anpassen bzw. PYTHONPATH/Struktur prüfen.

---

## 7. Manuelle CLI-Verifikation (Schritt 6)

Nicht in dieser Session ausgeführt. Empfohlen:

- `python scripts/pipeline_processor.py --file test.pdf --stage upload --verbose`
- `python scripts/pipeline_processor.py --document-id <uuid> --stage text_extraction --verbose`
- `python scripts/pipeline_processor.py --document-id <uuid> --stages 4,5,6 --verbose`
- `python scripts/pipeline_processor.py --document-id <uuid> --status`
- Smart Processing: `python scripts/pipeline_processor.py --document-id <uuid> --smart`

---

## 8. Performance Benchmarks (Schritt 7)

Benchmark wurde nicht ausgeführt (abhängig von PostgreSQL, MinIO, Ollama und vorregistrierten Benchmark-Dokumenten in `krai_system.benchmark_documents`).
Die Datei `benchmark_results_baseline.json` wurde als Vorlage/Platzhalter angelegt (siehe Abschnitt 11). Bei laufender Umgebung:

- `python scripts/select_benchmark_documents.py --count 10`
- `python scripts/run_benchmark.py --count 10 --baseline --verbose`
- `python scripts/run_benchmark.py --count 10 --compare --verbose`

---

## 9. Hardware-Monitoring und Alerts (Schritt 8)

- **performance_service.py:** Metriken und flush_metrics_buffer (mit aggregate_metrics) vorhanden; Korrektur siehe Abschnitt 2.
- **master_pipeline.py / base_processor.py:** Hardware-Monitoring und safe_process() nicht in dieser Verifikation getestet.
- **alert_service.py / krai_system.alerts:** Nicht ausgeführt.
- Scripts: test_advisory_locks.py, test_transient_errors.py nicht ausgeführt.

---

## 10. Test Coverage (Schritt 10)

**Befehl:** `pytest tests/processors/ --cov=backend --cov-report=term-missing --cov-fail-under=0` (mit Ignore der Module mit Importfehlern).

- **Ergebnis:** 363 passed, 107 failed, 93 skipped, 6 errors (Stage-Tracker-PostgreSQL-Adapter-Tests benötigen echte DB).
- **Coverage-Prozent:** In der Ausgabe nicht als einzelne Zeile erfasst; bei Bedarf mit `--cov-report=html` erneut laufen lassen und in `htmlcov/index.html` prüfen. Ziel >80 % für Backend wurde nicht verifiziert.

**Lücken (kurz):**

- Einige Processor-E2E-Tests erwarten Ollama/echte Adapter (Embedding, teils Classification/Metadata).
- Upload-Tests erwarten anderes Fehlerformat (ProcessingError vs. String).
- Integration-Conftest-Import verhindert Integration-Test-Lauf.
- Stage-Tracker-PostgreSQL-Tests benötigen laufendes PostgreSQL.

---

## 11. Performance-Ziele und Benchmark-Vorlage

| Dokumentgröße | Seiten | Ziel Laufzeit | Gemessen | Status |
|---------------|--------|----------------|----------|--------|
| Klein         | 10     | < 30 s        | TBD      | ⏳     |
| Mittel        | 100    | < 2 min       | TBD      | ⏳     |
| Groß          | 1000   | < 15 min      | TBD      | ⏳     |

Die Datei `benchmark_results_baseline.json` enthält die im Plan beschriebene Struktur als Platzhalter; bei durchgeführten Benchmarks Werte aus `run_benchmark.py` eintragen.

---

## 12. Test-Kategorien-Übersicht

| Kategorie         | Testdatei(en)                      | Zweck                          | Status |
|-------------------|------------------------------------|---------------------------------|--------|
| Master Pipeline E2E | test_master_pipeline_e2e.py        | Orchestrierung Vollpipeline     | ⚠️ 2/3 |
| Error Recovery    | test_master_pipeline_error_recovery.py | Retry/Fehlerbehandlung    | ⚠️ 1/3 |
| Processor E2E     | 15 test_*_processor_e2e.py         | Einzelne Stages                 | ⚠️ 66/162 (39 failed, 57 skipped) |
| Integration       | test_full_pipeline_integration.py  | Echte Dienste                   | ❌ Import |
| Performance       | run_benchmark.py                    | Laufzeit-Benchmarks             | ⏳ nicht ausgeführt |
| Manuell CLI       | pipeline_processor.py               | Manuelle Stage-Ausführung        | ⏳ nicht ausgeführt |

---

## 13. Gefundene Probleme und Empfehlungen

**Kritisch / Major**

1. **Integration-Conftest:** `backend/tests/integration/conftest.py` importiert `services.database_service`; Modul nicht gefunden. Import auf `backend.services`-Pfad umstellen (oder Projektwurzel/PYTHONPATH anpassen).
2. **Smart Processing completed_stages:** Ein Master-Pipeline-E2E-Test erwartet, dass alle fehlenden Stages (inkl. svg) in `completed_stages` stehen; aktuell nur classification, storage, embedding. Logik in `process_document_smart_stages` bzw. Testannahme prüfen.
3. **Error-Recovery-Tests:** Erwartete Fehlertexte (z. B. „processor boom“, „Upload failed“) stimmen nicht mit tatsächlichen Exceptions überein; Test-Mocks oder Fehlerbehandlung anpassen.

**Minor**

4. **Upload E2E:** Viele Tests gehen von anderem Rückgabetyp/Fehlerformat aus (ProcessingError vs. String, KeyError file_size_bytes). API/Return-Format vereinheitlichen oder Tests anpassen.
5. **Embedding E2E:** Tests schlagen fehl, wenn Ollama nicht läuft oder Mock-Adapter nicht genug liefert; optional Ollama-Mock oder Skip wenn Ollama nicht erreichbar.
6. **DocumentProcessor / create_database_adapter:** Mehrere Tests können nicht geladen werden (ModuleNotFoundError). Entweder Module wiederherstellen oder Tests aus pytest.ini/Discovery ausschließen und in der Doku vermerken.

**Empfehlung**

- Conftest-Import für Integrationstests korrigieren und Integrationstests erneut laufen lassen.
- Smart-Processing- und Error-Recovery-Tests mit aktuellem Code/Fehlertext abgleichen.
- Benchmark und manuelle CLI-Schritte in einer Umgebung mit PostgreSQL, MinIO und Ollama ausführen und `benchmark_results_baseline.json` sowie diesen Report aktualisieren.

---

## 14. Durchgeführte Code- und Fixture-Änderungen

1. **backend/services/performance_service.py**
   - In `flush_metrics_buffer`: innere Funktion `flush_one` zu `async def flush_one` geändert; Aufrufe `flush_one(...)` zu `await flush_one(...)`. Behebt SyntaxError: `'await' outside async function`.

2. **tests/processors/conftest.py**
   - In `MockDatabaseAdapter` fehlende abstrakte Methoden des `DatabaseAdapter`-ABC ergänzt: `disconnect`, `fetch_one`, `fetch_all`, `insert_chunk`, `insert_table`, `create_unified_embedding`, `insert_link`, `insert_part`, `start_stage`, `complete_stage`, `fail_stage`, `skip_stage`, `get_stage_status`. Ermöglicht Instanziierung von `MockDatabaseAdapter` und Lauf der Master-Pipeline- und Processor-E2E-Tests.

Diese Änderungen sind für die Ausführung der geplanten Verifikation notwendig und können gemeinsam mit dem Report geprüft werden.
