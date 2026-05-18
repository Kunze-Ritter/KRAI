# AI-Powered Product Research System

## Übersicht

Das Product Research System nutzt **AI, Firecrawl und Web-Scraping**, um automatisch Produktspezifikationen, Serien-Informationen und OEM-Beziehungen aus Hersteller-Websites zu extrahieren.

- Firecrawl für JavaScript-Rendering und strukturierte Datenextraktion

## Problem & Lösung

### Problem

```text
❌ Manuelle Pattern-Pflege für jeden Hersteller
❌ Neue Modelle werden nicht erkannt
❌ OEM-Beziehungen müssen recherchiert werden
❌ Specs müssen manuell eingegeben werden
❌ Komplexität steigt exponentiell
```

### Lösung

```text
✅ Automatische Online-Recherche (Firecrawl oder BeautifulSoup)
✅ JavaScript-Rendering (dynamische Websites)
✅ Markdown-Output für bessere LLM-Analyse
✅ Automatischer Fallback zu BeautifulSoup
✅ LLM extrahiert Specs aus Websites
✅ Selbstlernend (Pattern-Generation)
✅ Immer aktuelle Daten
✅ Skaliert auf alle Hersteller
```

## Architektur

### 1. Trigger-Punkte

Research wird ausgelöst wenn:

1. **Unbekanntes Produkt** (kein Pattern-Match)
2. **Niedrige Confidence** (< 0.7)
3. **Fehlende Serie**
4. **Fehlende Specs**
5. **Fehlende OEM-Info**

### 2. Research Pipeline

```text
Neues Produkt erkannt
  ↓
Pattern-Match? → JA → Fertig ✅
  ↓ NEIN
Web Search (Tavily/Direct)
  ↓
Scrape Content (Firecrawl oder BeautifulSoup)
  → Firecrawl: JavaScript-Rendering + Markdown
  → BeautifulSoup: Einfaches HTML-Parsing
  → Automatischer Fallback bei Fehlern
  ↓
LLM Analysis (Ollama) (Markdown-Format verbessert Extraktion)
  ↓
Extract: Specs, Series, OEM
  ↓
Save to Cache (90 Tage)
  ↓
Update Product in DB
  ↓
Fertig ✅
```

### 3. Web Scraping Backends

#### Firecrawl (Empfohlen)

- Self-hosted Scraping-Service mit erweiterten Funktionen
- Vorteile:
  - JavaScript-Rendering (Playwright)
  - LLM-ready Markdown-Output
  - Strukturierte Datenextraktion
  - URL-Mapping (Sitemap-Discovery)
  - Automatische Medien-Blockierung
- Nachteile:
  - Benötigt Docker-Services (Redis, Playwright, API, Worker)
  - Höherer Ressourcen-Verbrauch (~2GB RAM)
- Konfiguration: `SCRAPING_BACKEND=firecrawl`

#### BeautifulSoup (Fallback)

- Einfaches HTML-Parsing ohne externe Dependencies
- Vorteile:
  - Keine zusätzlichen Services benötigt
  - Geringer Ressourcen-Verbrauch
  - Schnell für statische Websites
- Nachteile:
  - Kein JavaScript-Rendering
  - Plain-Text statt Markdown
  - Keine strukturierte Extraktion
- Konfiguration: `SCRAPING_BACKEND=beautifulsoup`

#### Automatischer Fallback

- System wechselt automatisch zu BeautifulSoup wenn Firecrawl nicht verfügbar ist
- Beispiel: Firecrawl down → Automatischer Fallback → Keine Fehler

### 4. Database Schema

**Table:** `krai_intelligence.product_research_cache`

```sql
-- Product identification
manufacturer VARCHAR(100)
model_number VARCHAR(100)

-- Series information
series_name VARCHAR(200)
series_description TEXT

-- Specifications (JSONB)
specifications JSONB
-- {
--   "speed_mono": 75,
--   "speed_color": 75,
--   "resolution": "1200x1200 dpi",
--   "paper_sizes": ["A4", "A3"],
--   "duplex": "automatic",
--   "memory": "8192 MB",
--   "connectivity": ["USB", "Ethernet", "WiFi"]
-- }

-- Physical specs (JSONB)
physical_specs JSONB
-- {
--   "dimensions": {"width": 615, "depth": 685, "height": 1193},
--   "weight": 145.5,
--   "power_consumption": 1500
-- }

-- OEM information
oem_manufacturer VARCHAR(100)
oem_notes TEXT

-- Metadata
confidence FLOAT  -- 0.0 - 1.0
source_urls TEXT[]
cache_valid_until TIMESTAMP
verified BOOLEAN
```

## Setup

### 1. Migration ausführen

```sql
-- In Supabase SQL Editor
-- Execute: database/migrations/74_create_product_research_cache.sql
```

### 2. Environment Variables

```bash
# .env
ENABLE_PRODUCT_RESEARCH=true

# Optional: Tavily API (empfohlen)
TAVILY_API_KEY=your_api_key_here

# Cache duration
RESEARCH_CACHE_DAYS=90

# Web Scraping Backend
SCRAPING_BACKEND=firecrawl  # oder "beautifulsoup"

# Firecrawl Configuration (nur wenn SCRAPING_BACKEND=firecrawl)
FIRECRAWL_API_URL=http://localhost:3002
FIRECRAWL_LLM_PROVIDER=ollama  # oder "openai"
FIRECRAWL_MODEL_NAME=llama3.2:latest
FIRECRAWL_BLOCK_MEDIA=true

# Optional: OpenAI für bessere Extraktion
OPENAI_API_KEY=sk-...
```

**Tavily API Key erhalten:**

1. Gehe zu [tavily.com](https://tavily.com)
2. Sign up (kostenlos)
3. Kopiere API Key
4. Füge in `.env` ein

**Ohne Tavily:**

- System nutzt direkte Hersteller-URLs
- Funktioniert, aber weniger zuverlässig

### 2a. Firecrawl Setup (Optional)

1. Firecrawl-Services starten:

   ```bash
   docker-compose up -d krai-redis krai-playwright krai-firecrawl-api krai-firecrawl-worker
   ```

2. Health-Check: `curl http://localhost:3002/health`
3. Scraping-Backend aktivieren: `SCRAPING_BACKEND=firecrawl` in `.env`
4. LLM-Provider wählen: `FIRECRAWL_LLM_PROVIDER=ollama` (lokal) oder `openai` (Cloud)

**Ohne Firecrawl:** System nutzt automatisch BeautifulSoup (keine Konfiguration nötig)

### 3. Dependencies installieren

```bash
pip install beautifulsoup4 requests
```

## Usage

### CLI: Einzelnes Produkt recherchieren

```bash
# Basic research
python scripts/research_product.py "Konica Minolta" "C750i"

# Force refresh (ignore cache)
python scripts/research_product.py "HP" "LaserJet Pro M454dw" --force
```

**Output:**

```text
==============================================================================
Researching: Konica Minolta C750i
==============================================================================
==

✅ Research successful!
Confidence: 0.92

📋 Series: bizhub i-Series
Type: laser_multifunction

📊 Specifications:
{
  "speed_mono": 75,
  "speed_color": 75,
  "resolution": "1200x1200 dpi",
  "paper_sizes": ["A4", "A3", "Letter", "Legal"],
  "duplex": "automatic",
  "memory": "8192 MB",
  "connectivity": ["USB 2.0", "Ethernet", "WiFi"]
}

🔗 Sources:
   - https://kmbs.konicaminolta.us/products/multifunction/color-multi-function/bizhub-c750i/
   - https://www.konicaminolta.eu/eu-en/hardware/printing-devices/bizhub-c750i
```

### CLI: Batch Research

```bash
# Research 50 products without specs
python scripts/research_product.py --batch --limit 50
```

**Output:**

```text
==============================================================================
Batch Research (limit: 50)
==============================================================================
==

🔍 Researching product: Konica Minolta C750i
✅ Product enriched with research (confidence: 0.92)

🔍 Researching product: HP LaserJet Pro M454dw
✅ Product enriched with research (confidence: 0.88)

...

✅ Batch research complete:
   Enriched: 45
   Skipped: 3
   Failed: 2
```

### CLI: Unverified Results anzeigen

```bash
python scripts/research_product.py --verify
```

### Python API: Integration

```python
from backend.research.research_integration import ResearchIntegration
from supabase import create_client

supabase = create_client(url, key)
integration = ResearchIntegration(supabase=supabase, enabled=True)

# Enrich single product
success = integration.enrich_product(
    product_id=product_id,
    manufacturer_name="Konica Minolta",
    model_number="C750i",
    current_confidence=0.5
)

# Batch enrich
stats = integration.batch_enrich_products(limit=100)
```

### Automatic Integration

Research läuft **automatisch** während Document Processing:

```python
# backend/processors/document_processor.py

# Nach Product Extraction:
if ENABLE_PRODUCT_RESEARCH:
    integration = ResearchIntegration(supabase)
    integration.enrich_product(
        product_id=product_id,
        manufacturer_name=manufacturer,
        model_number=model,
        current_confidence=confidence
    )
```

## Was wird extrahiert?

### 1. Series Information

- `series_name`: "bizhub i-Series"
- `series_description`: "Latest generation with 10.1" touch panel"

### 2. Product Specifications

- **Speed:** mono/color ppm
- **Resolution:** dpi
- **Paper sizes:** A4, A3, Letter, etc.
- **Duplex:** automatic/manual/none
- **Memory:** MB
- **Storage:** SSD/HDD
- **Connectivity:** USB, Ethernet, WiFi
- **Scan speed:** ipm
- **Monthly duty cycle:** pages

### 3. Physical Specifications

- **Dimensions:** W x D x H (mm)
- **Weight:** kg
- **Power consumption:** W

### 4. OEM Information

- **OEM manufacturer:** Brother, Lexmark, etc.
- **OEM notes:** Engine details

### 5. Lifecycle

- **Launch date**
- **EOL date** (if available)

### 6. Product Type

- laser_printer
- laser_multifunction
- inkjet_printer
- production_printer
- etc.

## Performance

### Speed

- **Web search:** ~1-2 seconds
- **Scraping:** ~2-3 seconds per URL (concurrent)
- **Firecrawl:** ~3-5 seconds per URL (JavaScript-Rendering)
- **BeautifulSoup:** ~1-2 seconds per URL (statisches HTML)
- **LLM analysis:** ~10-15 seconds
- **Total:** ~15-25 seconds per product (mit Firecrawl)

### Caching

- **Cache duration:** 90 Tage (konfigurierbar)
- **Cache hit:** < 1ms
- **Reduces API calls:** 99%

### Costs

- **Tavily API:** $0.002 per search (1000 searches = $2)
- **Firecrawl (self-hosted):** FREE (nur Infrastruktur-Kosten)
- **Firecrawl + OpenAI:** ~$0.001 per extraction (optional)
- **LLM (Ollama):** FREE (local)
- **Total:** ~$0.002-0.003 per product (mit OpenAI)

## Firecrawl vs BeautifulSoup

| Feature | Firecrawl | BeautifulSoup |
|---------|-----------|---------------|
| JavaScript-Rendering | ✅ Ja | ❌ Nein |
| Output-Format | Markdown | Plain Text |
| Strukturierte Extraktion | ✅ Ja (LLM) | ❌ Nein |
| URL-Discovery | ✅ Ja | ⚠️ Begrenzt |
| Setup-Komplexität | ⚠️ Docker-Services | ✅ Einfach |
| Ressourcen | ⚠️ ~2GB RAM | ✅ Minimal |
| Geschwindigkeit | ⚠️ 3-5s/URL | ✅ 1-2s/URL |
| Qualität | ✅ Hoch | ⚠️ Mittel |

**Empfehlung:** Firecrawl für Produktion, BeautifulSoup für Entwicklung/Testing

## Confidence Scoring

```python
confidence = 0.0 - 1.0

0.9 - 1.0  → Excellent (verified data from official source)
0.7 - 0.9  → Good (multiple sources agree)
0.5 - 0.7  → Medium (some uncertainty)
0.0 - 0.5  → Low (needs manual verification)
```

## Manual Verification

### Workflow

- **Research läuft automatisch**
- **Ergebnisse in Cache gespeichert** (verified=false)
- **Admin prüft Ergebnisse:**

```bash
python scripts/research_product.py --verify
```

- **Manuelle Verifizierung:**

```sql
UPDATE krai_intelligence.product_research_cache
SET verified = true,
    verified_by = 'admin',
    verified_at = NOW()
WHERE manufacturer = 'Konica Minolta'
  AND model_number = 'C750i';
```

### Verification UI (TODO)

Geplant: Web-UI für einfache Verifizierung

## Troubleshooting

### Problem: No search results

**Symptom:** "No search results found"

**Lösung:**

1. Check Tavily API Key
2. Check internet connection
3. Try direct search (without Tavily)

### Problem: Scraping fails

**Symptom:** "Could not scrape content"

**Lösung:**

1. Check manufacturer website is accessible
2. Check for bot protection (Cloudflare, etc.)
3. Add User-Agent header

### Problem: LLM analysis fails

**Symptom:** "LLM analysis failed"

**Lösung:**

1. Check Ollama is running: `curl http://localhost:11434`
2. Check model is available: `ollama list`
3. Check timeout (increase if needed)

### Problem: Low confidence

**Symptom:** Confidence < 0.7

**Lösung:**

1. Manual verification
2. Add more source URLs
3. Improve LLM prompt

## Roadmap

### Phase 1: ✅ Basic Research (DONE)

- [x] Web search integration
- [x] Web scraping
- [x] LLM analysis
- [x] Cache system
- [x] CLI tools

### Phase 2: ✅ Integration (DONE)

- [x] Automatic integration in document processor
- [x] Firecrawl backend integration
- [x] Automatic fallback zu BeautifulSoup

### Phase 2.5: ✅ Firecrawl Integration (DONE)

- [x] Firecrawl Docker services
- [x] WebScrapingService abstraction
- [x] ProductResearcher refactoring
- [x] Automatic backend selection
- [x] Markdown output für LLM

### Phase 3: 📋 Planned

- [ ] Verification UI
- [ ] Pattern generation from research
- [ ] Confidence improvement
- [ ] Multi-language support
- [ ] Image analysis (extract specs from images)

## Examples

### Example 1: Unknown Product

```text
Input: "Konica Minolta C999i" (unbekannt)

1. Pattern-Match: ❌ Kein Match
2. Trigger: Online-Recherche
3. Search: "Konica Minolta C999i specifications"
4. LLM extrahiert:
   - Series: "bizhub i-Series"
   - Speed: 99 ppm
   - Type: "laser_multifunction"
5. Speichern in Cache
6. Update Product in DB
7. Nächstes Mal: ✅ Aus Cache
```

### Example 2: Missing Specs

```text
Input: Product "C750i" exists, but no specs

1. Trigger: Fehlende Specs
2. Research: Online-Suche
3. Extract: Alle Specs
4. Update: Product.specifications
5. Confidence: 0.92
```

### Example 3: OEM Discovery

```text
Input: "Lexmark CX950de" (kein OEM bekannt)

1. Trigger: Fehlende OEM-Info
2. Search: "Lexmark CX950de OEM engine"
3. LLM findet: "Konica Minolta engine"
4. Update: oem_manufacturer = "Konica Minolta"
```

### Example 4: Firecrawl Fallback

```text
Input: Firecrawl-Service nicht verfügbar

1. Trigger: Online-Recherche
2. Versuch: Firecrawl scraping
3. Fehler: Connection refused
4. Fallback: BeautifulSoup scraping
5. Erfolg: ✅ Daten extrahiert
6. Log: "Firecrawl unavailable, using BeautifulSoup"
```

## Best Practices

1. **Use Firecrawl for production** (bessere Qualität)
2. **Monitor fallback rate** (zu viele Fallbacks = Firecrawl-Problem)
3. **Test with both backends** (sicherstellen dass Fallback funktioniert)
4. **Start with Tavily API** (bessere Ergebnisse)
5. **Cache nutzen** (spart API calls)
6. **Batch processing** (effizienter)
7. **Manual verification** (für kritische Produkte)
8. **Monitor confidence** (< 0.7 = prüfen)

---

**Autor:** KRAI Development Team
**Version:** 1.1
**Letzte Aktualisierung:** 6. November 2025
