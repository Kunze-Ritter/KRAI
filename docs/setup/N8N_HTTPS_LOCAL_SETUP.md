# N8N Lokales HTTPS Setup

Diese Anleitung zeigt, wie du n8n mit **lokalem HTTPS** auf `https://localhost` einrichtest, um Microsoft Teams als Chat-Trigger zu nutzen.

## 🎯 Überblick

Diese Lösung nutzt:
- **Nginx** als Reverse Proxy mit SSL-Terminierung
- **Selbst-signiertes Zertifikat** für localhost
- **Docker Compose** für einfaches Setup

## ⚡ Automatisches Setup (Empfohlen)

```powershell
# Führe das automatische Setup-Script aus
.\scripts\setup-n8n-https.ps1
```

Das Script erstellt automatisch:
1. SSL-Zertifikat für localhost
2. Nginx-Konfiguration
3. Startet alle Docker-Container
4. Optional: Installiert Zertifikat im Windows Trust Store

## 📋 Manuelle Schritte

Falls du das Setup manuell durchführen möchtest:

### Schritt 1: SSL-Zertifikat erstellen

```powershell
# Führe das Zertifikat-Generator-Script aus
.\scripts\generate-ssl-cert.ps1
```

Dies erstellt:
- `nginx/ssl/localhost.crt` - SSL-Zertifikat
- `nginx/ssl/localhost.key` - Private Key

### Schritt 2: Zertifikat im Windows Trust Store installieren

**Warum?** Microsoft Teams akzeptiert nur vertrauenswürdige HTTPS-Verbindungen.

**Option A: PowerShell (Automatisch)**
```powershell
$certPath = ".\nginx\ssl\localhost.crt"
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($certPath)
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
$store.Open("ReadWrite")
$store.Add($cert)
$store.Close()
Write-Host "Zertifikat installiert!"
```

**Option B: GUI (Manuell)**
1. Rechtsklick auf `nginx/ssl/localhost.crt`
2. **"Zertifikat installieren..."**
3. Speicherort: **"Aktueller Benutzer"**
4. **"Alle Zertifikate in folgendem Speicher"**
5. Wähle: **"Vertrauenswürdige Stammzertifizierungsstellen"**
6. Fertigstellen

### Schritt 3: Docker-Container starten

```powershell
# Stoppe alte Container
docker-compose down

# Starte mit neuer Konfiguration
docker-compose up -d
```

### Schritt 4: Verbindung testen

1. Öffne Browser: **https://localhost**
2. Du solltest **KEINE** SSL-Warnung sehen (wenn Zertifikat installiert)
3. Login mit: `admin` / `krai_chat_agent_2024`

## 🏗️ Architektur

```
[Microsoft Teams]
       ↓ HTTPS
[https://localhost]
       ↓
   [Nginx :443]  ← SSL-Terminierung
       ↓ HTTP
   [n8n :5678]
```

## 📁 Dateistruktur

```
KRAI-minimal/
├── nginx/
│   ├── nginx.conf           # Nginx-Konfiguration
│   └── ssl/
│       ├── localhost.crt    # SSL-Zertifikat
│       └── localhost.key    # Private Key
├── scripts/
│   ├── generate-ssl-cert.ps1
│   └── setup-n8n-https.ps1
└── docker-compose.yml       # Enthält nginx + n8n (available in archive/docker/docker-compose.yml)
```

## 🔧 Konfiguration

### docker-compose.yml

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"  # HTTPS
      - "80:80"    # HTTP (redirect)
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro

  n8n:
    environment:
      - N8N_PROTOCOL=https
      - N8N_HOST=localhost
      - WEBHOOK_URL=https://localhost/
```

### nginx.conf

```nginx
server {
    listen 443 ssl http2;
    server_name localhost;

    ssl_certificate /etc/nginx/ssl/localhost.crt;
    ssl_certificate_key /etc/nginx/ssl/localhost.key;

    location / {
        proxy_pass http://n8n:5678;
        # WebSocket support für n8n
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 📱 Microsoft Teams Integration

### 1. Webhook in n8n erstellen

1. Öffne n8n: **https://localhost**
2. Erstelle neuen Workflow
3. Füge **Webhook-Node** hinzu
4. Konfiguration:
   - **HTTP Method**: POST
   - **Path**: `teams-webhook`
5. Kopiere die URL: `https://localhost/webhook/teams-webhook`

### 2. Microsoft Teams konfigurieren

**Incoming Webhook (Einfach)**:
1. Gehe zu deinem Team → **Einstellungen**
2. **Connectors** → **Incoming Webhook**
3. Konfigurieren:
   - Name: `KRAI n8n Bot`
   - Webhook-URL: `https://localhost/webhook/teams-webhook`
4. Speichern

**Bot Framework (Erweitert)**:
1. Registriere App im [Azure Portal](https://portal.azure.com)
2. Erstelle Bot Channel Registration
3. **Messaging Endpoint**: `https://localhost/webhook/teams`
4. In n8n: Nutze **Microsoft Teams Trigger** Node
5. Konfiguriere App ID und Secret

### 3. Webhook testen

**Von Teams senden**:
```
POST https://localhost/webhook/teams-webhook
Content-Type: application/json

{
  "text": "Test von Microsoft Teams"
}
```

**In n8n prüfen**:
- Öffne deinen Workflow
- Klicke auf "Execute Workflow"
- Sende Test-Nachricht von Teams
- n8n sollte die Daten empfangen

## 🐛 Troubleshooting

### Browser zeigt SSL-Warnung

**Problem**: "Ihre Verbindung ist nicht privat"

**Lösung**:
1. Zertifikat ist nicht im Trust Store
2. Installiere Zertifikat (siehe Schritt 2)
3. Browser neu starten

**Temporärer Workaround**:
- Chrome/Edge: Klicke "Erweitert" → "Weiter zu localhost"
- Firefox: "Erweitert" → "Risiko akzeptieren"

### Microsoft Teams akzeptiert Webhook nicht

**Problem**: Teams zeigt "URL ungültig" oder "Verbindung fehlgeschlagen"

**Ursachen**:
1. ❌ Zertifikat nicht vertrauenswürdig
2. ❌ Port 443 blockiert
3. ❌ n8n läuft nicht

**Lösung**:
```powershell
# 1. Prüfe ob Zertifikat installiert ist
certutil -store -user Root | Select-String "localhost"

# 2. Prüfe ob Port 443 erreichbar ist
Test-NetConnection -ComputerName localhost -Port 443

# 3. Prüfe Container-Status
docker ps | Select-String nginx
docker ps | Select-String n8n

# 4. Prüfe Logs
docker logs krai-nginx-ssl
docker logs krai-n8n-chat-agent
```

### Nginx startet nicht

**Problem**: Container `krai-nginx-ssl` stoppt sofort

**Ursachen**:
1. Port 443 bereits belegt
2. SSL-Zertifikat fehlt
3. nginx.conf fehlerhaft

**Lösung**:
```powershell
# Prüfe ob Port 443 belegt ist
netstat -ano | Select-String ":443"

# Prüfe ob Zertifikate existieren
Test-Path .\nginx\ssl\localhost.crt
Test-Path .\nginx\ssl\localhost.key

# Prüfe nginx-Logs
docker logs krai-nginx-ssl
```

### Webhook erhält keine Daten

**Problem**: n8n empfängt keine Daten von Teams

**Debug-Schritte**:
```powershell
# 1. Prüfe n8n-Logs
docker logs krai-n8n-chat-agent -f

# 2. Teste Webhook manuell
Invoke-WebRequest -Uri "https://localhost/webhook/teams-webhook" `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"test": "data"}'

# 3. Prüfe nginx-Logs
docker logs krai-nginx-ssl -f
```

### 502 Bad Gateway

**Problem**: Nginx zeigt "502 Bad Gateway"

**Ursache**: n8n-Container läuft nicht oder ist nicht erreichbar

**Lösung**:
```powershell
# Prüfe ob n8n läuft
docker ps | Select-String n8n

# n8n neu starten
docker-compose restart n8n

# Logs prüfen
docker logs krai-n8n-chat-agent
```

## 🔐 Sicherheit

### Production-Einsatz

Für produktiven Einsatz empfehle ich:

1. **Vertrauenswürdiges Zertifikat** (von Let's Encrypt, DigiCert, etc.)
2. **Starkes Basic Auth Passwort** ändern:
   ```yaml
   # In docker-compose.yml (available in archive/docker/docker-compose.yml)
   - N8N_BASIC_AUTH_PASSWORD=dein_sicheres_passwort
   ```
3. **Firewall-Regeln** einrichten
4. **Rate Limiting** in nginx aktivieren

### Teams-spezifische Sicherheit

Microsoft Teams sendet Requests mit:
- **User-Agent**: Enthält "Microsoft Teams"
- **Origin**: Teams-Domain

Optionale nginx-Regel für zusätzliche Sicherheit:
```nginx
location /webhook/teams {
    # Nur Teams-Requests erlauben
    if ($http_user_agent !~* "Microsoft Teams") {
        return 403;
    }
    proxy_pass http://n8n:5678;
}
```

## 📚 Nützliche Befehle

```powershell
# Container-Status
docker-compose ps

# Logs anzeigen (live)
docker logs krai-nginx-ssl -f
docker logs krai-n8n-chat-agent -f

# Container neu starten
docker-compose restart

# Container stoppen
docker-compose down

# Container neu bauen
docker-compose up -d --force-recreate

# Zertifikat-Infos anzeigen
openssl x509 -in .\nginx\ssl\localhost.crt -text -noout

# Installierte Zertifikate prüfen
certutil -store -user Root
```

## 🔄 Zertifikat erneuern

Selbst-signierte Zertifikate sind **1 Jahr** gültig.

**Erneuerung**:
```powershell
# 1. Alte Zertifikate löschen
Remove-Item .\nginx\ssl\*.crt, .\nginx\ssl\*.key

# 2. Neue Zertifikate erstellen
.\scripts\generate-ssl-cert.ps1

# 3. Im Windows Trust Store erneuern
# (Altes Zertifikat entfernen, neues installieren)

# 4. Container neu starten
docker-compose restart nginx
```

## 🌐 Alternative: Let's Encrypt (Öffentlich)

Falls dein Server öffentlich erreichbar ist, nutze **Let's Encrypt**:

```yaml
# docker-compose.yml
services:
  certbot:
    image: certbot/certbot
    volumes:
      - ./nginx/ssl:/etc/letsencrypt
    command: certonly --standalone -d deine-domain.de
```

## 📖 Weiterführende Links

- [n8n Webhook Documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [Microsoft Teams Webhooks](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [Let's Encrypt](https://letsencrypt.org/)

## ✅ Checkliste

Setup abgeschlossen, wenn:

- [ ] SSL-Zertifikat erstellt (`nginx/ssl/localhost.crt`)
- [ ] Zertifikat im Windows Trust Store installiert
- [ ] Container laufen (`docker-compose ps`)
- [ ] `https://localhost` erreichbar (ohne SSL-Warnung)
- [ ] n8n-Login funktioniert
- [ ] Webhook-URL kopiert
- [ ] Microsoft Teams Webhook konfiguriert
- [ ] Test-Nachricht empfangen

---

**Support**: Bei Problemen siehe `docs/troubleshooting/` oder öffne ein Issue.
