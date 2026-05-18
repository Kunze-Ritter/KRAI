# Toshiba Series Detection Patterns

## Overview

Vollständige Pattern-Erkennung für alle Toshiba-Produktserien: e-STUDIO (Production & Office) und Legacy-Serien.

## Series-Kategorien

### 1. e-STUDIO Production

#### e-STUDIO Production (High-end 65+ ppm)
- **Pattern**: `e-STUDIO [6-9]\d{3}[suffix]` (>= 6500)
- **Beispiele**: e-STUDIO 7527AC, e-STUDIO 6525AC
- **Beschreibung**: High-end Production Systems (65+ ppm)
- **Product Type**: `production_printer`
- **Besonderheit**: Topmodelle mit über 65 Seiten/min

---

### 2. e-STUDIO Office

#### e-STUDIO with Suffixes (AC/AM/AS/CP)
- **Pattern**: `e-STUDIO \d{4}(AC|AM|AS|CP)`
- **Beispiele**:
  - e-STUDIO 2500AC, 3505AC (Color)
  - e-STUDIO 2822AM (Monochrome)
- **Beschreibung**: Office MFPs with Display/Scanner Options
- **Product Type**: `laser_multifunction`
- **Suffixe**:
  - **AC** = Advanced Color
  - **AM** = Advanced Monochrome
  - **AS** = Advanced Standard
  - **CP** = Compact

#### e-STUDIO General
- **Pattern**: `e-STUDIO \d{3,4}A?`
- **Beispiele**: e-STUDIO 306, 2303A, 5008A
- **Beschreibung**: Office MFPs/Printers
- **Product Type**: `laser_multifunction`

#### e-STUDIO Hybrid
- **Pattern**: `e-STUDIO HYBRID`
- **Beispiele**: e-STUDIO Hybrid
- **Beschreibung**: Paper Recycling Technology
- **Product Type**: `laser_multifunction`
- **Besonderheit**: Papierrecycling-Technologie

---

### 3. Legacy Series

#### Pagelaser
- **Pattern**: `PAGELASER [A-Z]{0,2}\s?\d{3}`
- **Beispiele**: Pagelaser GX 200
- **Beschreibung**: Legacy Printers
- **Product Type**: `laser_printer`

#### PAL Series
- **Pattern**: `PAL \d{3}`
- **Beispiele**: PAL 100
- **Beschreibung**: Legacy Printers
- **Product Type**: `laser_printer`

#### Spot Series
- **Pattern**: `SPOT \d{1}`
- **Beispiele**: Spot 3
- **Beschreibung**: Legacy Printers
- **Product Type**: `laser_printer`

#### T Series
- **Pattern**: `T-\d{3}`
- **Beispiele**: T-100
- **Beschreibung**: Legacy Printers
- **Product Type**: `laser_printer`

#### TF Series
- **Pattern**: `TF\s?\d{3}`
- **Beispiele**: TF 111
- **Beschreibung**: Legacy Printers
- **Product Type**: `laser_printer`

#### TF-P Series
- **Pattern**: `TF-P\d{3}`
- **Beispiele**: TF-P100
- **Beschreibung**: Legacy Printers
- **Product Type**: `laser_printer`

---

## Test-Abdeckung

✅ **15/15 Tests bestanden** (100%)

- e-STUDIO Production: 2/2
- e-STUDIO Office: 6/6
- e-STUDIO Hybrid: 1/1
- Legacy: 6/6

---

## Beispiel-Output

```python
from utils.series_detector import detect_series
from utils.product_type_mapper import get_product_type

# Production
result = detect_series('e-STUDIO 7527AC', 'Toshiba')
# → {'series_name': 'e-STUDIO Production', ...}
product_type = get_product_type('e-STUDIO Production')
# → 'production_printer'

# Office MFP
result = detect_series('e-STUDIO 2500AC', 'Toshiba')
# → {'series_name': 'e-STUDIO', 'model_pattern': 'e-STUDIO 2xxxAC', ...}
product_type = get_product_type('e-STUDIO')
# → 'laser_multifunction'

# Hybrid
result = detect_series('e-STUDIO Hybrid', 'Toshiba')
# → {'series_name': 'e-STUDIO Hybrid', ...}
product_type = get_product_type('e-STUDIO Hybrid')
# → 'laser_multifunction'
```

---

## Besonderheiten

### 1. **e-STUDIO Suffix-System**
Toshiba verwendet verschiedene Suffixe für unterschiedliche Ausstattungen:
- **AC** = Advanced Color (Farbe)
- **AM** = Advanced Monochrome (S/W)
- **AS** = Advanced Standard
- **CP** = Compact

### 2. **e-STUDIO Hybrid**
Einzigartige Papierrecycling-Technologie:
- Recycelt bedrucktes Papier
- Macht es wieder verwendbar
- Umweltfreundliche Lösung

### 3. **Production vs Office**
- **Production**: Modelle >= 6500 (65+ ppm)
- **Office**: Modelle < 6500

---

## Zusammenfassung

Die Toshiba Series Detection unterstützt:

- ✅ Production (e-STUDIO 65+ ppm)
- ✅ Office MFP (e-STUDIO AC/AM/AS/CP)
- ✅ Hybrid (e-STUDIO Hybrid mit Papierrecycling)
- ✅ Legacy (Pagelaser, PAL, Spot, T, TF, TF-P)
- ✅ 100% Test-Abdeckung (15/15 Tests)
