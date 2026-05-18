# Forschungstagebuch: Sprint 1 Kickoff – Datenfundament

**Datum:** 2026-05-13
**Sprint:** 1 (Datenfundament)
**Zeitraum:** 2026-05-13 – 2026-05-31 (adjusted from planned 19.05–01.06)
**Owner:** Cursor-Claude

---

## Ausgangslage

KRAI existiert als 16-stage multimodale Dokumentenverarbeitungs-Pipeline (Stand 13.05.2026). Es fehlt:
- **Predictive-Maintenance-Modelle** – zentrale F&E-Erweiterung des Restprojekts
- **PM-Datenbank-Schema** – `krai_pm` mit Tickets, Sollwerte, Geräte-Lifecycle, Predictions
- **Datenintegration aus Excel** – KM-Anfragedaten (OF/PP/SOL, 6.447 Tickets) + Verbrauchsmaterial-Sollwerte (88 Modelle, 1.650 Laufzeitwerte)

**Forschungskontext:** BSFZ-Forschungszulage 926-241-950/2026-1/1, Frascati-konform. Vier Forschungsfragen (F1–F4) treiben die Methodenwahl.

---

## Ziele für Sprint 1

1. **Schema operationalisiert:** Migrations 019 & 020 laufen, alle Basis-Tabellen verfügbar
2. **Daten importiert:** ≥6.000 Tickets, ≥1.500 Sollwerte in DB
3. **Exploration dokumentiert:** Notebook mit Verteilungen, Long-Tail-Analyse, Replikation der Briefing-Zahlen
4. **Architektur begründet:** ADRs für Schema-Isolierung und Pseudonymisierung
5. **Tests in place:** Unit + Integrationstests für beide Importer, grün

---

## Forschungsfragen adressiert

- **F1 (Verbrauchsmaterial-Wartungsintervall-Prognose):** Datengrundbasis schaffen – Sollwerte, Tausch-Events
- **F2 (Bauteilausfall-Anomaliedetektion):** Long-Tail-Verteilung messbar machen – repliziere 67,6 % Klassen mit <2 Vorkommen
- **F3 (Generalisierbarkeit):** Vorbereitungen treffen für Cross-Manufacturer-Splits (ab Sprint 6)
- **F4 (Multimodale Anreicherung):** Embedding-Spalte in `service_tickets` vorbereiten (wird ab Sprint 2 gefüllt)

---

## Bisherige Annahmen & Abhängigkeiten

| Annahme | Status | Fallback |
|---------|--------|----------|
| KM-Excel-Daten (OF/PP/SOL) vorhanden | ✅ Verfügbar | Nutze verfügbare Daten |
| Docuform-Export für Zählerstände | ⏳ IT-Anfrage gestellt | Sprint 3 +2 Wochen Puffer; nutze synthetische Daten für Entwicklung |
| Radix-CRM-Dump (Lexmark, HP, Kyocera) | ⏳ Infominds angefragt | Sprint 6 +4 Wochen; validiere zuerst auf KM allein |
| pgvector-Extension in lokaler PG | ✅ Vermutlich vorhanden | Installier ggf. `CREATE EXTENSION IF NOT EXISTS vector` |

---

## Was wird gemacht (Reihenfolge)

1. **DB-Migrations (Aufgabe 1.1)** – 019 & 020 schreiben, lokal testen
2. **KM-Importer (Aufgaben 1.2 + 1.3)** – `ticket_ingestion_processor`, `part_lifetimes_importer`
3. **Explorations-Notebook (Aufgabe 1.4)** – Verteilungen, Long-Tail-Visualisierung
4. **ADRs (Aufgabe 1.5)** – Konzepte dokumentieren, Tobias gegenlesen
5. **Forschungstagebuch abschließen (Aufgabe 1.6)** – Sprint-Lessons

---

## Methodische Entscheidungen (zu diskutieren mit Tobias)

- **Schema-Isolation:** `krai_pm` vs. `krai_intelligence` – warum eine separate Tabelle für Tickets?
  → ADR-001 wird das begründen
- **Pseudonymisierung:** SHA-256 von Seriennummern in `entity_mapping` – Compliance by Design
  → ADR-002

---

## Offene Fragen für Tobias

1. Exakte Spalten der KM-Excel-Dateien (OF, PP, SOL) – Format-Variabilität?
2. Wo liegt die KM-Excel-Datei für Verbrauchsmaterial-Sollwerte?
3. Fallback-Plan: Falls Docuform-Daten erst in Sprint 4+ verfügbar – sollen wir synthetische Zählerstände für Entwicklung nutzen?

---

## Risiken & Mitigationen

| Risiko | Eintritt-WS | Mitigation |
|--------|------------|-----------|
| pgvector-Installation fehlt | Niedrig | `CREATE EXTENSION` in Migration 019; lokal testen |
| Excel-Format variiert zwischen Dateien | Mittel | Flexible Parser, Regex-basiert; Test-Fixtures mit Varianten |
| Datenqualität (fehlende Werte, Duplikate) | Hoch | Explorations-Notebook aufdecken; Data-Cleaning-Logik in Importern |
| Migrations-Rollback schlägt fehl | Niedrig | Test rollback lokal vor Merge |

---

## KPI für Sprint-Abschluss

- ✅ 6.000+ Tickets in DB
- ✅ 1.500+ Sollwerte in DB
- ✅ Unit-Test-Coverage > 80 % für Importer-Module
- ✅ Explorations-Notebook reproduziert Briefing-Zahlen
- ✅ ADRs abgeschlossen
- ✅ Alle Pre-Commit-Checks grün

---

**Erstellt:** 2026-05-13 von Cursor-Claude
**Nächster Eintrag:** Sprint-1-Close (geplant 2026-05-31)
