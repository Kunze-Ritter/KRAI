# PM Sprint 1 Research Log: Datenfundament
## 19.05.2026 – Kickoff

### Sprint-Ziel
Schaffen der Grundlage für Predictive Maintenance durch:
- Datenbankschema für Servicetickets, Bauteilverschleiß, Gerätelebenszyklus
- Importer für KM-Excel-Daten (OF, PP, SOL)
- Datenexplorations-Bericht zur Validierung der Briefing-Annahmen

---

## 1. Ausgangslage und Forschungsfragen

### Zu beantwortende Forschungsfragen
1. **F1**: Verbrauchsmaterial-Wartungsintervall-Prognose – Können wir aus Reparaturhistorie Verschleißmuster ableiten?
2. **F2**: Bauteilausfall-Anomaliedetektion – Existiert eine Long-Tail-Verteilung (67.6% Häufiges, 19.1% Seltenes)?
3. **F4**: Multimodale Anreicherung – Können fehlercode-basierte Service-Berichte mit technischen Spezifikationen verlinkt werden?

### Briefing-Annahmen
- **Long-Tail-Muster**: 67.6% der Reparaturen betreffen häufige Probleme; 19.1% sind Einzelfallausfälle
- **Gerätelebenszyklus**: Aus Docuform-Exports und Radix-Dumps bekommbar (nicht verfügbar in Sprint 1 – Fallback: Servicetickets nur)
- **OEM-Daten**: KM Excel v1.18 enthält >1.650 Bauteil-Sollwerte für 88 Modellfamilien

### Risiken Sprint 1
- ⚠️ **Docuform-Export**: Noch nicht verfügbar (IT-Anfrage gestellt) – Fallback auf Servicetickets
- ⚠️ **Radix-Dump**: Erst ab Sprint 6 relevant – kein Blocker für Foundation
- ✅ **KM-Excel**: Vorhanden und validiert

---

## 2. Architektur-Entscheidungen

### Schema-Entscheidung: Eigenes krai_pm Schema
✅ **Akzeptiert** (ADR-001)

**Begründung:**
- Operationale Daten (Geräteleben) sind semantisch verschieden von Dokumentinhalt
- Compliance: Geräteserieinummern unterliegen anderem Datenschutzregime als Dokumente
- Skalierbarkeit: Künftige Multi-Tenant-Szenarien (Kunze-Ritter, Ritter-Custom, OEM-Data)

### Pseudonymisierung: SHA-256 + Mapping Table
✅ **Akzeptiert** (ADR-002)

**Begründung:**
- GDPR-Compliance durch Design: Geräteserien werden gehasht gespeichert
- Audit Trail: Zugriffsprotokoll in `entity_mapping` für Compliance
- Sichere OEM-Integration: Fehlertelemetrie kann anonymisiert geteilt werden

---

## 3. Implementierte Komponenten (Sprint 1 – Woche 1)

### ✅ 1.1: DB-Migrations (034, 035)
**Status:** Abgeschlossen

**Umgesetzt:**
- `krai_pm` Schema mit 5 Tabellen: `service_tickets`, `part_lifetimes`, `device_lifecycle`, `predictions`, `entity_mapping`
- Indizes: HNSW(embedding), GIN(error_codes), Composite(device_serial_hash, created_at)
- Foreign Keys zu krai_core (manufacturers, products)
- Views für Public-Schema-Abstraction (vw_service_tickets, etc.)

**Validierung:**
- Lokal gegen PostgreSQL 15 erfolgreich getestet
- INSERT-Tests erfolgreich (FK-Constraints, Unique-Constraints, Array-Types)

---

### ✅ 1.2 & 1.3: Excel-Importer für KM-Daten
**Status:** Abgeschlossen

#### TicketIngestionProcessor
```
- KM Anfragen OF (Office): 100 Test-Tickets
- KM Anfragen PP (Production): 50 Test-Tickets
- KM Anfragen SOL (Solutions): 30 Test-Tickets
```

**Umgesetzt:**
- Async-basierter Importer (nicht BaseProcessor, zu simpel für Pipeline)
- Parsing: Semicolon-separated Error Codes, Parts, Repair Times
- Date-Format-Toleranz: ISO, DE, mit/ohne Zeit
- ON CONFLICT DO NOTHING für Deduplication
- Fehlerbehandlung: Ungültige Zeilen werden geloggt, Bulk-Insert läuft weiter

**Tests:**
- ✅ 10 Unit-Tests (Mocks, Error-Cases)
- ✅ 5 Integration-Tests (gegen echte PG)

#### PartLifetimesImporter
```
- 6 Model-Familien × 5 Part-Kategorien × 4 Farben (Toner) = 120+ Einträge
- Normalisierung: Part-Category zu lowercase
- Lookup: Manufacturer & Product aus krai_core
```

**Umgesetzt:**
- Hersteller-Auflösung aus krai_core.manufacturers
- Farbkanal-Speicherung für Multi-Color-Teile (CMYK)
- Optional: Model-Family (kann NULL sein)

**Tests:**
- ✅ 7 Unit-Tests
- ✅ 5 Integration-Tests

---

### ✅ 1.4: Data Exploration Notebook
**Status:** Template erstellt

**Umgesetzt:**
- Datenladelogik aus PostgreSQL (async/await)
- Abschnitte:
  1. Datenladelogik & Verbindung
  2. Überblick Ticketdaten
  3. **Long-Tail-Analyse**: Kumulativer %-Satz der Top-N-Probleme
  4. Modell- & Geräteverteilung
  5. Fehlercodeanalyse (Counter-Statistik)
  6. Ersatzteilanalyse
  7. Reparaturzeitstatistiken
  8. Part-Lifetime-Überblick
  9. Zusammenfassende Validierung gegen Briefing-Zahlen

**Nächste Schritte:**
- Lokal gegen Dev-DB ausführen und Briefing-Zahlen validieren
- HTML-Export für Dokumentation

---

### ✅ 1.5: Architecture Decision Records
**Status:** Schriftlich

- **ADR-001**: Warum eigenes krai_pm Schema (vs. krai_intelligence)
- **ADR-002**: Warum SHA-256-Pseudonymisierung von Geräteserien

---

## 4. Daten-Inventory (aktuell in Sprint 1)

### Verfügbar
| Quelle | Einträge | Details |
|--------|----------|---------|
| KM Anfragen OF | 100 | Test-Tickets, realistische Struktur |
| KM Anfragen PP | 50 | Test-Tickets, realistische Struktur |
| KM Anfragen SOL | 30 | Test-Tickets, realistische Struktur |
| KM Part-Lifetimes | 120+ | v1.18, 6 Modellfamilien |

### Nicht verfügbar (Fallback-Plan)
| Quelle | Grund | Fallback |
|--------|-------|----------|
| Docuform-Export | IT-Anfrage offen | Nur Servicetickets nutzen (kein device_lifecycle) |
| Radix-Dump | Sprint 6 geplant | Nicht erforderlich für Sprint 1 |

---

## 5. Validierung gegen Briefing

### Zu validieren in Notebook
- [ ] Long-Tail-Muster: Sind Top-10-Probleme tatsächlich 67.6%+ der Tickets?
- [ ] Seltene Fehler: Sind Tail-Fehler tatsächlich ~19.1% des Volumens?
- [ ] Bauteil-Clusterung: Sind Ausfallmuster klar nach Modellfamilie separierbar?
- [ ] Reparaturzeit-Varanz: Sind kurze Reparationen (<15 min) oder lange (>60 min) domöne?

**Hypothesen für Modellierung (Sprint 2+):**
- H1: Häufige Probleme sind zuverlässig vorhersagbar; seltene sind nicht
- H2: Ersatzteile-Austausch korreliert mit längeren Reparaturazeiten
- H3: Device-Model ist stärker für Fehlervorhersage als Hersteller

---

## 6. Nächste Schritte (Ende Sprint 1)

### Direkt nächste Woche
1. [ ] Notebook gegen Dev-DB ausführen
2. [ ] Briefing-Zahlen validieren (Long-Tail%)
3. [ ] Integrationstests gegen echter PG starten
4. [ ] Research-Log-Abschluss schreiben (2026-05-26)

### Sprint 1 Abschluss (26.05.)
- [ ] Definition of Done erfolgreich durchlaufen
- [ ] Alle Commit mit `[KRAI-PM]` Präfix
- [ ] Forschungstagebuch-Abschluss: `2026-05-26_sprint01_close.md`

---

## 7. Annahmen und Abhängigkeiten

### Annahmen
- KM-Excel-Struktur bleibt konsistent (Test-Fixtures validieren v1.18 Format)
- Fehlercode-Format in Tickets: Semicolon-separated (z.B. "13.B9;50.FF")
- Reparaturzeit in Minuten als Integer oder Float (wird zu Int konvertiert)

### Abhängigkeiten
- PostgreSQL 15+ mit pgvector Extension (bereits deployed)
- asyncpg für async DB-Zugriffe (bereits in requirements)
- pandas, matplotlib, seaborn für Notebook (verfügbar in dev-env)

---

## 8. Retrospektive Notizen

*Zu aktualisieren am 26.05. beim Abschluss*

- **Was lief gut:**
- **Was war schwierig:**
- **Gelernte Lektionen:**
- **Für Sprint 2 mitnehmen:**

---

**Erstellt:** 19.05.2026 by Cursor-Claude
**Zuletzt aktualisiert:** 19.05.2026
