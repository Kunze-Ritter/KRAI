# 🔧 Database Fixes Checklist

**Datum:** 21.10.2025
**Status:** Bereit zur Ausführung

---

## ✅ REIHENFOLGE DER AUSFÜHRUNG:

### 1️⃣ Supabase RPC Function Update (ZUERST!)

**Datei:** `database/migrations/100_update_rpc_function_add_chunk_id.sql`
**Was:** Fügt `chunk_id` Parameter zur `insert_error_code` Funktion hinzu
**Warum:** Ermöglicht Bilder-Verknüpfung für Error Codes
**Ausführung:** Supabase SQL Editor

```sql
-- Siehe: UPDATE_RPC_FUNCTION.sql
-- Fügt p_chunk_id Parameter hinzu
```

**Status:** ⏳ Muss ausgeführt werden

---

### 2️⃣ Links manufacturer_id Update

**Datei:** `database/migrations/101_fix_links_manufacturer_id.sql`
**Was:** Setzt `manufacturer_id` für alle Links basierend auf ihrem Document
**Warum:** Links können nach Hersteller gefiltert werden
**Ausführung:** Supabase SQL Editor

```sql
-- Siehe: FIX_LINKS_MANUFACTURER.sql
UPDATE krai_content.links l
SET manufacturer_id = d.manufacturer_id
FROM krai_core.documents d
WHERE l.document_id = d.id
AND l.manufacturer_id IS NULL
AND d.manufacturer_id IS NOT NULL;
```

**Erwartung:** ~678 Links werden updated
**Status:** ⏳ Muss ausgeführt werden

---

### 3️⃣ Video Platform Fix (Python Script)

**Datei:** `scripts/fix_unknown_platform_videos.py`
**Was:** Setzt `platform` und `video_url` für Videos mit platform=NULL
**Warum:** 13 YouTube Videos hatten platform=NULL
**Ausführung:** Terminal

```bash
cd C:\Users\haast\Docker\KRAI-minimal
python scripts/fix_unknown_platform_videos.py
```

**Erwartung:** 13 Videos werden updated
**Status:** ✅ BEREITS AUSGEFÜHRT (13/13 erfolgreich)

---

### 4️⃣ Video manufacturer_id Update (Python Script)

**Datei:** `scripts/update_video_manufacturers.py`
**Was:** Setzt `manufacturer_id` für alle Videos basierend auf Document
**Warum:** Videos können nach Hersteller gefiltert werden
**Ausführung:** Terminal

```bash
cd C:\Users\haast\Docker\KRAI-minimal
python scripts/update_video_manufacturers.py
```

**Erwartung:** 217 Videos werden updated
**Status:** ✅ BEREITS AUSGEFÜHRT (217/217 erfolgreich)

---

## 📝 NACH PROCESSING AUSFÜHREN:

### 4️⃣ Product Code Spalte hinzufügen

**Datei:** `database/migrations/102_add_product_code_to_products.sql`
**Was:** Fügt `product_code` Spalte zu Products hinzu (z.B. A93E, AAJN)
**Warum:** Konica Minolta nutzt erste 4 Zeichen als Product Code
**Ausführung:** Supabase SQL Editor
**Status:** ⏳ Bereit zur Ausführung

### 5️⃣ Page Labels für Chunks

**Datei:** `database/migrations/103_add_page_labels_to_chunks.sql`
**Was:** Fügt `page_label_start` und `page_label_end` zu Chunks hinzu
**Warum:** HP nutzt römische Zahlen (i, ii, iii) + arabische (1, 2, 3) - User brauchen echte Seitenzahlen
**Ausführung:** Supabase SQL Editor
**Status:** ⏳ Bereit zur Ausführung

### 6️⃣ Cleanup unnötige Spalten

**Datei:** `database/migrations/104_cleanup_unused_columns.sql`
**Was:** Löscht `content_text`, `content_summary`, `original_filename` aus documents
**Warum:** Nie verwendet, redundant, verschwenden Speicher (1.17 MB pro Dokument)
**Ausführung:** Supabase SQL Editor
**Status:** ⏳ Bereit zur Ausführung

### 7️⃣ Parts Catalog Products fixen

**Datei:** `scripts/fixes/fix_parts_catalog_products.py`
**Was:** Entfernt falsche Products (Part Numbers) und erstellt korrekte Products mit product_code
**Warum:** Parts Catalogs haben aktuell 21 "Products" die eigentlich Parts sind
**Ausführung:** Terminal

```bash
python scripts/fixes/fix_parts_catalog_products.py
```

**Status:** ⏳ Nach Migration 102 ausführen

### 6️⃣ Video-Product Linking (nach neuem Processing)

**Datei:** `scripts/fixes/link_videos_to_products.py`
**Was:** Verknüpft Videos mit Products
**Warum:** Bessere Filterung und Suche
**Blocker:** Wartet auf Document-Product Links (werden beim nächsten Processing erstellt)
**Status:** ⏳ Warten auf Processing

---

## 🎯 ZUSAMMENFASSUNG:

### Sofort ausführen (in Supabase):
1. ✅ `UPDATE_RPC_FUNCTION.sql` - RPC Function Update
2. ✅ `FIX_LINKS_MANUFACTURER.sql` - Links manufacturer_id

### Bereits erledigt:
3. ✅ `scripts/fix_unknown_platform_videos.py` - Platform Fix (13/13)
4. ✅ `scripts/update_video_manufacturers.py` - Video manufacturer_id (217/217)

### Nach neuem Processing:
5. ⏳ `scripts/link_videos_to_products.py` - Video-Product Links

---

## 📊 ERWARTETE ERGEBNISSE:

Nach Ausführung von 1-2:

```sql
-- Links mit manufacturer_id
SELECT
    COUNT(*) FILTER (WHERE manufacturer_id IS NOT NULL) as with_mfr,
    COUNT(*) as total
FROM krai_content.links;
-- Erwartung: ~678/678

-- Videos mit platform
SELECT
    COUNT(*) FILTER (WHERE platform IS NOT NULL) as with_platform,
    COUNT(*) as total
FROM krai_content.videos;
-- Erwartung: 217/217

-- Videos mit manufacturer_id
SELECT
    COUNT(*) FILTER (WHERE manufacturer_id IS NOT NULL) as with_mfr,
    COUNT(*) as total
FROM krai_content.videos;
-- Erwartung: 217/217
```

---

## ⚠️ WICHTIG:

**Reihenfolge einhalten!**
1. Zuerst: RPC Function Update (sonst können neue Error Codes keine chunk_id haben)
2. Dann: Links manufacturer_id (wichtig für Filterung)
3. Python Scripts sind bereits gelaufen ✅

**Nach neuem Processing:**
- Document-Product Links werden automatisch erstellt (Code-Fix in `document_processor.py`)
- Parts-Error Code Links werden automatisch erstellt (Code-Fix in `document_processor.py`)
- Dann kann `link_videos_to_products.py` ausgeführt werden

---

**Status:** 2 SQL Fixes müssen noch in Supabase ausgeführt werden! 🎯
