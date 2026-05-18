# Vision Model Alternativen zu LLaVA

## 🎯 Aktuell verwendet: LLaVA

**Problem**: Crasht manchmal trotz aller Optimierungen

---

## 🔄 Ollama Vision Model Alternativen

### **1. BakLLaVA** (Empfohlen als Alternative)
**Modell**: `bakllava:7b`
**VRAM**: ~4-5 GB
**Vorteile**:
- ✅ Basiert auf Mistral (statt Llama)
- ✅ Oft stabiler als LLaVA
- ✅ Gleiche Größe wie llava:7b
- ✅ Gute Performance bei technischen Bildern

**Installation**:
```bash
ollama pull bakllava:7b
```

**Verwendung in .env**:
```bash
OLLAMA_MODEL_VISION=bakllava:7b
```

---

### **2. LLaVA-Phi** (Kleiner & Schneller)
**Modell**: `llava-phi3:latest`
**VRAM**: ~2-3 GB
**Vorteile**:
- ✅ Viel kleiner (3.8B Parameter)
- ✅ Schneller
- ✅ Weniger VRAM
- ✅ Basiert auf Phi-3

**Nachteile**:
- ⚠️ Weniger genau als 7B Modelle
- ⚠️ Schlechter bei komplexen technischen Bildern

**Installation**:
```bash
ollama pull llava-phi3
```

**Verwendung**:
```bash
OLLAMA_MODEL_VISION=llava-phi3:latest
```

---

### **3. Moondream** (Sehr klein)
**Modell**: `moondream:latest`
**VRAM**: ~1-2 GB
**Vorteile**:
- ✅ Sehr klein (1.6B Parameter)
- ✅ Extrem schnell
- ✅ Läuft auf fast jeder GPU
- ✅ Sehr stabil

**Nachteile**:
- ⚠️ Deutlich weniger genau
- ⚠️ Nur für einfache Bildanalyse
- ⚠️ Nicht gut für Error Code Extraction

**Installation**:
```bash
ollama pull moondream
```

**Verwendung**:
```bash
OLLAMA_MODEL_VISION=moondream:latest
```

---

### **4. MiniCPM-V** (Neu & Effizient)
**Modell**: `minicpm-v:latest`
**VRAM**: ~4 GB
**Vorteile**:
- ✅ Effizientes 2.8B Modell
- ✅ Gute Performance/Size Ratio
- ✅ Optimiert für Effizienz
- ✅ Unterstützt mehrere Sprachen

**Nachteile**:
- ⚠️ Relativ neu
- ⚠️ Weniger getestet

**Installation**:
```bash
ollama pull minicpm-v
```

**Verwendung**:
```bash
OLLAMA_MODEL_VISION=minicpm-v:latest
```

---

## 📊 Vergleich

| Modell | VRAM | Parameter | Geschwindigkeit | Genauigkeit | Stabilität | Empfehlung |
|--------|------|-----------|-----------------|-------------|------------|------------|
| **llava:7b** | 4-5 GB | 7B | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Aktuell |
| **bakllava:7b** | 4-5 GB | 7B | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ Beste Alternative |
| **llava-phi3** | 2-3 GB | 3.8B | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | Für schwache GPUs |
| **minicpm-v** | 4 GB | 2.8B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Interessant |
| **moondream** | 1-2 GB | 1.6B | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | Nur Notfall |

---

## 🚀 Empfohlene Reihenfolge zum Testen

### **Für 8GB VRAM (RTX 2000):**
1. ✅ **bakllava:7b** (Erste Alternative)
2. ✅ **minicpm-v** (Wenn bakllava auch crasht)
3. ✅ **llava-phi3** (Wenn alles andere crasht)
4. ❌ **moondream** (Nur als letzte Option)

### **Für 16GB+ VRAM:**
1. ✅ **bakllava:7b** (Sollte stabiler sein)
2. ✅ **llava:13b** / **llava:latest** (Original in größer)

---

## 🔧 Automatisches Fallback konfigurieren

Aktuell im Code (ai_service.py):
```python
# Vision fallbacks - DISABLED due to VRAM issues
'llava:latest': ['llava:7b'],
'llava:7b': [],  # No fallbacks
'bakllava:latest': [],
```

**Empfohlen: Fallback aktivieren**

```python
# Vision fallbacks
'llava:7b': ['bakllava:7b', 'llava-phi3:latest'],
'llava:latest': ['llava:7b', 'bakllava:7b'],
'bakllava:7b': ['llava-phi3:latest', 'moondream:latest'],
```

**ABER**: Fallback bedeutet bei Crash wird anderes Model probiert → Kann noch mehr Probleme verursachen

---

## 🧪 Schnelltest für Alternativen

```bash
# BakLLaVA testen
ollama pull bakllava:7b
ollama run bakllava:7b

# Danach in .env:
OLLAMA_MODEL_VISION=bakllava:7b

# Pipeline laufen lassen
python backend/tests/krai_master_pipeline.py
```

---

## 💡 Warum BakLLaVA empfohlen?

**Basiert auf Mistral statt Llama:**
- ✅ Andere Architektur → Andere Speicherverwaltung
- ✅ Oft stabiler bei wiederholten Aufrufen
- ✅ Gute Performance bei technischen Dokumenten
- ✅ Gleiche VRAM-Anforderungen wie llava:7b

**Community-Feedback:**
- Weniger "model runner stopped" Fehler
- Besser für Batch-Verarbeitung
- Stabiler bei langen Sessions

---

## 🎯 Alternative: Vision komplett deaktivieren

**Option 1**: Nur Pattern-Matching (kein Vision AI)
```bash
DISABLE_VISION_PROCESSING=true
```
- ✅ 100% stabil
- ✅ Kein VRAM-Problem
- ❌ Keine Error Codes aus Screenshots

**Option 2**: Externes Vision API nutzen
- OpenAI GPT-4 Vision (kostenpflichtig)
- Google Gemini Vision (kostenpflichtig)
- Anthropic Claude Vision (kostenpflichtig)

---

## 📝 Zusammenfassung

### **Wenn llava:7b crasht:**

**Schnelle Lösung:**
```bash
# 1. BakLLaVA installieren
ollama pull bakllava:7b

# 2. In .env ändern
OLLAMA_MODEL_VISION=bakllava:7b

# 3. Pipeline neu starten
```

**Wenn auch BakLLaVA crasht:**
```bash
# Kleineres Modell
ollama pull llava-phi3
OLLAMA_MODEL_VISION=llava-phi3:latest
```

**Wenn alles crasht:**
```bash
# Vision AI deaktivieren
DISABLE_VISION_PROCESSING=true
```

---

## 🔍 Weitere Optionen (Zukunft)

Ollama entwickelt ständig neue Vision Models:
- LLaVA 1.6 (verbessert)
- Obsidian (neu)
- CogVLM (sehr groß, aber sehr gut)

Check: `ollama list` und `ollama search vision`

---

**Empfehlung**: **BakLLaVA:7b als erste Alternative testen!** 🚀

**Datum**: Oktober 2, 2025
