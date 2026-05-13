# 🚀 KR-AI-Engine - Single Source of Truth Configuration

## 📋 **Übersicht**

Alle Environment-Variablen sind jetzt **zentral im Root-Verzeichnis** gespeichert. Das löst das Problem, dass auf anderen PCs die Credentials fehlen.

---

## 🔧 **Setup auf neuem PC**

### **1. Repository klonen:**
```bash
git clone https://github.com/Kunze-Ritter/Manual2Vector.git
cd Manual2Vector
```

### **2. Environment-Datei erstellen:**
```bash
# Kopiere das Template
copy env.template .env

# ODER: Verwende die echte credentials.txt (falls verfügbar)
copy credentials.txt .env
```

### **3. Dependencies installieren:**
```bash
cd backend
pip install -r requirements.txt
```

### **4. Testen:**
```bash
python tests/krai_master_pipeline.py
```

---

## 📁 **Dateistruktur**

```
KRAI-minimal/
├── .env                    ← 🎯 ZENTRALE KONFIGURATION (nicht in Git)
├── env.template           ← 📋 Template für neue Installationen
├── credentials.txt        ← 🔒 Echte Credentials (nicht in Git)
├── backend/
│   ├── env.example        ← 📋 Backend-spezifisches Template
│   └── main.py           ← 🔄 Lädt automatisch .env aus Root
└── database_migrations/
```

---

## 🔄 **Automatische .env-Erkennung**

Alle Scripts suchen automatisch nach der `.env` Datei:

1. **Root-Verzeichnis** (`.env`) - **PRIORITÄT 1**
2. **Parent-Verzeichnis** (`../.env`) - **PRIORITÄT 2**
3. **Lokales Verzeichnis** (`.env`) - **PRIORITÄT 3**

### **Beispiel-Log:**
```
✅ Environment variables loaded from root .env file
```

---

## 🔒 **Sicherheit**

### **Git-Ignore:**
```gitignore
.env
credentials.txt
```

### **Was ist sicher:**
- ✅ `env.template` - Template ohne echte Credentials
- ✅ `backend/env.example` - Backend-Template

### **Was ist NICHT sicher:**
- ❌ `.env` - Enthält echte Credentials
- ❌ `credentials.txt` - Enthält echte Credentials

---

## 🛠️ **Manuelle Konfiguration**

Falls die automatische Erkennung nicht funktioniert:

### **Option 1: Symlink erstellen**
```bash
# Von backend/ aus
mklink .env ..\.env
```

### **Option 2: Hardcopy erstellen**
```bash
# Von backend/ aus
copy ..\.env .env
```

### **Option 3: Environment-Variablen setzen**
```bash
set SUPABASE_URL=https://crujfdpqdjzcfqeyhang.supabase.co
set SUPABASE_ANON_KEY=your-key-here
# ... weitere Variablen
```

---

## 🧪 **Test der Konfiguration**

### **Quick Test:**
```python
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Test key variables
print("SUPABASE_URL:", os.getenv('SUPABASE_URL'))
print("OBJECT_STORAGE_ACCESS_KEY:", os.getenv('OBJECT_STORAGE_ACCESS_KEY')[:10] + "...")
```

### **Erwartete Ausgabe:**
```
SUPABASE_URL: https://crujfdpqdjzcfqeyhang.supabase.co
OBJECT_STORAGE_ACCESS_KEY: minioadmin...
```

---

## 🚨 **Troubleshooting**

### **Problem: "Environment variables not found"**

**Lösung 1:** Prüfe .env-Datei:
```bash
dir .env
```

**Lösung 2:** Prüfe Pfad:
```bash
# Von backend/ aus
dir ..\.env
```

**Lösung 3:** Manuell laden:
```python
from dotenv import load_dotenv
load_dotenv('../.env')  # Expliziter Pfad
```

### **Problem: "SUPABASE_URL not found"**

**Lösung:** Prüfe .env-Inhalt:
```bash
type .env | findstr SUPABASE_URL
```

### **Problem: "Object storage credentials missing"**

**Lösung:** Prüfe Object-Storage-Variablen:
```bash
type .env | findstr OBJECT_STORAGE_
```

---

## ✅ **Checklist für neue Installation**

- [ ] Repository geklont
- [ ] `.env` Datei erstellt (aus `env.template`)
- [ ] Alle Credentials korrekt eingetragen
- [ ] Dependencies installiert (`pip install -r requirements.txt`)
- [ ] Test ausgeführt (`python tests/krai_master_pipeline.py`)
- [ ] Log zeigt: "Environment variables loaded from root .env file"

---

## 🎯 **Vorteile der zentralen Konfiguration**

1. **✅ Single Source of Truth** - Alle Credentials an einem Ort
2. **✅ Automatische Erkennung** - Scripts finden .env automatisch
3. **✅ Sicherheit** - .env nicht in Git committed
4. **✅ Einfache Wartung** - Ein Template für alle
5. **✅ Cross-Platform** - Funktioniert auf Windows, Linux, macOS

---

**Bei Fragen:** Siehe KRAI Development Team Lead
**Version:** 1.0 (Oktober 2025)
