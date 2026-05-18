# Unified Multi-Resource Error Code Search - Deployment Guide

## 🎯 Overview

This deployment enables technicians to find **ALL resources** for an error code in one search:
- ✅ Service Bulletins (priority 1 - newest fixes!)
- ✅ Service Manual entries (priority 2)
- ✅ Video Tutorials (priority 3)
- ✅ External Links (priority 4)
- ✅ Related Spare Parts (priority 5)

**Version:** 2.0.44 (Commit 52+)
**Date:** 2025-10-05

---

## 📋 What's Included

### Database Changes (Migrations)
1. **Migration 27:** `stage_tracking` table (prerequisite fix)
2. **Migration 28:** Schema denormalization (links/videos/documents)
3. **Migration 29:** Unified search function

### Code Changes
1. **document_processor.py:** Auto-link manufacturer/series to links/videos
2. **N8N Tool:** New "Search Error Code Resources" tool

### Documentation
1. **N8N Tool Setup Guide:** Complete N8N configuration
2. **This Deployment Guide:** Step-by-step deployment instructions

---

## 🚀 Deployment Steps

### STEP 1: Pull Latest Code

```powershell
cd C:\Users\haast\Docker\KRAI-minimal
git fetch origin
git reset --hard origin/master
```

**Expected Commits:**
- Commit 51: Migration 27 (stage_tracking)
- Commit 52: Migration 28 (denormalization)
- Commit 53: Migration 29 (search function)
- Commit 54: document_processor update

---

### STEP 2: Apply Database Migrations

#### 2.1 Migration 27: Stage Tracking Table

```sql
-- In Supabase SQL Editor:
-- Run complete contents of:
-- database/migrations/27_create_stage_tracking_table.sql
```

**Verify:**
```sql
SELECT COUNT(*) FROM krai_system.stage_tracking;
-- Should work without error
```

---

#### 2.2 Migration 28: Denormalize Schema

```sql
-- In Supabase SQL Editor:
-- Run complete contents of:
-- database/migrations/28_denormalize_links_videos_for_unified_search.sql
```

**Verify:**
```sql
-- Check links have new columns
SELECT
    COUNT(*) as total_links,
    COUNT(manufacturer_id) as with_manufacturer,
    COUNT(series_id) as with_series
FROM krai_content.links;

-- Check documents have priority
SELECT document_type, priority_level, COUNT(*)
FROM krai_core.documents
GROUP BY document_type, priority_level
ORDER BY priority_level;
```

**Expected:**
- Links have `manufacturer_id` and `series_id` columns
- Most existing links now have `manufacturer_id` populated (via backfill)
- Documents have `priority_level` (1=bulletins, 2=manuals, etc.)

---

#### 2.3 Migration 29: Unified Search Function

```sql
-- In Supabase SQL Editor:
-- Run complete contents of:
-- database/migrations/29_unified_error_code_search_function.sql
```

**Verify:**
```sql
-- Test with a real error code from your database
SELECT error_code FROM krai_intelligence.error_codes LIMIT 1;
-- Copy that error code, then:

SELECT * FROM search_error_code('C-2801');  -- Replace with your error code
```

**Expected Output:**
- Multiple rows with different `resource_type` values
- Sorted by `priority` (lowest number first)
- Service bulletins appear first if available

---

### STEP 3: Update Processing Pipeline

#### 3.1 Verify Code Changes

```powershell
cd C:\Users\haast\Docker\KRAI-minimal\backend\processors_v2
git log --oneline -5
```

**Should show:**
- document_processor.py updated with auto-linking

#### 3.2 Test Processing (Optional)

```powershell
# Process a test document to verify auto-linking works
python backend/processors_v2/process_production.py
```

**Check logs for:**
```
INFO     Saved X links to database
DEBUG    Could not auto-link manufacturer/series: [only if it fails]
```

---

### STEP 4: Configure N8N Tool

#### 4.1 Open N8N Workflow
- Navigate to your KRAI Agent workflow
- Open the Agent node

#### 4.2 Add New Tool

**Tool Settings:**
- **Tool Type:** Supabase
- **Operation:** Call RPC Function
- **Function Name:** `search_error_code_resources`

**Tool Description (Copy this):**
```
Search for ALL resources related to an error code. Returns service manuals, bulletins, videos, links, and parts ranked by priority. Always check Service Bulletins FIRST - they contain the most up-to-date fixes!

Input: error_code (required), manufacturer_id (optional), series_id (optional)
Output: Multiple resource types sorted by priority (1=bulletins, 2=manuals, 3=videos, 4=links, 5=parts)
```

**Parameters:**
```json
{
  "p_error_code": "={{$json.error_code}}",
  "p_manufacturer_id": "={{$json.manufacturer_id || null}}",
  "p_series_id": "={{$json.series_id || null}}",
  "p_limit": 20
}
```

#### 4.3 Update Agent System Prompt

Add to your agent's system message (see `N8N_UNIFIED_ERROR_SEARCH_TOOL.md` for full prompt).

**Key Addition:**
```
WICHTIG - Bei Fehlercode-Suchen:
1. Nutze das "Search Error Code Resources" Tool
2. Priorisiere die Ergebnisse:
   🔴 Service Bulletins ZUERST (neueste Fixes!)
   📘 Service Manual (Standard-Info)
   🎥 Videos (Visual guides)
   🔗 Links (Zusätzliche Ressourcen)
   🔧 Ersatzteile (Häufig benötigt)
3. Erwähne IMMER wenn ein Service Bulletin gefunden wurde!
```

#### 4.4 Test the Tool

**In N8N Chat:**
```
Suche nach Fehlercode C-2801
```

**Expected Response:**
```
🔴 **AKTUELLSTE INFORMATION - Service Bulletin**
[If bulletin exists...]

📘 **Service Manual**
- Beschreibung: ...
- Lösung: ...
- Seite: 345

🎥 **Video Tutorial verfügbar**
- Titel: "Fix C-2801 step by step"
- Link: [URL]

🔧 **Ersatzteil häufig benötigt**
- Fusing Unit (P/N: XYZ-123)
```

---

## ✅ Verification Checklist

### Database
- [ ] Migration 27 applied (stage_tracking exists)
- [ ] Migration 28 applied (links have manufacturer_id)
- [ ] Migration 29 applied (search_error_code function exists)
- [ ] Test query returns results

### Code
- [ ] Latest code pulled from git
- [ ] document_processor.py has auto-linking code
- [ ] Processing still works (test optional)

### N8N
- [ ] New tool added to agent
- [ ] Agent system prompt updated
- [ ] Test search returns structured results
- [ ] Service bulletins highlighted if available

---

## 🧪 Testing Guide

### Test 1: Simple Search
```
User: "Was ist Fehlercode C-2801?"
Agent: [Should search and return ALL resources]
```

### Test 2: Manufacturer Filter
```
User: "Zeige mir HP Fehlercode 10.92.15"
Agent: [Should filter to HP only]
```

### Test 3: No Bulletin
```
User: "Error C-9999"  (non-existent)
Agent: [Should gracefully handle - "Keine Informationen gefunden"]
```

### Test 4: Bulletin Priority
```
User: "C-2801 fix"
Agent: [Service Bulletin MUST be mentioned first if it exists]
```

---

## 📊 Expected Impact

### Before
- Average search time: **5 minutes** (multiple separate searches)
- Resources found: **1-2 sources** (usually just manual)
- Bulletin awareness: **Low** (often missed)
- Video usage: **Rare** (hard to find)

### After
- Average search time: **30 seconds** (one unified search)
- Resources found: **4-5 sources** (all types)
- Bulletin awareness: **High** (always shown first!)
- Video usage: **High** (automatically suggested)

### Business Impact
- ✅ Faster repairs (less research time)
- ✅ Better fixes (latest bulletins used)
- ✅ Fewer callbacks (more complete information)
- ✅ Happier technicians (easier to use)
- ✅ Higher customer satisfaction

---

## 🐛 Troubleshooting

### Issue: "Function search_error_code_resources does not exist"
**Solution:** Migration 29 not applied. Run it in Supabase SQL Editor.

### Issue: "No results returned"
**Solution:**
1. Check if error codes exist: `SELECT COUNT(*) FROM krai_intelligence.error_codes;`
2. Verify error code spelling
3. Check manufacturer filter isn't too restrictive

### Issue: "Links/Videos don't have manufacturer_id"
**Solution:**
1. Migration 28 backfill may have failed
2. Run manual backfill:
```sql
UPDATE krai_content.links l
SET manufacturer_id = d.manufacturer_id
FROM krai_core.documents d
WHERE l.document_id = d.id AND l.manufacturer_id IS NULL;
```

### Issue: "Service Bulletins not shown first"
**Solution:**
1. Check document priority: `SELECT document_type, priority_level FROM krai_core.documents WHERE document_type = 'service_bulletin';`
2. Should be `priority_level = 1`
3. If not, run Migration 28 again

---

## 📞 Support

For issues or questions:
1. Check migration verification queries
2. Review Supabase logs for RPC function errors
3. Test with SQL queries directly before using N8N
4. Consult `N8N_UNIFIED_ERROR_SEARCH_TOOL.md` for N8N setup details

---

## 🎉 Success!

Once deployed, your technicians can:
- Search once, find everything
- Get latest fixes first (bulletins)
- Watch video guides
- Find related parts
- Solve problems faster

**Result:** Better service, happier customers! 🚀
