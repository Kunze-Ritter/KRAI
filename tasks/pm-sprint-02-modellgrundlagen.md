# Sprint 2: Modellgrundlagen (KW 23–24, 02.06.–15.06.2026)

**Sprint-Ziel:** ML Model v1 Architektur steht, Feature Engineering Framework funktioniert, Long-Tail-Klassifizierung läuft gegen Test-Daten. Vorbereitung für Docuware/Radix-Integration abgeschlossen.

**Owner:** Cursor-Claude

**Datenverfügbarkeit:** ⚠️ Docuware + Radix ausstehend (IT-Termin pending)

---

## Forschungsfragen adressiert
- F1 (Verbrauchsmaterial-Wartungsintervall-Prognose): Feature Engineering & Modell-Baseline definieren
- F2 (Bauteilausfall-Anomaliedetektion): Long-Tail vs. Common-Problem Klassifizierer trainieren
- F4 (Multimodale Anreicherung): Feature-Pipeline vorbereiten für Docuware-Daten

---

## Definition of Done

| Aufgabe | Status | Anmerkung |
|---------|--------|-----------|
| ML Model v1 Architektur definiert | ⬜ | Decision Record für Modellauswahl |
| Feature Engineering Framework | ⬜ | Skeleton mit Docuware-Placeholders |
| Long-Tail Klassifizierer trainiert | ⬜ | Gegen 180 Test-Tickets, Baseline-Genauigkeit |
| Error Pattern Analysator | ⬜ | Pro-Hersteller Fehler-Cluster (HP, Konica, Ricoh) |
| Device Lifecycle Tracker Prep | ⬜ | Schema, Importer-Skeleton (blockiert auf Docuware-Struktur) |
| Model Evaluation Framework | ⬜ | Metriken, Cross-validation, Ablation Testing |
| Unit-Tests für ML Pipeline | ⬜ | Feature extraction, model inference, edge cases |
| Integration-Tests gegen PG | ⬜ | Model Outputs → krai_pm.predictions Speicherung |
| ADR-003 schriftlich | ⬜ | Warum Long-Tail Classification + nicht Regression/Clustering |
| Forschungstagebuch aktualisiert | ⬜ | Learnings aus Model Development |
| Commits mit [KRAI-PM] | ⬜ | Saubere Git-Historie |

---

## Detaillierte Aufgaben

### 🟢 KATEGORIE A: Kann JETZT starten (unabhängig von Docuware/Radix)

#### Aufgabe 2.1: ML Model v1 Architektur definieren

- [ ] Entscheidung treffen: Klassifizierung vs. Regression vs. Clustering
  - **Empfehlung**: Gradient Boosting (XGBoost/LightGBM) für Long-Tail vs. Common Classification
  - Begründung: Interpretierbar, schnell, gut für Imbalance
- [ ] ADR-003: `docs/adr/003-long-tail-classification-strategy.md`
  - Status: Proposed
  - Inhalt: Warum Klassifikation statt Regression, Trade-offs
- [ ] Feature-Set definieren (vorerst ohne Docuware-Daten)
  - Aus `service_tickets`: problem_short, error_codes, replaced_parts, repair_time_minutes
  - Aus `part_lifetimes`: nominal_lifetime_pages (per part category)
  - Aus `manufacturers` (lookup): manufacturer_name
  - Placeholders für Docuware: page_count, device_age_months, service_history_count
- [ ] Target Variable: Binary (Common = 1, Long-Tail = 0)
  - Threshold: Top 20 problems = Common, Rest = Long-Tail (anpassbar)

#### Aufgabe 2.2: Feature Engineering Framework bauen

- [ ] Datei: `backend/ml/feature_engineering.py`
  - Klasse `FeatureEngineer` mit async `extract_features()`
  - Input: ticket_id aus `krai_pm.service_tickets`
  - Output: Feature-Dict (numerisch + kategorisch)
  - Features:
    - **Error-Codes-Vektor**: Häufigkeit Top 10 Error Codes (One-Hot)
    - **Problem-Häufigkeit**: Wie oft kommt dieser Problem in historischen Daten vor?
    - **Part-Häufigkeit**: Wie oft werden diese Parts bei diesem Model ersetzt?
    - **Repair-Time**: Gemittelt für ähnliche Probleme
    - **Manufacturer**: Categorical (encode as int)
    - **Model**: Categorical (encode as int)
    - **Placeholders** (None für jetzt, füllen bei Docuware):
      - device_age_months, page_count, service_history_count, part_replacement_frequency
- [ ] Unit-Tests: `backend/tests/pm/test_feature_engineering.py`
  - Test mit Mock-Tickets, verifiziere Feature-Shape und Typen
  - Test mit fehlenden Docuware-Daten (soll graceful auf None fallen)

#### Aufgabe 2.3: Long-Tail Klassifizierung implementieren

- [ ] Datei: `backend/ml/long_tail_classifier.py`
  - Klasse `LongTailClassifier` mit `train()` und `predict()`
  - Training gegen `service_tickets` + `part_lifetimes` (kombinierte Features)
  - Model: XGBoost oder LightGBM
  - Cross-validation (5-fold) gegen 180 Test-Tickets
  - Output: Prediction + Confidence Score
- [ ] Baseline-Metriken
  - Accuracy, Precision, Recall (für beide Klassen)
  - Feature Importance Plot (save as PNG für Research Log)
- [ ] Unit-Tests: `backend/tests/pm/test_long_tail_classifier.py`
  - Test Training mit Mock-Daten
  - Test Prediction mit Edge Cases (sehr seltene Fehler, fehlende Parts)
  - Test Model Persistence (save/load)
- [ ] Integration-Test: `backend/tests/pm/test_classifier_integration.py`
  - Trainiere gegen echte DB-Daten (180 Tickets)
  - Verifiziere dass Predictions in `krai_pm.predictions` gespeichert werden können

#### Aufgabe 2.4: Error Pattern Analysator für Cross-Manufacturer

- [ ] Datei: `backend/ml/error_pattern_analyzer.py`
  - Klasse `ErrorPatternAnalyzer` mit `analyze_by_manufacturer()`
  - Ziel: Herstellerspezifische Fehler-Cluster identifizieren
  - Ausgabe: Pro Hersteller (HP, Konica Minolta, Ricoh):
    - Top 15 Error Codes
    - Error-Code Co-occurrence Matrix (welche Fehler treten zusammen auf?)
    - Problem Distribution (skewed vs. uniform)
  - Visualisierung: Heatmap für Co-occurrence (speichern als PNG)
- [ ] Unit-Tests: `backend/tests/pm/test_error_pattern_analyzer.py`
  - Test mit Mock-Tickets verschiedener Hersteller
  - Verifiziere dass Co-occurrence Matrix symmetrisch ist
- [ ] Notebook: `examples/pm/02_error_pattern_analysis.ipynb`
  - Lade `service_tickets`, group by manufacturer
  - Zeige Error-Pattern-Unterschiede
  - Save Visualisierungen für Research Log

#### Aufgabe 2.5: Model Evaluation Framework

- [ ] Datei: `backend/ml/model_evaluation.py`
  - Klasse `ModelEvaluator` mit Metriken
  - Unterstütze: Accuracy, Precision, Recall, F1, AUC-ROC, Confusion Matrix
  - Cross-validation Helper (stratified 5-fold)
  - Ablation Testing: Remove each feature, measure impact
- [ ] Unit-Tests: `backend/tests/pm/test_model_evaluation.py`
  - Test Metriken-Berechnung gegen Known Good Values
  - Test Ablation Testing

#### Aufgabe 2.6: Long-Tail Klassifizierer in DB speichern

- [ ] Datei: `backend/processors/prediction_processor.py`
  - Async Processor, erbt von `BaseProcessor`
  - Input: ticket_id aus `krai_pm.service_tickets`
  - Pipeline:
    1. Lade Ticket-Daten
    2. Extract Features (via FeatureEngineer)
    3. Predict Long-Tail (via LongTailClassifier)
    4. Speichere in `krai_pm.predictions` (prediction_type='long_tail', result_json)
  - Error Handling: Graceful fallback wenn Features nicht berechnet werden können
- [ ] Integration-Tests: `backend/tests/pm/test_prediction_processor_integration.py`
  - Test Prediction für alle 180 Test-Tickets
  - Verifiziere dass alle Predictions in DB gespeichert sind
  - Verifiziere dass Duplicate Tickets nicht doppelt gepredicted werden (Idempotency)

#### Aufgabe 2.7: ADR-003 schreiben

- [ ] `docs/adr/003-long-tail-classification-strategy.md`
  - Status: Proposed (→ Accepted nach Validierung)
  - Kontext: Warum Klassifikation (Common vs. Long-Tail) und nicht Regression?
  - Entscheidung: Binary Classifier mit Threshold-based Common/Tail Split
  - Konsequenzen: Einfacheres Modell, bessere Interpretierbarkeit, aber loss of granularity
  - Trade-offs: Accuracy vs. Simplicity

#### Aufgabe 2.8: Unit + Integration Tests grün

- [ ] Alle neuen Tests laufen: `pytest backend/tests/pm/ -v`
- [ ] Coverage: Mindestens 80% für neue ML-Module

---

### 🔴 KATEGORIE B: Blockiert durch Docuware/Radix (für Sprint 2 vorbereiten, starten wenn Daten kommen)

#### Aufgabe 2.9: Device Lifecycle Tracker Vorbereitung

⚠️ **Blockiert auf:** Docuware-Datenstruktur (page_count, service_history, device_age)

- [ ] Schema Design (pending Docuware-Termin):
  - Tabelle: `krai_pm.device_lifecycle` (bereits erstellt, aber leer)
  - Weitere Spalten je nach Docuware-Format?
  - Views für häufige Abfragen
- [ ] Datei: `backend/processors/device_lifecycle_importer.py` (Skeleton)
  - Async Processor, wartet auf Docuware-Connector
  - Placeholder: `# TODO: Implement when Docuware data structure known`
- [ ] Feature Engineering erweitern (Feature 2.2):
  - Placeholders für device_age, page_count, service_frequency füllen

#### Aufgabe 2.10: Datenvolumen-Validierung (6.000+ echte Tickets)

⚠️ **Blockiert auf:** Docuware-Export

- [ ] Notebook: `examples/pm/03_datenvolumen_validation.ipynb`
  - Lade 6.000+ echte Tickets (wenn verfügbar)
  - Validiere Long-Tail-Distribution gegen Briefing (67.6% + 19.1%)
  - Vergleiche mit Test-Daten (180 Tickets) — sind Patterns konsistent?
  - Check: Fehler bei Scale? Performance der Features?

#### Aufgabe 2.11: Cross-Manufacturer Model Validation

⚠️ **Blockiert auf:** Ausreichend Daten pro Hersteller in Docuware

- [ ] Notebook: `examples/pm/04_cross_manufacturer_patterns.ipynb`
  - Trainiere separate Klassifizierer pro Hersteller (wenn 500+ Tickets pro Hersteller)
  - Vergleiche: HP vs. Konica vs. Ricoh Error Patterns
  - Feature Importance unterscheidet sich pro Hersteller?

---

## Abhängigkeiten / Risiken / Hinweise

### 🔴 KRITISCH: Docuware + Radix Termin ausstehend

**Stand:** 18.05.2026 — Termin wird intern abgestimmt

**Implikation für Sprint 2:**
- Kategorie A (🟢) kann JETZT starten — nicht blockiert
- Kategorie B (🔴) warten auf Termin-Bestätigung
- **Workaround:** Mit 180 Test-Tickets trainieren, aber Validierung gegen echte Daten = Sprint 3

**Action:** Wenn Docuware/Radix-Termin bekannt → sofort in dieses Dokument eintragen + Kategorie B freigeben

### Technische Risiken

1. **Class Imbalance**: Long-Tail ist seltener → braucht Weighted Loss oder Resampling
2. **Feature Leakage**: Docuware-Features noch nicht verfügbar → Training auf Daten trainieren, die in Produktion fehlen
   - **Mitigation**: Feature Framework mit Placeholders, Graceful Fallback
3. **Model Overfitting**: 180 Test-Tickets klein für XGBoost
   - **Mitigation**: 5-fold Cross-Validation + Feature Importance für Interpretability

---

## Sprint-Abschluss Checklist

**Kategorie A (Muss abgeschlossen sein):**
- [ ] Alle Aufgaben 2.1–2.8 abgehakt
- [ ] Alle Unit- und Integrationstest grün
- [ ] Linter sauber (`ruff check`, `black --check`, `mypy`)
- [ ] ADR-003 geschrieben (Status: Proposed oder Accepted)
- [ ] Commits mit `[KRAI-PM]` Präfix
- [ ] Feature Importance Plot + Error Pattern Heatmaps im Research Log
- [ ] Baseline-Metriken dokumentiert (Accuracy, Precision, Recall)

**Kategorie B (Vorbereitet, warten auf Docuware-Termin):**
- [ ] Aufgaben 2.9–2.11 sind mit Blockers dokumentiert
- [ ] Skeleton-Code geschrieben (Device Lifecycle Importer)
- [ ] Placeholder-Notebooks erstellt (`03_datenvolumen_validation.ipynb`, `04_cross_manufacturer_patterns.ipynb`)
- [ ] Termin-Abhängigkeit in `MASTER-TODO.md` oder `MEMORY.md` dokumentiert

**Dokumentation:**
- [ ] Forschungstagebuch: `docs/research-log/2026-06-15_sprint02_close.md`
  - Baseline-Metriken, Learnings, Blockade-Status Docuware

---

## Hinweis: Docuware/Radix Termin

⏳ **Ausstehend:** Interner Termin für Datenverfügbarkeit

**Wenn Termin bestätigt:**
1. Ersetze `⚠️ **Blockiert auf:** ...` mit konkrettem Datum
2. Gib Freigabe für Kategorie B
3. Verschiebe Aufgaben 2.9–2.11 ggf. in Sprint 3 (falls Termin zu spät)

**Kontakt:** [Nutzer definieren]

---

**Sprint-Kickoff-Datum:** 02.06.2026
**Sprint-End-Datum:** 15.06.2026
**Status:** Ready to Start (Category A) | Waiting on Data (Category B)
