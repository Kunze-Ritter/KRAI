# 🚀 Migration 13 Anwenden - Documents Cleanup + document_products

## ⚡ **SCHNELL-ANLEITUNG (2 Minuten):**

### **1. Supabase SQL Editor öffnen:**
```
https://supabase.com/dashboard/project/[DEIN-PROJECT]/sql/new
```

### **2. SQL Code kopieren & ausführen:**

Siehe: `database/migrations/13_cleanup_documents_and_add_document_products.sql`

**ODER direkt hier:**

```sql
-- Migration 13: Cleanup documents table + Add document_products Many-to-Many

-- Remove unused columns (CASCADE removes dependent views)
ALTER TABLE krai_core.documents
DROP COLUMN IF EXISTS storage_url CASCADE;

ALTER TABLE krai_core.documents
DROP COLUMN IF EXISTS product_id CASCADE;

ALTER TABLE krai_core.documents
DROP COLUMN IF EXISTS manufacturer_id CASCADE;

-- Add comments
COMMENT ON COLUMN krai_core.documents.manufacturer IS 'Manufacturer name (text) - auto-detected during processing';
COMMENT ON COLUMN krai_core.documents.models IS 'Array of model numbers extracted from document';

-- Create document_products Many-to-Many relationship table
CREATE TABLE IF NOT EXISTS krai_core.document_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES krai_core.documents(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES krai_core.products(id) ON DELETE CASCADE,

    -- Relationship metadata
    is_primary_product BOOLEAN DEFAULT false,
    confidence_score DECIMAL(3,2) DEFAULT 0.80,
    extraction_method VARCHAR(50),
    page_numbers INTEGER[],

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(document_id, product_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_document_products_document_id
ON krai_core.document_products(document_id);

CREATE INDEX IF NOT EXISTS idx_document_products_product_id
ON krai_core.document_products(product_id);

CREATE INDEX IF NOT EXISTS idx_document_products_primary
ON krai_core.document_products(document_id, is_primary_product)
WHERE is_primary_product = true;

-- Comments
COMMENT ON TABLE krai_core.document_products IS 'Many-to-Many relationship between documents and products';
COMMENT ON COLUMN krai_core.document_products.is_primary_product IS 'True if this is the main product covered by the document';
COMMENT ON COLUMN krai_core.document_products.extraction_method IS 'How the product was extracted: pattern, llm, vision, or manual';

-- Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON krai_core.document_products TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON krai_core.document_products TO service_role;

-- Helper function
CREATE OR REPLACE FUNCTION krai_core.get_document_products(doc_id UUID)
RETURNS TABLE (
    product_id UUID,
    model_number VARCHAR,
    manufacturer_name VARCHAR,
    is_primary BOOLEAN,
    confidence DECIMAL,
    extraction_method VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id as product_id,
        p.model_number,
        m.name as manufacturer_name,
        dp.is_primary_product as is_primary,
        dp.confidence_score as confidence,
        dp.extraction_method
    FROM krai_core.document_products dp
    JOIN krai_core.products p ON dp.product_id = p.id
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
    WHERE dp.document_id = doc_id
    ORDER BY dp.is_primary_product DESC, dp.confidence_score DESC;
END;
$$ LANGUAGE plpgsql;
```

### **3. "Run" klicken!**

---

## 📊 **Was wird geändert:**

### **ENTFERNT:**
| Spalte | Grund |
|--------|-------|
| `storage_url` | ❌ PDFs liegen lokal, keine externen Storage-URLs mehr |
| `product_id` | ❌ Kann nur 1 Produkt - falsch für Manuals mit 22 Produkten |
| `manufacturer_id` | ❌ Redundant zu `manufacturer` VARCHAR |

### **NEU:**
| Tabelle | Zweck |
|---------|-------|
| `document_products` | ✅ Many-to-Many Relationship (1 Dokument → viele Produkte) |

---

## 🎯 **WARUM WICHTIG:**

### **VORHER (FALSCH):**
```
documents:
- product_id: UUID  ← Kann nur 1 Produkt speichern ❌
- manufacturer_id: UUID ← Leer, wird nie gefüllt ❌

PDF: "AccurioPress C4080 Service Manual"
→ 22 Produkte extrahiert
→ ABER: product_id kann nur 1 Produkt halten ❌
```

### **NACHHER (RICHTIG):**
```
documents:
- manufacturer: "Konica Minolta"  ← VARCHAR (direkt gefüllt) ✅
- models: ['C4080', 'C4070', ...]  ← Array ✅

document_products:
- document_id: abc-123, product_id: prod-1 (C4080), is_primary: true
- document_id: abc-123, product_id: prod-2 (MK-730), is_primary: false
- document_id: abc-123, product_id: prod-3 (FS-536), is_primary: false
... (22 Einträge total) ✅
```

---

## 📋 **document_products Tabelle:**

### **Spalten:**
```sql
document_id         UUID      ← FK zu documents
product_id          UUID      ← FK zu products
is_primary_product  BOOLEAN   ← Haupt-Produkt? (erstes = true)
confidence_score    DECIMAL   ← Extraction confidence (0-1)
extraction_method   VARCHAR   ← 'pattern', 'llm', 'vision'
page_numbers        INTEGER[] ← Wo wurde Produkt erwähnt?
```

### **Beispiel:**
```
document_id: abc-123 (AccurioPress C4080 Manual)
   ↓
document_products:
   - product: C4080, primary: true, confidence: 0.95, method: pattern
   - product: MK-730, primary: false, confidence: 0.87, method: pattern
   - product: FS-536, primary: false, confidence: 0.91, method: llm
```

---

## 🔍 **QUERY BEISPIELE:**

### **1. Alle Produkte eines Dokuments:**
```sql
SELECT * FROM krai_core.get_document_products('abc-123');
-- Returns: Alle Produkte mit Manufacturer, sortiert nach Primary/Confidence
```

### **2. Haupt-Produkt eines Dokuments:**
```sql
SELECT p.model_number, m.name as manufacturer
FROM krai_core.document_products dp
JOIN krai_core.products p ON dp.product_id = p.id
LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
WHERE dp.document_id = 'abc-123'
  AND dp.is_primary_product = true;
```

### **3. Alle Dokumente für ein Produkt:**
```sql
SELECT d.filename, dp.is_primary_product, dp.confidence_score
FROM krai_core.document_products dp
JOIN krai_core.documents d ON dp.document_id = d.id
WHERE dp.product_id = 'prod-xyz'
ORDER BY dp.is_primary_product DESC, d.created_at DESC;
```

---

## ✅ **NACH der Migration:**

### **Script speichert jetzt:**
1. ✅ **Products** → `krai_core.products` Tabelle
2. ✅ **Document Metadata** → `documents.manufacturer`, `documents.models`
3. ✅ **Relationships** → `document_products` (ALLE Produkte verlinkt)

### **Beispiel Log:**
```
✅ Saved 22 products to DB
✅ Saved 22 document-product relationships
✅ Updated document metadata: Konica Minolta, 22 models
```

---

## 🚀 **DANN SCRIPT NEU STARTEN:**

```bash
cd backend/processors_v2
python process_production.py
```

**→ Manufacturer und Products werden jetzt korrekt gespeichert!** ✅

---

## 💡 **ZUSAMMENFASSUNG:**

✅ **Entfernt:** 3 unnötige Spalten (storage_url, product_id, manufacturer_id)
✅ **Erstellt:** document_products Many-to-Many Tabelle
✅ **Helper Function:** `get_document_products()`
✅ **Script Update:** Speichert manufacturer, models, relationships

**→ Jetzt kann 1 Dokument VIELE Produkte haben!** 🎉
