# Embedding and Search Processor Tests

Comprehensive tests for the semantic search stages:

- **EmbeddingProcessor** – generates 768‑dimensional embeddings via an
  Ollama‑style interface, writes to legacy `vw_chunks` and
  `krai_intelligence.chunks.embedding`, supports adaptive batching and similarity search.
- **SearchProcessor** – finalises search indexing by counting records in
  `vw_chunks`, `vw_embeddings`, `vw_links`, `vw_videos`, updating
  document flags, and logging analytics.

The suite focuses on realistic usage patterns using the
`MockDatabaseAdapter` and deterministic embedding services, so **no real
Ollama or PostgreSQL connection is required**.

---

## Test Files

- **`test_embedding_processor_unit.py`**
  Unit tests for `EmbeddingProcessor` internals: configuration and
  status reporting, adaptive batch size logic, the `search_similar`
  helper (RPC parameter construction), and the JSON‑safety helper.

- **`test_embedding_processor_e2e.py`**
  E2E‑style tests for Stage 7 using `E2EEmbeddingProcessor`, a
  test‑only subclass that writes directly into `MockDatabaseAdapter`
  stores instead of Supabase. Verifies that:
  - all chunks in a small batch get embedded,
  - adapter‑side counts (`chunks`, `krai_intelligence.chunks.embedding`, `legacy_embeddings`)
    line up with the reported `embeddings_created`,
  - partial failures are surfaced via `partial_success` and
    `failed_chunks`.

- **`test_search_processor_unit.py`**
  Unit tests for `SearchProcessor` internals and error paths:
  - behaviour when no `database_adapter` is configured,
  - happy‑path record counting against the `MockDatabaseAdapter`
    (`vw_chunks`, `vw_embeddings`, `vw_links`, `vw_videos`),
  - graceful handling when `execute_query` raises.

- **`test_search_processor_e2e.py`**
  E2E‑style tests for the search indexing stage using real
  `SearchProcessor` + `MockDatabaseAdapter`. Stubs
  `SearchAnalytics.log_document_indexed` to avoid `asyncio.run` in tests
  while asserting that the analytics layer receives the same counts as
  the `ProcessingResult` metadata.

- **`test_embedding_quality.py`**
  Embedding‑quality tests built on deterministic embeddings from
  `embedding_quality_metrics` and `sample_embeddings`. Checks
  self‑similarity, relative similarity of related vs. unrelated chunks,
  variance across diverse samples, and basic value‑range sanity.

- **`test_search_relevance.py`**
  High-level relevance smoke tests: uses the same deterministic
  embedding logic as above to rank chunks for a few canonical queries
  (paper jams, network configuration, fuser errors). Asserts that
  top-ranked texts contain the expected phrases.

- **`test_embedding_search_pipeline_e2e.py`**
  Pipeline tests chaining Stage 7 (`E2EEmbeddingProcessor`) and Stage 10
  (`SearchProcessor`) on the same `MockDatabaseAdapter`. Confirms that
  `SearchProcessor` sees the exact chunk/embedding counts produced by
  the embedding stage and that the mock search-readiness snapshot marks
  the document as ready.

- **`test_embedding_storage_integration.py`**
  Integration-style tests that ensure consistency between legacy
  chunk-based embeddings (`chunks`/`legacy_embeddings`) and the new
  `krai_intelligence.chunks.embedding` storage, including similarity-search behaviour via
  the `MockDatabaseAdapter` helpers.

> **Legacy manual tests**: The file
> `tests/processors/test_embedding_processor.py` contains older
> manual/interactive checks (printing to stdout, direct Ollama calls).
> Es ist jetzt explizit per `--ignore=tests/processors/test_embedding_processor.py`
> von normalen Pytest-Läufen ausgeschlossen und dient nur noch als
> manuelles Harness, das bei Bedarf mit
> `python tests/processors/test_embedding_processor.py` ausgeführt
> werden kann.

---

## Running Tests

Alle Processor‑Tests:

```bash
pytest tests/processors/ -v
```

Nur Embedding‑ und Search‑bezogene Tests:

```bash
pytest tests/processors/ -m "embedding or search" -v
```

Nur Embedding‑Tests:

```bash
pytest tests/processors/ -m embedding -v
```

Nur Search‑Tests:

```bash
pytest tests/processors/ -m search -v
```

Qualität/Relevanz separat:

```bash
# Embedding-Qualität
pytest tests/processors/ -m embedding_quality -v

# Search-Relevanz
pytest tests/processors/ -m search_quality -v
```

Spezifische Dateien/Tests:

```bash
pytest tests/processors/test_embedding_processor_unit.py -v
pytest tests/processors/test_search_processor_e2e.py::TestSearchProcessorE2E::test_end_to_end_indexing_with_analytics_stub -v
```

Parallel (mit `pytest-xdist`):

```bash
pytest tests/processors/ -m "embedding or search" -n auto
```

Coverage‑Beispiel:

```bash
pytest tests/processors/ -m "embedding or search" --cov=backend/processors --cov-report=html
```

---

## Fixtures

Wichtige Fixtures aus `tests/processors/conftest.py` für diese Suite:

- **`mock_database_adapter`**
  In‑Memory‑Implementierung von `DatabaseAdapter` mit Stores für
  `documents`, `chunks`, `links`, `videos`, `structured_tables`,
  `krai_intelligence.chunks.embedding`, `legacy_embeddings` u.a. Bietet Helper wie
  `count_chunks_by_document`, `count_embeddings_by_document` und
  `get_document_search_status`.

- **`mock_embedding_service`**
  Deterministischer Embedding‑Generator mit fester Dimension (768). Die
  Methode `_generate_embedding(text)` verwendet einen SHA‑256‑Hash des
  Textes, um pro Testlauf reproduzierbare Vektoren zu liefern.

- **`mock_ollama_service`**
  Kleine Mock‑Ollama‑Klasse mit `generate_embedding(text)`, die für
  Szenarien genutzt werden kann, in denen eine explizite „Ollama“‑API
  simuliert werden soll.

- **`sample_chunks_with_content`**
  Diverser Satz von Text‑Chunks mit realistischen Inhalten (Fehlercodes,
  Teilelisten, Troubleshooting‑Schritte, Spezifikationen, mehrsprachige
  Phrasen, Video/Link‑Kontext). Dient als Grundlage für Embedding‑ und
  Relevanztests.

- **`sample_embeddings`**
  Vorberechnete Embeddings für alle `sample_chunks_with_content` unter
  Verwendung von `mock_embedding_service`. Jede Struktur enthält
  `chunk_id`, `embedding`, `content`, `metadata`.

- **`search_quality_test_data`**
  Kleines Mapping von Beispielqueries auf erwartete Phrasen, das in den
  Search‑Relevanztests zur Interpretation der Rankings genutzt wird.

- **`embedding_quality_metrics`**
  Helferobjekt mit `cosine_similarity`,
  `calculate_embedding_variance(vectors)` und
  `check_embedding_distribution(vec)`, damit Qualitätstests kompakt und
  lesbar bleiben.

Weitere generische Fixtures wie `processing_context`,
`mock_stage_tracker`, `sample_pdf_files` etc. stehen wie in den anderen
Processor‑Suiten zur Verfügung und werden hier dort genutzt, wo sie
sinnvoll sind.

---

## Test Patterns

Die Embedding/Search‑Tests folgen den allgemeinen Patterns der
Processor‑Suiten:

- **Async‑Tests**
  Wo die Produktions‑API async ist (z.B. `SearchProcessor.process`),
  werden `@pytest.mark.asyncio`‑Tests verwendet.

- **Deterministische Embeddings**
  Produktionscode nutzt Ollama; Tests ersetzen `_generate_embedding`
  konsequent durch deterministische Mock‑Services, so dass die Suite
  ohne Netzwerk/Modelle läuft und stabile Asserts auf Similarity und
  Ranking möglich sind.

- **MockDatabaseAdapter als Quelle der Wahrheit**
  E2E‑ und Pipeline‑Tests verlassen sich ausschließlich auf die
  In‑Memory‑Stores des Mock‑Adapters (Chunks, Embeddings, Links, Videos)
  und auf seine Zähl‑Helper. Supabase‑spezifische
  `.table(...).insert()/upsert()`‑Aufrufe werden in Test‑Subklassen
  umgangen.

- **Analytics stubben statt deaktivieren**
  `SearchProcessor` ruft `SearchAnalytics.log_document_indexed` auf.
  Tests ersetzen diese Methode durch einen einfachen Stub, der
  aufgerufene Parameter speichert. So bleibt das Analytics‑Wiring
  getestet, ohne echte Datenbankoperationen oder `asyncio.run` in
  Tests.

- **Fehlertoleranz**
  Mehrere Tests prüfen, dass Fehler (z.B. fehlender Adapter,
  `execute_query`‑Fehler, partiell fehlgeschlagene Embedding‑Stores)
  **nicht** zu ungefangenen Exceptions führen, sondern zu klaren
  Fehl‑ oder Partial‑Ergebnissen.

---

## Markers

Die folgenden pytest‑Marker sind für diese Suite in `pytest.ini`
registriert:

- `@pytest.mark.processor` – Alle Processor‑Tests in diesem Paket.
- `@pytest.mark.embedding` – EmbeddingProcessor‑bezogene Tests.
- `@pytest.mark.search` – SearchProcessor‑bezogene Tests.
- `@pytest.mark.embedding_quality` – explizite Embedding‑Qualitätstests.
- `@pytest.mark.search_quality` – explizite Search‑Relevanztests.

Sie können diese Marker mit `-m` kombinieren, z.B.:

```bash
pytest tests/processors/ -m "embedding and not search" -v
pytest tests/processors/ -m "search and not embedding_quality" -v
```

---

## Plan Coverage und bewusst ausgelassene Szenarien

Die Embedding/Search‑Suite deckt die wichtigsten Happy Paths und
Fehlerfälle der Stages 7 und 10 ab, ist aber bewusst schlank gehalten,
um schnell in CI zu laufen:

- **Abgedeckt**:
  - adaptive Batch‑Logik und Konfigurationsstatus der
    `EmbeddingProcessor`‑Instanz,
  - erfolgreiche Embedding‑Generierung für repräsentative Chunks,
  - partielle Fehler beim Speichern einzelner Embeddings,
  - Konsistenz von Zählerwerten zwischen Embedding‑ und Search‑Stage,
  - grundlegende Embedding‑Qualität (Self‑Similarity, Varianz,
    Similarity‑Vergleiche),
  - grobe Search‑Relevanz für typische Support‑Queries.

- **Bewusst ausgelassen (in dieser Suite)**:
  - echte Ollama‑Netzwerkfehler, Timeout‑Szenarien und
    Reconnect‑Strategien,
  - vollständige Pipeline vom Upload bis zur Suche (dafür existieren
    separate Integrations‑/Performance‑Tests),
  - große Volumen‑ und Latenz‑Benchmarks für Embedding/Search, die eher
    in dedizierte Performance‑Suites gehören.

Neue Szenarien sollten sich entweder nahtlos in diese Suite einfügen
oder – falls sie umfangreiche externe Abhängigkeiten oder lange
Laufzeiten erfordern – in die bestehenden Integrations‑ und
Performance‑Testpfade ausgelagert werden.

---

## Contributing

Beim Erweitern der Embedding/Search‑Tests:

- nutze die bestehenden Fixtures in `conftest.py` (keine eigenen
  Embedded‑Mocks bauen, sofern nicht zwingend nötig),
- halte Tests klein, fokussiert und deterministisch,
- setze Marker (`embedding`, `search`, `embedding_quality`,
  `search_quality`) konsequent,
- beschreibe in Docstrings klar, **warum** der Test existiert
  (Fehlerklasse, Invariante, Regression etc.).

Aktualisiere dieses README, wenn du neue Testdateien oder wesentliche
Szenarien hinzufügst, damit die Suite für zukünftige Arbeiten
nachvollziehbar bleibt.
