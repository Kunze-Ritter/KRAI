# UTAX Series Detection Patterns

## Overview

UTAX ist ein **Kyocera-Rebrand** (TA Triumph-Adler). Die Pattern-Erkennung unterstützt alle UTAX-spezifischen Modellnummern.

## Series-Kategorien

### 1. P-Serie (Monochrom & Farb MFP/Drucker)

#### P-Serie MFP mit i-Suffix (Neuere Modelle)
- **Pattern**: `P-\d{4}I MFP`
- **Beispiele**:
  - P-4532i MFP, P-4539i MFP
  - P-5539i MFP, P-6039i MFP
- **Beschreibung**: Multifunction Printers mit integrierter Technologie
- **Besonderheit**: "i" steht für integrierte/intelligente Funktionen

#### P-Serie MFP ohne i-Suffix
- **Pattern**: `P-\d{4} MFP`
- **Beispiele**:
  - P-4532 MFP, P-4539 MFP
- **Beschreibung**: Standard Multifunction Printers

#### P-Serie Drucker (Single Function)
- **Pattern**: `P-\d{4}[DN|suffix]`
- **Beispiele**:
  - P-4534DN, P-5034DN
  - P-5534DN, P-6034DN
- **Beschreibung**: Single Function Drucker
- **Suffixe**: DN (Duplex + Network)

---

### 2. LP-Serie (A3-Monochrom Drucker)

#### LP-Serie
- **Pattern**: `LP \d{4}[suffix]`
- **Beispiele**:
  - LP 3130DN, LP 4155DN
  - LP 3245, LP 4345
- **Beschreibung**: A3 Monochrom-Laserdrucker
- **Suffixe**: DN (Duplex + Network)

---

### 3. CDC/CDP/CD-Serie (Farb-MFP/Drucker)

#### CDC Serie - Color MFP
- **Pattern**: `CDC \d{4}`
- **Beispiele**:
  - CDC 1720, CDC 2240
- **Beschreibung**: Color Multifunction Printers

#### CDP Serie - Color Printer
- **Pattern**: `CDP \d{4}`
- **Beispiele**: CDP-Modelle
- **Beschreibung**: Color Single Function Printers

#### CD Serie - Color Devices
- **Pattern**: `CD \d{4}`
- **Beispiele**: CD 1630
- **Beschreibung**: Color Geräte (allgemein)

---

### 4. Numeric Models (Kyocera-based)

#### xxxci Serie
- **Pattern**: `\d{4}ci`
- **Beispiele**:
  - 5006ci, 4006ci
  - 3206ci, 2506ci
- **Beschreibung**: Kyocera TASKalfa Rebrands
- **Besonderheit**: "ci" = color inkjet/integrated

---

## Pattern-Priorität

Die Patterns werden in dieser Reihenfolge geprüft:

1. **P-Serie** (MFP mit i, MFP ohne i, Drucker)
2. **LP-Serie** (A3-Monochrom)
3. **CDC/CDP/CD-Serie** (Farb-Geräte)
4. **Numeric Models** (xxxci - Kyocera-based)

Diese Reihenfolge stellt sicher, dass spezifischere Patterns (z.B. "P-4532i MFP") vor allgemeineren Patterns (z.B. "P-4532") geprüft werden.

---

## Modellnummern-Struktur

### P-Serie Format
```
P-[Serie][Modell][Suffix] [MFP]

Beispiel: P-4532i MFP
- P-: Prefix (UTAX P-Serie)
- 4: Serie (4xxx)
- 532: Modellnummer
- i: Integriert/Intelligent
- MFP: Multifunction Printer
```

### LP-Serie Format
```
LP [Serie][Modell][Suffix]

Beispiel: LP 4155DN
- LP: Prefix (UTAX LP-Serie)
- 4: Serie (4xxx)
- 155: Modellnummer
- DN: Duplex + Network
```

### CDC/CD-Serie Format
```
CDC/CD [Serie][Modell]

Beispiel: CDC 2240
- CDC: Color Device Color (MFP)
- 2: Serie (2xxx)
- 240: Modellnummer
```

---

## Suffix-Bedeutungen

| Suffix | Bedeutung |
|--------|-----------|
| **i** | Integriert/Intelligent (neuere Modelle) |
| **MFP** | Multifunction Printer |
| **DN** | Duplex + Network |
| **ci** | Color Integrated (Kyocera-based) |

---

## Besonderheiten

### 1. **i-Suffix Erkennung**
Neuere UTAX-Modelle haben ein "i"-Suffix für erweiterte Funktionen:
- P-4532i MFP (mit i) vs. P-4532 MFP (ohne i)
- Beide werden korrekt als P-Series MFP erkannt

### 2. **Kyocera-Rebrand**
UTAX ist ein Kyocera-Rebrand, daher:
- Numeric models (5006ci, 4006ci) sind Kyocera TASKalfa Rebrands
- Error Code Patterns können von Kyocera übernommen werden
- Technologie und Architektur sind identisch

### 3. **Triumph-Adler Alias**
UTAX wird auch als "TA Triumph-Adler" verkauft:
- `detect_series('P-4532i MFP', 'Triumph-Adler')` ✅
- `detect_series('LP 3245', 'TA Triumph-Adler')` ✅

### 4. **Flexible Spacing**
Das System toleriert verschiedene Schreibweisen:
- `P-4532i MFP` ✅
- `P-4532I MFP` ✅ (Case-insensitive)
- `LP 3130DN` ✅
- `LP3130DN` ✅ (mit/ohne Space)

---

## Test-Abdeckung

✅ **20/20 Tests bestanden** (100%)

- P-Serie MFP (mit i): 4/4
- P-Serie MFP (ohne i): 2/2
- P-Serie Drucker: 4/4
- LP-Serie: 4/4
- CDC/CD-Serie: 3/3
- Numeric Models: 3/3
- Triumph-Adler Alias: 2/2

---

## Beispiel-Output

```python
from utils.series_detector import detect_series

# P-Serie MFP mit i
result = detect_series('P-4532i MFP', 'UTAX')
# {
#     'series_name': 'P-Series MFP',
#     'model_pattern': 'P-4xxxI MFP',
#     'series_description': 'UTAX P-4xxx series multifunction printers (i-model)'
# }

# LP-Serie A3
result = detect_series('LP 4155DN', 'UTAX')
# {
#     'series_name': 'LP-Series',
#     'model_pattern': 'LP 4xxx',
#     'series_description': 'UTAX LP 4xxx series A3 monochrome printers'
# }

# Kyocera-based
result = detect_series('5006ci', 'UTAX')
# {
#     'series_name': '5xxxci Series',
#     'model_pattern': '5xxxci',
#     'series_description': 'UTAX 5xxxci series color MFPs (Kyocera-based)'
# }
```

---

## Regex-Patterns (Technisch)

### P-Serie
```regex
^P-(\d)(\d{3})I\s*MFP$          # P-Serie MFP mit i
^P-(\d)(\d{3})\s*MFP$           # P-Serie MFP ohne i
^P-(\d)(\d{3})([A-Z]{0,3})$     # P-Serie Drucker
```

### LP-Serie
```regex
^LP\s*(\d)(\d{3})([A-Z]{0,3})$  # LP-Serie A3
```

### CDC/CD-Serie
```regex
^CDC\s*(\d{4})$                 # CDC Serie
^CDP\s*(\d{4})$                 # CDP Serie
^CD\s*(\d{4})$                  # CD Serie
```

### Numeric Models
```regex
^(\d)(\d{3})CI$                 # xxxci Serie (Kyocera-based)
```

---

## Integration

Die UTAX-Erkennung ist vollständig in `series_detector.py` integriert:

```python
from utils.series_detector import detect_series

# UTAX
series_data = detect_series('P-4532i MFP', 'UTAX')

# Triumph-Adler (Alias)
series_data = detect_series('P-4532i MFP', 'Triumph-Adler')

# TA Triumph-Adler (Alias)
series_data = detect_series('LP 3245', 'TA Triumph-Adler')
```

---

## Manufacturer Aliases

UTAX wird unter verschiedenen Namen erkannt:

```python
# In manufacturer_normalizer.py
'Utax': [
    'utax', 'Utax', 'UTAX',
    'TA Triumph-Adler', 'ta triumph-adler',
    'Triumph-Adler', 'triumph-adler'
]
```

---

## Zusammenfassung

Die UTAX Series Detection unterstützt:

- ✅ Alle P-Serie Modelle (MFP mit/ohne i, Drucker)
- ✅ Alle LP-Serie Modelle (A3-Monochrom)
- ✅ Alle CDC/CDP/CD-Serie Modelle (Farb-Geräte)
- ✅ Numeric Models (Kyocera-based)
- ✅ Triumph-Adler Aliase
- ✅ Flexible Spacing und Case-Insensitive
- ✅ 100% Test-Abdeckung (20/20 Tests)

---

## Hinweis: Kyocera-Rebrand

Da UTAX ein Kyocera-Rebrand ist:

1. **Error Code Patterns**: UTAX verwendet Kyocera Error Codes
2. **Parts Catalog**: Viele Teile sind mit Kyocera kompatibel
3. **Service Manuals**: Oft identisch mit Kyocera TASKalfa-Modellen
4. **Technologie**: Gleiche Hardware-Plattform

Beispiel-Mapping:
- UTAX 5006ci ≈ Kyocera TASKalfa 5006ci
- UTAX P-4532i MFP ≈ Kyocera TASKalfa 4053ci
