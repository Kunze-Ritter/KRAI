# 🎯 Master TODO List - Data Quality & Linking

## 📊 Aktueller Status (21.10.2025)

### ✅ Was funktioniert:
- [x] Error Code Extraction
- [x] Error Code → chunk_id Linking (für Bilder)
- [x] Video Enrichment (99.7%)
- [x] Video → manufacturer_id Linking (100%)
- [x] Progressive Search API
- [x] OpenAI-compatible API

### ❌ Was fehlt / broken:

## 1. 🎥 VIDEO DATA QUALITY

### Problem: Fehlende Daten
- ❌ **Description:** Nur 32% haben Description
  - Vimeo: 0% ❌
  - Brightcove: 100% ✅
  - YouTube: 0% ❌

- ❌ **YouTube ID:** Nur 6% haben youtube_id
  - Sollte: 100% bei YouTube Videos

**Fix:** Video Enrichment Script verbessern
- Vimeo Description aus oEmbed holen
- YouTube ID korrekt extrahieren und speichern

**Script:** `scripts/enrich_video_metadata.py`
**Priority:** MEDIUM

---

## 2. 🔗 LINKS LINKING

### Problem: Links haben keine manufacturer_id/product_id

**Status:**
- 0/10 Links haben `manufacturer_id` ❌
- 10/10 Links haben `document_id` ✅

**Fix:** Links sollten manufacturer_id vom Document erben

**Workflow:**
```sql
UPDATE krai_content.links l
SET manufacturer_id = d.manufacturer_id
FROM krai_core.documents d
WHERE l.document_id = d.id
AND l.manufacturer_id IS NULL;
```

**Priority:** HIGH (wichtig für Filterung)

---

## 3. 📦 PRODUCT EXTRACTION & LINKING

### Problem: Products werden nicht richtig extrahiert

**Status:**
- Documents haben Products: ~10-20 ❌
- Sollte: 100+ ✅

**Ursache:** Product Extraction im Document Processor läuft nicht richtig

**Fix:**
1. Prüfe `ProductExtractor` in `backend/processors/product_extractor.py`
2. Prüfe ob Products gespeichert werden
3. Prüfe ob Document-Product Links erstellt werden

**Test:**
```python
python -m backend.pipeline.master_pipeline --file test.pdf
# Dann prüfen:
# - Wurden Products extrahiert?
# - Wurden document_products Links erstellt?
```

**Priority:** HIGH (blocker für Video-Product Linking)

---

## 4. 🔧 PARTS LINKING

### Problem: Parts nicht mit Error Codes/Products verknüpft

**Status:**
- Parts haben `related_error_codes`: 0% ❌
- Parts haben `related_products`: 0% ❌

**Fix:**
- [x] Model updated (fields hinzugefügt)
- [x] `parts_linker.py` Modul erstellt
- [ ] Integration in Document Processor
- [ ] Test mit Service Manual

**Priority:** MEDIUM

---

## 5. 📄 DOCUMENT-PRODUCT LINKING

### Problem: Documents nicht mit Products verknüpft

**Status:**
- Nur ~10-20 Documents haben Products
- Sollte: Alle Service Manuals haben Products

**Ursache:**
- Product Extraction funktioniert nicht richtig
- Oder: Products werden extrahiert aber nicht verknüpft

**Fix:**
1. Prüfe Product Extraction Logs
2. Prüfe ob `document_products` Table befüllt wird
3. Falls nein: Fix im `document_processor.py`

**Priority:** HIGH

---

## 6. 🎬 VIDEO-PRODUCT LINKING

### Problem: Videos nicht mit Products verknüpft

**Status:**
- 0/217 Videos haben Products ❌

**Blocker:** Document-Product Linking muss zuerst funktionieren!

**Fix:**
- [x] Script erstellt: `link_videos_to_products.py`
- [ ] Warte auf Document-Product Linking
- [ ] Dann Script ausführen

**Priority:** LOW (wartet auf #5)

---

## 7. 🖼️ CHUNK-ID LINKING

### Problem: Error Codes haben chunk_id aber keine Bilder

**Status:**
- Error Codes mit chunk_id: ~80% ✅
- Chunks mit Bildern: 41 ✅
- Error Codes mit Bildern: 0 ❌

**Ursache:** Die Chunks mit Bildern sind nicht die gleichen wie die Error Code Chunks

**Fix:**
- [ ] Prüfe Image Processing
- [ ] Stelle sicher dass Images mit richtigen Chunks verknüpft werden
- [ ] Re-process Documents mit Bildern

**Priority:** MEDIUM

---

## 8. 📋 SERVICE BULLETINS

### Problem: Keine Service Bulletins in DB

**Status:**
- Documents mit type='bulletin': 0 ❌

**Fix:**
- [ ] Document Type Detection verbessern
- [ ] Bulletins als separaten Type erkennen
- [ ] Oder: Bulletins sind in Links? (prüfen)

**Priority:** LOW

---

## 🚀 PRIORITY REIHENFOLGE:

### Phase 1: Data Quality (diese Woche)
1. **Links → manufacturer_id** (SQL Update)
2. **Product Extraction Fix** (Document Processor)
3. **Document-Product Linking** (Processing)

### Phase 2: Enrichment (nächste Woche)
4. **Video Description Fix** (Enrichment Script)
5. **Parts Linking** (Integration)
6. **Chunk-Image Linking** (Processing)

### Phase 3: Nice-to-have
7. **Video-Product Linking** (nach Phase 1)
8. **Service Bulletins** (später)

---

## 📝 QUICK WINS (heute machbar):

### 1. Links manufacturer_id Update (5 min)
```sql
UPDATE krai_content.links l
SET manufacturer_id = d.manufacturer_id
FROM krai_core.documents d
WHERE l.document_id = d.id
AND l.manufacturer_id IS NULL;
```

### 2. Video Description Fix (30 min)
- Vimeo oEmbed hat Description
- Einfach speichern statt ignorieren

### 3. YouTube ID Fix (10 min)
- Wird extrahiert aber nicht gespeichert
- Einfach in DB schreiben

---

## 🎯 ZIEL für nächstes Processing:

Nach Fixes sollte gelten:
- ✅ 100% Videos haben Description
- ✅ 100% YouTube Videos haben youtube_id
- ✅ 100% Links haben manufacturer_id
- ✅ 80%+ Documents haben Products
- ✅ 80%+ Videos haben Products
- ✅ 60%+ Parts haben related_error_codes
- ✅ 50%+ Error Codes haben Bilder

---

**Status:** Viele Baustellen, aber systematisch lösbar! 💪
**Nächster Schritt:** Quick Wins umsetzen, dann Processing Fixes!
