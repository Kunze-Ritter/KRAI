# OKI Series Detection Patterns

## Overview

Vollständige Pattern-Erkennung für alle OKI-Produktserien: Production, MFP, Printer und Executive.

## Series-Kategorien

### 1. Production Printing

#### Pro9 Series (Industrial Production)
- **Pattern**: `PRO9\d{3}[suffix]`
- **Beispiele**: Pro9431dn, Pro9541dn, Pro9542dn
- **Beschreibung**: Industrial Production Printers
- **Product Type**: `production_printer`

#### Pro10 Series (Label Printers)
- **Pattern**: `PRO10[45]0`
- **Beispiele**: Pro1040, Pro1050
- **Beschreibung**: Roll-to-roll Label Printers für Packaging
- **Product Type**: `production_printer`
- **Technologie**: Spezialisiert auf Etiketten/Verpackungsdruck

---

### 2. MC Series (Color MFP)

#### MC Series
- **Pattern**: `MC\d{3}[suffix]`
- **Beispiele**:
  - MC363dn, MC573dn
  - MC853dn, MC883dn (High-End)
  - MC770dn, MC780dn
- **Beschreibung**: Color Multifunction Printers
- **Product Type**: `laser_multifunction`
- **Besonderheit**: MC883dn auch für produktive Umgebungen

---

### 3. MB Series (Monochrome MFP)

#### MB Series
- **Pattern**: `MB\d{3}[suffix]`
- **Beispiele**:
  - MB472dnw, MB492dn
  - MB562dnw
- **Beschreibung**: Monochrome Multifunction Printers
- **Product Type**: `laser_multifunction`

---

### 4. C Series (Color Printer)

#### C Series
- **Pattern**: `C\d{3}[suffix]`
- **Beispiele**:
  - C332dn, C542dn, C612dn
  - C824dn, C833dn, C843dn
- **Beschreibung**: Color LED Printers (A4/A3)
- **Product Type**: `laser_printer`
- **Technologie**: LED statt Laser

---

### 5. B Series (Monochrome Printer/MFP)

#### B Series MFP
- **Pattern**: `B\d{4} MFP`
- **Beispiele**: B2520 MFP, B2540 MFP
- **Beschreibung**: Monochrome MFPs
- **Product Type**: `laser_multifunction`

#### B Series Printer
- **Pattern**: `B\d{3}[suffix]`
- **Beispiele**:
  - B401d, B431dn
  - B512dn, B721dn, B731dn
- **Beschreibung**: Monochrome LED Printers
- **Product Type**: `laser_printer`

---

### 6. ES Series (Executive)

#### ES Series MFP
- **Pattern**: `ES\d{4} MFP`
- **Beispiele**: ES4191 MFP, ES4192 MFP
- **Beschreibung**: Executive Multifunction Printers
- **Product Type**: `laser_multifunction`

#### ES Series Printer
- **Pattern**: `ES\d{4}[suffix]`
- **Beispiele**: ES4191dn, ES5112dn
- **Beschreibung**: Executive Printers
- **Product Type**: `laser_printer`

---

### 7. CX Series (Office Color)

#### CX Series
- **Pattern**: `CX \d{4}( SERIES)?`
- **Beispiele**: CX 3500, CX 3535
- **Beschreibung**: Office Color MFPs/Devices
- **Product Type**: `laser_multifunction`

---

## Test-Abdeckung

✅ **27/27 Tests bestanden** (100%)

- Production: 4/4
- MC Series: 5/5
- MB Series: 3/3
- C Series: 5/5
- B Series: 5/5
- ES Series: 3/3
- CX Series: 2/2

---

## Beispiel-Output

```python
from utils.series_detector import detect_series
from utils.product_type_mapper import get_product_type

# Production
result = detect_series('Pro9541dn', 'OKI')
# → {'series_name': 'Pro9', 'model_pattern': 'Pro95xx', ...}
product_type = get_product_type('Pro9')
# → 'production_printer'

# Color MFP
result = detect_series('MC883dn', 'OKI')
# → {'series_name': 'MC Series', 'model_pattern': 'MC8xx', ...}
product_type = get_product_type('MC Series')
# → 'laser_multifunction'
```

---

## Zusammenfassung

Die OKI Series Detection unterstützt:

- ✅ Production (Pro9, Pro10)
- ✅ Color MFP (MC Series)
- ✅ Monochrome MFP (MB Series, B Series MFP, ES Series MFP)
- ✅ Color Printer (C Series)
- ✅ Monochrome Printer (B Series, ES Series)
- ✅ Office Color (CX Series)
- ✅ 100% Test-Abdeckung (27/27 Tests)
