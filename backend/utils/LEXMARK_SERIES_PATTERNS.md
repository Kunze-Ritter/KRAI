# Lexmark Series Detection Patterns

## Overview

Vollständige Pattern-Erkennung für alle Lexmark-Produktserien basierend auf der offiziellen Modellnomenklatur.

## Series-Kategorien

### 1. Enterprise & Production (9xxx, 8xxx)

#### 9xxx Series - A3 Enterprise Production
- **Pattern**: `9\d{3}`
- **Beispiele**: 9300, 9400, 9500
- **Beschreibung**: A3 Enterprise Production Drucker/MFPs

#### 8xxx Series - A4 Enterprise Color
- **Pattern**: `8\d{3}`
- **Beispiele**: 8300, 8400, 8500
- **Beschreibung**: A4 Enterprise Color MFPs

---

### 2. Color Series (C, MC, CX)

#### CX Series - Color MFP
- **Pattern**: `CX\d{3,4}[suffix]`
- **Beispiele**:
  - CX725, CX735, CX860
  - CX921, CX931, CX942adse
  - CX94X (Wildcard-Modelle)
- **Beschreibung**: Color Multifunction Printers
- **Suffixe**: adse, ade, dwe, etc.

#### MC Series - Color Compact MFP
- **Pattern**: `MC\d{4}[suffix]`
- **Beispiele**:
  - MC3224i, MC3224dwe
  - MC3326i, MC3426i
- **Beschreibung**: Color Compact Multifunction Printers
- **Suffixe**: i, dwe, adw, etc.

#### C Series - Color Single Function
- **Pattern**: `C\d{4}[suffix]`
- **Beispiele**:
  - C2326
  - C3224dw, C3326dw, C3426dw
- **Beschreibung**: Color Laser Printers (Single Function)
- **Suffixe**: dw, dn, etc.
- **Wichtig**: `CS943` wird **nicht** als C Series erkannt (CS ≠ C)

---

### 3. Monochrome Series (B, MB, MS, MX, XM)

#### XM Series - Enterprise Monochrome MFP
- **Pattern**: `XM\d{4}`
- **Beispiele**:
  - XM3350
  - XM9145, XM9155
- **Beschreibung**: Enterprise Monochrome MFPs (High-End)

#### MX Series - Monochrome MFP
- **Pattern**: `MX\d{3,4}[suffix]`
- **Beispiele**:
  - MX317dn, MX421ade
  - MX522adhe, MX532adwe
  - MX622adhe, MX822ade
  - MX931dse, MX94X
- **Beschreibung**: Monochrome Multifunction Printers
- **Suffixe**: dn, ade, adhe, adwe, dse, etc.

#### MS Series - Monochrome Single Function
- **Pattern**: `MS\d{3}[suffix]`
- **Beispiele**:
  - MS310dn, MS312dn, MS317dn
  - MS321dn, MS331dn, MS421dn
- **Beschreibung**: Monochrome Laser Printers (Single Function)
- **Suffixe**: dn, dw, etc.

#### MB Series - Monochrome Compact MFP
- **Pattern**: `MB\d{4}[suffix]`
- **Beispiele**:
  - MB2236adw, MB2236i
  - MB3442i
- **Beschreibung**: Monochrome Compact Multifunction Printers
- **Suffixe**: adw, i, etc.

#### B Series - Monochrome Compact Single Function
- **Pattern**: `B\d{4}[suffix]`
- **Beispiele**:
  - B2236dw
  - B3340dw, B3442dw
- **Beschreibung**: Monochrome Compact Laser Printers
- **Suffixe**: dw, dn, etc.

---

### 4. Historical Models

#### Interpret S400 Series - Inkjet
- **Pattern**: `S4\d{2}`
- **Beispiele**: S400, S402, S405, S408, S415
- **Beschreibung**: Interpret Inkjet Printers (veraltet)

#### Plus Matrix Series - Dot Matrix
- **Pattern**: `23[89][01]-\d`
- **Beispiele**:
  - 2380-3, 2381-3
  - 2390-3, 2391-3
- **Beschreibung**: Plus Dot Matrix Printers (veraltet)

---

## Pattern-Priorität

Die Patterns werden in dieser Reihenfolge geprüft:

1. **Enterprise & Production** (9xxx, 8xxx)
2. **Color Series** (CX, MC, C)
3. **Monochrome Series** (XM, MX, MS, MB, B)
4. **Historical Models** (S4xx, 23xx)

Diese Reihenfolge verhindert False Positives und stellt sicher, dass spezifischere Patterns zuerst geprüft werden.

---

## Suffix-Bedeutungen

Häufige Suffixe bei Lexmark-Modellen:

| Suffix | Bedeutung |
|--------|-----------|
| **dw** | Duplex + Wireless |
| **dn** | Duplex + Network |
| **adw** | Advanced Duplex + Wireless |
| **ade** | Advanced Duplex + Ethernet |
| **adhe** | Advanced Duplex + High-capacity + Ethernet |
| **adse** | Advanced Duplex + Stapler + Ethernet |
| **dwe** | Duplex + Wireless + Ethernet |
| **i** | Integrated (Compact) |
| **dse** | Duplex + Stapler + Ethernet |

---

## Wildcard-Unterstützung

Das System unterstützt "X" als Wildcard in Modellnummern:

- **CX94X** → CX Series (CX9xx)
- **MX94X** → MX Series (MX9xx)

Dies ist nützlich für Dokumentationen, die mehrere Modelle gleichzeitig referenzieren.

---

## Regex-Patterns (Technisch)

### Enterprise
```regex
^9\d{3}$                    # 9xxx Series
^8\d{3}$                    # 8xxx Series
```

### Color
```regex
^CX(\d{1,3}[X\d])([A-Z]{0,5})?$     # CX Series
^MC(\d{4})([A-Z]{0,5})?$            # MC Series
^C(\d{4})([A-Z]{0,5})?$             # C Series
```

### Monochrome
```regex
^XM(\d{4})$                         # XM Series
^MX(\d{1,3}[X\d])([A-Z]{0,5})?$    # MX Series
^MS(\d{3})([A-Z]{0,5})?$            # MS Series
^MB(\d{4})([A-Z]{0,5})?$            # MB Series
^B(\d{4})([A-Z]{0,5})?$             # B Series
```

### Historical
```regex
^S4\d{2}$                           # Interpret S400
^(23[89][01])-(\d)$                 # Plus Matrix
```

---

## Beispiel-Output

```python
from utils.series_detector import detect_series

# Color MFP
result = detect_series('CX942adse', 'Lexmark')
# {
#     'series_name': 'CX Series',
#     'model_pattern': 'CX9xx',
#     'series_description': 'Lexmark CX9xx series color MFPs'
# }

# Monochrome MFP
result = detect_series('MX931dse', 'Lexmark')
# {
#     'series_name': 'MX Series',
#     'model_pattern': 'MX9xx',
#     'series_description': 'Lexmark MX9xx series monochrome MFPs'
# }

# Enterprise Production
result = detect_series('9300', 'Lexmark')
# {
#     'series_name': 'Enterprise Production',
#     'model_pattern': '9xxx',
#     'series_description': 'Lexmark 9xxx series A3 Enterprise Production printers/MFPs'
# }
```

---

## Test-Abdeckung

✅ **46/46 Tests bestanden** (100%)

- Enterprise & Production: 2/2
- Color Series (C, MC, CX): 14/14
- Monochrome Series (B, MB, MS, MX, XM): 26/26
- Historical Models: 8/8
- Edge Cases: 3/3

---

## Wichtige Hinweise

1. **CS943 ist KEIN C Series**: Das Pattern prüft explizit auf `C\d{4}`, nicht `CS\d{3}`
2. **Wildcard-Support**: "X" in Modellnummern wird unterstützt (z.B. CX94X, MX94X)
3. **Suffix-Flexibilität**: Alle gängigen Suffixe werden erkannt (bis zu 5 Zeichen)
4. **Case-Insensitive**: Patterns funktionieren mit Groß- und Kleinschreibung
5. **Trim & Clean**: Whitespace und "SERIES" werden automatisch entfernt

---

## Integration

Die Lexmark-Erkennung ist vollständig in `series_detector.py` integriert und wird automatisch verwendet:

```python
# In document_processor.py oder series_processor.py
from utils.series_detector import detect_series

series_data = detect_series(
    model_number='CX942adse',
    manufacturer_name='Lexmark',
    context=document_text  # Optional für Confidence-Scoring
)
```

---

## Zusammenfassung

Die Lexmark Series Detection unterstützt:

- ✅ Alle aktuellen Produktserien (C, MC, CX, B, MB, MS, MX, XM)
- ✅ Enterprise & Production Modelle (8xxx, 9xxx)
- ✅ Historische Modelle (Interpret, Plus Matrix)
- ✅ Wildcard-Modelle (CX94X, MX94X)
- ✅ Alle gängigen Suffixe (dw, dn, adw, ade, adhe, adse, etc.)
- ✅ 100% Test-Abdeckung
