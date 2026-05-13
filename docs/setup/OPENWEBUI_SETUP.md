# OpenWebUI Integration für KRAI

## 🎯 Übersicht

KRAI bietet jetzt eine **OpenAI-kompatible API**, die direkt mit OpenWebUI verwendet werden kann!

## ✅ Was ist implementiert?

### OpenAI-Compatible Endpoints
- ✅ `GET /v1/models` - Liste verfügbarer Modelle
- ✅ `POST /v1/chat/completions` - Chat-Completions (streaming & non-streaming)

### Features
- ✅ **Fehlercode-Suche** - Automatische Erkennung von Fehlercodes (C9402, 10.00.33, etc.)
- ✅ **Semantic Search** - Vector-basierte Suche für allgemeine Fragen
- ✅ **Streaming Support** - Echtzeitantworten im Chat
- ✅ **Multi-Hersteller** - HP, Konica Minolta, Canon, etc.

## 🚀 Setup

### 1. API läuft bereits

Die API läuft auf: `http://localhost:8000`

Teste die OpenAI-kompatiblen Endpoints:

```powershell
# Modelle auflisten
curl http://localhost:8000/v1/models

# Chat Completion (non-streaming)
curl -X POST http://localhost:8000/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{
    "model": "krai-assistant",
    "messages": [
      {"role": "user", "content": "Konica Minolta C3320i Fehler C9402"}
    ]
  }'
```

### 2. OpenWebUI Installation

#### Option A: Docker (Empfohlen)

```powershell
# OpenWebUI mit Docker starten
docker run -d `
  -p 3000:8080 `
  --name openwebui `
  -e OPENAI_API_BASE_URLS=http://host.docker.internal:8000/v1 `
  -e OPENAI_API_KEYS=dummy-key `
  ghcr.io/open-webui/open-webui:main
```

**Wichtig für Windows:**
- `host.docker.internal` ermöglicht Docker-Container Zugriff auf localhost
- Port 3000 für OpenWebUI (um Konflikt mit Port 8000 zu vermeiden)

#### Option B: Lokale Installation

```powershell
# Python Virtual Environment
python -m venv openwebui-env
.\openwebui-env\Scripts\activate

# OpenWebUI installieren
pip install open-webui

# Starten
open-webui serve --port 3000
```

### 3. OpenWebUI Konfiguration

1. **Öffne OpenWebUI**: `http://localhost:3000`

2. **Erstelle einen Account** (erster User wird Admin)

3. **Gehe zu Settings** → **Connections**

4. **OpenAI API konfigurieren**:
   - **API Base URL**: `http://localhost:8000/v1` (oder `http://host.docker.internal:8000/v1` bei Docker)
   - **API Key**: `dummy-key` (wird nicht validiert)
   - Klicke **Save**

5. **Modell auswählen**:
   - Gehe zu **Models**
   - Wähle `krai-assistant`
   - Starte einen Chat!

## 🧪 Test-Queries

Probiere diese Queries in OpenWebUI:

### Fehlercode-Suche
```
Konica Minolta C3320i Fehler C9402
```

```
HP Fehler 10.00.33
```

### Allgemeine Fragen
```
Wie behebe ich einen Papierstau?
```

```
Toner wechseln Anleitung
```

## 📊 Erwartete Antworten

### Fehlercode C9402
```
**Fehlercode C9402** (Konica Minolta):
- **Beschreibung**: Exposure LED lighting abnormally...
- **Lösung**: 1. Turn OFF the machine. 2. Check the connection...
- **Seite**: 450
```

### Semantic Search
```
**Relevante Informationen:**
1. Paper Registration shutter Paper Tray 2 media type detection... (Relevanz: 0.55)
2. ...
```

## 🔧 Troubleshooting

### OpenWebUI kann API nicht erreichen

**Problem**: Connection refused oder timeout

**Lösung**:
```powershell
# Prüfe ob KRAI API läuft
curl http://localhost:8000/health

# Prüfe OpenAI-Endpoint
curl http://localhost:8000/v1/models
```

### Docker kann localhost nicht erreichen

**Problem**: Docker-Container kann nicht auf localhost:8000 zugreifen

**Lösung**: Verwende `host.docker.internal` statt `localhost`:
```
http://host.docker.internal:8000/v1
```

### Keine Antworten

**Problem**: OpenWebUI zeigt keine Antworten

**Lösung**:
1. Prüfe API-Logs im Terminal wo `python main.py` läuft
2. Prüfe Browser-Console (F12) in OpenWebUI
3. Teste direkt mit curl (siehe oben)

### Streaming funktioniert nicht

**Problem**: Antworten kommen nicht in Echtzeit

**Lösung**:
- Streaming ist implementiert, aber OpenWebUI zeigt manchmal erst am Ende
- Das ist normal und ein OpenWebUI-Verhalten

## 🎨 OpenWebUI Features

### Was funktioniert:
- ✅ Chat-Interface
- ✅ Conversation History
- ✅ Model Selection
- ✅ Streaming Responses
- ✅ Markdown Formatting

### Was NICHT funktioniert:
- ❌ Function Calling (noch nicht implementiert)
- ❌ Image Upload (Vision Model separat)
- ❌ Voice Input/Output

## 📈 Nächste Schritte

### Sofort verfügbar:
1. ✅ Starte OpenWebUI
2. ✅ Teste Fehlercode-Suche
3. ✅ Teste Semantic Search

### Zukünftige Erweiterungen:
- [ ] Function Calling Support
- [ ] RAG mit Conversation Context
- [ ] Multi-Turn Conversations mit Memory
- [ ] Image Upload für Defect Detection
- [ ] Voice Input/Output

## 🔐 Sicherheit

**Wichtig für Produktion:**

1. **API Key Validation**: Aktuell wird kein API Key validiert
2. **CORS**: Aktuell erlaubt für alle Origins (`*`)
3. **Rate Limiting**: Nicht implementiert

Für Produktion solltest du:
```python
# In openai_compatible_api.py
from fastapi import Header, HTTPException

async def verify_api_key(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {EXPECTED_API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid API key")
```

## 📞 Support

Bei Problemen:
1. Prüfe API-Logs
2. Prüfe OpenWebUI-Logs: `docker logs openwebui`
3. Teste Endpoints direkt mit curl

## 🎉 Fertig!

Du hast jetzt ein vollständiges Chat-Interface für KRAI! 🚀

**Viel Spaß beim Testen!**
