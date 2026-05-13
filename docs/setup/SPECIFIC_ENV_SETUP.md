# 🔧 KR-AI-Engine - Specific Environment Configuration

## 📋 **Übersicht**

Statt einer generischen `.env` Datei verwenden wir **spezifische Environment-Dateien** für verschiedene Konfigurationsbereiche. Das verhindert Konflikte und macht die Konfiguration übersichtlicher.

---

## 📁 **Environment-Dateien Struktur**

```
KRAI-minimal/
├── env.database          ← 🗄️ Database Configuration
├── env.storage           ← ☁️ Storage Configuration
├── env.ai               ← 🤖 AI Configuration
├── env.system           ← ⚙️ System Configuration
├── .env                 ← 🔄 Legacy Fallback
└── templates/
    ├── env.database.template
    ├── env.storage.template
    ├── env.ai.template
    ├── env.system.template
    └── env.template
```

---

## 🗄️ **env.database** - Database Configuration

**Zweck:** Supabase Cloud Database Einstellungen

```bash
# SUPABASE CONFIGURATION
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_STORAGE_URL=https://your-project.supabase.co/storage/v1

# DATABASE CONNECTION
DATABASE_CONNECTION_URL=postgresql://postgres:password@db.project.supabase.co:5432/postgres
DATABASE_PASSWORD=your-database-password

# DATABASE BUCKETS
DATABASE_STORAGE_BUCKET=krai-documents
DATABASE_IMAGE_BUCKET=krai-images

# CONNECTION POOL SETTINGS
DB_POOL_SIZE=10
DB_MAX_CONNECTIONS=20
DB_CONNECTION_TIMEOUT=30
```

---

## ☁️ **env.storage** - Storage Configuration

**Zweck:** MinIO Object Storage Einstellungen

```bash
# MINIO OBJECT STORAGE CONFIGURATION
OBJECT_STORAGE_TYPE=s3
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=your-minio-secret-key
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_USE_SSL=false
OBJECT_STORAGE_PUBLIC_URL=http://localhost:9000
```

---

## 🤖 **env.ai** - AI Configuration

**Zweck:** Ollama AI Models und Hardware Einstellungen

```bash
# OLLAMA CONFIGURATION
OLLAMA_URL=http://localhost:11434
OLLAMA_BASE_URL=http://localhost:11434

# CUSTOM MODEL NAMES
TEXT_CLASSIFICATION_MODEL=llama3.2:latest
EMBEDDING_MODEL=embeddinggemma:latest
VISION_MODEL=llava:latest

# AI PERFORMANCE SETTINGS
AI_TIMEOUT_SECONDS=120
AI_MAX_RETRIES=3
AI_CONCURRENT_REQUESTS=5

# GPU ACCELERATION SETTINGS
GPU_ACCELERATION=true
GPU_MEMORY_LIMIT=8192
GPU_BATCH_SIZE=4

# MODEL DOWNLOAD SETTINGS
AUTO_DOWNLOAD_MODELS=true
MODEL_CACHE_DIR=./models
MODEL_UPDATE_CHECK=true
```

---

## ⚙️ **env.system** - System Configuration

**Zweck:** System Performance und Processing Einstellungen

```bash
# SYSTEM CONFIGURATION
LOG_LEVEL=INFO
MAX_WORKERS=8
MAX_CONCURRENT_DOCUMENTS=5
MAX_CONCURRENT_CHUNKS=20

# TEXT CHUNKING SETTINGS
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_CHUNK_SIZE=2000

# PERFORMANCE TIER
# PERFORMANCE_TIER=low_performance|medium_performance|high_performance

# MEMORY MANAGEMENT
MEMORY_LIMIT_GB=16
MEMORY_WARNING_THRESHOLD=0.8
MEMORY_CLEANUP_INTERVAL=300

# PROCESSING TIMEOUTS
UPLOAD_TIMEOUT_SECONDS=60
PROCESSING_TIMEOUT_SECONDS=1800
EMBEDDING_TIMEOUT_SECONDS=300

# CACHE SETTINGS
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
CACHE_MAX_SIZE_MB=512

# SECURITY SETTINGS
ENABLE_AUDIT_LOGGING=true
AUDIT_LOG_RETENTION_DAYS=90
ENCRYPTION_ENABLED=false
```

---

## 🚀 **Setup auf neuem PC**

### **1. Repository klonen:**
```bash
git clone https://github.com/Kunze-Ritter/Manual2Vector.git
cd Manual2Vector
```

### **2. Dependencies installieren:**
```bash
cd backend
pip install -r requirements.txt
```

### **3. Environment-Dateien erstellen:**
```bash
# Das Script erstellt automatisch alle .env Dateien aus Templates
python tests/krai_master_pipeline.py
```

**Falls das nicht funktioniert:**
```bash
# Manuell kopieren
copy env.database.template env.database
copy env.storage.template env.storage
copy env.ai.template env.ai
copy env.system.template env.system
```

### **4. Credentials eintragen:**
```bash
# Alle Dateien bearbeiten
notepad env.database
notepad env.storage
notepad env.ai
notepad env.system
```

---

## 🔄 **Automatische .env-Erkennung**

Das Script lädt **alle gefundenen .env Dateien** automatisch:

### **Lade-Reihenfolge:**
1. `env.database` (Database Configuration)
2. `env.storage` (Storage Configuration)
3. `env.ai` (AI Configuration)
4. `env.system` (System Configuration)
5. `.env` (Legacy Fallback)

### **Such-Pfade (für jede Datei):**
- Script-Verzeichnis
- Parent-Verzeichnis
- Project-Root
- Current Working Directory
- Relative Pfade

### **Beispiel-Log:**
```
✅ Environment loaded from 4 file(s):
   📄 C:\Manual2Vector\env.database
   📄 C:\Manual2Vector\env.storage
   📄 C:\Manual2Vector\env.ai
   📄 C:\Manual2Vector\env.system
```

---

## 🎯 **Vorteile der spezifischen .env Dateien**

### **1. ✅ Keine Konflikte:**
- Keine falschen `.env` Dateien von anderen Projekten
- Spezifische Dateinamen verhindern Verwechslungen

### **2. ✅ Übersichtlichkeit:**
- Jeder Bereich hat seine eigene Konfiguration
- Einfacher zu warten und zu debuggen

### **3. ✅ Sicherheit:**
- Sensitive Daten sind getrennt
- Einfacher zu sichern und zu teilen

### **4. ✅ Flexibilität:**
- Verschiedene Konfigurationen für verschiedene Umgebungen
- Einfacher zu testen und zu entwickeln

### **5. ✅ Best Practice:**
- Folgt modernen Konfigurationsstandards
- Professionelle Projektstruktur

---

## 🔍 **Template-System**

### **Template-Mappings:**
```python
template_mappings = {
    'env.database': ['env.database.template', 'env.template'],
    'env.storage': ['env.storage.template', 'env.template'],
    'env.ai': ['env.ai.template', 'env.template'],
    'env.system': ['env.system.template', 'env.template'],
    '.env': ['env.template', 'backend/env.example']
}
```

### **Automatische Erstellung:**
```bash
📋 Found template: env.database.template
💡 Creating: env.database
📋 Found template: env.storage.template
💡 Creating: env.storage
✅ Created 4 .env file(s): env.database, env.storage, env.ai, env.system
⚠️  Please edit these files with your actual credentials
```

---

## 🛠️ **Troubleshooting**

### **Problem: "Environment files not found"**

**Lösung 1:** Prüfe Template-Dateien:
```bash
dir env.*.template
```

**Lösung 2:** Erstelle manuell:
```bash
copy env.database.template env.database
copy env.storage.template env.storage
copy env.ai.template env.ai
copy env.system.template env.system
```

**Lösung 3:** Verwende Legacy .env:
```bash
copy env.template .env
```

### **Problem: "SUPABASE_URL not found"**

**Lösung:** Prüfe env.database:
```bash
type env.database | findstr SUPABASE_URL
```

### **Problem: "Object storage credentials missing"**

**Lösung:** Prüfe env.storage:
```bash
type env.storage | findstr OBJECT_STORAGE_ACCESS_KEY
```

---

## ✅ **Migration von generischer .env**

### **Vorher (generisch):**
```bash
# Eine große .env Datei
SUPABASE_URL=...
OBJECT_STORAGE_ACCESS_KEY=...
OLLAMA_URL=...
LOG_LEVEL=...
# ... alles gemischt
```

### **Nachher (spezifisch):**
```bash
# env.database
SUPABASE_URL=...
DATABASE_PASSWORD=...

# env.storage
OBJECT_STORAGE_ACCESS_KEY=...
OBJECT_STORAGE_SECRET_KEY=...

# env.ai
OLLAMA_URL=...
TEXT_CLASSIFICATION_MODEL=...

# env.system
LOG_LEVEL=...
MAX_WORKERS=...
```

---

## 🎯 **Best Practices**

1. **✅ Verwende spezifische Dateien** statt generischer .env
2. **✅ Trenne Konfigurationen** nach Funktionsbereichen
3. **✅ Verwende Templates** für neue Installationen
4. **✅ Dokumentiere alle Variablen** in den Templates
5. **✅ Sichere sensitive Daten** getrennt

---

**Bei Fragen:** Siehe KRAI Development Team Lead
**Version:** 1.0 Specific Environment (Oktober 2025)
