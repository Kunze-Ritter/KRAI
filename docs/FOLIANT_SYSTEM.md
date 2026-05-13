# FOLIANT COMPATIBILITY SYSTEM

## 🎯 Overview

Das Foliant-System extrahiert Produktdaten und Kompatibilitätsregeln aus Konica Minolta Foliant PDFs und importiert sie in die KRAI-Datenbank.

## 📊 Datenstruktur

### **Produkte & Accessories**
- **products**: Hauptprodukte (C227i, C257i, etc.) und Accessories (FS-533, DF-633, etc.)
- **product_accessories**: Kompatibilitätsbeziehungen zwischen Produkten

### **Neue Felder (Migration 111)**
```sql
mounting_position VARCHAR(20)  -- top, side, bottom, internal, accessory
slot_number INTEGER            -- Slot-Nummer (z.B. FK-513_1 = Slot 1)
max_quantity INTEGER           -- Max. Anzahl gleichzeitig (default: 1)
```

## 🏗️ Mounting Positions

### **TOP (max 1)**
- **Was:** Document Feeders
- **Beispiel:** DF-633
- **Regel:** Nur 1x gleichzeitig möglich

### **SIDE (max 3)**
- **Was:** Finishers, Large Capacity Units
- **Beispiel:** FS-533, FS-539, LU-301
- **Regel:** Max 3x gleichzeitig möglich

### **BOTTOM (max 1)**
- **Was:** Cabinets, Desks, Working Tables
- **Beispiel:** PC-118, DK-518, WT-515
- **Regel:** Nur 1x gleichzeitig möglich

### **INTERNAL (max 5)**
- **Was:** Controllers, Authentication, Fax, Network
- **Beispiel:** CU-101, AU-102, FK-513, IC-READER
- **Regel:** Max 5x gleichzeitig möglich

### **ACCESSORY (max 10)**
- **Was:** Mount Kits, Punch Kits, Keypads
- **Beispiel:** MK-734, PK-519, HT-509
- **Regel:** Max 10x gleichzeitig möglich

## 🔧 Slot-System

Manche Accessories können in mehreren Positionen installiert werden:

**Beispiel: FK-513 (Fax Kit)**
```
FK-513_1 → Slot 1 (internal)
FK-513_2 → Slot 2 (internal)
```

**In der DB:**
```sql
-- Nur 1x Produkt:
INSERT INTO products (model_number) VALUES ('FK-513');

-- 2x Kompatibilitätseinträge:
INSERT INTO product_accessories (product_id, accessory_id, mounting_position, slot_number)
VALUES
  ('C257i', 'FK-513', 'internal', 1),
  ('C257i', 'FK-513', 'internal', 2);
```

## 📥 Import-Prozess

### **1. PDF in `input_foliant/` ablegen**

### **2. Import-Script ausführen**
```bash
python scripts/import_foliant_to_db.py
```

### **3. Was wird extrahiert:**
- ✅ Produktnamen und Article Codes
- ✅ Physische Specs (Breite, Höhe, Tiefe, Gewicht, Leistung)
- ✅ Kompatibilitätsregeln (aus TABSUM-Konfigurationen)
- ✅ Mounting Positions (aus Sprite-Analyse)

### **4. Verarbeitete PDFs**
→ Werden nach `input_foliant/processed/` verschoben

## 🤖 Agent-Integration

### **Kompatibilitäts-Abfragen**

**Beispiel 1: Ist Konfiguration möglich?**
```sql
-- User fragt: "Kann ich C257i mit FS-539 + DF-633 + PC-418 konfigurieren?"

SELECT
  pa.accessory_id,
  pa.mounting_position,
  pa.max_quantity
FROM product_accessories pa
WHERE pa.product_id = 'C257i'
  AND pa.accessory_id IN ('FS-539', 'DF-633', 'PC-418');

-- Prüfung:
-- FS-539: side (max 3) ✅ → 1 used, 2 remaining
-- DF-633: top (max 1) ✅ → 1 used, 0 remaining
-- PC-418: bottom (max 1) ✅ → 1 used, 0 remaining
-- → KOMPATIBEL! (Different mounting positions)
```

**WICHTIG:** Mounting positions sind KOMPATIBEL miteinander!
- TOP + SIDE + BOTTOM + INTERNAL + ACCESSORY = ✅ ALLE GLEICHZEITIG MÖGLICH
- Nur INNERHALB einer Position gilt max_quantity

**Beispiel 2: Was fehlt noch?**
```sql
-- User hat: C257i + FS-539
-- Frage: "Was kann ich noch hinzufügen?"

SELECT
  pa.accessory_id,
  pa.mounting_position,
  p.product_type
FROM product_accessories pa
JOIN products p ON p.id = pa.accessory_id
WHERE pa.product_id = 'C257i'
  AND pa.mounting_position IN ('top', 'bottom', 'internal', 'accessory')
ORDER BY pa.mounting_position;

-- Antwort: Du kannst noch hinzufügen:
-- - 1x TOP (DF-633)
-- - 1x BOTTOM (PC-118, PC-218, PC-418, DK-518, WT-515)
-- - 5x INTERNAL (CU-101, AU-102, etc.)
-- - 10x ACCESSORY (MK-734, PK-519, etc.)
```

### **Abhängigkeiten (Dependencies)**

**Beispiel: FS-539 benötigt RU-514 (Relay Unit)**

```sql
-- In product_accessories:
INSERT INTO product_accessories (
  product_id,
  accessory_id,
  mounting_position,
  requires_accessory_id,  -- NEU!
  notes
) VALUES (
  'C257i',
  'FS-539',
  'side',
  'RU-514',  -- Benötigt RU-514
  'Finisher requires relay unit for connection'
);
```

**Agent-Abfrage:**
```sql
-- User wählt: FS-539
-- Frage: "Was wird noch benötigt?"

SELECT
  pa.requires_accessory_id,
  p.model_number,
  p.product_type
FROM product_accessories pa
JOIN products p ON p.id = pa.requires_accessory_id
WHERE pa.product_id = 'C257i'
  AND pa.accessory_id = 'FS-539'
  AND pa.requires_accessory_id IS NOT NULL;

-- Antwort: "FS-539 benötigt RU-514 (Relay Unit)"
```

## 📤 Dashboard-Integration

### **Upload-Flow**

1. **User uploaded PDF** → `uploads/foliant/`
2. **Backend verarbeitet:**
   ```python
   from scripts.import_foliant_to_db import extract_foliant_data, import_to_database

   data = extract_foliant_data(pdf_path)
   success = import_to_database(data)
   ```
3. **Status zurück an Frontend:**
   ```json
   {
     "success": true,
     "products_imported": 3,
     "accessories_imported": 38,
     "compatibility_links": 114
   }
   ```

### **API Endpoint**

```python
@app.post("/api/foliant/upload")
async def upload_foliant_pdf(file: UploadFile):
    # Save file
    pdf_path = f"uploads/foliant/{file.filename}"
    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    # Process
    data = extract_foliant_data(pdf_path)
    success = import_to_database(data)

    # Move to processed
    if success:
        shutil.move(pdf_path, f"uploads/foliant/processed/{file.filename}")

    return {
        "success": success,
        "stats": {
            "products": len([a for a in data['articles'] if is_main_product(a)]),
            "accessories": len([a for a in data['articles'] if not is_main_product(a)]),
            "compatibility_items": len(data['compatibility_matrix'])
        }
    }
```

## 🔍 Fehlende Features

### **1. Dependencies (requires_accessory_id)**
- [ ] Migration für `requires_accessory_id` Spalte
- [ ] Parsing von Abhängigkeiten aus Foliant
- [ ] Agent-Abfragen für "Was wird benötigt?"

### **2. Mutual Exclusivity (WITHIN positions)**
- [x] Mounting positions (top/side/bottom/internal/accessory) are COMPATIBLE with each other
- [ ] Within SAME position: max_quantity defines mutual exclusivity
- [ ] Example: PC-118 vs PC-218 vs PC-418 (only 1x BOTTOM allowed)

### **3. Quantity Limits per Accessory**
- [ ] Manche Accessories haben eigene Limits
- [ ] Beispiel: "Max 2x PK-519"

## 📚 Weitere Dokumentation

- **DATABASE_SCHEMA.md**: Vollständige DB-Struktur
- **FOLIANT_COMPATIBILITY_MATRIX.md**: Alle Kompatibilitätsregeln
- **TODO_PRODUCT_ACCESSORIES.md**: Offene Tasks für Accessory-System
