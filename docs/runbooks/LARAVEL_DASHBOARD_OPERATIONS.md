# Laravel Dashboard – Operations Runbook

Dieses Runbook beschreibt Alltagsaufgaben, Fehlerbehebung, Konfiguration und Wartung für das Laravel-Filament-Dashboard der KRAI-Pipeline.

---

## Häufige Aufgaben

### Pipeline-Status prüfen

1. Im Browser öffnen: `http://localhost/admin` (bzw. Ihre Laravel-URL).
2. Einloggen (Admin-Benutzer).
3. **Pipeline-Status:** Navigation → „Pipeline-Status“ (`/admin/pipeline-status`).
4. Prüfen:
   - Fortschrittsbalken (Completed / In Processing).
   - Tabelle aller 15 Stages (Status, Pending, Processing, Completed, Failed, Ø Dauer, Success Rate).
   - Hardware-Status (CPU, RAM, GPU).
   - Data Quality (Success Rate, Validation Errors, Duplicate Documents).

Die Seite aktualisiert sich automatisch alle 15 Sekunden (konfigurierbar in `laravel-admin/config/krai.php`).

### Fehlgeschlagene Stages erneut ausführen (Retry)

1. **Pipeline-Fehler:** Navigation → „Pipeline-Fehler“ (`/admin/pipeline-errors`).
2. Fehler mit Status „pending“ auswählen.
3. Aktion **„Erneut versuchen“** (Retry) klicken.
4. Bestätigungsdialog bestätigen.
5. Backend verarbeitet die Stage erneut; Status wechselt zu „retrying“ und danach je nach Ergebnis.

Alternativ: Einzelnes Dokument unter **Dokumente** → Dokument auswählen → Bulk-Aktion **„Stage verarbeiten“** → gewünschte Stage wählen.

### Fehler als gelöst markieren

1. **Pipeline-Fehler** öffnen (`/admin/pipeline-errors`).
2. Einzelnen Fehler: **„Als gelöst markieren“** → im Modal **Lösungsnotizen** eintragen (Pflicht, max. 1000 Zeichen) → speichern.
3. Mehrere Fehler: Fehler auswählen → Bulk-Aktion **„Als gelöst markieren“** → Lösungsnotizen eingeben → speichern.
4. Erfolgsmeldung prüfen (lokal markiert / mit Backend synchronisiert).

### Prozessor-Health überwachen

1. Navigation → **„Prozessor-Status“** (`/admin/processor-health`).
2. Karten pro Prozessor prüfen:
   - Name, Stage (deutsche Bezeichnung), Status (Running/Idle/Failed/Degraded).
   - Health-Score (Kreis), Dokumente in Bearbeitung, Warteschlange, Ø Bearbeitungszeit, Fehlerrate.
   - Letzte Aktivität, aktuelles Dokument (falls vorhanden).
3. Seite aktualisiert sich standardmäßig alle 30 Sekunden.

---

## Fehlerbehebung

### Backend nicht erreichbar / Verbindungsfehler

- **Symptom:** Meldungen wie „Backend service unavailable“ oder „Connection refused“ im Dashboard bzw. in Widgets.
- **Prüfen:**
  - Ist der Backend-Container (z. B. `krai-engine`) gestartet?
    `docker ps | findstr krai-engine` (Windows) bzw. `docker ps | grep krai-engine` (Linux/macOS).
  - Erreichbarkeit von Laravel aus:
    `curl -s -o NUL -w "%{http_code}" http://krai-engine:8000/health` aus dem Laravel-Container oder von einem Host, der denselben Docker-Netzwerk-Namen nutzt.
- **Lösung:** Backend starten bzw. neu starten:
  `docker start krai-engine-prod` bzw. `docker-compose -f docker-compose.simple.yml up -d krai-engine`.

### Authentifizierungsfehler (401/403)

- **Symptom:** Meldungen wie „Authentication failed (check KRAI_SERVICE_JWT)“.
- **Prüfen:**
  - `.env` (Laravel): `KRAI_SERVICE_JWT` oder `KRAI_ENGINE_SERVICE_JWT` gesetzt?
  - Alternativ: `KRAI_ENGINE_ADMIN_USERNAME` und `KRAI_ENGINE_ADMIN_PASSWORD` für Auto-Login gesetzt?
- **Lösung:**
  - Gültigen JWT vom Backend holen (z. B. Login-Endpoint) und in `KRAI_SERVICE_JWT` eintragen.
  - Oder Admin-Zugangsdaten setzen; Laravel cached den JWT ca. 55 Minuten.
  - Cache leeren, falls Token gewechselt wurde:
    `php artisan cache:clear` oder Nutzung des Clear-Cache-Commands (falls vorhanden).

### Langsame Antwortzeiten / träge UI

- **Prüfen:**
  - Backend- und DB-Antwortzeiten (z. B. `/health`, schwere Abfragen).
  - Polling-Intervalle in `laravel-admin/config/krai.php` (monitoring.polling_intervals, error_monitoring).
- **Lösung:**
  - Polling-Intervalle erhöhen (weniger Last).
  - Monitoring-Cache prüfen; bei Bedarf Cache leeren (siehe Wartung).
  - Backend- und DB-Ressourcen (CPU/RAM) prüfen.

### Polling / Live-Updates funktionieren nicht

- **Symptom:** Daten auf Pipeline-Status, Prozessor-Health oder Fehler-Seite aktualisieren sich nicht.
- **Prüfen:**
  - Browser-Konsole auf JavaScript-/Livewire-Fehler.
  - Netzwerk-Tab: periodische Requests zu Livewire-Endpoints (alle 15s/30s/60s je nach Seite/Widget).
- **Lösung:**
  - Seite hart neu laden (Ctrl+F5).
  - Cache leeren (Laravel + ggf. Browser).
  - `config/krai.php`: polling_intervals und cache_ttl prüfen; ggf. Werte anpassen und Config cachen:
    `php artisan config:cache`.

---

## Konfiguration

### Relevante Umgebungsvariablen (Laravel `.env`)

| Variable | Beschreibung | Beispiel |
|----------|--------------|----------|
| `KRAI_ENGINE_URL` | Backend-Basis-URL (Engine) | `http://krai-engine:8000` |
| `KRAI_SERVICE_JWT` / `KRAI_ENGINE_SERVICE_JWT` | JWT für API-Aufrufe | (JWT-String) |
| `KRAI_ENGINE_ADMIN_USERNAME` | Admin-Benutzer für Auto-Login | `admin` |
| `KRAI_ENGINE_ADMIN_PASSWORD` | Admin-Passwort für Auto-Login | (Passwort) |
| `MONITORING_BASE_URL` | Optional: eigene Monitoring-URL | wie `KRAI_ENGINE_URL` |

Weitere Optionen (Cache-TTL, Polling) siehe `laravel-admin/config/krai.php`.

### Cache-Einstellungen

- In `laravel-admin/config/krai.php` unter `monitoring.cache_ttl`:
  - z. B. `metrics` 30s, `queue` 15s, `dashboard` 180s, `data_quality` 300s, `navigation_badges` 20s, `pipeline` 15s, `performance` 60s.
- Überschreibung per Umgebung: z. B. `MONITORING_CACHE_TTL_DASHBOARD=120`.

### Polling-Intervalle

- In `laravel-admin/config/krai.php` unter `monitoring.polling_intervals`:
  - dashboard, queue, processor, metrics, performance (Werte in Sekunden).
- Fehler-Monitoring: `error_monitoring.summary_polling_interval`, `recent_failures_polling_interval`, `recent_failures_limit`.

### Stage-Definitionen

- Alle 15 Stages in `laravel-admin/config/krai.php` unter `stages` (label, description, icon, group, order).
- Gruppen: initialization, extraction, processing, enrichment, finalization.
- Anpassungen dort wirken in Dokumenten-Stage-Auswahl, Pipeline-Status und Fehler-Stage-Filter.

---

## Wartung

### Cache leeren

- **Laravel-Cache:**
  `cd laravel-admin && php artisan cache:clear`
- **Nur Monitoring-Caches:** Falls ein Artisan-Command dafür existiert (z. B. `ClearAllCaches`), diesen ausführen.
  Ansonsten leeren die Services beim nächsten Request die jeweiligen Cache-Keys (MonitoringService::clearCache()).

### JWT erneuern

- JWT wird von Laravel bis zu 55 Minuten gecacht.
- Nach manueller Änderung von `KRAI_SERVICE_JWT` in `.env`:
  `php artisan cache:clear` (oder gezielt den JWT-Cache-Key leeren, falls bekannt).
- Bei Nutzung von Auto-Login: Nach Ablauf wird automatisch ein neuer Token geholt, wenn Admin-Zugangsdaten gesetzt sind.

### Monitoring-Daten zurücksetzen

- Dashboard zeigt Daten aus dem Backend (API) und ggf. aus der lokalen DB (z. B. Pipeline-Fehler).
- „Zurücksetzen“ bedeutet in der Regel:
  - Backend-Metriken/DB im Backend zurücksetzen (nicht in diesem Runbook).
  - Laravel: Cache leeren, damit beim nächsten Abruf frische Daten vom Backend geholt werden.

---

## Referenzen

- **Verifikationsbericht:** [VERIFICATION_REPORT_LARAVEL_DASHBOARD.md](../../VERIFICATION_REPORT_LARAVEL_DASHBOARD.md)
- **Konfiguration:** `laravel-admin/config/krai.php`
- **Fehlerbehandlung Pipeline (allgemein):** [OPERATIONAL_RUNBOOK_ERROR_HANDLING.md](../OPERATIONAL_RUNBOOK_ERROR_HANDLING.md)
