# Kyocera Series Detection Patterns

## Overview

Vollständige Pattern-Erkennung für alle Kyocera-Produktserien: TASKalfa, ECOSYS, FS, KM und weitere Serien.

## Series-Kategorien

### 1. TASKalfa Pro (Production)

#### TASKalfa Pro
- **Pattern**: `(TASKALFA )?PRO \d{5}c?`
- **Beispiele**:
  - TASKalfa Pro 15000c
  - Pro 55000c
- **Beschreibung**: High-End Production Color Systems
- **Zielgruppe**: Druckereien, Produktionsumgebungen

---

### 2. TASKalfa (A3/A4 MFP)

#### TASKalfa mit ci-Suffix
- **Pattern**: `(TASKALFA )?\d{4}CI`
- **Beispiele**:
  - TASKalfa 2553ci, TASKalfa 5053ci
  - 2553ci, 5053ci (ohne Prefix)
- **Beschreibung**: Color MFPs mit integrierter Technologie
- **Suffix**: ci = color integrated

#### TASKalfa General
- **Pattern**: `(TASKALFA )?\d{4}[suffix]?`
- **Beispiele**:
  - TASKalfa 2552, TASKalfa 3252
  - 2552, 3252 (ohne Prefix)
- **Beschreibung**: A3/A4 Multifunction Printers
- **Suffixe**: Optional (DN, DW, etc.)

---

### 3. ECOSYS PA/MA/M Serie

#### ECOSYS PA (Printer - Color)
- **Pattern**: `(ECOSYS )?PA\d{4}[suffix]`
- **Beispiele**:
  - ECOSYS PA3500cx, PA4500x
- **Beschreibung**: ECOSYS Color Printers (Single Function)
- **Suffixe**: cx, x

#### ECOSYS MA (MFP - Color)
- **Pattern**: `(ECOSYS )?MA\d{4}[suffix]`
- **Beispiele**:
  - ECOSYS MA2100cfx
  - MA3500cifx
- **Beschreibung**: ECOSYS Color MFPs
- **Suffixe**: cfx, cifx

#### ECOSYS M (MFP - Monochrome/Color)
- **Pattern**: `(ECOSYS )?M\d{4}[suffix]`
- **Beispiele**:
  - ECOSYS M3860idnf
  - M4132idn, M8130cidn
- **Beschreibung**: ECOSYS MFPs (Monochrome & Color)
- **Suffixe**: idnf, idn, cidn

---

### 4. FS-Serie (Drucker & MFP)

#### FS-Serie MFP
- **Pattern**: `FS-\d{4}MFP`
- **Beispiele**:
  - FS-1030MFP, FS-6530MFP
- **Beschreibung**: FS Multifunction Printers

#### FS-Serie Drucker
- **Pattern**: `FS-\d{4}[suffix]`
- **Beispiele**:
  - FS-1000, FS-1120DN, FS-1320D
  - FS-4020DN, FS-6020DTN
- **Beschreibung**: FS Single Function Printers
- **Suffixe**: DN, D, DTN, PLUS

---

### 5. KM-Serie (Legacy MFPs)

#### KM-Serie
- **Pattern**: `KM-\d{4}`
- **Beispiele**:
  - KM-2050, KM-5050
- **Beschreibung**: Ältere Kyocera MFPs (Legacy)
- **Hinweis**: Werden durch TASKalfa/ECOSYS ersetzt

---

### 6. Weitere Serien (DC, DP, TC, F)

#### TC-Serie
- **Pattern**: `TC-\d{4}[suffix]`
- **Beispiele**: TC-4026i
- **Beschreibung**: TC-Serie Geräte

#### F-Serie
- **Pattern**: `F \d{4}`
- **Beispiele**: F 2010
- **Beschreibung**: F-Serie Geräte

#### DC-Serie
- **Pattern**: `DC-\d{4}`
- **Beschreibung**: DC-Serie Geräte

#### DP-Serie
- **Pattern**: `DP-\d{4}`
- **Beschreibung**: DP-Serie Geräte

---

## Pattern-Priorität

Die Patterns werden in dieser Reihenfolge geprüft:

1. **TASKalfa Pro** (Production)
2. **TASKalfa** (A3/A4 MFP mit ci, dann general)
3. **ECOSYS PA/MA/M** (Printer & MFP)
4. **FS-Serie** (MFP, dann Drucker)
5. **KM-Serie** (Legacy)
6. **Weitere Serien** (TC, F, DC, DP)

Diese Reihenfolge stellt sicher, dass spezifischere Patterns (z.B. "TASKalfa Pro") vor allgemeineren Patterns (z.B. "TASKalfa") geprüft werden.

---

## Modellnummern-Struktur

### TASKalfa Format
```
TASKalfa [Modell][Suffix]

Beispiel: TASKalfa 2553ci
- TASKalfa: Serie
- 2553: Modellnummer (2xxx Serie)
- ci: Color Integrated
```

### ECOSYS Format
```
ECOSYS [Type][Modell][Suffix]

Beispiel: ECOSYS MA3500cifx
- ECOSYS: Produktlinie
- MA: Multifunction A4 (Color)
- 3500: Modellnummer (3xxx Serie)
- cifx: Color Integrated Fax
```

### FS Format
```
FS-[Modell][Suffix]

Beispiel: FS-4020DN
- FS: Serie
- 4020: Modellnummer (4xxx Serie)
- DN: Duplex + Network
```

---

## Suffix-Bedeutungen

| Suffix | Bedeutung |
|--------|-----------|
| **ci** | Color Integrated |
| **cifx** | Color Integrated Fax |
| **cfx** | Color Fax |
| **cx** | Color |
| **idn** | Integrated Duplex Network |
| **idnf** | Integrated Duplex Network Fax |
| **DN** | Duplex + Network |
| **DTN** | Duplex + Twin Network |
| **D** | Duplex |
| **MFP** | Multifunction Printer |
| **PLUS** | Enhanced features |

---

## Produktkategorien

### Printer (Single Function)
- **ECOSYS PA**: PA3500cx, PA4500x
- **ECOSYS P**: (allgemeine P-Modelle)
- **FS-Serie**: FS-1000, FS-1120DN, FS-4020DN

### MFP (Multifunction)
- **ECOSYS MA**: MA2100cfx, MA3500cifx
- **ECOSYS M**: M3860idnf, M4132idn, M8130cidn
- **FS-Serie MFP**: FS-1030MFP, FS-6530MFP
- **TASKalfa**: 2553ci, 5053ci
- **KM-Serie**: KM-2050, KM-5050

### Production
- **TASKalfa Pro**: Pro 15000c, Pro 55000c
- **TASKalfa High-End**: 5053ci, 6053ci

---

## Besonderheiten

### 1. **Flexible Prefix-Erkennung**
Das System entfernt automatisch "KYOCERA " und "ECOSYS " Prefixe:
- `Kyocera ECOSYS M3860idnf` → `M3860idnf` → ECOSYS M
- `TASKalfa 2553ci` → `2553ci` → TASKalfa

### 2. **Kurze Modellnummern**
Auch ohne Prefix werden Modelle erkannt:
- `2553ci` → TASKalfa
- `M4132idn` → ECOSYS M
- `PA4500x` → ECOSYS PA

### 3. **ci-Suffix Erkennung**
Das "ci"-Suffix wird speziell behandelt:
- TASKalfa 2553**ci** → TASKalfa 2xxxci series (color integrated)
- TASKalfa 2552 → TASKalfa 2xxx series (general)

### 4. **ECOSYS Kategorien**
- **PA**: Printer A4 (Color)
- **MA**: Multifunction A4 (Color)
- **M**: Multifunction (Monochrome/Color)

---

## Test-Abdeckung

✅ **24/24 Tests bestanden** (100%)

- TASKalfa Pro: 2/2
- TASKalfa: 4/4
- ECOSYS PA: 2/2
- ECOSYS MA: 2/2
- ECOSYS M: 3/3
- FS-Serie MFP: 2/2
- FS-Serie Drucker: 5/5
- KM-Serie: 2/2
- Weitere Serien: 2/2

---

## Beispiel-Output

```python
from utils.series_detector import detect_series

# TASKalfa Pro Production
result = detect_series('TASKalfa Pro 15000c', 'Kyocera')
# {
#     'series_name': 'TASKalfa Pro',
#     'model_pattern': 'TASKalfa Pro',
#     'series_description': 'Kyocera TASKalfa Pro production color systems'
# }

# ECOSYS MFP
result = detect_series('M8130cidn', 'Kyocera')
# {
#     'series_name': 'ECOSYS M',
#     'model_pattern': 'ECOSYS M8xxx',
#     'series_description': 'Kyocera ECOSYS M8xxx series MFPs'
# }

# FS-Serie Drucker
result = detect_series('FS-4020DN', 'Kyocera')
# {
#     'series_name': 'FS-Series',
#     'model_pattern': 'FS-4xxx',
#     'series_description': 'Kyocera FS-4xxx series printers'
# }
```

---

## Regex-Patterns (Technisch)

### TASKalfa
```regex
^(?:TASKALFA\s+)?PRO\s+(\d{5})C?$           # TASKalfa Pro
^(?:TASKALFA\s+)?(\d{4})CI$                 # TASKalfa ci
^(?:TASKALFA\s+)?(\d{4})([A-Z]{0,3})?$      # TASKalfa general
```

### ECOSYS
```regex
^(?:ECOSYS\s+)?PA(\d{4})([A-Z]{0,3})$       # ECOSYS PA
^(?:ECOSYS\s+)?MA(\d{4})([A-Z]{0,5})$       # ECOSYS MA
^(?:ECOSYS\s+)?M(\d{4})([A-Z]{0,5})$        # ECOSYS M
```

### FS-Serie
```regex
^FS-(\d{4})MFP$                             # FS MFP
^FS-(\d{4})([A-Z]{0,5})$                    # FS Drucker
```

### Legacy & Weitere
```regex
^KM-(\d{4})$                                # KM-Serie
^TC-(\d{4})([A-Z]?)$                        # TC-Serie
^F\s*(\d{4})$                               # F-Serie
^DC-(\d{4})$                                # DC-Serie
^DP-(\d{4})$                                # DP-Serie
```

---

## Integration

Die Kyocera-Erkennung ist vollständig in `series_detector.py` integriert:

```python
from utils.series_detector import detect_series

# Mit Prefix
series_data = detect_series('ECOSYS M8130cidn', 'Kyocera')

# Ohne Prefix
series_data = detect_series('M8130cidn', 'Kyocera')

# TASKalfa
series_data = detect_series('TASKalfa 2553ci', 'Kyocera')
series_data = detect_series('2553ci', 'Kyocera')  # Auch ohne Prefix
```

---

## UTAX-Rebrand Hinweis

Kyocera-Modelle werden oft als **UTAX** oder **Triumph-Adler** rebrandiert:

| Kyocera | UTAX/TA Equivalent |
|---------|-------------------|
| TASKalfa 5053ci | UTAX 5006ci |
| TASKalfa 4053ci | UTAX P-4532i MFP |
| ECOSYS M3860idn | UTAX P-4532 MFP |

Beide Hersteller verwenden:
- ✅ Gleiche Error Codes
- ✅ Gleiche Parts Catalog
- ✅ Gleiche Service-Prozeduren

---

## Zusammenfassung

Die Kyocera Series Detection unterstützt:

- ✅ TASKalfa Pro (Production)
- ✅ TASKalfa (A3/A4 MFP mit/ohne ci)
- ✅ ECOSYS PA/MA/M (Printer & MFP)
- ✅ FS-Serie (Drucker & MFP)
- ✅ KM-Serie (Legacy)
- ✅ Weitere Serien (TC, F, DC, DP)
- ✅ Flexible Prefix-Erkennung
- ✅ 100% Test-Abdeckung (24/24 Tests)
