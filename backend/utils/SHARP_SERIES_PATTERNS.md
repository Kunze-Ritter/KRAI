# Sharp Series Detection Patterns

## Overview

Vollständige Pattern-Erkennung für alle Sharp-Produktserien: Production, Office MFP, Printer und Legacy.

## Series-Kategorien

### 1. Production Printing

#### BP Pro Series
- **Pattern**: `BP-[9]\d[CM]\d{2,3}` (BP-90C70, BP-90C80)
- **Beispiele**: BP-90C70, BP-90C80
- **Beschreibung**: Production/Light Production Systems
- **Product Type**: `production_printer`

#### MX Production Series
- **Pattern**: `MX-[6-8]\d{3}`
- **Beispiele**: MX-6500, MX-7500, MX-8090
- **Beschreibung**: High-Performance Production MFPs
- **Product Type**: `production_printer`

---

### 2. BP Series (Office MFP & Printer)

#### BP Series MFP
- **Pattern**: `BP-\d{2}[CEQ]\d{2,3}`
- **Beispiele**:
  - BP-50C31, BP-50C55
  - BP-60C45, BP-55C26
  - BP-22C25
- **Beschreibung**: Office MFPs
- **Product Type**: `laser_multifunction`
- **Suffixe**: C (Color), E (Essentials), Q (Quality)

#### BP Printer
- **Pattern**: `BP-[CEQ]\d{3}[suffix]`
- **Beispiele**: BP-C131PW
- **Beschreibung**: Office Printers
- **Product Type**: `laser_printer`

---

### 3. MX Series (A3/A4 MFP & Printer)

#### MX Series MFP (General)
- **Pattern**: `MX-\d{4}`
- **Beispiele**: MX-3071, MX-4071, MX-3571, MX-2651
- **Beschreibung**: A3/A4 MFPs
- **Product Type**: `laser_multifunction`

#### MX-B Series (Monochrome MFP)
- **Pattern**: `MX-B\d{3,4}`
- **Beispiele**: MX-B350
- **Beschreibung**: Monochrome A4 MFPs
- **Product Type**: `laser_multifunction`

#### MX-C Series (Color MFP)
- **Pattern**: `MX-C\d{3,4}`
- **Beispiele**: MX-C300
- **Beschreibung**: Color A4 MFPs
- **Product Type**: `laser_multifunction`

#### MX-B/C Printer
- **Pattern**: `MX-[BC]\d{3}P`
- **Beispiele**: MX-B350P, MX-C300P
- **Beschreibung**: A4 Printers
- **Product Type**: `laser_printer`

---

### 4. Legacy (AR/AL Series)

#### AR Series (Legacy MFP)
- **Pattern**: `AR-\d{4}[suffix]`
- **Beispiele**: AR-6020N
- **Beschreibung**: Legacy MFPs
- **Product Type**: `laser_multifunction`

#### AL Series (Legacy Printer)
- **Pattern**: `AL-\d{4}`
- **Beispiele**: AL-2040
- **Beschreibung**: Legacy Printers
- **Product Type**: `laser_printer`

---

## Test-Abdeckung

✅ **22/22 Tests bestanden** (100%)

- Production: 5/5
- BP Series: 7/7
- MX Series: 8/8
- Legacy: 2/2

---

## Beispiel-Output

```python
from utils.series_detector import detect_series
from utils.product_type_mapper import get_product_type

# Production
result = detect_series('BP-90C70', 'Sharp')
# → {'series_name': 'BP Pro', 'model_pattern': 'BP Pro', ...}
product_type = get_product_type('BP Pro')
# → 'production_printer'

# Office MFP
result = detect_series('BP-50C31', 'Sharp')
# → {'series_name': 'BP Series', 'model_pattern': 'BP-50C', ...}
product_type = get_product_type('BP Series')
# → 'laser_multifunction'

# MX MFP
result = detect_series('MX-3071', 'Sharp')
# → {'series_name': 'MX Series', 'model_pattern': 'MX-3xxx', ...}
product_type = get_product_type('MX Series')
# → 'laser_multifunction'
```

---

## Besonderheiten

### 1. **BP Series Naming**
Sharp verwendet verschiedene Suffixe:
- **C** = Color
- **E** = Essentials (Entry-level)
- **Q** = Quality (High-end)

### 2. **MX Series Evolution**
- **MX-6xxx/7xxx/8xxx**: High-Performance Production
- **MX-2xxx/3xxx/4xxx/5xxx**: Office MFPs
- **MX-B/C**: Neuere A4-Modelle (B=Mono, C=Color)

### 3. **Legacy AR/AL**
Ältere Sharp-Modelle vor der BP/MX-Ära:
- **AR**: MFPs
- **AL**: Printers

---

## Zusammenfassung

Die Sharp Series Detection unterstützt:

- ✅ Production (BP Pro, MX Production)
- ✅ Office MFP (BP Series, MX Series, MX-B, MX-C)
- ✅ Printer (BP Printer, MX-B/C Printer)
- ✅ Legacy (AR, AL)
- ✅ 100% Test-Abdeckung (22/22 Tests)
