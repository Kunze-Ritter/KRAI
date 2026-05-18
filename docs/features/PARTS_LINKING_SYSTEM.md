# Parts Linking System 🔧

## Problem:
Parts werden extrahiert aber NICHT mit Error Codes oder Products verknüpft!

## Lösung:

### 1. ✅ Wiederverwendbares Modul
**Datei:** `backend/processors/parts_linker.py`

**Funktionen:**
- `find_parts_in_error_solution()` - Findet Parts die in Error Lösung erwähnt werden
- `find_parts_near_error_code()` - Findet Parts nahe beim Error Code (gleiche Seite)
- `link_parts_to_error_codes()` - Verknüpft Parts mit Error Codes
- `find_parts_for_product()` - Findet Parts für ein Product
- `extract_parts_from_context()` - Extrahiert Part Numbers aus Text
- `validate_parts_linking()` - Validiert Verknüpfung mit Statistiken

### 2. ✅ Model Update
**Datei:** `backend/processors/models.py`

Zu `ExtractedPart` hinzugefügt:
```python
related_error_codes: List[str] = []  # Error codes die dieses Part erwähnen
related_products: List[str] = []     # Products die dieses Part nutzen
chunk_id: Optional[str] = None       # Für Bilder (wie bei Error Codes)
```

## 📊 Verknüpfungs-Strategien:

### Strategie 1: Parts in Error Solution
```
Error Code: 66.60.32
Solution: "Replace formatter (RM1-12345-000)"
         ↓
Part: RM1-12345-000 → related_error_codes = ["66.60.32"]
```

### Strategie 2: Parts in Nähe (gleiche Seite)
```
Page 45: Error Code 66.60.32
Page 46: Part RM1-12345-000
         ↓
Part: RM1-12345-000 → related_error_codes = ["66.60.32"]
```

### Strategie 3: Parts für Product
```
Product: HP E877
Parts Catalog: RM1-12345-000 compatible_models = "E877, E878"
              ↓
Part: RM1-12345-000 → related_products = ["E877"]
```

## 🚀 Integration in Document Processor:

```python
# Nach Error Code Extraction:
error_codes = extractor.extract_from_text(text, page)

# Nach Parts Extraction:
parts = parts_extractor.extract_from_text(text, page)

# Verknüpfe Parts mit Error Codes
from backend.processors.parts_linker import link_parts_to_error_codes

links = link_parts_to_error_codes(
    error_codes=error_codes,
    parts=parts,
    strategy="both",  # solution + proximity
    verbose=True
)

# Setze related_error_codes für jedes Part
for error_code, part_numbers in links.items():
    for part in parts:
        if part.part_number in part_numbers:
            part.related_error_codes.append(error_code)

# Verknüpfe Parts mit Products
from backend.processors.parts_linker import find_parts_for_product

for product in products:
    product_parts = find_parts_for_product(
        product=product,
        parts=parts,
        verbose=True
    )

    for part in parts:
        if part.part_number in product_parts:
            part.related_products.append(product.model_number)
```

## 📝 Verwendungs-Beispiele:

### Beispiel 1: Service Manual mit Parts
```python
# Service Manual: HP E877 Service Manual
# Seite 45: Error 66.60.32 - Formatter failure
# Seite 46: Part RM1-12345-000 - Formatter Assembly

# Nach Processing:
error = error_codes[0]  # 66.60.32
part = parts[0]         # RM1-12345-000

print(part.related_error_codes)  # ["66.60.32"]
print(error.solution_text)       # "Replace formatter (RM1-12345-000)"
```

### Beispiel 2: Parts Catalog
```python
# Parts Catalog: HP Parts List
# Part RM1-12345-000 compatible with E877, E878, E879

# Nach Processing:
part = parts[0]  # RM1-12345-000
print(part.related_products)  # ["E877", "E878", "E879"]
```

### Beispiel 3: Progressive Search mit Parts
```python
# In progressive_search.py:
# Wenn Error Code gefunden, suche passende Parts:

error_code = "66.60.32"
parts = db.table('vw_parts').select('*').contains(
    'related_error_codes', [error_code]
).execute()

# Zeige Parts:
for part in parts.data:
    print(f"• {part['part_number']} - {part['part_name']}")
```

## 🗄️ Datenbank Schema Update:

### Tabelle: krai_parts.parts_catalog

Neue Spalten hinzufügen:
```sql
ALTER TABLE krai_parts.parts_catalog
ADD COLUMN related_error_codes TEXT[] DEFAULT '{}',
ADD COLUMN related_products TEXT[] DEFAULT '{}',
ADD COLUMN chunk_id UUID REFERENCES krai_intelligence.chunks(id);

-- Index für schnelle Suche
CREATE INDEX idx_parts_error_codes ON krai_parts.parts_catalog USING GIN(related_error_codes);
CREATE INDEX idx_parts_products ON krai_parts.parts_catalog USING GIN(related_products);
CREATE INDEX idx_parts_chunk_id ON krai_parts.parts_catalog(chunk_id);
```

### View Update: vw_parts

```sql
CREATE OR REPLACE VIEW vw_parts AS
SELECT
    p.id,
    p.part_number,
    p.part_name,
    p.part_description,
    p.part_category,
    p.manufacturer_id,
    m.name as manufacturer_name,
    p.unit_price_usd,
    p.compatible_models,
    p.related_error_codes,  -- NEU!
    p.related_products,     -- NEU!
    p.chunk_id,             -- NEU!
    p.created_at,
    p.updated_at
FROM krai_parts.parts_catalog p
LEFT JOIN krai_core.manufacturers m ON m.id = p.manufacturer_id;
```

## 🔍 Progressive Search Update:

In `progressive_search.py` Parts-Suche verbessern:

```python
# AKTUELL: Sucht nur nach manufacturer_id + keyword
part_response = database_service.client.table('vw_parts').select(
    'part_number, part_name'
).eq('manufacturer_id', mfr_id).ilike('part_name', f'*{keyword}*').limit(3).execute()

# NEU: Sucht auch nach related_error_codes
part_response = database_service.client.table('vw_parts').select(
    'part_number, part_name, related_error_codes'
).or_(
    f'manufacturer_id.eq.{mfr_id},related_error_codes.cs.{{{error_code}}}'
).limit(5).execute()
```

## 📊 Erwartete Ergebnisse:

Nach Implementation:
- ✅ **60%+ Parts** haben `related_error_codes`
- ✅ **80%+ Parts** haben `related_products`
- ✅ **Progressive Search** zeigt relevante Parts statt zufällige
- ✅ **Bessere Ersatzteil-Empfehlungen**

## 🎯 Nächste Schritte:

1. ⏳ Integration in `document_processor.py`
2. ⏳ Datenbank Schema Update (SQL)
3. ⏳ Progressive Search Update
4. ⏳ Test mit Service Manual + Parts Catalog

## 💡 Vorteile:

1. **Service Manual Parts** → Direkt mit Error Codes verknüpft
2. **Parts Catalog Parts** → Mit Products verknüpft
3. **Intelligente Suche** → Zeigt nur relevante Parts
4. **Bessere UX** → User sieht sofort welche Parts er braucht

---

**Status:** Modul erstellt, Model updated, bereit für Integration! 🚀
