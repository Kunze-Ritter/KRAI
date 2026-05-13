# 📦 KR-AI-Engine Dependencies Installation

## 🚀 Schnelle Installation (Empfohlen):

### **1. Minimal Requirements:**
```bash
pip install -r backend/requirements-minimal.txt
```

### **2. Vollständige Installation:**
```bash
pip install -r backend/requirements.txt
```

---

## 📋 Wichtige Dependencies erklärt:

### **🔧 Document Processing (KRITISCH!):**
```bash
PyMuPDF>=1.23.0      # PDF Text/Image Extraction
Pillow>=10.0.0       # Image Processing
pytesseract>=0.3.0   # OCR Engine
easyocr>=1.7.0       # Alternative OCR
```

### **🗄️ Database:**
```bash
asyncpg>=0.28.0       # PostgreSQL Async Driver
psycopg2-binary>=2.9.0  # PostgreSQL Driver (fallback)
```

### **🤖 AI & Machine Learning:**
```bash
ollama>=0.1.0        # Ollama Client
numpy>=1.24.0        # Numerical Computing
sentence-transformers>=2.2.0  # Embeddings
```

### **☁️ Cloud Storage:**
```bash
boto3>=1.34.0        # AWS S3 / S3-compatible storage
```

### **⚡ System & Performance:**
```bash
psutil>=5.9.0        # System Monitoring
asyncio>=3.4.3       # Async Processing
```

---

## 🐛 Häufige Installation-Probleme:

### **Problem 1: PyMuPDF Build Error**
```bash
# Lösung:
pip install --upgrade pip setuptools wheel
pip install --only-binary=all PyMuPDF
```

### **Problem 2: Pillow Installation Error**
```bash
# Lösung:
pip install --upgrade pip
pip install Pillow
```

### **Problem 3: psycopg2-binary Error**
```bash
# Lösung:
pip install --upgrade pip
pip install psycopg2-binary
```

### **Problem 4: Microsoft Visual C++ fehlt (Windows)**
```bash
# Lösung: Installiere Microsoft C++ Build Tools
# Oder verwende:
pip install --only-binary=all -r backend/requirements-minimal.txt
```

---

## 🔍 Verifikation der Installation:

### **Test Script:**
```python
# test_dependencies.py
def test_dependencies():
    try:
        import fitz
        print("✅ PyMuPDF: OK")
    except ImportError:
        print("❌ PyMuPDF: FEHLT")

    try:
        from PIL import Image
        print("✅ Pillow: OK")
    except ImportError:
        print("❌ Pillow: FEHLT")

    try:
        import asyncpg
        print("✅ AsyncPG: OK")
    except ImportError:
        print("❌ AsyncPG: FEHLT")

    try:
        import psycopg2
        print("✅ Psycopg2: OK")
    except ImportError:
        print("❌ Psycopg2: FEHLT")

    try:
        import boto3
        print("✅ Boto3: OK")
    except ImportError:
        print("❌ Boto3: FEHLT")

    try:
        import ollama
        print("✅ Ollama: OK")
    except ImportError:
        print("❌ Ollama: FEHLT")

if __name__ == "__main__":
    test_dependencies()
```

---

## 🎯 Installation-Reihenfolge:

### **1. Python Environment:**
```bash
python -m venv krai-env
source krai-env/bin/activate  # Linux/Mac
# oder
krai-env\Scripts\activate     # Windows
```

### **2. Upgrade pip:**
```bash
python -m pip install --upgrade pip
```

### **3. Install Dependencies:**
```bash
# Minimal (schnell):
pip install -r backend/requirements-minimal.txt

# Vollständig (alle Features):
pip install -r backend/requirements.txt
```

### **4. Test Installation:**
```bash
cd backend/tests
python krai_master_pipeline.py
```

---

## 📊 Requirements Vergleich:

| Package | Minimal | Vollständig | Zweck |
|---------|---------|-------------|-------|
| PyMuPDF | ✅ | ✅ | PDF Processing |
| Pillow | ✅ | ✅ | Image Processing |
| AsyncPG | ✅ | ✅ | PostgreSQL Async |
| Psycopg2 | ✅ | ✅ | PostgreSQL Sync |
| Ollama | ✅ | ✅ | AI Models |
| Boto3 | ✅ | ✅ | Cloud Storage |
| pytesseract | ✅ | ✅ | OCR |
| easyocr | ✅ | ✅ | Alternative OCR |
| sentence-transformers | ❌ | ✅ | Embeddings |
| torch | ❌ | ✅ | Deep Learning |
| redis | ❌ | ✅ | Caching |
| pytest | ❌ | ✅ | Testing |

---

**🎯 Empfehlung: Starte mit `requirements-minimal.txt` für schnelle Installation!**
