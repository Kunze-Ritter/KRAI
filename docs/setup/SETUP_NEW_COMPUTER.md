# 🖥️ Setup auf neuem Computer

## Schnellstart (5 Minuten)

### 1. Repository klonen
```bash
git clone https://github.com/Kunze-Ritter/Manual2Vector.git
cd Manual2Vector
```

### 2. Environment Setup
```bash
# Automatisches Setup
python setup_computer.py

# ODER manuell:
cp .env.example .env
# Dann .env editieren und Keys eintragen
```

### 3. Dependencies installieren
```bash
# Python Virtual Environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Packages
pip install -r backend/requirements.txt
```

### 4. Ollama installieren (für Embeddings)
```bash
# Windows: Download von https://ollama.ai
# Linux: curl https://ollama.ai/install.sh | sh

# Models installieren
ollama pull embeddinggemma:latest
ollama pull llama3.2:latest
ollama pull llava:7b
```

### 5. Konfiguration prüfen
```bash
python backend/scripts/check_config.py
```

### 6. Git Hooks installieren (Version Management)
```bash
# Automatische Version-Synchronisation aktivieren
python scripts/install_git_hooks.py

# Verifiziere Installation
ls -la .git/hooks/commit-msg   # Linux/Mac
dir .git\hooks\commit-msg*    # Windows
```

**Was macht das?**
- Installiert einen `commit-msg` Hook für automatische Version-Updates
- Aktualisiert `__version__.py` bei jedem Commit (Version & Datum)
- Lässt `__commit__` lokal unverändert – CI (GitHub Actions) schreibt den Hash nach dem Push
- Ermöglicht Semantic Versioning via Commit-Messages
- Siehe: [Version Management Guide](../development/VERSION_MANAGEMENT.md)

> 💡 **Windows:** Das Install-Skript legt zusätzlich `.git/hooks/commit-msg.cmd` an. Falls Python nicht gefunden wird, `py` in den PATH aufnehmen oder die Datei mit dem vollständigen Python-Pfad anpassen.

---

## 📋 Benötigte API Keys

### Supabase (erforderlich)
1. Gehe zu: https://supabase.com/dashboard
2. Wähle Projekt: `crujfdpqdjzcfqeyhang`
3. Settings → API
4. Kopiere:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`

### MinIO Object Storage
1. Open MinIO Console: http://localhost:9001
2. Navigate to Access Keys
3. Create Access Key
4. Copy OBJECT_STORAGE_ACCESS_KEY and OBJECT_STORAGE_SECRET_KEY

### YouTube API (optional)
1. https://console.cloud.google.com/apis/credentials
2. Create Credentials → API Key
3. Enable YouTube Data API v3
4. Kopiere: `YOUTUBE_API_KEY`

---

## 🔒 Sicherheit

**WICHTIG:** Die `.env` Datei enthält Secrets!

- ✅ `.env` ist in `.gitignore` → wird nicht committed
- ✅ Jeder Computer hat seine eigene `.env`
- ✅ Secrets werden NIEMALS ins Repository committed
- ❌ Teile Keys NICHT über unsichere Kanäle

---

## 🚀 Erste Schritte

### Test-Verarbeitung
```bash
# Einzelnes PDF testen
python backend/processors/process_production.py

# Oder mit Master Pipeline
python backend/processors/test_master_pipeline.py
```

### Production Processing
```bash
# Alle PDFs in input_pdfs/ verarbeiten
python backend/processors/process_production.py
```

---

## 🐛 Troubleshooting

### `.env` nicht gefunden
```bash
# Prüfe aktuelles Verzeichnis
pwd  # oder: cd

# Stelle sicher, dass du im Projekt-Root bist
cd /path/to/Manual2Vector
```

### Ollama nicht erreichbar
```bash
# Starte Ollama
ollama serve

# Prüfe Status
curl http://localhost:11434/api/tags
```

### Supabase Connection Error
```bash
# Prüfe .env
cat .env | grep SUPABASE

# Teste Connection
python backend/scripts/test_supabase_connection.py
```

---

## 📚 Weitere Dokumentation

- [Installation Guide](docs/setup/INSTALLATION_GUIDE.md)
- [Configuration Setup](docs/setup/CONFIGURATION_SETUP.md)
- [Version Management](../development/VERSION_MANAGEMENT.md)
- [Troubleshooting](docs/troubleshooting/)
