# Ricoh Series Detection Patterns

## Overview

Vollständige Pattern-Erkennung für alle Ricoh-Produktserien: Production, Office MFP, Printer, Large Format und GelJet.

## Series-Kategorien

### 1. Production Printing

#### Pro C Series (Production Color)
- **Pattern**: `PRO C\d{3,4}[suffix]`
- **Beispiele**:
  - Pro C5300s, Pro C5310s
  - Pro C7500, Pro C9500
  - Pro C901, Pro C7200sx
- **Beschreibung**: Production Color Systems
- **Product Type**: `production_printer`

#### Pro VC Series (Inkjet High-speed)
- **Pattern**: `PRO VC\d{5}`
- **Beispiele**: Pro VC80000, Pro VC70000
- **Beschreibung**: High-speed Inkjet Production
- **Product Type**: `production_printer`
- **Technologie**: Continuous inkjet für Hochgeschwindigkeitsdruck

#### Pro 8 Series (High-volume B&W)
- **Pattern**: `PRO 8\d{3}`
- **Beispiele**: Pro 8420
- **Beschreibung**: High-volume Monochrome Production
- **Product Type**: `production_printer`

---

### 2. Large Format/CAD

#### MP W Series (Wide Format)
- **Pattern**: `(AFICIO )?MP W\d{4}`
- **Beispiele**:
  - MP W6700
  - Aficio MP W3601
- **Beschreibung**: Wide Format MFPs für CAD/Pläne
- **Product Type**: `inkjet_plotter`

#### IM CW Series (Wide Format)
- **Pattern**: `IM CW\d{4}`
- **Beispiele**: IM CW2200
- **Beschreibung**: Smart Wide Format MFPs
- **Product Type**: `inkjet_plotter`

---

### 3. IM Series (Smart MFP)

#### IM C Series (Color)
- **Pattern**: `IM C\d{3,4}[suffix]`
- **Beispiele**:
  - IM C400F, IM C401F
  - IM C4510, IM C4510(A)
- **Beschreibung**: Smart Color MFPs (neueste Generation)
- **Product Type**: `laser_multifunction`
- **Features**: Cloud-ready, Smart Operation Panel

#### IM Series (Monochrome)
- **Pattern**: `IM \d{4}[suffix]`
- **Beispiele**:
  - IM 2500A, IM 3000A, IM 3500A
  - IM 2702
- **Beschreibung**: Smart Monochrome MFPs
- **Product Type**: `laser_multifunction`

---

### 4. MP Series (Office MFP)

#### MP C Series (Color)
- **Pattern**: `MP C\d{3,4}[suffix]`
- **Beispiele**:
  - MP C2503SP, MP C501SP
- **Beschreibung**: Color Office MFPs
- **Product Type**: `laser_multifunction`
- **Suffixe**: SP (Special Performance)

#### MP Series (Monochrome)
- **Pattern**: `MP \d{4}[suffix]`
- **Beispiele**:
  - MP 2014AD
  - MP 2555SP, MP 3055SP, MP 6055SP
- **Beschreibung**: Monochrome Office MFPs
- **Product Type**: `laser_multifunction`
- **Suffixe**: AD (Advanced Duplex), SP (Special Performance)

---

### 5. Aficio MP Series (Legacy)

#### Aficio MP C Series (Color)
- **Pattern**: `AFICIO MP C\d{3,4}`
- **Beispiele**:
  - Aficio MP C2030
  - Aficio MP C2800, MP C3500
- **Beschreibung**: Legacy Color MFPs
- **Product Type**: `laser_multifunction`

#### Aficio MP Series (Monochrome)
- **Pattern**: `AFICIO MP \d{3}`
- **Beispiele**: Aficio MP 171, MP 161
- **Beschreibung**: Legacy Monochrome MFPs
- **Product Type**: `laser_multifunction`

---

### 6. SP Series (Printer)

#### SP C Series (Color)
- **Pattern**: `SP C\d{3}[suffix]`
- **Beispiele**: SP C261DNw
- **Beschreibung**: Color Laser Printers
- **Product Type**: `laser_printer`

#### SP Series (Monochrome)
- **Pattern**: `SP \d{3}[suffix]`
- **Beispiele**:
  - SP 230DNw, SP 230SFNw
  - SP 311
- **Beschreibung**: Monochrome Laser Printers
- **Product Type**: `laser_printer`

---

### 7. P Series (Modern Printer)

#### P C Series (Color)
- **Pattern**: `P C\d{3}[suffix]`
- **Beispiele**: P C200W
- **Beschreibung**: Modern Color Printers
- **Product Type**: `laser_printer`

#### P Series (Monochrome)
- **Pattern**: `P \d{3}`
- **Beispiele**: P 502
- **Beschreibung**: Modern Monochrome Printers
- **Product Type**: `laser_printer`

---

### 8. Aficio SG Series (GelJet)

#### Aficio SG Series
- **Pattern**: `(AFICIO )?SG \d{4}[suffix]`
- **Beispiele**:
  - Aficio SG 2100N
  - SG 3110DN, SG 3100SNw
- **Beschreibung**: GelJet Color Printers
- **Product Type**: `inkjet_printer`
- **Technologie**: Liquid Gel (Ricoh-eigene Tinten-Technologie)

---

## Pattern-Priorität

Die Patterns werden in dieser Reihenfolge geprüft:

1. **Production Printing** (Pro C, Pro VC, Pro 8)
2. **Large Format/CAD** (MP W, IM CW)
3. **IM Series** (IM C, IM)
4. **MP Series** (MP C, MP)
5. **Aficio MP Series** (Aficio MP C, Aficio MP)
6. **SP Series** (SP C, SP)
7. **P Series** (P C, P)
8. **Aficio SG Series** (GelJet)

Diese Reihenfolge stellt sicher, dass spezifischere Patterns (z.B. "Pro C") vor allgemeineren Patterns (z.B. "MP C") geprüft werden.

---

## Modellnummern-Struktur

### Pro C Format
```
Pro C[Modell][Suffix]

Beispiel: Pro C5300s
- Pro C: Production Color Serie
- 5300: Modellnummer (5xxx Serie)
- s: Special features
```

### IM Format
```
IM [C][Modell][Suffix]

Beispiel: IM C4510(A)
- IM: Intelligent Machine
- C: Color (optional)
- 4510: Modellnummer (4xxx Serie)
- (A): Advanced features
```

### MP Format
```
MP [C][Modell][Suffix]

Beispiel: MP C2503SP
- MP: Multi-Purpose
- C: Color (optional)
- 2503: Modellnummer (2xxx Serie)
- SP: Special Performance
```

---

## Suffix-Bedeutungen

| Suffix | Bedeutung |
|--------|-----------|
| **SP** | Special Performance |
| **AD** | Advanced Duplex |
| **DNw** | Duplex + Network + Wireless |
| **SFNw** | Scanner + Fax + Network + Wireless |
| **s** | Special features (Production) |
| **sx** | Special extended (Production) |
| **(A)** | Advanced features |
| **F** | Fax |
| **W** | Wireless |

---

## Test-Abdeckung

✅ **29/29 Tests bestanden** (100%)

- Production: 5/5
- Large Format: 3/3
- IM Series: 7/7
- MP Series: 4/4
- Aficio MP: 3/3
- SP Series: 3/3
- P Series: 2/2
- Aficio SG: 2/2

---

## Beispiel-Output

```python
from utils.series_detector import detect_series
from utils.product_type_mapper import get_product_type

# Production
result = detect_series('Pro C5300s', 'Ricoh')
# {
#     'series_name': 'Pro C',
#     'model_pattern': 'Pro C5xxx',
#     'series_description': 'Ricoh Pro C5xxx series production color systems'
# }
product_type = get_product_type('Pro C')
# → 'production_printer'

# Smart MFP
result = detect_series('IM C400F', 'Ricoh')
# {
#     'series_name': 'IM C',
#     'model_pattern': 'IM C4xxx',
#     'series_description': 'Ricoh IM C4xxx series smart color MFPs'
# }
product_type = get_product_type('IM C')
# → 'laser_multifunction'

# GelJet Printer
result = detect_series('Aficio SG 3110DN', 'Ricoh')
# {
#     'series_name': 'Aficio SG',
#     'model_pattern': 'Aficio SG 3xxx',
#     'series_description': 'Ricoh Aficio SG 3xxx series GelJet printers'
# }
product_type = get_product_type('Aficio SG')
# → 'inkjet_printer'
```

---

## Regex-Patterns (Technisch)

### Production
```regex
^PRO\s+C(\d{3,4})([A-Z]{0,2})$      # Pro C
^PRO\s+VC(\d{5})$                   # Pro VC
^PRO\s+(8\d{3})$                    # Pro 8
```

### Large Format
```regex
^(?:AFICIO\s+)?MP\s+W(\d{4})$       # MP W
^IM\s+CW(\d{4})$                    # IM CW
```

### IM Series
```regex
^IM\s+C(\d{3,4})([A-Z]?)\(?[A-Z]?\)?$   # IM C
^IM\s+(\d{4})([A-Z]?)$                  # IM
```

### MP Series
```regex
^MP\s+C(\d{3,4})([A-Z]{0,3})$       # MP C
^MP\s+(\d{4})([A-Z]{0,3})$          # MP
```

### Aficio MP
```regex
^AFICIO\s+MP\s+C(\d{3,4})$          # Aficio MP C
^AFICIO\s+MP\s+(\d{3})$             # Aficio MP
```

### SP/P Series
```regex
^SP\s+C(\d{3})([A-Z]{0,5})$         # SP C
^SP\s+(\d{3})([A-Z]{0,5})$          # SP
^P\s+C(\d{3})([A-Z]?)$              # P C
^P\s+(\d{3})$                       # P
```

### Aficio SG
```regex
^(?:AFICIO\s+)?SG\s+(\d{4})([A-Z]{0,5})$   # Aficio SG
```

---

## Besonderheiten

### 1. **IM Series = Smart Operation**
Die IM-Serie ist Ricohs neueste Generation mit:
- Smart Operation Panel (10.1" Touchscreen)
- Cloud-ready
- App-Integration
- Ersetzt die MP-Serie

### 2. **GelJet-Technologie**
Aficio SG verwendet **Liquid Gel** statt normaler Tinte:
- Schneller als Laser
- Günstiger als Laser
- Wasserfest
- Ricoh-eigene Technologie

### 3. **Wide Format**
Ricoh bietet zwei Wide Format Serien:
- **MP W**: Legacy Wide Format (Aficio MP W3601)
- **IM CW**: Moderne Smart Wide Format (IM CW2200)

### 4. **Flexible Prefix-Erkennung**
Das System entfernt automatisch "RICOH " und "AFICIO " Prefixe:
- `Ricoh IM C400F` → `IM C400F` → IM C
- `Aficio MP W3601` → `MP W3601` → MP W

---

## Integration

Die Ricoh-Erkennung ist vollständig in `series_detector.py` integriert:

```python
from utils.series_detector import detect_series

series_data = detect_series('IM C400F', 'Ricoh')
series_data = detect_series('Pro C5300s', 'Ricoh')
series_data = detect_series('Aficio SG 3110DN', 'Ricoh')
```

---

## Zusammenfassung

Die Ricoh Series Detection unterstützt:

- ✅ Production (Pro C, Pro VC, Pro 8)
- ✅ Large Format (MP W, IM CW)
- ✅ Smart MFP (IM C, IM)
- ✅ Office MFP (MP C, MP)
- ✅ Legacy MFP (Aficio MP C, Aficio MP)
- ✅ Printer (SP C, SP, P C, P)
- ✅ GelJet (Aficio SG)
- ✅ 100% Test-Abdeckung (29/29 Tests)
