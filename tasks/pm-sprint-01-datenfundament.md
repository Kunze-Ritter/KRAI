# Sprint 1: Datenfundament (KW 21–22, 19.05.–01.06.2026)

**Sprint-Ziel:** PM-Schema steht, KM-Excel-Daten sind importiert, Datenexplorations-Bericht liegt vor.

**Owner:** Cursor-Claude

---

## Forschungsfragen adressiert
- F1 (Verbrauchsmaterial-Wartungsintervall-Prognose): Datengrundlage schaffen
- F2 (Bauteilausfall-Anomaliedetektion): Long-Tail-Verteilung analysieren
- F4 (Multimodale Anreicherung): Basis-Schemas vorbereiten

---

## Definition of Done (aus Master-Plan)

- [ ] Migrations 019/020 laufen sauber `docker-compose -f docker-compose.simple.yml exec postgres ...`
- [ ] Mindestens 6.000 Tickets in `krai_pm.service_tickets`
- [ ] Mindestens 1.500 Einträge in `krai_pm.part_lifetimes`
- [ ] Unit-Tests für beide Importer (Mock-Excel + Mock-DB), grün
- [ ] Notebook reproduziert die Briefing-Zahlen
- [ ] ADR-001 (warum eigenes Schema, nicht in `krai_intelligence`)
- [ ] ADR-002 (warum SHA-256-Pseudonymisierung der Geräte-Seriennummern)
- [ ] Commit mit `[KRAI-PM] ...` Präfix

---

## Detaillierte Aufgaben

### Aufgabe 1.1: DB-Migrations erstellen (019 + 020)

- [ ] Datei `database/migrations_postgresql/019_create_krai_pm_schema.sql` anlegen
  - Schemas: `krai_pm` mit fünf Tabellen:
    - `service_tickets` (Harmonisierung aller Ticket-Quellen)
    - `part_lifetimes` (Hersteller-Sollwerte)
    - `device_lifecycle` (Zählerstände aus Docuform)
    - `predictions` (Modell-Outputs)
    - `entity_mapping` (Pseudonymisierung)
  - Indizes nach Spezifikation
- [ ] Datei `database/migrations_postgresql/020_create_krai_pm_views.sql` anlegen
  - Views: `vw_service_tickets`, `vw_part_lifetimes`, `vw_device_lifecycle`, `vw_predictions`
- [ ] Lokal testen: Migrations applyen, Tabellen verifizieren

### Aufgabe 1.2: Excel-Importer für KM-Anfragedaten

- [ ] Datei `backend/processors/ticket_ingestion_processor.py` erstellen
  - Liest KM-Excel-Dateien (OF, PP, SOL)
  - Normalisiert zu `krai_pm.service_tickets` Schema
  - Error Handling, Logging
- [ ] Unit-Tests `backend/tests/pm/test_ticket_ingestion.py`
  - Mock-Excel-Fixture
  - Assertions auf INSERT-Counts
- [ ] Integrationstest gegen lokale PG

### Aufgabe 1.3: Excel-Importer für Verbrauchsmaterial-Sollwerte

- [ ] Datei `backend/processors/part_lifetimes_importer.py` erstellen
  - Liest KM-Excel v1.18 (88 Modellfamilien, 1.650 Laufzeitwerte)
  - Normalisiert zu `krai_pm.part_lifetimes`
- [ ] Unit-Tests `backend/tests/pm/test_part_lifetimes_importer.py`
- [ ] Integrationstest

### Aufgabe 1.4: Datenexplorations-Notebook

- [ ] Datei `examples/pm/01_data_exploration.ipynb` erstellen
  - Datenquellen laden
  - Verteilungen, fehlende Werte, Plausibilität visualisieren
  - Long-Tail-Analyse: repliziere 67,6 % und 19,1 % aus Briefing
  - Summary-Statistiken pro Hersteller
  - Export als HTML für Dokumentation

### Aufgabe 1.5: ADRs schreiben

- [ ] `docs/adr/001-eigenes-pm-schema.md` – Begründung für neues `krai_pm` Schema (vs. `krai_intelligence`)
- [ ] `docs/adr/002-pseudonymisierung-geraete.md` – SHA-256-Hashing statt Klartext-Seriennummern

### Aufgabe 1.6: Forschungstagebuch-Kickoff

- [ ] `docs/research-log/2026-05-19_sprint01_kickoff.md` anlegen
  - Datum, Sprint-Ziele, Ausgangslage, Forschungsfragen
  - Was wird ausprobiert, zu welchem Zeitpunkt
  - Bisherige Annahmen zu Datenverfügbarkeit

---

## Abhängigkeiten / Risiken

**Datenrisiken:**
- ⚠️ Docuform-Export noch nicht verfügbar (IT-Anfrage gestellt) → für Sprint 1 nicht kritisch, erst ab Sprint 3
- ⚠️ Radix-Dump noch nicht vorhanden → erst ab Sprint 6 für Cross-Manufacturer
- **Workaround:** Für Sprint 1 nur KM-Excel-Daten verwenden

**Technische Risiken:**
- Migrations-Fehler bei pgvector-Indizes → lokal intensiv testen
- Excel-Format-Variabilität → Mock-Excel mit realistischen Varianten in Test-Fixtures

---

## Sprint-Abschluss Checklist

- [ ] Alle Aufgaben 1.1–1.6 abgehakt
- [ ] Alle Unit- und Integrationstest grün
- [ ] Linter sauber (`ruff check`, `black --check`, `mypy`)
- [ ] Migrations rollback-getestet
- [ ] Commit: `[KRAI-PM] Setup: PM extension structure for sprint 1 (foundation)`
- [ ] Forschungstagebuch abgeschlossen: `docs/research-log/2026-05-19_sprint01_close.md`

---

**Sprint-Kickoff-Datum:** 19.05.2026  
**Sprint-End-Datum:** 01.06.2026
