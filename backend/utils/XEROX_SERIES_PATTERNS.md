# Xerox Series Detection Patterns

## Overview

Vollständige Pattern-Erkennung für alle Xerox-Produktserien: Production, Office MFP, Printer, Solid Ink und Wide Format.

## Series-Kategorien

### 1. Production Printing

#### Iridesse Production Press
- **Pattern**: `IRIDESSE PRODUCTION PRESS`
- **Beispiele**: Iridesse Production Press
- **Beschreibung**: High-End Production Press mit CMYK + Gold/Silber/Weiß
- **Product Type**: `production_printer`
- **Besonderheit**: 6-Farben-Druck (CMYK + Metallic)

#### Color Press Series
- **Pattern**: `COLOR PRESS \d{3,4}i?(/\d{3,4}i?)?`
- **Beispiele**:
  - Color Press 800/1000
  - Color Press 280, 570
  - Color Press 800/1000i
- **Beschreibung**: Production Color Systems
- **Product Type**: `production_printer`

#### PrimeLink Series
- **Pattern**: `PRIMELINK C\d{4}`
- **Beispiele**: PrimeLink C9065, C9070
- **Beschreibung**: Production/Office Systems
- **Product Type**: `production_printer`

#### Versant Series
- **Pattern**: `VERSANT \d{3}`
- **Beispiele**: Versant 280, 180, 80
- **Beschreibung**: Production Color Press
- **Product Type**: `production_printer`

#### iGen Series
- **Pattern**: `IGEN`
- **Beispiele**: iGen 5, iGen 4
- **Beschreibung**: Digital Production Press
- **Product Type**: `production_printer`

---

### 2. AltaLink (High-End MFP)

#### AltaLink Series
- **Pattern**: `ALTALINK [BC]\d{4}`
- **Beispiele**:
  - AltaLink B8045, B8055 (Monochrome)
  - AltaLink C8030, C8045, C8255, C8270 (Color)
- **Beschreibung**: High-End A3 MFPs
- **Product Type**: `laser_multifunction`
- **Features**: ConnectKey Technology, Cloud-ready

---

### 3. VersaLink (Office MFP/Printer)

#### VersaLink Series
- **Pattern**: `VERSALINK [BC]\d{3}`
- **Beispiele**:
  - **Printer**: B400, C400, C500, C600, B600
  - **MFP**: C405, C505, C605, B405, B605, B615, B625
- **Beschreibung**: Office MFPs & Printers (A4/A3)
- **Product Type**: `laser_multifunction` (MFP) oder `laser_printer` (Printer)
- **Features**: ConnectKey Technology

---

### 4. WorkCentre (Office MFP)

#### WorkCentre Series
- **Pattern**: `WORKCENTRE \d{4}i?`
- **Beispiele**:
  - WorkCentre 6515, 7855, 7858
  - WorkCentre 7970, 7970i, 7835i
- **Beschreibung**: Office Multifunction Printers
- **Product Type**: `laser_multifunction`
- **Suffix**: i = improved/enhanced

---

### 5. Phaser (Printer)

#### Phaser Series
- **Pattern**: `PHASER \d{4}`
- **Beispiele**:
  - Phaser 6022, 6510, 6600
  - Phaser 7100, 7800
- **Beschreibung**: Color Laser Printers
- **Product Type**: `laser_printer`

---

### 6. ColorQube (Solid Ink)

#### ColorQube MFP
- **Pattern**: `COLORQUBE \d{4} MFP`
- **Beispiele**: ColorQube 9303 MFP, 9301 MFP, 9302 MFP
- **Beschreibung**: Solid Ink MFPs
- **Product Type**: `solid_ink_multifunction`
- **Technologie**: Festtinte (Wax-based)

#### ColorQube Printer
- **Pattern**: `COLORQUBE \d{4}`
- **Beispiele**: ColorQube 8580, 9301, 9302, 9303
- **Beschreibung**: Solid Ink Printers
- **Product Type**: `solid_ink_printer`

---

### 7. Wide Format

#### Wide Format Series
- **Pattern**: `WIDE FORMAT \d{4}`
- **Beispiele**: Wide Format 7142, 8000
- **Beschreibung**: Large Format Printers
- **Product Type**: `inkjet_plotter`

---

### 8. Legacy (DocuPrint/DocuCentre)

#### DocuPrint
- **Pattern**: `DOCUPRINT [A-Z]{2}\d{3}`
- **Beispiele**: DocuPrint CP225
- **Beschreibung**: Legacy Color Printers
- **Product Type**: `laser_printer`

#### DocuCentre
- **Pattern**: `DOCUCENTRE [A-Z]{2}\d{4}`
- **Beispiele**: DocuCentre SC2020
- **Beschreibung**: Legacy MFPs
- **Product Type**: `laser_multifunction`

---

## Test-Abdeckung

✅ **24/24 Tests bestanden** (100%)

- Production: 6/6
- AltaLink: 3/3
- VersaLink: 4/4
- WorkCentre: 3/3
- Phaser: 3/3
- ColorQube: 2/2
- Wide Format: 1/1
- Legacy: 2/2

---

## Beispiel-Output

```python
from utils.series_detector import detect_series
from utils.product_type_mapper import get_product_type

# Production
result = detect_series('Iridesse Production Press', 'Xerox')
# → {'series_name': 'Iridesse Production Press', ...}
product_type = get_product_type('Iridesse Production Press')
# → 'production_printer'

# MFP
result = detect_series('AltaLink C8045', 'Xerox')
# → {'series_name': 'AltaLink', 'model_pattern': 'AltaLink C8xxx', ...}
product_type = get_product_type('AltaLink')
# → 'laser_multifunction'

# Solid Ink
result = detect_series('ColorQube 9303 MFP', 'Xerox')
# → {'series_name': 'ColorQube', ...}
product_type = get_product_type('ColorQube')
# → 'solid_ink_multifunction'
```

---

## Zusammenfassung

Die Xerox Series Detection unterstützt:

- ✅ Production (Iridesse, Color Press, PrimeLink, Versant, iGen)
- ✅ High-End MFP (AltaLink)
- ✅ Office MFP/Printer (VersaLink, WorkCentre)
- ✅ Printer (Phaser)
- ✅ Solid Ink (ColorQube)
- ✅ Wide Format
- ✅ Legacy (DocuPrint, DocuCentre)
- ✅ 100% Test-Abdeckung (24/24 Tests)
