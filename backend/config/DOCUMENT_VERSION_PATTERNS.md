# 📄 Document Version Patterns

## 🎯 **Zweck**

Diese Patterns extrahieren die **DOKUMENT-VERSION** (nicht Firmware-Versionen!) aus Service Manuals basierend auf **herstellerspezifischen Versionsschemas**.

---

## 📊 **Manufacturer-Specific Patterns**

### **1. HP**
```
Format: Edition X, MM/YYYY
Example: "Edition 3, 5/2024"
Fallback: "Edition 4.0"
```

**Warum:** HP verwendet Edition-basierte Versionierung mit Datum.

---

### **2. Konica Minolta**
```
Format: YYYY/MM/DD
Example: "2024/12/25"
Fallback: "2024.01.15"
```

**Warum:** Konica Minolta nutzt ISO-Datumsformat als Dokumentversion.

---

### **3. Lexmark**
```
Format: Month YYYY
Example: "November 2024"
Fallback: "11/15/2024"
```

**Warum:** Lexmark verwendet ausgeschriebene Monate.

---

### **4. UTAX**
```
Format: Version X.Y
Example: "Version 1.0"
Fallback: "v1.0"
```

**Warum:** UTAX nutzt klassische Versionsnummern.

---

### **5. Triumph Adler**
```
Format: Version X.Y
Example: "Version 1.0"
Fallback: "5/2024"
```

**Warum:** Triumph Adler kombiniert Versionsnummern und Datum.

---

## ⚙️ **Extraction Rules**

### **1. Manufacturer-Specific Search**
```python
manufacturer = "Konica Minolta"
→ Nutzt nur Konica Minolta patterns

manufacturer = "HP"
→ Nutzt nur HP patterns
```

### **2. One Document = One Version**
```python
# STOP nach ERSTEM Match!
if match_found:
    return [version]  # Nur 1 Version
```

### **3. Priority Order**
```
Priority 1: Haupt-Pattern (höchste Confidence)
Priority 2: Fallback-Pattern
```

### **4. Generic Fallback**
```
Falls Manufacturer nicht erkannt:
→ Nutzt generic_fallback patterns
```

---

## ❌ **Was NICHT extrahiert wird:**

- ❌ **Firmware Versions** (FW 4.2, Function Version 4.2)
- ❌ **Revision Lists** (alle Revisions in der Tabelle)
- ❌ **Datum im Header** (auf jeder Seite wiederholt)
- ❌ **Copyright Dates** (2024 Copyright)

---

## ✅ **Was extrahiert wird:**

- ✅ **Document Version** (erste erwähnte Version)
- ✅ **Edition** (bei HP)
- ✅ **Publish Date** (bei Konica Minolta, Lexmark)
- ✅ **Version Number** (bei UTAX, Triumph Adler)

---

## 📋 **Beispiele:**

### **HP Manual:**
```
Text: "Edition 3, 5/2024 ... Service Manual ... Copyright 2024"

Extracted: "Edition 3, 5/2024" ✅
Ignored: "2024" (Copyright Date)
```

### **Konica Minolta Manual:**
```
Text: "AccurioPress C4080 Service Manual
       2024/12/25

       Page 1 Header: 2024/12/25
       Page 2 Header: 2024/12/25"

Extracted: "2024/12/25" ✅ (first occurrence)
Ignored: All subsequent headers
```

### **Lexmark Manual:**
```
Text: "Service Manual
       November 2024

       Firmware: FW 4.2"

Extracted: "November 2024" ✅
Ignored: "FW 4.2" (Firmware, nicht Document Version)
```

---

## 🔧 **Usage in Code:**

```python
from backend.processors.version_extractor import VersionExtractor

extractor = VersionExtractor()

# Mit Manufacturer (empfohlen)
versions = extractor.extract_from_text(
    text=first_5_pages,
    manufacturer="Konica Minolta"
)
# Result: ["2024/12/25"]

# Ohne Manufacturer (generic fallback)
versions = extractor.extract_from_text(
    text=first_5_pages
)
# Result: ["2024/12/25"] oder ["Edition 3, 5/2024"]
```

---

## 📁 **Files:**

| File | Purpose |
|------|---------|
| `version_patterns.json` | Manufacturer-specific patterns (NEU, simplified) |
| `version_patterns.json.backup` | Alte komplexe Version (240 Zeilen) |
| `document_version_patterns.json` | Identisch zu neuer version_patterns.json |
| `version_extractor.py` | Extractor Implementation |

---

## 🎯 **Key Benefits:**

✅ **Manufacturer-Specific** - Gezielt pro Hersteller
✅ **Simple** - Nur 5 Manufacturer + Fallback
✅ **Reliable** - Stoppt nach erstem Match
✅ **Maintainable** - Klar strukturiert
✅ **Fast** - Keine komplexen Regex-Kombinationen

---

## 🚀 **Adding New Manufacturer:**

```json
{
  "manufacturer_specific": {
    "ricoh": {
      "name": "Ricoh Document Versions",
      "description": "Ricoh uses ...",
      "patterns": [
        {
          "pattern": "...",
          "example": "...",
          "priority": 1
        }
      ]
    }
  }
}
```

**WICHTIG:** Pattern auch in `version_extractor.py` hinzufügen:

```python
manufacturer_patterns = {
    'ricoh': [
        (r'...', 'ricoh_version', 0.95),
    ],
}
```

---

## ✅ **Result:**

**1 Document = 1 Version** (nicht 200!)
**Manufacturer-Specific** (gezielt & präzise)
**No Firmware Versions** (nur Document Versions)
