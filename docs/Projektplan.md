 # KRAI / Manual2Vector – Projektplan

 ## 1. Einordnung & Vision

 KRAI (Knowledge Retrieval and Intelligence) / Manual2Vector ist eine **lokal-first Multimodal-AI-Plattform** zur Verarbeitung technischer Dokumentation (Handbücher, Service-Guides, Datenblätter, Videos) mit Fokus auf:

 - **Schnelles Auffinden** relevanter Stellen (z. B. Fehlercodes, Wartungsschritte, Ersatzteile)
 - **Multimodale Aufbereitung** von Text, Bildern, Tabellen, SVG-Grafiken und Videos
 - **Lokale Datenhoheit** (PostgreSQL + MinIO + Ollama auf eigener Infrastruktur)
 - **Erweiterbarkeit** für neue Hersteller, Produkte, Dokumenttypen und Integrationen

 Zielgruppe sind Service-Organisationen, Techniker, Support-Teams und OEM-Partner, die komplexe technische Inhalte effizient nutzen möchten.

 ---

 ## 2. Projektziele

 ### 2.1 Produktziele

 - **Z1 – Schneller Zugriff auf Wissen**
   Häufige Service-Fragen (z. B. Fehlercodes, typische Störungen) sollen innerhalb von Sekunden beantwortbar sein.

 - **Z2 – Multimodale Suche**
   Anwender können nicht nur nach Text, sondern auch nach **Bildern, Diagrammen, Tabellen, Videos** und strukturierten Entitäten (Fehlercodes, Produkte) suchen.

 - **Z3 – Hersteller- & Modell-Normalisierung**
   Unterschiedliche Bezeichnungen, Schreibweisen und Serien eines Herstellers werden zusammengeführt, damit Suchanfragen robust sind.

 - **Z4 – Lokale Compliance & Datensouveränität**
   Alle Daten laufen über eine **lokale Infrastruktur** (Docker, PostgreSQL, MinIO, Ollama). Externe Cloud-Modelle sind optional.

 - **Z5 – Erweiterbarkeit & OEM-Integration**
   Die Plattform ist modular aufgebaut (APIs, Pipelines, Adapter), sodass **OEM-Partnerschaften** und kundenspezifische Erweiterungen schnell umgesetzt werden können.

 ### 2.2 Technische Ziele

 - **T1 – Robuste Pipeline** für PDF/HTML/Video-Verarbeitung mit klaren Stages, Fehlerhandling und Monitoring
 - **T2 – Saubere Datenbasis** in PostgreSQL (pgvector) mit normalisierten Strukturen für Produkte, Fehlercodes, Dokumente
 - **T3 – Hohe Testabdeckung** (Unit, Integration, E2E) für Kernfunktionen (Ingestion, Suche, Auth, Dashboard)
 - **T4 – Security by Design** (Rate-Limits, RBAC, API Keys, Validierung) gemäß `docs/SECURITY.md`
 - **T5 – Betriebssichere Docker-Stacks** für lokale Entwicklung, Test, Produktion inkl. Health-Checks

 ### 2.3 Business-Ziele

 - **B1 – Reduktion der Suchzeit** für Techniker (z. B. 50 % weniger Zeit für die Beantwortung von Standardanfragen)
 - **B2 – Bessere Erstlösungsquote** im Support durch schnell auffindbare, strukturierte Fehler-/Lösungsinformationen
 - **B3 – Grundlage für OEM-Partnerschaften** mit klaren APIs, Datenmodellen und Integrationspfaden

 ---

 ## 3. Projektumfang (Scope)

 ### 3.1 Im Scope

 - **Dokumenten-Ingestion**
   - Upload von PDFs und verwandten Dokumenttypen über API
   - Speicherung der Original-Dateien in MinIO (S3-kompatibel)
   - Metadaten-Extraktion (Titel, Hersteller, Modell, Serien, Sprache usw.)

 - **Verarbeitungspipeline (Backend)**
   - Smart Chunking (hierarchische Struktur, Fehlercode-Grenzen)
   - Text-, Bild-, Tabellen-, SVG- und Link-Extraktion
   - Embedding-Generierung für semantische Suche (pgvector)
   - Hersteller-/Modell- und Fehlercode-Extraktion

 - **Such- & Content-APIs**
   - Dokument-/Chunk-Suche (semantisch + Filter)
   - Produktsuche, Fehlersuche, Video-/Bild-APIs
   - Agent-/Pipeline-APIs für fortgeschrittene Workflows

 - **Dashboard-Frontend**
   - Übersicht über Systemstatus, Queues, letzte Dokumente
   - CRUD-Views für Dokumente, Produkte, Hersteller, Fehlercodes, Videos
   - Admin-Funktionen (API Keys, Benutzer/Rollen perspektivisch)

 - **Security & Operations**
   - Rate-Limits (SlowAPI), Request-Validation, Security-Header, CORS
   - API-Key-Management inkl. Rotation & Audit
   - Logging, Health-Checks, Metriken & Monitoring-Endpunkte

 ### 3.2 Außerhalb des Scopes (aktuell)

 - Vollautomatisches OEM-spezifisches Ticketing / CRM-Integration (nur vorbereitete APIs/Webhooks)
 - Vollständig automatisierte Cloud-Multi-Tenant-Plattform (Fokus aktuell: On-Prem/Single Tenant)
 - Native Mobile Apps (perspektivisch)
 - Generelle Endkunden-Self-Service-Portale (Fokus: B2B/OEM & interne Nutzung)

 ---

 ## 4. Stakeholder & Rollen

 - **Produktverantwortliche / Business Owner**
   Definieren Ziele, Prioritäten, OEM-Fokus, Go-to-Market-Strategie.

- **Tech Lead / Architektur**
  Verantwortlich für System-Design, Tech-Stack, Security- und Skalierungsentscheidungen.

- **Backend-Team**
  Implementiert APIs, Datenmodelle, Pipelines, Integrationen mit PostgreSQL/MinIO/Ollama.

- **Dashboard-Team**
  Entwickelt das Laravel/Filament-Dashboard, UX, E2E-Tests und API-Integration.

- **DevOps / Infrastruktur**
  Verantwortlich für Docker-Compose-Stacks, Monitoring, Backups, Produktions-Deployments.

- **Qualitätssicherung / Testing**
  Pflege von Unit-, Integrations- und E2E-Tests, Testdaten und Test-Skripten.
   Pflege von Unit-, Integrations- und E2E-Tests, Testdaten und Test-Skripten.

 - **OEM-Partner / Pilotkunden**
   Stellen Beispiel-Daten zur Verfügung, validieren UX & Ergebnisqualität, definieren Integrationsanforderungen.

 ---

 ## 5. Systemüberblick (Kurzfassung)

 Die detaillierte Architektur ist in `docs/ARCHITECTURE.md` beschrieben. Kurzüberblick:

 - **Dashboard-Layer (Laravel/Filament)**
   Laravel/Filament-Dashboard + API-Zugriff

 - **Service-Layer (FastAPI)**
   Dokument-, Such-, Pipeline-, Agent-, Admin-, Auth- und File-Upload-APIs

 - **Processing-Layer**
   Master-Pipeline mit Stages für Text, Bilder, SVG, Tabellen, Kontexte, Embeddings

 - **Daten-/Infrastruktur-Layer**
   PostgreSQL (pgvector), MinIO (S3), Ollama, Redis (optional), Docker + Nginx

 - **Security & Observability**
   Rate-Limits, Request-Validation, RBAC, API Keys, Logging, Metriken, Health-Checks

 ---

 ## 6. Technologie-Stack

 ### 6.1 Backend

 - **Framework:** FastAPI (Python 3.11+)
 - **Server:** Uvicorn mit Security-/Performance-Tuning (`UVICORN_*` Variablen)
 - **Struktur:** Monorepo mit modularen Services (`backend/api`, `backend/services`, `backend/models`)

 ### 6.2 Dashboard

 - **Framework:** Laravel 12+ mit Filament 3+
 - **UI Components:** Livewire, Alpine.js
 - **UI:** Moderne Admin-Oberfläche mit Filament-Komponenten

 ### 6.3 Datenbank & Storage

 - **PostgreSQL 15+** mit **pgvector** für Embeddings & semantische Suche
 - **Schemas:** `krai_core`, `krai_intelligence`, `krai_parts`, `krai_system`, `krai_users` (Details: `DATABASE_SCHEMA.md`)
 - **Object Storage:** MinIO (S3-kompatibel) für Dokumente, Bilder, Videos, SVGs

 ### 6.4 AI / ML

 - **Ollama** als lokaler AI-Service (Text, Embeddings, Vision-Modelle)
 - Konfigurierbare Modelle per `.env` (`AI_TEXT_MODEL`, `AI_EMBEDDING_MODEL`, `AI_VISION_MODEL`)
 - Nutzung für Klassifikation, Chunking-Unterstützung, Beschreibungen, Kontext-Extraktion

 ### 6.5 Infrastruktur & Operations

 - **Containerisierung:** Docker, Docker Compose (mehrere Stacks: `simple`, `production`, `test`, `with-firecrawl`, `infrastructure` usw.)
 - **Reverse Proxy:** Nginx (Dashboard-Serving, API-Routing)
 - **Monitoring & Tools:** Health-Endpoints, Metriken, Skripte (`scripts/verify_local_setup.py`, `scripts/validate_env.py`)

 ### 6.6 Security

 - Zentrale Security-Konfiguration über `config/security_config.py` und `.env`
 - Rate-Limits via SlowAPI (Auth, Upload, Search, Standard, Health-Profile)
 - Request-Validation (Size-Limits, File-Type-Checks, SQL/XSS-Schutz)
 - Security-Header & CORS-Konfiguration
 - API-Key-Management in `krai_system.api_keys` + `APIKeyService`

 ### 6.7 Testing & Qualität

 - **Backend:** `pytest`, Integrationstests, Performance-Tests (`tests/`)
 - **Dashboard:** Laravel Feature-Tests, Browser-Tests (Dusk optional)
 - **CI:** GitHub Actions Workflows (`.github/workflows/*.yml`)

 ---

 ## 7. Projektphasen & Meilensteine

 Die Umsetzung orientiert sich an inkrementellen Phasen (1–6), die sich teilweise mit bestehenden Dokumenten (`docs/PHASE*_*.md`) überschneiden.

 ### Phase 1 – Basis-Infrastruktur & Setup

 - Ziel: Entwickler können das System lokal mit einem Befehl starten.
 - Inhalte:
   - Repository-Struktur, Setup-Skripte (`setup.sh`, `setup.ps1`, `setup.bat`)
   - Docker-Compose-Stacks (simple, with-firecrawl, test)
   - `.env`-Konzept und Validierung
 - Deliverable: `docker-compose.simple.yml` + funktionierender Health-Check.

 ### Phase 2 – Dokumenten-Pipeline (MVP)

 - Ziel: PDFs können hochgeladen, geparst, gechunkt und als Embeddings gespeichert werden.
 - Inhalte:
   - Master-Pipeline-Stufen (Extraktion, Chunking, Embedding)
   - Speicherung in PostgreSQL (`krai_intelligence.chunks`) + MinIO
   - Basis-Metadaten für Hersteller/Produkte
 - Deliverable: Upload-Endpoint + erste semantische Suche.

 ### Phase 3 – Content-Modelle & Suche

 - Ziel: Strukturierte Entitäten und Such-APIs sind stabil verfügbar.
 - Inhalte:
   - Datenmodelle für Produkte, Hersteller, Fehlercodes, Videos, Bilder
   - Such- & Filterfunktionen (REST-APIs + Index-Design)
   - Normalisierung von Herstellern/Modellen, Fehlercode-Erkennung
 - Deliverable: Konsistente Search-API + UI-Integration im Dashboard.

 ### Phase 4 – Dashboard & UX

 - Ziel: Bedienbares Admin-/Operator-Dashboard für Alltagseinsatz.
 - Inhalte:
   - Startseite mit Kennzahlen, Queues, letzten Dokumenten
   - CRUD-Views (Dokumente, Produkte, Hersteller, Fehlercodes, Videos)
   - Verbesserte Navigation, Filter, Tabellen-Komponenten
 - Deliverable: Stable Dashboard-Release.

 ### Phase 5 – Security, API Keys & Governance

 - Ziel: Sicherer Betrieb in produktionsnahen Umgebungen.
 - Inhalte:
   - Konsequent angewendete Rate-Limits & Request-Validation
   - RBAC (JWT-Claims, `require_permission`-Dependencies)
   - API-Key-Management inkl. Rotation & Audit-Logging
   - Security-Checklisten (Deployment-Guide, `docs/SECURITY.md`)
 - Deliverable: Security-hardened Stack, bereit für externe Integrationen.

 ### Phase 6 – Stabilisierung, E2E & Produktion

 - Ziel: Produktionsreife mit E2E-Tests, Monitoring und klaren Betriebsprozessen.
 - Inhalte:
   - Playwright-E2E-Tests inkl. Page Objects und Fixtures
   - Monitoring-/Troubleshooting-Guides (`DOCKER_SETUP.md`, Metriken, Logs)
   - Optimierung von Pipeline-Performance & Fehlertoleranz
   - Dokumentation von Deployments (`DEPLOYMENT.md`, `PHASE6_DEPLOYMENT_GUIDE`)
 - Deliverable: Produktions-Stack + definierter Betriebsleitfaden.

 ### Langfristige Erweiterungen (Backlog / Roadmap)

 - OEM-spezifische Integrationen (z. B. Ticketing-Systeme, Portale)
 - GraphQL-Gateway, zusätzliche Agent-Funktionalitäten
 - Erweiterte Multimodalität (Audio, generative Vorschläge, Insights)
 - Mandantenfähigkeit & Hosted-Version

 ---

 ## 8. Meilensteine & Deliverables (Kurzliste)

 - **M1 – Lokales System lauffähig**
   Setup-Skripte, Docker-Stack, Health-Endpunkte

 - **M2 – Dokumenten-Ingestion & Semantische Suche**
   PDFs hochladen, Chunks + Embeddings erzeugen, einfache Suche

 - **M3 – Strukturierte Content-Modelle & Suche**
   Produkte, Fehlercodes, Videos, Bilder mit passenden APIs + UI

 - **M4 – Dashboard-Release**
   Voll funktionsfähige Admin-/Operator-Oberfläche

 - **M5 – Security-Hardening & API Keys**
   Deployment-taugliche Security-Konfiguration

 - **M6 – Produktionsfreigabe**
   E2E-Tests, Monitoring, Betriebs-Dokumentation

 ---

 ## 9. Qualitätsziele & Metriken

 - **Performance**
   - Zeit vom Upload bis zur durchsuchbaren Indexierung (Pipeline-Durchlauf)
   - Latenz der Such-Endpoints unter Last

 - **Qualität der Ergebnisse**
   - Relevanz-Feedback von Pilot-Usern / OEM-Partnern
   - Abdeckung von typischen Problemfällen (Fehlercodes, Wartung, Teile)

 - **Betrieb & Zuverlässigkeit**
   - Uptime der Kern-Services (API, DB, MinIO, Ollama)
   - Anzahl kritischer Fehler pro Release

 - **Security & Compliance**
   - Erfolgreiche Anwendung von Rate-Limits, API-Key-Rotation
   - Regelmäßige Überprüfung der Security-Checkliste

 ---

 ## 10. Risiken & Annahmen

 ### 10.1 Wichtige Risiken

 - **R1 – Komplexität der OEM-Daten**
   Unterschiedliche Datenqualität, Formate und Schreibweisen.

 - **R2 – Infrastruktur-Ressourcen**
   Docker-Umgebungen (v. a. Ollama) benötigen ausreichend RAM/CPU/GPU.

 - **R3 – Modellqualität & -drift**
   LLM-/Embedding-Modelle können sich im Verhalten ändern oder müssen getauscht werden.

 - **R4 – Security-Misskonfigurationen**
   Falsch gesetzte `.env`-Werte (CORS, Rate-Limits, API Keys) können Angriffsflächen öffnen.

 ### 10.2 Annahmen

 - Pilotkunden / OEMs stellen ausreichend Beispieldaten bereit.
 - Zielumgebungen unterstützen Docker und haben Basis-Monitoring.
 - Security- und Compliance-Vorgaben sind mit lokalem Betrieb vereinbar.

 ---

 ## 11. Betriebs- & Deploymentkonzept (High-Level)

 - **Lokal / On-Prem** via Docker-Compose-Stacks (`docker-compose.simple.yml`, `docker-compose.production*.yml`)
 - Konfiguration über `.env` / `.env.local` (siehe `README.md`, `DOCKER_SETUP.md`)
 - Backup-Strategien für PostgreSQL & MinIO (siehe Datenbank-/Storage-Dokumente)
 - Health-Checks & Metriken über definierte Endpunkte

 Für erweiterte Produktions-Szenarien (Kubernetes, Cloud-Services) kann der Stack schrittweise migriert werden (siehe `docs/ARCHITECTURE.md`, Abschnitt "Deployment Architecture").

 ---

 ## 12. Dokumentation & Wissensmanagement

 Zentrale Dokumente im Repository:

 - `README.md` – Überblick, Quick Start, Setup, Konfiguration
 - `docs/ARCHITECTURE.md` – Detaillierte Systemarchitektur
 - `docs/SECURITY.md` – Security-Referenz & Checklisten
 - `docs/api/*` – API-Dokumentation
 - `docs/dashboard/*` – Dashboard-Guides
 - `docs/database/DATABASE_SCHEMA.md` – Aktuelles DB-Schema (über Script generiert)
 - `TODO.md` & weitere TODO-Dateien – Arbeitsstand, nächste Tasks, Session-Statistiken

 ---

 ## 13. Nächste Schritte

 Kurzfristige Fokuspunkte (abhängig vom aktuellen Stand in `TODO.md`):

 - PDF-Ingestion-Smoketests mit Beispiel-Dokumenten
 - Validierung der Suchqualität mit realen Service-Anfragen
 - Vorbereitung von OEM-Demos (Dashboards, Use-Case-Flows)
 - Verfeinerung von Security- und Monitoring-Setups für Produktionsbetrieb
