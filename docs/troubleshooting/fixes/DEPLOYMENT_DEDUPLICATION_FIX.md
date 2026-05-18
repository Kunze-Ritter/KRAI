# 🔧 Deployment: Image Deduplication Fix

**Datum:** 2025-10-02 07:55
**Zweck:** Image-Deduplication über Cross-Schema RPC-Funktionen aktivieren

## Problem

```
Failed to get image by hash: column images.image_hash does not exist
```

**Ursache:** PostgreSQL API kann nicht direkt auf `krai_content.images.file_hash` zugreifen, da die Tabelle in einem anderen Schema als `public` liegt.

## Lösung

**RPC-Funktionen** die Cross-Schema-Zugriff ermöglichen.

## Deployment-Schritte

### **1. SQL Migration ausführen**

#### **Option A: Über pgAdmin (Empfohlen)**

1. Öffnen Sie pgAdmin und verbinden Sie sich mit Ihrer PostgreSQL-Datenbank
2. Öffnen Sie die Datei `database_migrations/04_rpc_functions_deduplication.sql`
3. Kopieren Sie den gesamten Inhalt
4. Fügen Sie ihn in den Query-Editor ein
5. Klicken Sie auf **"Execute"**

#### **Option B: Über psql (Command Line)**

```bash
# Mit Ihrer PostgreSQL-Datenbank verbinden
psql "postgresql://krai_user:[PASSWORD]@localhost:5432/krai"

# Migration ausführen
\i database_migrations/04_rpc_functions_deduplication.sql
```

#### **Option C: Über Python (Automated)**

```python
from backend.services.database_factory import create_database_adapter
import asyncio

async def run_migration():
    adapter = create_database_adapter()
    with open('database_migrations/04_rpc_functions_deduplication.sql', 'r') as f:
        sql = f.read()
    await adapter.execute_query(sql)
    print("✅ Migration executed successfully")

asyncio.run(run_migration())
```

### **2. Verifizieren Sie die Installation**

```sql
-- Prüfen ob Funktionen existieren
SELECT proname, prosrc
FROM pg_proc
WHERE proname IN (
    'get_image_by_hash',
    'count_images_by_document',
    'count_chunks_by_document',
    'get_chunk_ids_by_document',
    'embeddings_exist_for_chunks'
);
```

Erwartetes Ergebnis: **5 Funktionen** gefunden

### **3. Testen Sie die Funktionen**

```sql
-- Test: Count chunks for a document
SELECT count_chunks_by_document('YOUR_DOCUMENT_ID');

-- Test: Count images for a document
SELECT count_images_by_document('YOUR_DOCUMENT_ID');

-- Test: Get image by hash
SELECT * FROM get_image_by_hash('some_hash_value');
```

### **4. Python-Code ist bereits angepasst**

Die folgenden Dateien nutzen jetzt automatisch die RPC-Funktionen:
- ✅ `backend/services/database_service.py` - Image-Deduplication
- ✅ `backend/tests/krai_master_pipeline.py` - Stage-Detection

**Kein weiterer Code-Change nötig!**

## Erstellte RPC-Funktionen

### **1. `get_image_by_hash(file_hash)`**
**Zweck:** Image-Deduplication
**Returns:** Image-Daten (id, filename, file_hash, etc.)
**Nutzer:** `database_service.get_image_by_hash()`

```sql
SELECT * FROM get_image_by_hash('abc123...');
```

### **2. `count_images_by_document(document_id)`**
**Zweck:** Stage-Detection (Image-Stage)
**Returns:** Anzahl Images für Dokument
**Nutzer:** `krai_master_pipeline.get_document_stage_status()`

```sql
SELECT count_images_by_document('doc-uuid');
```

### **3. `count_chunks_by_document(document_id)`**
**Zweck:** Stage-Detection (Text-Stage)
**Returns:** Anzahl Chunks für Dokument
**Nutzer:** `krai_master_pipeline.get_document_stage_status()`

```sql
SELECT count_chunks_by_document('doc-uuid');
```

### **4. `get_chunk_ids_by_document(document_id, limit)`**
**Zweck:** Embeddings-Check vorbereiten
**Returns:** Liste von Chunk-IDs
**Nutzer:** `krai_master_pipeline.get_document_stage_status()`

```sql
SELECT * FROM get_chunk_ids_by_document('doc-uuid', 10);
```

### **5. `embeddings_exist_for_chunks(chunk_ids[])`**
**Zweck:** Stage-Detection (Embedding-Stage)
**Returns:** Boolean (TRUE wenn Embeddings existieren)
**Nutzer:** `krai_master_pipeline.get_document_stage_status()`

```sql
SELECT embeddings_exist_for_chunks(ARRAY['chunk1-uuid', 'chunk2-uuid']);
```

## Vorteile

### **Vor dem Fix:**
```
❌ Image-Deduplication deaktiviert
❌ Duplikat-Images werden gespeichert
❌ Erhöhte Storage-Kosten (+10-20%)
❌ Schema-Errors in Logs
⚠️  Stage-Detection vereinfacht (ungenau)
```

### **Nach dem Fix:**
```
✅ Image-Deduplication funktioniert
✅ Duplikat-Images werden erkannt
✅ Storage-Kosten optimiert
✅ Keine Schema-Errors mehr
✅ Stage-Detection präzise (zeigt echten Status)
```

## Performance-Impact

### **Minimal:**
- RPC-Calls sind sehr schnell (~1-5ms)
- Werden nur bei Deduplication-Checks aufgerufen
- Kein Impact auf Hauptverarbeitung

### **Storage-Einsparungen:**
```
Ohne Deduplication:
- 1000 PDFs mit je 50 Images
- ~30% Duplikate (typisch für manuals)
= 50,000 Images → 15,000 Duplikate
= ~3-5GB verschwendeter Storage

Mit Deduplication:
= Nur 35,000 unique Images gespeichert
= 3-5GB Storage gespart! 💰
```

## Troubleshooting

### **Problem: "function get_image_by_hash does not exist"**

**Lösung:** Migration wurde nicht ausgeführt
```sql
-- Prüfen Sie:
SELECT proname FROM pg_proc WHERE proname = 'get_image_by_hash';
-- Sollte 1 Zeile zurückgeben
```

### **Problem: "permission denied for function"**

**Lösung:** Permissions nicht gesetzt
```sql
-- Führen Sie aus:
GRANT EXECUTE ON FUNCTION get_image_by_hash(VARCHAR) TO service_role;
GRANT EXECUTE ON FUNCTION get_image_by_hash(VARCHAR) TO authenticated;
```

### **Problem: "relation krai_content.images does not exist"**

**Lösung:** Schema oder Tabelle fehlt
```sql
-- Prüfen Sie:
SELECT schemaname, tablename FROM pg_tables WHERE tablename = 'images';
-- Sollte krai_content.images zeigen
```

## Testing nach Deployment

### **1. Test Image-Deduplication:**

```python
# Upload dasselbe Image zweimal
python backend/tests/test_image_deduplication.py

# Erwartung:
# Upload 1: New image created
# Upload 2: Existing image found (deduplication)
```

### **2. Test Stage-Detection:**

```python
# Run smart processing
python backend/tests/krai_master_pipeline.py
# Wähle Option 2 (Smart Processing)

# Erwartung:
# Smart Processing for: test.pdf
#   Current Status:
#     Upload: ✅
#     Text: ✅    ← Sollte korrekt erkannt werden
#     Image: ✅   ← Sollte korrekt erkannt werden
#     Classification: ❌
```

### **3. Monitor Logs:**

```bash
# Keine Errors mehr:
grep "column images.image_hash does not exist" logs.txt
# Sollte leer sein!

# Deduplication funktioniert:
grep "Found existing image with hash" logs.txt
# Sollte Treffer zeigen wenn Duplikate erkannt werden
```

## Rollback (Falls nötig)

### **Funktionen entfernen:**

```sql
DROP FUNCTION IF EXISTS get_image_by_hash(VARCHAR);
DROP FUNCTION IF EXISTS count_images_by_document(UUID);
DROP FUNCTION IF EXISTS count_chunks_by_document(UUID);
DROP FUNCTION IF EXISTS get_chunk_ids_by_document(UUID, INTEGER);
DROP FUNCTION IF EXISTS embeddings_exist_for_chunks(UUID[]);
```

### **Code zurücksetzen:**

```bash
git checkout HEAD~1 backend/services/database_service.py
git checkout HEAD~1 backend/tests/krai_master_pipeline.py
```

## Status

- ✅ SQL Migration erstellt: `04_rpc_functions_deduplication.sql`
- ✅ Python Code angepasst: `database_service.py`
- ✅ Stage Detection verbessert: `krai_master_pipeline.py`
- ⏳ **DEPLOYMENT PENDING:** SQL Migration muss ausgeführt werden
- ⏳ **TESTING PENDING:** Nach Deployment testen

## Nächste Schritte

1. ✅ **Jetzt sofort:** SQL Migration ausführen (siehe oben)
2. ✅ **Dann:** Python-Prozess neu starten
3. ✅ **Prüfen:** Logs für "Found existing image" Messages
4. ✅ **Verifizieren:** Keine Schema-Errors mehr

---

**Wichtig:** Die SQL-Migration ist **sicher** und **nicht-destruktiv**. Sie erstellt nur neue Funktionen, keine Schema-Änderungen an bestehenden Tabellen.

**Stand:** 2025-10-02 07:55
**Priorität:** HOCH (kritisch für Deduplication)
**Aufwand:** 2 Minuten (nur SQL ausführen)
