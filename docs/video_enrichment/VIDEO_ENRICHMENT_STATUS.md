# Video Enrichment Status 🎥

## ✅ Was funktioniert:

1. **Enrichment Script läuft** ✅
   - 676/678 Videos enriched (99.7%)
   - Deduplizierung funktioniert
   - YouTube, Vimeo, Brightcove Support

2. **Metadata wird extrahiert** ✅
   - Titel, Beschreibung, Duration
   - Thumbnails
   - Platform Detection

## ❌ Was NICHT funktioniert:

### Problem: manufacturer_id wird NICHT gesetzt!

**Status:** 0/217 Videos haben `manufacturer_id` ❌

**Grund:** `detect_manufacturer_from_domain()` findet keine Hersteller

**Beispiel:**
```
URL: https://player.vimeo.com/video/219628749
Domain: player.vimeo.com
         ↓
detect_manufacturer_from_domain("player.vimeo.com", supabase)
         ↓
Returns: None ❌
```

## 🔧 Lösung:

### Option 1: manufacturer_id aus Link Context
Videos werden aus Links extrahiert die bereits `document_id` haben.
Das Document hat einen `manufacturer_id`!

```python
# In enrich_video_metadata.py:
# Statt nur Domain zu prüfen:
if not manufacturer_id:
    # Hole manufacturer_id vom Document
    if link.get('document_id'):
        doc = supabase.table('vw_documents').select('manufacturer_id').eq(
            'id', link['document_id']
        ).single().execute()

        if doc.data:
            manufacturer_id = doc.data.get('manufacturer_id')
```

### Option 2: manufacturer_id aus Video Titel
Viele Videos haben Hersteller im Titel:

```
"HP LaserJet Pro M404 - How to..."
"Canon imageRUNNER ADVANCE..."
"Konica Minolta bizhub C308..."
```

```python
# In enrich_video_metadata.py:
from backend.utils.manufacturer_utils import detect_manufacturer_from_text

if not manufacturer_id:
    # Versuche aus Titel zu extrahieren
    title = metadata.get('title', '')
    manufacturer_id = detect_manufacturer_from_text(title, supabase)
```

### Option 3: Beide kombinieren
```python
# Priority:
# 1. Aus Link Context (document_id)
# 2. Aus Video Titel
# 3. Aus Domain (aktuell)

if not manufacturer_id and link.get('document_id'):
    # Option 1
    ...

if not manufacturer_id:
    # Option 2
    ...

if not manufacturer_id:
    # Option 3 (aktuell)
    ...
```

## 📊 Erwartete Verbesserung:

Nach Fix:
- **80%+ Videos** mit `manufacturer_id` (aus Document)
- **10%+ Videos** mit `manufacturer_id` (aus Titel)
- **10%- Videos** ohne `manufacturer_id` (generische Videos)

## 🚀 Nächste Schritte:

1. ⏳ Implementiere Option 1 (Document Context)
2. ⏳ Implementiere Option 2 (Titel Extraction)
3. ⏳ Re-run Enrichment mit `--force`
4. ⏳ Validiere Ergebnisse

## 🎯 Test Command:

```bash
# Nach Fix:
python scripts/enrich_video_metadata.py --limit 10 --force

# Dann prüfen:
python check_videos_status.py

# Erwartung:
# Manufacturer Linking:
#   With manufacturer_id: 8-9 ✅  (80-90%)
#   Without manufacturer_id: 1-2 ❌
```

## 📝 Aktueller Code-Flow:

```
Link → enrich_video_metadata.py
         ↓
      detect_manufacturer_from_url(url)
         ↓
      detect_manufacturer_from_domain(domain, supabase)
         ↓
      Sucht in manufacturers Tabelle nach domain
         ↓
      Findet NICHTS (player.vimeo.com ist kein Hersteller!)
         ↓
      manufacturer_id = None ❌
```

## 💡 Besserer Code-Flow:

```
Link → enrich_video_metadata.py
         ↓
      1. Hole document_id vom Link
         ↓
      2. Hole manufacturer_id vom Document
         ↓
      3. Falls None: Extrahiere aus Titel
         ↓
      4. Falls None: Versuche Domain
         ↓
      manufacturer_id = <UUID> ✅
```

---

**Status:** Enrichment funktioniert, aber `manufacturer_id` Linking fehlt! 🔧
**Priority:** HIGH - Ohne `manufacturer_id` funktioniert die Video-Suche nicht richtig!
