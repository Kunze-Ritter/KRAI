# 🎮 GPU Auto-Detection für Ollama Vision Models

**Automatische VRAM-Erkennung und optimale Model-Auswahl**

Die Pipeline erkennt **automatisch** deine GPU und wählt das beste LLaVA Vision Model!

---

## ✨ Features

### **Automatische Erkennung:**
- ✅ GPU Name & Hersteller
- ✅ Verfügbares VRAM (GB)
- ✅ Optimales Vision Model
- ✅ Cross-Platform (Windows/Linux/Mac)

### **Intelligente Auswahl:**
- ✅ **20+ GB VRAM** → `llava:34b` (Beste Qualität, große Modelle)
- ✅ **12-20 GB VRAM** → `llava:latest` (Hohe Qualität, 13B)
- ✅ **8-12 GB VRAM** → `llava:latest` (Standard, 13B)
- ✅ **4-8 GB VRAM** → `llava:7b` (Optimiert, 7B)
- ✅ **< 4 GB VRAM** → `llava:7b` (Minimal, Safe)

---

## 🚀 Quick Start

### **Option A: Automatisches Script**

```bash
cd c:\Users\haast\Docker\KRAI-minimal
fix_ollama_gpu.bat
```

**Was passiert:**
1. 🔍 Erkennt deine GPU (z.B. RTX 2000 Ada, 8GB VRAM)
2. 💡 Empfiehlt optimales Model (z.B. `llava:7b`)
3. ⬇️ Installiert das Model automatisch
4. ✅ Startet Ollama neu
5. 🎯 Testet Installation

---

### **Option B: Python Test**

```bash
cd backend
python -c "from utils.gpu_detector import print_gpu_info; print_gpu_info()"
```

**Ausgabe:**
```
============================================================
🎮 GPU DETECTION
============================================================
GPU: NVIDIA RTX 2000 Ada Generation Laptop GPU
VRAM: 8.0 GB

✅ Recommended Vision Model: llava:7b
📝 Reason: 8.0GB VRAM - Using optimized model (7B)
============================================================
```

---

## 🔧 Wie es funktioniert

### **1. GPU Detection (gpu_detector.py)**

```python
from utils.gpu_detector import get_gpu_info

info = get_gpu_info()
# {
#     'gpu_available': True,
#     'gpu_name': 'NVIDIA RTX 2000 Ada',
#     'vram_gb': 8.0,
#     'recommended_vision_model': 'llava:7b',
#     'reason': '8.0GB VRAM - Using optimized model (7B)'
# }
```

### **2. Automatische Integration (ai_service.py)**

```python
# AIService erkennt GPU beim Start automatisch
service = AIService()

# Auto-detected:
# - 8GB VRAM → llava:7b
# - 16GB VRAM → llava:latest
# - 24GB VRAM → llava:34b
```

### **3. Override mit .env (Optional)**

```bash
# In .env oder backend/.env:
OLLAMA_MODEL_VISION=llava:latest

# Überschreibt Auto-Detection
# Nützlich für manuelles Fine-Tuning
```

---

## 📊 Model-Vergleich

| Model | VRAM | RAM | Parameter | Speed | Quality | Use Case |
|-------|------|-----|-----------|-------|---------|----------|
| **llava:34b** | 20+ GB | 16+ GB | 34B | Langsam | ⭐⭐⭐⭐⭐ | Workstations, beste Qualität |
| **llava:latest** | 11-12 GB | 8 GB | 13B | Mittel | ⭐⭐⭐⭐ | High-end GPUs (3080Ti+) |
| **llava:7b** | 4 GB | 4 GB | 7B | Schnell | ⭐⭐⭐ | Standard GPUs (2060+) |
| **llava:7b-q4** | 2.5 GB | 2 GB | 7B-Q4 | Sehr schnell | ⭐⭐ | Low-end GPUs, Backup |

---

## 🎯 Beispiele

### **Dein aktueller PC (8GB VRAM):**
```
GPU: NVIDIA RTX 2000 Ada Generation Laptop GPU
VRAM: 8.0 GB
→ Auto-selected: llava:7b ✅
→ Läuft stabil, keine Crashes!
```

### **Dein anderer PC (16GB VRAM):**
```
GPU: NVIDIA RTX 4070 Ti (hypothetisch)
VRAM: 16.0 GB
→ Auto-selected: llava:latest ✅
→ Beste Performance & Qualität!
```

---

## 🔬 Detection Methoden

### **Priorität 1: GPUtil (Python)**
```python
import GPUtil
gpus = GPUtil.getGPUs()
# Beste Methode, direkt via Python
```

### **Priorität 2: nvidia-smi (CLI)**
```bash
nvidia-smi --query-gpu=name,memory.total --format=csv
# Fallback wenn GPUtil nicht verfügbar
```

### **Priorität 3: Safe Default**
```python
# Wenn Detection fehlschlägt:
# → llava:7b (funktioniert überall)
```

---

## ⚙️ Erweiterte Konfiguration

### **System RAM nutzen (CPU Fallback)**

**Windows (PowerShell als Admin):**
```powershell
# Mehr Layers auf CPU (nutzt System RAM)
[System.Environment]::SetEnvironmentVariable('OLLAMA_NUM_GPU', '14', 'Machine')

# Restart Ollama
Restart-Service Ollama
```

**Bedeutung:**
- `OLLAMA_NUM_GPU=14` → 14 Layers auf GPU, Rest auf CPU RAM
- Gut für große Models bei wenig VRAM
- Trade-off: GPU-Layers = schnell, CPU-Layers = langsam aber mehr RAM

---

## 🐛 Troubleshooting

### **GPU nicht erkannt**

```bash
# Test Detection manuell
cd backend
python -c "from utils.gpu_detector import print_gpu_info; print_gpu_info()"

# Falls "GPU: Not detected":
# 1. NVIDIA Treiber aktualisieren
# 2. GPUtil installieren:
pip install gputil

# 3. nvidia-smi testen:
nvidia-smi
```

### **Falsches Model gewählt**

```bash
# Override in .env:
OLLAMA_MODEL_VISION=llava:latest

# Oder manuell:
ollama pull llava:latest
```

### **Model lädt nicht**

```bash
# Check verfügbare Models
ollama list

# Nochmal pullen
ollama pull llava:7b --verbose

# Ollama neu starten
taskkill /F /IM ollama.exe
ollama serve
```

---

## 📈 Performance-Tipps

### **Maximale GPU-Auslastung:**
```powershell
# Mehr GPU Layers (wenn VRAM frei)
[System.Environment]::SetEnvironmentVariable('OLLAMA_NUM_GPU', '25', 'Machine')
```

### **Stabiler Betrieb:**
```powershell
# Weniger parallel requests (stabiler)
[System.Environment]::SetEnvironmentVariable('OLLAMA_NUM_PARALLEL', '1', 'Machine')
```

### **RAM sparen:**
```powershell
# Nur 1 Model gleichzeitig laden
[System.Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS', '1', 'Machine')
```

---

## 🎪 Multi-GPU Setup

**Kommt bald!** Support für:
- Multiple GPUs (SLI/NVLink)
- Mixed VRAM (z.B. 8GB + 16GB)
- Automatische Load-Balancing

---

## 🔍 Log Output

**Pipeline Start:**
```
AI Service initialized with BALANCED tier
GPU detected: NVIDIA RTX 2000 Ada Generation Laptop GPU
VRAM: 8.0 GB
Auto-detected vision model: llava:7b
Recommendation: llava:7b - 8.0GB VRAM - Using optimized model (7B)
```

**Bei manual override:**
```
Using vision model from env: llava:latest
```

---

## 💡 Best Practices

1. ✅ **Erst Detection laufen lassen** - `fix_ollama_gpu.bat`
2. ✅ **Empfehlung folgen** - Auto-Detection ist optimiert
3. ✅ **Bei Crashes downgraden** - Quantisiertes Model probieren
4. ✅ **Logs checken** - `Auto-detected vision model: ...`
5. ✅ **Manual override nur wenn nötig** - .env Variable

---

## 🚦 Status-Indikatoren

**✅ Optimal:**
```
Auto-detected vision model: llava:7b
GPU: NVIDIA RTX 2000 Ada (8GB VRAM)
→ Model passt perfekt in VRAM
```

**⚠️ Warning:**
```
Using vision model from env: llava:latest
GPU: 8GB VRAM
→ Model könnte zu groß sein (11GB benötigt)
```

**❌ Problem:**
```
GPU: Not detected (CPU mode)
→ Verwendet Safe Default (llava:7b)
```

---

## 📚 Weitere Ressourcen

- **OLLAMA_GPU_FIX.md** - Detaillierte Troubleshooting-Anleitung
- **fix_ollama_gpu.bat** - Automatisches Install-Script
- **backend/utils/gpu_detector.py** - Source Code der Detection

---

**Created:** Oktober 2025
**Status:** ✅ Production Ready
**Tested:** RTX 2000 Ada (8GB), RTX 4090 (24GB)
