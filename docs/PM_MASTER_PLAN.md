# PM-Erweiterung für KRAI – Master-Plan für Cursor

**Projekt:** Kunze & Ritter GmbH – KRAI (Knowledge Retrieval and Intelligence)
**Repo:** https://github.com/Kunze-Ritter/KRAI
**Zeitraum:** 13.05.2026 – 31.12.2026
**Owner:** Tobias Haas
**Förderkontext:** BSFZ Forschungszulage, Vorhabens-ID 926-241-950/2026-1/1 (Erstantrag abgelehnt, Neueinreichung in Vorbereitung)

---

## 0. Wie dieser Plan zu nutzen ist (an Cursor-Claude)

Du bekommst dieses Dokument als Master-Plan für die Predictive-Maintenance-Erweiterung des KRAI-Projekts. Arbeite es **sprintweise** ab. Für jeden Sprint:

1. **Lies zuerst die zugehörige `tasks/pm-sprint-XX-*.md`-Datei** (siehe Sprint-Setup unten). Falls noch nicht vorhanden, lege sie zu Beginn jedes Sprints an, basierend auf dem Sprint-Abschnitt in diesem Plan.
2. **Erkläre den Sprint-Inhalt kurz auf Deutsch**, bevor du mit Code anfängst – Tobias ist domänenstark, aber baut ML-Wissen erst auf. Bei ML-Konzepten (Random Forest, Prophet, MAPE, Stratified Sampling, Few-Shot Learning, etc.): immer ein 3–5-Satz-Briefing bevor du implementierst, mit konkretem Bezug zu unseren Daten.
3. **Halte dich strikt an die existierenden KRAI-Konventionen** (siehe Abschnitt 2 unten).
4. **Schreibe Tests parallel zur Implementierung**, nicht hinterher. Definition of Done (Abschnitt 11) gilt strikt.
5. **Dokumentiere jede methodische Entscheidung als ADR** (`docs/adr/`). Eine Entscheidung pro ADR, kurz: Kontext, Optionen, Entscheidung, Konsequenzen.
6. **Schreibe ein Forschungstagebuch** (`docs/research-log/`) mit Datumsstempel pro Sprint: was wurde versucht, was hat funktioniert, was nicht, was hat das gelehrt. Das ist der **Frascati-Nachweis** für die spätere Forschungszulagen-Prüfung beim Finanzamt – ohne dieses Tagebuch wird die Förderung nicht ausgezahlt.
7. **Frage zurück, wenn unklar.** Nicht halluzinieren. Wenn eine Annahme über die Datenstruktur unsicher ist, lass Tobias prüfen.
8. **Niemals Cloud-Services einbinden.** Local-First ist ein konstitutiver Bestandteil des Antrags (KRITIS-Argument). Keine OpenAI-API, kein AWS, kein GCP, kein HuggingFace-Inference-API. Local Ollama only.

**Wenn du eine Aufgabe abschließt:**
- Commit-Message-Format: `[KRAI-PM] What changed` (passend zur existierenden Konvention `[Component] What was changed`)
- Aktualisiere `tasks/pm-sprint-XX-*.md` mit Stand
- Mache einen kurzen Forschungstagebuch-Eintrag

---

## 1. Ausgangslage und Forschungsziel

### 1.1 Was bereits existiert (Stand 13.05.2026)

KRAI ist eine **multimodale Dokumentenverarbeitungs-Pipeline** mit 16 Stages, lokal lauffähig, mit PostgreSQL+pgvector und Local-LLM (Ollama). Aktuell verarbeitet sie Service-Manuals, extrahiert hierarchische Fehlercodes (8 Hersteller mit aktiver Hierarchie) und stellt eine multimodale Wissensbasis bereit (Text, Bilder, SVG, Tabellen, Videos – alles in einer DB mit Cross-Modal-Linking).

**Was es noch NICHT gibt:** Predictive-Maintenance-Modelle. Das ist der **zentrale F&E-Anteil des Restprojekts** und Gegenstand dieses Plans.

### 1.2 Forschungsfragen (Frascati-konform)

Folgende Forschungsfragen leiten die PM-Erweiterung. Sie sind so formuliert, dass die Antwort *vor Projektstart nicht entscheidbar* ist – das ist das BSFZ-Kriterium „Unwägbarkeit".

**F1 – Verbrauchsmaterial-Wartungsintervall-Prognose (Tier 1):**
Können geräteindividuelle Wartungsintervalle für Verbrauchsmaterialien (Toner, Drum, Fuser, Image Units) aus der Kombination von Hersteller-Sollwerten und tatsächlichen Nutzungsdaten (Zählerstände aus Docuform) mit MAPE < 20 % prognostiziert werden?

**F2 – Bauteilausfall-Anomaliedetektion bei Long-Tail-Datenlage (Tier 2):**
Können Ausfälle nicht-verschleißender Komponenten (Boards, Sensoren, Motoren, Netzteile) mit Recall ≥ 0,60 (Top-X% Risiko-Liste, 30-Tage-Horizont) vorhergesagt werden, wenn über 67 % der dokumentierten Fehlerklassen nur einmalig auftreten?

**F3 – Herstellerübergreifende Generalisierbarkeit:**
Wie stark verschlechtert sich die Modellperformance, wenn ein auf Konica-Minolta-Daten trainiertes Modell auf Lexmark-, HP- oder Kyocera-Daten angewendet wird? Können Transfer-Learning-Strategien (Few-Shot, Embedding-basierte Ähnlichkeitssuche) diese Verschlechterung um mindestens 30 % reduzieren?

**F4 – Multimodale Anreicherung:**
Verbessert die Verknüpfung von Servicetickets mit den existierenden multimodalen Wissensbasis-Inhalten (Service-Manual-Chunks, Fehlerbilder, technische Zeichnungen) die Prognosegenauigkeit gegenüber rein numerischen/tabellarischen Features?

### 1.3 Scope

**In-Scope:**
- Datenintegration Radix-CRM, Docuform-Fleetmanagement, KM-Anfragedatenbank (Office/PP/SOL), KM-Verbrauchsmaterial-Sollwerte
- Tier-1- und Tier-2-Modelle für Konica Minolta als Hauptdatensatz
- Cross-Manufacturer-Validierung gegen Lexmark, HP, Kyocera/UTAX, Fujifilm, Canon (mit Radix-Daten, sobald verfügbar)
- Integration ins existierende KRAI-Datenmodell (neues Schema `krai_pm`)
- Filament-Dashboard-Erweiterung für PM-Visualisierung
- Mobile-App-Integration (Vor-Ort-Anzeige von Wartungsempfehlungen)

**Out-of-Scope:**
- Vollautomatische Ersatzteilbestellung an externen Lieferanten
- Realtime-Stream-Verarbeitung (Sensordaten existieren nicht)
- Marktreife für Kunden außerhalb K&R (nicht förderfähig)
- Eigene Transformer-Architekturen mit > 100M Parametern (Datenmenge zu klein)
- Cloud-AutoML (widerspricht Local-First)

---

## 2. Architektur-Constraints (NICHT VERHANDELBAR)

Diese Regeln sind verbindlich. Bei Konflikt zwischen Implementierungs-Bequemlichkeit und dieser Regel: immer die Regel wählen.

1. **Local-First, KEINE Cloud-Services.** Keine OpenAI-API, keine Cloud-LLMs, kein AWS/GCP. Lokales Ollama für LLM, lokales scikit-learn/PyTorch für ML. Public Model-Hub-Downloads sind erlaubt (Initial-Download, dann lokal).

2. **Strikte Wiederverwendung der existierenden KRAI-Infrastruktur:**
   - Neue Processors erben von `BaseProcessor` (`backend/core/base_processor.py`) und nutzen `safe_process()`.
   - DB-Zugriff über `DatabaseAdapter` (`backend/services/database_adapter.py`), niemals direkte SQL-Verbindungen außerhalb.
   - Correlation-IDs im Format `req_{uuid}.stage_{name}.retry_{n}`.
   - Advisory Locks für Idempotenz (siehe `IdempotencyChecker`).
   - SHA-256 Data-Hashing für Stage-Completion-Marker.
   - Alerts über `AlertService.queue_alert()`, nie direkt.

3. **DB-Schema-Konsistenz:**
   - Neues Schema: `krai_pm` (parallel zu `krai_core`, `krai_intelligence`, etc.).
   - Migrations als sequentielle SQL-Dateien in `database/migrations_postgresql/` (aktuell bei 018, also als 019, 020, 021, ... fortlaufend).
   - Views mit `vw_`-Prefix in `public`.
   - **NIEMALS Spaltennamen erfinden.** Vor jedem DB-Zugriff `DATABASE_SCHEMA.md` konsultieren.

4. **Embedding-Konsistenz:** Wir nutzen `nomic-embed-text` über Ollama, 768-dimensional, konsistent mit `krai_intelligence.chunks.embedding`. Keine andere Embedding-Modelle für PM einführen.

5. **Pipeline-Integration:** PM-spezifische Verarbeitung läuft als neue Stages **nach** der bestehenden 16-Stage-Pipeline, nicht als parallele Pipeline. Stages werden in `master_pipeline.py` registriert. Naming: `TICKET_INGESTION`, `TICKET_NORMALIZATION`, `TICKET_LINKING`, `PM_FEATURE_EXTRACTION`, `PM_PREDICTION`.

6. **Test-First:** Pro neuem Processor mindestens ein Unit-Test mit Mock-DB und ein Integrationstest mit echter PG-Instanz (Docker). Test-Pfade entsprechend `pytest.ini`.

7. **Reproduzierbarkeit:** Alle ML-Experimente werden mit **MLflow** getrackt. Random Seeds explizit setzen (`numpy.random.seed`, `random.seed`, `torch.manual_seed`). Datensplits (Train/Test) versioniert ablegen (Hash der Indizes).

8. **Datenschutz:** Kundendaten aus Docuform und Radix werden vor dem Eintritt in Trainingsdaten pseudonymisiert (Mapping-Tabelle in `krai_pm.entity_mapping`, nur Tobias hat Zugriff). Kein Klartext-Kundenname in MLflow-Logs.

9. **Commit-Konvention:** `[KRAI-PM] What changed` – siehe CLAUDE.md.

10. **Coding-Standards:** ruff, black, mypy, bandit – wie im Repo bereits konfiguriert. Pre-commit-Hook nutzen.

---

## 3. Datenstrategie

### 3.1 Datenquellen-Übersicht

| Quelle | Inhalt | Volumen | Anbindung | Status 13.05.26 |
|---|---|---|---|---|
| **KM-Anfragedetails OF** | Office-Servicefälle | 5.234 Tickets, 2013–2026 | Excel-Import | Verfügbar |
| **KM-Anfragedetails PP** | Production-Servicefälle | 221 Tickets, 2013–2024 | Excel-Import | Verfügbar |
| **KM-Anfragedetails SOL** | Software/Solutions | 992 Tickets | Excel-Import | Verfügbar |
| **KM-Verbrauchsmaterial-Sollwerte** | 88 Modellfamilien, 1.650 Laufzeitwerte | Excel v1.18 | Excel-Import | Verfügbar |
| **Radix CRM (Infominds)** | Tickets über alle Hersteller | mehrere tausend, ab 2019 | SQL-Dump, später API | Dump bei Infominds angefragt |
| **Docuform CSP** | Zählerstände, Verbrauchsfüllstände | Live-Daten pro Gerät | Export, später API | IT-Anfrage gestellt |
| **KRAI-Bestand** | Service-Manuals, Fehlercodes, Bilder | 44 Tabellen | Direkter DB-Zugriff | Verfügbar |

### 3.2 Neues Schema `krai_pm`

Migrations-Reihenfolge (`database/migrations_postgresql/`):

**019_create_krai_pm_schema.sql** – Schema-Erstellung + Basis-Tabellen:

```sql
CREATE SCHEMA IF NOT EXISTS krai_pm;

-- Harmonisierte Servicetickets aus allen Quellen
CREATE TABLE krai_pm.service_tickets (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_system         varchar(50)  NOT NULL,   -- 'radix' | 'docuform' | 'km_anfragen_of' | 'km_anfragen_pp' | 'km_anfragen_sol'
  source_ticket_id      varchar(200) NOT NULL,
  manufacturer_id       uuid REFERENCES krai_core.manufacturers(id),
  product_id            uuid REFERENCES krai_core.products(id),
  model_string_raw      text,                     -- Roh-Modellangabe wenn nicht gemappt
  created_at_source     timestamptz,              -- Erstellungsdatum im Quellsystem
  problem_short         text,
  problem_long          text,
  solution_text         text,
  error_codes           text[],                   -- extrahierte Fehlercodes
  replaced_parts        text[],                   -- erkannte Ersatzteilnummern
  replaced_part_categories text[],                -- normalisierte Kategorien: 'toner', 'drum', 'fuser', 'board', ...
  repair_time_minutes   int,
  ticket_embedding      vector(768),              -- für semantische Ähnlichkeitssuche
  metadata              jsonb,
  ingested_at           timestamptz DEFAULT now(),
  UNIQUE(source_system, source_ticket_id)
);
CREATE INDEX ON krai_pm.service_tickets USING hnsw (ticket_embedding vector_cosine_ops);
CREATE INDEX ON krai_pm.service_tickets (manufacturer_id, created_at_source DESC);
CREATE INDEX ON krai_pm.service_tickets USING gin (error_codes);

-- Hersteller-Sollwerte für Verbrauchsmaterial/Ersatzteile
CREATE TABLE krai_pm.part_lifetimes (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  manufacturer_id       uuid NOT NULL REFERENCES krai_core.manufacturers(id),
  product_id            uuid REFERENCES krai_core.products(id),     -- nullable wenn modellübergreifend
  part_category         varchar(50)  NOT NULL,                       -- 'toner', 'drum', 'fuser', 'transfer_belt', 'pickup_roller', ...
  part_number           varchar(100),
  nominal_lifetime_pages int,                                        -- in tatsächlichen Seiten (NICHT in 1000er)
  color_channel         varchar(10),                                  -- 'K', 'C', 'M', 'Y', null
  source                varchar(50)  NOT NULL,                        -- 'km_excel_v1.18', 'oem_manual', ...
  metadata              jsonb,
  ingested_at           timestamptz DEFAULT now()
);
CREATE INDEX ON krai_pm.part_lifetimes (manufacturer_id, product_id, part_category);

-- Zählerstände und Geräte-Historie aus Docuform
CREATE TABLE krai_pm.device_lifecycle (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_serial_hash    varchar(64)  NOT NULL,    -- SHA-256 der Seriennummer (Pseudonymisierung)
  product_id            uuid REFERENCES krai_core.products(id),
  counter_total         bigint,
  counter_color         bigint,
  counter_bw            bigint,
  measured_at           timestamptz NOT NULL,
  toner_levels          jsonb,                     -- {"K": 75, "C": 60, ...}
  maintenance_events    jsonb,                     -- [{"date": "...", "part_category": "fuser", "action": "replace"}]
  metadata              jsonb,
  ingested_at           timestamptz DEFAULT now()
);
CREATE INDEX ON krai_pm.device_lifecycle (device_serial_hash, measured_at DESC);

-- Modell-Outputs (für Monitoring, Audit, Backtest)
CREATE TABLE krai_pm.predictions (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_serial_hash    varchar(64),
  prediction_type       varchar(50)  NOT NULL,    -- 'wartungsintervall' | 'anomalie' | 'remaining_useful_life'
  target_part_category  varchar(50),
  predicted_event_date  date,
  predicted_remaining_pages int,
  risk_score            float,                     -- 0..1 für Anomaliedetektion
  confidence            float,                     -- 0..1
  model_name            varchar(100) NOT NULL,
  model_version         varchar(50)  NOT NULL,
  mlflow_run_id         varchar(100),
  created_at            timestamptz DEFAULT now(),
  ground_truth_event_date date,                    -- für Backtesting nachträglich gesetzt
  ground_truth_set_at   timestamptz
);
CREATE INDEX ON krai_pm.predictions (device_serial_hash, prediction_type, created_at DESC);
CREATE INDEX ON krai_pm.predictions (model_name, model_version);

-- Pseudonymisierungs-Mapping (zugriffsbeschränkt)
CREATE TABLE krai_pm.entity_mapping (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type           varchar(50)  NOT NULL,    -- 'device_serial' | 'customer' | 'technician'
  raw_value             text         NOT NULL,
  hash_value            varchar(64)  NOT NULL,
  created_at            timestamptz DEFAULT now(),
  UNIQUE(entity_type, hash_value)
);
-- DB-Rechte: Nur ein dedizierter PG-User darf SELECT auf entity_mapping
```

**020_create_krai_pm_views.sql** – Views im `public`-Namespace:

```sql
CREATE OR REPLACE VIEW public.vw_service_tickets AS SELECT * FROM krai_pm.service_tickets;
CREATE OR REPLACE VIEW public.vw_part_lifetimes AS SELECT * FROM krai_pm.part_lifetimes;
CREATE OR REPLACE VIEW public.vw_device_lifecycle AS SELECT * FROM krai_pm.device_lifecycle;
CREATE OR REPLACE VIEW public.vw_predictions AS SELECT * FROM krai_pm.predictions;
```

### 3.3 Pipeline-Erweiterung – neue Stages

Drei neue Stages nach `SEARCH_INDEXING`:

```
... → SEARCH_INDEXING → TICKET_INGESTION → TICKET_NORMALIZATION → TICKET_LINKING
```

Plus zwei „offline" Stages, die zeitgesteuert (nicht pro Dokument) laufen:

- `PM_FEATURE_EXTRACTION` – nightly cron, extrahiert Features aus `service_tickets` + `device_lifecycle`
- `PM_PREDICTION` – nightly cron, berechnet Vorhersagen, schreibt nach `predictions`

Registrierung in `backend/pipeline/master_pipeline.py` (unconditional, siehe CLAUDE.md-Regel: niemals auf None setzen).

---

## 4. Methodenstrategie

### 4.1 Two-Tier-Architektur

**Tier 1 – Verbrauchsmaterial-Wartungsintervall-Prognose (Regression)**

Datenlage: gut. Hersteller-Sollwerte verfügbar, Docuform-Zählerstände verfügbar, klare Ground Truth (Tausch-Datum aus Docuform-Events).

Methoden-Roadmap (eine Phase pro Sprint, siehe Roadmap unten):
1. **Baseline:** Lineare Extrapolation vom Hersteller-Sollwert auf geräteindividuellen Verbrauch
2. **Geräteindividuell:** RandomForest- oder XGBoost-Regression mit Features (Druckvolumen, Farbanteil, Modell, historische Tausch-Intervalle)
3. **Zeitreihen:** Prophet oder ARIMA auf geräteindividuellen Zählerstand-Zeitreihen
4. **Hybrid (falls Zeit reicht):** Stacking von Phase-2- und Phase-3-Output

Zielmetrik: **MAPE < 20 %** auf historischen Tausch-Events (Forschungsfrage F1).

**Tier 2 – Bauteilausfall-Anomaliedetektion (Klassifikation)**

Datenlage: schwierig. Long-Tail (67,6 % Klassen mit < 2 Vorkommen, in KM-Stichprobe gemessen), keine Hersteller-Sollwerte für Elektronik, häufig Freitext-Tickets.

Methoden-Roadmap:
1. **Baseline:** Häufigkeitsbasierte Heuristik – Geräte mit ungewöhnlich vielen Tickets in den letzten 90 Tagen
2. **Klassifikation:** RandomForest auf aggregierten Geräte-Features (Ticket-Frequenz, Fehlercode-Hierarchie-Anteile, Alter, Druckvolumen) mit binärer Ground Truth (Ausfall ja/nein im 30-Tage-Horizont)
3. **Embedding-basiert:** Nutzung der `ticket_embedding`-Vektoren, um ähnliche historische Fälle zu finden → kollektives Risiko-Scoring (Forschungsfrage F4)
4. **LLM-augmentiert (explorativ):** Lokales LLM (Ollama) zur Strukturierung von Freitext-Tickets

Zielmetrik: **Recall ≥ 0,60** bei einer Top-10%-Risiko-Liste, False-Positive-Rate < 30 % (Forschungsfrage F2).

### 4.2 Validierungsstrategie

**Temporal Train-Test-Split:** Training auf Daten bis Datum X, Validierung auf Daten nach X. Mehrere Split-Punkte für Drift-Erkennung.

**Stratifizierung nach Hersteller:** Cross-Manufacturer-Validierung (Forschungsfrage F3). Trainiere nur auf KM, validiere auf Lexmark/HP/Kyocera-Tickets (sobald Radix-Dump verfügbar).

**Manuelle Plausibilitätsprüfung:** Top-10-Predictions pro Woche werden im Filament-Dashboard angezeigt und können von Servicetechnikern bewertet werden (Feedback-Mechanismus existiert in `krai_intelligence.feedback`).

### 4.3 Tooling-Stack (NEU als requirements.txt-Erweiterung)

Bewusst pragmatisch, konsistent mit Python 3.11:

```
scikit-learn>=1.4,<2.0
xgboost>=2.0,<3.0
prophet>=1.1,<2.0
statsmodels>=0.14,<1.0
mlflow>=2.10,<3.0
pandas>=2.1,<3.0
numpy>=1.26,<2.0
```

NICHT auf der Liste (explizite Begründungen):
- **TensorFlow / Keras** – zu groß für unsere Datenmenge, scikit-learn reicht
- **HuggingFace `transformers` für Trainingsmodelle** – Datenmenge zu klein für sinnvolles Fine-Tuning
- **sktime** – Prophet/statsmodels reicht für Forschungsfrage F1
- **Cloud-AutoML** – widerspricht Local-First

Bei Bedarf später (begründet): PyTorch für LSTM, falls Prophet/ARIMA an seine Grenzen kommt. Erst dann hinzufügen, mit eigenem ADR.

---

## 5. Roadmap – 8 Sprints à 2 Wochen

Jeder Sprint hat eine eigene `tasks/pm-sprint-XX-NAME.md`-Datei mit Detail-Aufgaben. Hier nur Überblick + Definition of Done.

### Sprint 1 (KW 21–22, 19.05.–01.06.) – Datenfundament

**Ziel:** PM-Schema steht, KM-Excel-Daten sind importiert, Datenexplorations-Bericht liegt vor.

**Aufgaben:**
- Migration 019 (Schema `krai_pm`) und 020 (Views) erstellen, lokal testen
- Excel-Importer für KM-Anfragedetails (OF, PP, SOL) als `backend/processors/ticket_ingestion_processor.py`
- Excel-Importer für KM-Verbrauchsmaterial-Sollwerte als `backend/processors/part_lifetimes_importer.py`
- Jupyter-Notebook unter `examples/pm/01_data_exploration.ipynb` mit:
  - Verteilungen, fehlende Werte, Plausibilität
  - Long-Tail-Visualisierung
  - Replikation der Zahlen aus dem Briefing (67,6 %, 19,1 %)
- Forschungstagebuch-Eintrag

**Definition of Done:**
- Migrations 019/020 laufen sauber `docker-compose -f docker-compose.simple.yml exec postgres ...`
- Mindestens 6.000 Tickets in `krai_pm.service_tickets`
- Mindestens 1.500 Einträge in `krai_pm.part_lifetimes`
- Unit-Tests für beide Importer (Mock-Excel + Mock-DB), grün
- Notebook reproduziert die Briefing-Zahlen
- ADR-001 (warum eigenes Schema, nicht in `krai_intelligence`)
- ADR-002 (warum SHA-256-Pseudonymisierung der Geräte-Seriennummern)

### Sprint 2 (KW 23–24, 02.06.–15.06.) – Ticket-Harmonisierung

**Ziel:** Tickets sind normalisiert (Modelle, Fehlercodes, Ersatzteile) und semantisch eingebettet.

**Aufgaben:**
- `backend/processors/ticket_normalization_processor.py`:
  - Modell-String → `product_id` mit Fuzzy-Matching gegen `krai_core.products`
  - Fehlercodes via existierender `ErrorCodeExtractor` aus Lösungstext extrahieren
  - Ersatzteilnummern via Regex (Hersteller-spezifisch) extrahieren
  - Bauteilkategorien normalisieren (siehe Briefing-Tabelle: Festplatte, Motor, Netzteil, Toner, Drum, Fuser, ...)
- `backend/processors/ticket_linking_processor.py`:
  - Embedding-Generierung pro Ticket via Ollama `nomic-embed-text`
  - Ticket → Manual-Chunks via Vector Similarity (Top-5)
  - Ticket → Fehlercode-Hierarchie via exact match
- Stages in `master_pipeline.py` registrieren

**Definition of Done:**
- ≥ 70 % der KM-Tickets haben gemappte `product_id`
- ≥ 60 % der Tickets mit Fehlercode-Erwähnung haben `error_codes`-Array gefüllt
- ≥ 50 % der Tickets mit Tausch-Aktion haben `replaced_part_categories` gefüllt
- Stichprobe (n=50): manuelle Validierung der Linkings, ≥ 80 % Treffer-Genauigkeit
- Integrationstest mit echter PG-Instanz, grün

### Sprint 3 (KW 25–26, 16.06.–29.06.) – Tier-1 Baseline

**Ziel:** Erstes funktionierendes PM-Modell für Toner-Wartungsintervall-Prognose.

**Aufgaben:**
- **Konzept-Briefing für Tobias:** Lineare Extrapolation, Regression, MAPE – was bedeutet das, was ist der Tradeoff?
- Docuform-Importer als `backend/processors/docuform_importer.py` (mit Pseudonymisierung der Seriennummern). Falls Docuform-Daten noch nicht verfügbar: Mock-Generator mit synthetischen, aber plausiblen Daten unter `tests/fixtures/docuform_mock.py`
- Tier-1 Phase 1: `backend/pm/models/toner_linear_baseline.py`
- Tier-1 Phase 2: `backend/pm/models/toner_random_forest.py`
- MLflow-Setup (`docker-compose.simple.yml` erweitern, separate Compose-Datei `docker-compose.mlflow.yml`)
- Backtest-Skript `scripts/pm/backtest_tier1.py` mit Temporal Split
- Ergebnisdokumentation als Notebook `examples/pm/03_tier1_baseline.ipynb`

**Definition of Done:**
- Beide Modelle lauffähig, in MLflow getrackt
- Backtest auf historischen Daten ergibt MAPE-Werte (Wert egal, Hauptsache messbar und reproduzierbar)
- Mindestens drei Modell-Runs in MLflow vergleichbar
- ADR-003 (Wahl scikit-learn-RandomForest statt XGBoost als Phase-2-Modell, mit Begründung)
- Forschungstagebuch-Eintrag: was hat funktioniert, was nicht, was hat das gelehrt

### Sprint 4 (KW 27–28, 30.06.–13.07.) – Tier-1 Zeitreihen + Tier-2 Baseline

**Ziel:** Zeitreihen-Methoden für Tier 1 evaluiert, Tier-2 Baseline lauffähig.

**Aufgaben:**
- **Konzept-Briefing für Tobias:** Prophet, ARIMA, Saisonalität, Trend, Anomalie vs. Klassifikation
- Tier-1 Phase 3: `backend/pm/models/toner_prophet.py`
- Tier-2 Phase 1 (Heuristik): `backend/pm/models/anomaly_frequency_heuristic.py`
- Tier-2 Phase 2 (RandomForest-Klassifikation): `backend/pm/models/anomaly_random_forest.py`
- Erweiterung Tier-1 auf Drum und Fuser (gleiche Methodik, andere Bauteilkategorie)
- Vergleichs-Notebook `examples/pm/04_tier1_methods_comparison.ipynb`

**Definition of Done:**
- Drei Tier-1-Methoden für drei Bauteilklassen (Toner, Drum, Fuser) im Vergleich
- Tier-2 mit binärer Ground Truth lauffähig
- ADR-004 (Prophet vs. ARIMA – welches Modell wann?)
- Forschungstagebuch: Welche Phase ist die beste für welche Bauteilklasse?

### Sprint 5 (KW 29–30, 14.07.–27.07.) – Filament Dashboard Integration

**Ziel:** PM-Predictions sind im Dashboard sichtbar, Techniker können Feedback geben.

**Aufgaben:**
- Filament-Resources für `krai_pm.predictions` und `krai_pm.device_lifecycle` in `laravel-admin/`
- Dashboard-Widget: „Top-10 Geräte mit Wartungsbedarf (nächste 30 Tage)"
- Dashboard-Widget: „Anomalie-Risiko-Liste"
- Recharts-basierte Visualisierung von Verbrauchsprognosen pro Gerät mit Konfidenzbändern
- Feedback-Mechanismus: Techniker bestätigt/widerlegt Prognose, schreibt in `krai_intelligence.feedback`
- E2E-Test (Playwright oder ähnliches, falls bereits im Repo)

**Definition of Done:**
- PM-Dashboard erreichbar unter `http://localhost:80/admin/pm`
- Predictions werden mit Konfidenz und Begründung angezeigt
- Feedback wird persistiert, fließt in spätere Trainings zurück
- ADR-005 (UI-Design-Prinzipien für PM-Anzeige)

### Sprint 6 (KW 31–34, 28.07.–24.08.) – Tier-2 Embedding-Forschung + Cross-Manufacturer

**Ziel:** Embedding-basierte Anomaliedetektion + Cross-Manufacturer-Validierung.

Dieser Sprint ist **4 Wochen** lang, weil hier der Hauptforschungsanteil steckt. Auch der Sommerurlaub kann hier liegen.

**Aufgaben:**
- Tier-2 Phase 3: `backend/pm/models/anomaly_embedding_similarity.py`
  - Für jedes Gerät: aggregiere Embeddings seiner Tickets der letzten N Tage
  - Finde k-nächste Nachbarn in Trainings-Embeddings, deren Ausfall bereits passiert ist
  - Score = Anteil der Nachbarn mit dokumentiertem Ausfall im 30-Tage-Folgefenster
- Cross-Manufacturer-Validierung **sobald Radix-Dump verfügbar**:
  - Datenimport Radix → `service_tickets`-Tabelle
  - Auswertung: Long-Tail-Verteilung pro Hersteller (replizieren wir die KM-Befunde?)
  - Train on KM, test on Lexmark/HP/Kyocera → Performance-Drop quantifizieren
- Falls Radix-Dump nicht verfügbar: Cross-Validation **nur innerhalb KM** zwischen Modellfamilien (ZEUS vs. EAGLE etc.) als Vorab-Studie
- LLM-augmentierte Strukturierung von Freitext-Tickets (explorativ): `backend/pm/processors/freetext_structuring.py` mit lokalem Ollama-LLM (z.B. `llama3.1:8b`)

**Definition of Done:**
- Embedding-basiertes Tier-2-Modell trainiert und evaluiert
- Performance-Tabelle: pro Modell × pro Hersteller, mit Recall@10% und FPR
- ADR-006 (Embedding-Ähnlichkeit als Few-Shot-Approximation – wissenschaftliche Begründung)
- Forschungstagebuch: zentrale Frage – konnte F3 (Generalisierbarkeit) bestätigt werden?

### Sprint 7 (KW 35–38, 25.08.–21.09.) – Mobile + Production-Hardening

**Ziel:** Vor-Ort-Anzeige von Wartungsempfehlungen, Production-Setup.

**Aufgaben:**
- Mobile-API-Endpunkte unter `backend/api/routes/pm.py`:
  - `GET /pm/devices/{serial_hash}/predictions` – aktuelle Prognosen für ein Gerät
  - `POST /pm/predictions/{id}/feedback` – Techniker-Feedback
- Mobile-App-Anbindung (falls native App existiert; falls nicht: PWA-Variante des Filament-Dashboards)
- Rate-Limiting, Authentifizierung über existierende Middleware
- Performance-Tests: p50/p95/p99 für Prediction-API-Aufrufe
- Sicherheits-Hardening: Bandit-Scan, Pen-Test-Checkliste durchgehen
- Deployment-Setup für Production-Compose

**Definition of Done:**
- Mobile-Workflow lauffähig: Techniker scannt Gerät vor Ort → sieht Top-3-Wartungsempfehlungen + Ersatzteilverfügbarkeit
- p95 < 500 ms für Prediction-API
- Bandit-Scan ohne Critical-Findings
- ADR-007 (PWA vs. native App, Begründung)

### Sprint 8 (KW 39–43, 22.09.–26.10.) + Puffer bis 31.12. – Finale Evaluation + Dokumentation

**Ziel:** Forschungsbericht, BSFZ-Verwendungsnachweis-Material, Lessons Learned.

**Aufgaben:**
- Vollständige Evaluation gegen Hold-out-Test-Set:
  - Tier 1: MAPE pro Bauteilklasse pro Hersteller
  - Tier 2: Recall, Precision, F1 pro Hersteller
  - Cross-Manufacturer-Generalisierung: Performance-Drop quantifizieren
- Forschungsbericht `docs/research-report/KRAI-PM-Final-Report.md`:
  - Forschungsfragen F1–F4 mit Befund
  - Methoden-Vergleich
  - Limitationen
  - Empfehlungen für Phase 2 (nach Förderzeitraum)
- Frascati-Konformitäts-Checkliste (siehe Abschnitt 12)
- Aufbereitung für BSFZ-Verwendungsnachweis: Stundenzettel, Git-Commit-Historie, ADRs, Forschungstagebuch als Anlage-Pack
- **Puffer** für ungeplante Probleme bis 31.12.2026

**Definition of Done:**
- Forschungsbericht abgeschlossen, mit Tobias und Judith abgestimmt
- BSFZ-Anlage-Pack vorbereitet
- Code im Repo, Tests grün, Coverage > 70 % für `backend/pm/`
- Demo-Video (5 Min, lokal aufgenommen) zeigt End-to-End-Workflow

---

## 6. Sprint-Setup für Cursor-Claude

**Bevor du mit einem Sprint anfängst:**

1. Erstelle `tasks/pm-sprint-XX-NAME.md` (XX = Sprint-Nummer, NAME = Kurzname, z.B. `pm-sprint-01-datenfundament.md`).
2. Inhalt der Datei:
   - Sprint-Ziel
   - Definition of Done (aus diesem Master-Plan)
   - Detail-Aufgaben als Checkliste (du brichst die Sprint-Aufgaben aus diesem Plan in einzelne Implementierungs-Schritte herunter)
   - Forschungsfragen, die dieser Sprint adressiert (F1/F2/F3/F4)
   - Risiken/Unsicherheiten für diesen Sprint
3. Bei jedem Bearbeitungsschritt: Checkbox abhaken, Commit machen.

**Wenn ein Sprint blockiert ist** (z.B. weil Radix-Dump fehlt):
- Dokumentiere die Blockade in der Sprint-Datei
- Schaue, welche Aufgaben *unabhängig* erledigt werden können
- Beginne mit denen, lass die blockierten offen
- Sprich Tobias auf die Blockade an

---

## 7. Branching-Strategie

- `master` – stabil, läuft in Production
- `feature/pm-foundation` – Sprint-1-Sammelbranch (eröffnet von dir gleich zu Beginn)
- `feature/pm-sprintXX-AUFGABE` – pro Aufgabe ein eigener Branch von `feature/pm-foundation`
- Merge in `feature/pm-foundation` per PR (Self-Review reicht, da kleines Team), bei größeren Meilensteinen Merge nach `master`
- Niemals direkt nach `master` committen

---

## 8. Verzeichnis-Struktur (NEU)

Folgende Verzeichnisse werden im Laufe der Sprints angelegt – konsistent zur bestehenden Struktur:

```
backend/
  processors/
    ticket_ingestion_processor.py        # neu, Sprint 1
    ticket_normalization_processor.py    # neu, Sprint 2
    ticket_linking_processor.py          # neu, Sprint 2
    docuform_importer.py                 # neu, Sprint 3
    part_lifetimes_importer.py           # neu, Sprint 1
  pm/                                    # neu (gesamtes Unterverzeichnis), Sprint 3
    __init__.py
    models/
      __init__.py
      toner_linear_baseline.py           # Sprint 3
      toner_random_forest.py             # Sprint 3
      toner_prophet.py                   # Sprint 4
      drum_random_forest.py              # Sprint 4
      fuser_random_forest.py             # Sprint 4
      anomaly_frequency_heuristic.py     # Sprint 4
      anomaly_random_forest.py           # Sprint 4
      anomaly_embedding_similarity.py    # Sprint 6
    features/
      __init__.py
      device_aggregation.py              # Sprint 4
      ticket_aggregation.py              # Sprint 4
      consumption_features.py            # Sprint 3
    evaluation/
      __init__.py
      backtest.py                        # Sprint 3
      cross_manufacturer.py              # Sprint 6
      metrics.py                         # Sprint 3 (MAPE, Recall@K)
    processors/
      __init__.py
      freetext_structuring.py            # Sprint 6, optional
  api/
    routes/
      pm.py                              # neu, Sprint 7
database/
  migrations_postgresql/
    019_create_krai_pm_schema.sql         # Sprint 1
    020_create_krai_pm_views.sql          # Sprint 1
    021_add_pm_indexes.sql               # nach Bedarf
docs/
  adr/                                   # neu
    001-eigenes-pm-schema.md             # Sprint 1
    002-pseudonymisierung-geraete.md     # Sprint 1
    003-randomforest-statt-xgboost.md    # Sprint 3
    004-prophet-vs-arima.md              # Sprint 4
    005-pm-dashboard-design.md           # Sprint 5
    006-embedding-fewshot.md             # Sprint 6
    007-pwa-vs-native.md                 # Sprint 7
  research-log/                          # neu
    2026-05-XX_sprint01_start.md
    2026-05-XX_sprint01_close.md
    ...
  research-report/                       # neu
    KRAI-PM-Final-Report.md              # Sprint 8
examples/
  pm/                                    # neu
    01_data_exploration.ipynb            # Sprint 1
    02_ticket_harmonization_qa.ipynb     # Sprint 2
    03_tier1_baseline.ipynb              # Sprint 3
    04_tier1_methods_comparison.ipynb    # Sprint 4
    05_tier2_anomaly_methods.ipynb       # Sprint 6
    06_cross_manufacturer.ipynb          # Sprint 6
backend/tests/
  pm/                                    # neu
    test_ticket_ingestion.py
    test_ticket_normalization.py
    test_models_tier1.py
    test_models_tier2.py
    test_evaluation_metrics.py
tasks/
  pm-sprint-01-datenfundament.md         # Sprint 1
  pm-sprint-02-ticket-harmonisierung.md  # Sprint 2
  ...
scripts/pm/
  backtest_tier1.py                      # Sprint 3
  backtest_tier2.py                      # Sprint 4
  cross_manufacturer_eval.py             # Sprint 6
  generate_mlflow_report.py              # Sprint 8
```

---

## 9. ML-Konzepte – Pflicht-Briefings

Bevor du eine dieser Methoden zum ersten Mal implementierst, musst du Tobias ein **kurzes deutsches Briefing** geben (3–5 Sätze). Format:

> **Konzept:** XYZ
> **Was es macht:** ...
> **Warum hier sinnvoll:** ... (Bezug zu unseren Daten)
> **Tradeoffs / Limitationen:** ...
> **Quelle für Vertiefung:** ... (Link zu scikit-learn-Doku oder Paper)

Pflicht-Briefings:

- Random Forest (Sprint 3)
- MAPE und warum nicht RMSE (Sprint 3)
- Temporal Train-Test-Split vs. zufälliger Split (Sprint 3)
- MLflow-Konzept (Tracking, Runs, Experiments) (Sprint 3)
- Prophet (Sprint 4)
- ARIMA und warum Prophet meistens praktischer ist (Sprint 4)
- Klassifikations-Metriken Recall/Precision/F1 (Sprint 4)
- Embedding-basierte Ähnlichkeitssuche (Sprint 6)
- Cross-Validation und ihre Tücken bei Zeitreihen (Sprint 6)

---

## 10. Datenschutz & Compliance

1. **DSGVO-Pseudonymisierung:** Geräteseriennummern und Kundennamen aus Docuform werden vor Eintritt in Trainingsdaten via SHA-256 gehasht. Mapping nur in `krai_pm.entity_mapping` (zugriffsbeschränkt).
2. **Keine personenbezogenen Daten in MLflow:** MLflow-Logs enthalten nur gehashte IDs und numerische Features.
3. **Auftragsverarbeitungsvertrag** mit Infominds (Radix) und Docuform-Anbieter prüfen, bevor produktive Auswertung läuft (Tobias-Aufgabe, nicht Cursor-Claude).
4. **Audit-Trail:** Jede Prediction wird mit MLflow-Run-ID, Modellversion und Erstellungszeitpunkt persistiert. Niemals stille Modell-Wechsel.
5. **KRITIS-Argument:** Local-First ist kein Marketing-Element, sondern Förderkriterium. Jeder Cloud-Aufruf ist ein Compliance-Bruch.

---

## 11. Definition of Done (übergreifend)

Eine Aufgabe ist erst „done", wenn:

- [ ] Code geschrieben und in einem Feature-Branch committet
- [ ] Unit-Tests vorhanden, lokal grün (`pytest backend/tests/pm/test_XXX.py -v`)
- [ ] Integrationstest (falls relevant) gegen lokale PG-Instanz grün
- [ ] Linter sauber (`ruff check`, `black --check`, `mypy`)
- [ ] Wenn ML-Komponente: MLflow-Run vorhanden
- [ ] Wenn DB-Änderung: Migration sauber, rollback-fähig getestet
- [ ] Wenn neue Methode: Konzept-Briefing für Tobias geschrieben
- [ ] Bei strategischen Entscheidungen: ADR geschrieben
- [ ] Forschungstagebuch-Eintrag bei Sprint-Abschluss
- [ ] Commit-Message im Format `[KRAI-PM] What changed`
- [ ] PR-Description erklärt was, warum, wie getestet

---

## 12. Frascati-Konformität (Checkliste für BSFZ-Verwendungsnachweis)

Diese Checkliste wird bei Sprint 8 final abgehakt. Jeder Punkt muss am Ende belegbar sein – sonst Probleme bei der Forschungszulagen-Prüfung.

- [ ] **Neuartig:** Es gibt einen dokumentierten Vergleich zum Stand der Technik (cloudbasierte herstellergebundene Lösungen). Eigene Innovation: hierarchische Multi-Manufacturer-Fehlercode-Extraktion + Two-Tier-PM-Methodik unter Long-Tail-Bedingungen.
- [ ] **Schöpferisch:** Mindestens zwei eigene methodische Ansätze sind dokumentiert (z.B. Two-Tier-Architektur, Embedding-basierte Few-Shot-Anomaliedetektion).
- [ ] **Ungewiss:** Forschungsfragen F1–F4 sind dokumentiert, mit Antwort am Ende: was ist gelungen, was nicht, was haben wir gelernt. Ein Teilziel darf scheitern – das ist genau das Förderkriterium.
- [ ] **Systematisch:** Sprintplan, ADRs, MLflow-Logs, Forschungstagebuch zeigen reproduzierbares Vorgehen.
- [ ] **Übertragbar:** Code im Repo, Datenmodell erweiterbar auf weitere Hersteller, Methoden dokumentiert.

---

## 13. Was Tobias macht, was Cursor-Claude macht

**Tobias:**
- IT-Anfragen weiterverfolgen (Radix-Dump, Docuform-Export)
- Mit Judith (Leyton) abstimmen, sobald Antrag genehmigt
- Strategische Entscheidungen bei Konflikt zwischen Aufwand und wissenschaftlichem Anspruch
- Stundenzettel führen (BSFZ-Pflicht)
- ADRs gegenlesen
- Manuelle Plausibilitätsprüfung von Predictions (Stichproben)

**Cursor-Claude:**
- Implementierung gemäß diesem Plan
- ADR-Entwürfe schreiben, Tobias gegenlesen lassen
- Konzept-Briefings auf Deutsch
- Forschungstagebuch-Einträge
- Tests, MLflow-Tracking, Validierungen
- Bei Unklarheit: zurückfragen, nicht halluzinieren

---

## 14. Quick-Start für Cursor-Claude

Wenn du mit der Arbeit beginnst:

1. Lege Branch an: `git checkout -b feature/pm-foundation`
2. Lege Verzeichnisse an: `docs/adr/`, `docs/research-log/`, `docs/research-report/`, `examples/pm/`, `backend/pm/` (mit `__init__.py`)
3. Lege `tasks/pm-sprint-01-datenfundament.md` an (Inhalt: Sprint-1-Aufgaben aus diesem Plan)
4. Lege `docs/research-log/2026-05-19_sprint01_kickoff.md` an mit Datum, Ausgangslage, Zielen
5. **Erster Commit:** `[KRAI-PM] Setup: PM extension structure for sprint 1 (foundation)`
6. Dann mit Sprint 1, Aufgabe 1 starten.

Bei Fragen zu diesem Plan: stoppe und frage Tobias, bevor du anfängst zu raten.

---

**Ende des Master-Plans. Stand 13.05.2026.**
