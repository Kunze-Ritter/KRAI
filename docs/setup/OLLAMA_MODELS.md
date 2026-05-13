# 🤖 Benötigte Ollama Modelle

## ✅ **PFLICHT-MODELLE** (für Basis-Funktionalität)

### 1️⃣ **embeddinggemma** - Vector Embeddings
```bash
ollama pull embeddinggemma
```

**Verwendung:**
- Generiert 768-dimensionale Embeddings
- Ermöglicht semantische Suche
- Stage 7: Embedding Processor

**Größe:** ~1.5 GB
**Speed:** ~100 embeddings/Sekunde
**RAM:** ~2 GB

---

### 2️⃣ **qwen2.5:7b** - LLM Extraktion
```bash
ollama pull qwen2.5:7b
```

**Verwendung:**
- Intelligente Produkt-Extraktion
- Spezifikations-Parsing
- JSON-strukturierte Antworten

**Größe:** ~4.7 GB
**Speed:** Schnell
**RAM:** ~6 GB

---

## 🎨 **OPTIONAL-MODELLE** (für Vision AI)

### 3️⃣ **llava-phi3** - Vision AI (EMPFOHLEN)
```bash
ollama pull llava-phi3
```

**Verwendung:**
- Bild-basierte Extraktion
- Tabellen-Erkennung
- Diagramm-Analyse

**Größe:** ~2.9 GB
**Speed:** Schnell (Phi3-basiert)
**RAM:** ~4 GB
**Vorteil:** Schneller als llava:13b!

---

### 3️⃣ **ALTERNATIVE: llava:13b** - Vision AI (Besser, aber langsamer)
```bash
ollama pull llava:13b
```

**Verwendung:**
- Bessere Qualität als llava-phi3
- Komplexe Tabellen

**Größe:** ~8 GB
**Speed:** Langsamer
**RAM:** ~12 GB

---

## 🚀 **SCHNELL-INSTALLATION**

### **Basis-Setup (ohne Vision AI):**
```bash
# Schritt 1: Ollama starten
ollama serve

# Schritt 2: Modelle installieren
ollama pull embeddinggemma
ollama pull qwen2.5:7b

# Schritt 3: Verifizieren
ollama list
```

**→ Reicht für:**
- ✅ Text-Extraktion
- ✅ Produkt-Extraktion
- ✅ Error Code-Extraktion
- ✅ Link & Video-Extraktion
- ✅ Embeddings
- ❌ Vision AI (Bilder/Tabellen)

---

### **FULL-Setup (mit Vision AI):**
```bash
# Basis-Modelle
ollama pull embeddinggemma
ollama pull qwen2.5:7b

# Vision AI (wähle EINES):
ollama pull llava-phi3        # SCHNELLER, empfohlen
# ODER
ollama pull llava:13b         # BESSER, aber langsamer

# Verifizieren
ollama list
```

**→ Ermöglicht:**
- ✅ Alles von Basis-Setup
- ✅ Vision AI (OCR, Tabellen, Diagramme)
- ✅ Image-basierte Produkt-Extraktion

---

## 📊 **MODELL-VERGLEICH**

| Modell | Größe | RAM | Speed | Zweck |
|--------|-------|-----|-------|-------|
| **embeddinggemma** | 1.5 GB | 2 GB | ⚡⚡⚡ | Embeddings (PFLICHT) |
| **qwen2.5:7b** | 4.7 GB | 6 GB | ⚡⚡ | LLM Extraktion (PFLICHT) |
| **llava-phi3** | 2.9 GB | 4 GB | ⚡⚡ | Vision AI (OPTIONAL) |
| **llava:13b** | 8 GB | 12 GB | ⚡ | Vision AI besser (OPTIONAL) |

**Gesamt-Bedarf:**
- **Minimum:** 6.2 GB Disk + 8 GB RAM (ohne Vision)
- **Empfohlen:** 9.1 GB Disk + 12 GB RAM (mit llava-phi3)
- **Maximum:** 14.2 GB Disk + 20 GB RAM (mit llava:13b)

---

## ✅ **VERIFIZIERUNG**

### **Nach Installation prüfen:**
```bash
ollama list
```

**Sollte zeigen:**
```
NAME                 ID              SIZE      MODIFIED
embeddinggemma:latest   abc123...       1.5 GB    X minutes ago
qwen2.5:7b             def456...       4.7 GB    X minutes ago
llava-phi3:latest      ghi789...       2.9 GB    X minutes ago  (optional)
```

---

### **Test ob Ollama läuft:**
```bash
# Windows PowerShell
curl http://localhost:11434/api/tags

# Oder im Browser:
http://localhost:11434
```

---

## 🔧 **TROUBLESHOOTING**

### **Problem: "Ollama not found"**
```bash
# Windows:
winget install Ollama.Ollama

# Oder Download:
https://ollama.ai/download
```

---

### **Problem: "Model not found"**
```bash
# Liste alle installierten Modelle:
ollama list

# Modell neu installieren:
ollama pull embeddinggemma
```

---

### **Problem: "Out of memory"**
```bash
# Kleinere Vision-Modell verwenden:
ollama pull llava-phi3    # Statt llava:13b

# Oder Vision AI deaktivieren im Script:
enable_vision=False
```

---

### **Problem: "Ollama not responding"**
```bash
# Windows:
# 1. Task Manager → Ollama beenden
# 2. Neu starten:
ollama serve

# Oder Service neu starten:
# Services → Ollama → Restart
```

---

## 📝 **EMPFEHLUNG**

### **Für normale Nutzung:**
```bash
ollama pull embeddinggemma
ollama pull qwen2.5:7b
ollama pull llava-phi3
```

**→ 9.1 GB Disk, 12 GB RAM, beste Balance!**

---

### **Für Low-RAM System (<16 GB):**
```bash
ollama pull embeddinggemma
ollama pull qwen2.5:7b
# Kein Vision AI Modell
```

**→ 6.2 GB Disk, 8 GB RAM**

**Im Script dann setzen:**
```python
enable_vision=False
```

---

### **Für High-End System (>32 GB RAM):**
```bash
ollama pull embeddinggemma
ollama pull qwen2.5:7b
ollama pull llava:13b    # Beste Qualität
```

**→ 14.2 GB Disk, 20 GB RAM, beste Qualität!**

---

## 🎯 **QUICK START**

```bash
# 1. Ollama starten (Neues Terminal)
ollama serve

# 2. Modelle installieren (Anderes Terminal)
ollama pull embeddinggemma
ollama pull qwen2.5:7b
ollama pull llava-phi3

# 3. Prüfen
ollama list

# 4. Script starten
cd backend/processors_v2
python process_production.py
```

---

**Fertig! Alle benötigten Modelle sind installiert!** ✅
