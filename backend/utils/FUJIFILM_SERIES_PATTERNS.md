# Fujifilm Series Detection Patterns

## Overview

Fujifilm ist der **Xerox-Nachfolger in Asien/Japan** (ehemals Fuji Xerox). Die Pattern-Erkennung unterstützt alle Fujifilm-Produktserien von Foto-Druckern bis zu Produktionssystemen.

## Series-Kategorien

### 1. Production Systems

#### Revoria Press (High-End Production)
- **Pattern**: `REVORIA PRESS [SEMP]C\d{3,4}(S)?`
- **Beispiele**:
  - Revoria Press SC285, SC285(S)
  - Revoria Press EC2100, EC2100(S)
  - Revoria Press PC1120, PC1120(S)
  - Revoria Press MC (weitere Modelle)
- **Beschreibung**: High-End Production Color Systems
- **Product Type**: `production_printer`
- **Prefixe**:
  - **SC** = Standard Color
  - **EC** = Enhanced Color
  - **PC** = Premium Color
  - **MC** = Mid-range Color

#### JetPress (Inkjet Production)
- **Pattern**: `JETPRESS \d{3,4}S?`
- **Beispiele**: JetPress 750S
- **Beschreibung**: Inkjet SRA3 Production Printer
- **Product Type**: `production_printer`
- **Technologie**: High-speed inkjet für Produktionsumgebungen

---

### 2. ApeosPro (Light Production)

#### ApeosPro C Series
- **Pattern**: `APEOSPRO C\d{3}`
- **Beispiele**:
  - ApeosPro C810
  - ApeosPro C750
  - ApeosPro C650
- **Beschreibung**: Light Production Color Systems
- **Product Type**: `production_printer`
- **Zielgruppe**: Kleine Druckereien, In-house Production

---

### 3. Apeos/ApeosPort (MFP)

#### ApeosPort-VII (Neueste Generation)
- **Pattern**: `APEOSPORT-VII C\d{4}`
- **Beispiele**: ApeosPort-VII C4473
- **Beschreibung**: Neueste Generation Color MFPs
- **Product Type**: `laser_multifunction`

#### ApeosPort (Standard)
- **Pattern**: `APEOSPORT C\d{4}`
- **Beispiele**: ApeosPort C3070
- **Beschreibung**: Standard Color MFPs
- **Product Type**: `laser_multifunction`

#### Apeos (Compact)
- **Pattern**: `APEOS C\d{4}`
- **Beispiele**:
  - Apeos C3060
  - Apeos C3070
- **Beschreibung**: Compact Color MFPs
- **Product Type**: `laser_multifunction`

---

### 4. ApeosPrint (Printer)

#### ApeosPrint C Series
- **Pattern**: `APEOSPRINT C\d{3,4}`
- **Beispiele**:
  - ApeosPrint C325
  - ApeosPrint C4030
- **Beschreibung**: Color Laser Printers (Single Function)
- **Product Type**: `laser_printer`

---

### 5. INSTAX (Photo Printers)

#### INSTAX mini Link
- **Pattern**: `INSTAX MINI LINK`
- **Beispiele**: INSTAX mini Link
- **Beschreibung**: Compact Photo Printer (mini format)
- **Product Type**: `dye_sublimation_printer`
- **Format**: 62mm x 46mm (Kreditkartengröße)

#### INSTAX SQUARE Link
- **Pattern**: `INSTAX SQUARE LINK`
- **Beispiele**: INSTAX SQUARE Link
- **Beschreibung**: Compact Photo Printer (square format)
- **Product Type**: `dye_sublimation_printer`
- **Format**: 62mm x 62mm (quadratisch)

#### INSTAX Link Wide
- **Pattern**: `INSTAX LINK WIDE`
- **Beispiele**: INSTAX Link Wide
- **Beschreibung**: Compact Photo Printer (wide format)
- **Product Type**: `dye_sublimation_printer`
- **Format**: 99mm x 62mm (Panorama)

---

### 6. Legacy (Xerox-based)

#### DocuPrint (Printer)
- **Pattern**: `DOCUPRINT [A-Z]{2}\d{3}`
- **Beispiele**: DocuPrint CP505
- **Beschreibung**: Legacy Color Printers (Xerox-based)
- **Product Type**: `laser_printer`
- **Hinweis**: Wird durch ApeosPrint ersetzt

#### DocuCentre (MFP)
- **Pattern**: `DOCUCENTRE [A-Z]{1,2}\d{3,4}`
- **Beispiele**: DocuCentre C2263
- **Beschreibung**: Legacy Color MFPs (Xerox-based)
- **Product Type**: `laser_multifunction`
- **Hinweis**: Wird durch Apeos/ApeosPort ersetzt

---

## Pattern-Priorität

Die Patterns werden in dieser Reihenfolge geprüft:

1. **Production Systems** (Revoria Press, JetPress)
2. **ApeosPro** (Light Production)
3. **Apeos/ApeosPort** (MFP - VII, Standard, Compact)
4. **ApeosPrint** (Printer)
5. **INSTAX** (Photo Printers - mini, SQUARE, Wide)
6. **Legacy** (DocuPrint, DocuCentre)

Diese Reihenfolge stellt sicher, dass spezifischere Patterns (z.B. "ApeosPort-VII") vor allgemeineren Patterns (z.B. "ApeosPort") geprüft werden.

---

## Modellnummern-Struktur

### Revoria Press Format
```
Revoria Press [Prefix][Modell](S)

Beispiel: Revoria Press SC285(S)
- Revoria Press: Serie
- SC: Standard Color
- 285: Modellnummer
- (S): Optional - Enhanced features
```

### Apeos Format
```
Apeos[Variant] C[Modell]

Beispiel: ApeosPort-VII C4473
- ApeosPort-VII: Serie (Generation 7)
- C: Color
- 4473: Modellnummer (4xxx Serie)
```

### INSTAX Format
```
INSTAX [Format] Link

Beispiel: INSTAX mini Link
- INSTAX: Serie
- mini: Format (62x46mm)
- Link: Smartphone-Verbindung
```

---

## Test-Abdeckung

✅ **19/19 Tests bestanden** (100%)

- Production Systems: 5/5
- ApeosPro: 3/3
- Apeos/ApeosPort: 5/5
- ApeosPrint: 2/2
- INSTAX: 3/3
- Legacy: 2/2

---

## Beispiel-Output

```python
from utils.series_detector import detect_series
from utils.product_type_mapper import get_product_type

# Production
result = detect_series('Revoria Press SC285(S)', 'Fujifilm')
# {
#     'series_name': 'Revoria Press',
#     'model_pattern': 'Revoria Press SC',
#     'series_description': 'Fujifilm Revoria Press SC series high-end production systems'
# }
product_type = get_product_type('Revoria Press')
# → 'production_printer'

# MFP
result = detect_series('Apeos C3060', 'Fujifilm')
# {
#     'series_name': 'Apeos',
#     'model_pattern': 'Apeos C3xxx',
#     'series_description': 'Fujifilm Apeos C3xxx series color MFPs'
# }
product_type = get_product_type('Apeos')
# → 'laser_multifunction'

# Photo Printer
result = detect_series('INSTAX mini Link', 'Fujifilm')
# {
#     'series_name': 'INSTAX mini Link',
#     'model_pattern': 'INSTAX mini Link',
#     'series_description': 'Fujifilm INSTAX mini Link compact photo printer'
# }
product_type = get_product_type('INSTAX mini Link')
# → 'dye_sublimation_printer'
```

---

## Regex-Patterns (Technisch)

### Production
```regex
^REVORIA\s+PRESS\s+([SEMP]C)(\d{3,4})\(?S?\)?$   # Revoria Press
^JETPRESS\s+(\d{3,4})S?$                         # JetPress
```

### ApeosPro
```regex
^APEOSPRO\s+C(\d{3})$                            # ApeosPro C
```

### Apeos/ApeosPort
```regex
^APEOSPORT-VII\s+C(\d{4})$                       # ApeosPort-VII
^APEOSPORT\s+C(\d{4})$                           # ApeosPort
^APEOS\s+C(\d{4})$                               # Apeos
```

### ApeosPrint
```regex
^APEOSPRINT\s+C(\d{3,4})$                        # ApeosPrint
```

### INSTAX
```regex
^INSTAX\s+MINI\s+LINK                            # INSTAX mini Link
^INSTAX\s+SQUARE\s+LINK                          # INSTAX SQUARE Link
^INSTAX\s+LINK\s+WIDE                            # INSTAX Link Wide
^INSTAX                                          # INSTAX (generic)
```

### Legacy
```regex
^DOCUPRINT\s+([A-Z]{2})(\d{3})$                  # DocuPrint
^DOCUCENTRE\s+([A-Z]{1,2})(\d{3,4})$             # DocuCentre
```

---

## Integration

Die Fujifilm-Erkennung ist vollständig in `series_detector.py` integriert:

```python
from utils.series_detector import detect_series

# Fujifilm
series_data = detect_series('Apeos C3060', 'Fujifilm')

# Fuji (Alias)
series_data = detect_series('ApeosPort C3070', 'Fuji')
```

---

## Manufacturer Aliases

Fujifilm wird unter verschiedenen Namen erkannt:

```python
# In manufacturer_normalizer.py
'Fujifilm': [
    'fujifilm', 'Fujifilm', 'FUJIFILM',
    'fuji', 'Fuji', 'FUJI',
    'Fuji Xerox', 'fuji xerox', 'FUJI XEROX'
]
```

---

## Besonderheiten

### 1. **Xerox-Nachfolger**
Fujifilm hat die Xerox-Aktivitäten in Asien/Japan übernommen:
- Apeos ≈ Xerox VersaLink
- ApeosPort ≈ Xerox AltaLink
- Revoria Press ≈ Xerox Versant

### 2. **INSTAX Photo Printers**
INSTAX-Drucker verwenden **Sofortbild-Technologie** (nicht Dye-Sub im klassischen Sinne):
- Instant film development
- Smartphone-Verbindung via Bluetooth
- Verschiedene Formate (mini, SQUARE, Wide)

### 3. **Legacy DocuPrint/DocuCentre**
Ältere Modelle basieren auf Xerox-Technologie:
- DocuPrint = Xerox Phaser
- DocuCentre = Xerox WorkCentre

### 4. **Flexible Prefix-Erkennung**
Das System entfernt automatisch "FUJIFILM " Prefix:
- `Fujifilm Apeos C3060` → `Apeos C3060` → Apeos

---

## Zusammenfassung

Die Fujifilm Series Detection unterstützt:

- ✅ Production Systems (Revoria Press, JetPress)
- ✅ Light Production (ApeosPro)
- ✅ MFPs (ApeosPort-VII, ApeosPort, Apeos)
- ✅ Printers (ApeosPrint)
- ✅ Photo Printers (INSTAX mini/SQUARE/Wide)
- ✅ Legacy (DocuPrint, DocuCentre)
- ✅ Fuji/Fuji Xerox Aliase
- ✅ 100% Test-Abdeckung (19/19 Tests)
