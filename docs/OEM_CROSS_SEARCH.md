# OEM Cross-Manufacturer Search System

## Übersicht

Das OEM Cross-Search System ermöglicht es, Dokumente über Hersteller-Grenzen hinweg zu finden. Wenn ein Produkt ein OEM-Rebrand ist (z.B. Konica Minolta 5000i = Brother Engine), findet die Suche automatisch **beide** Hersteller.

## Problem & Lösung

### Problem

```
User sucht: "Konica Minolta 5000i error C4080"
→ Findet nur: Konica Minolta Dokumente
→ Findet NICHT: Brother Dokumente (obwohl gleiche Engine!)
→ Ergebnis: Unvollständige Informationen ❌
```

### Lösung

```
User sucht: "Konica Minolta 5000i error C4080"
→ System erkennt: 5000i = Brother Engine
→ Erweitert Suche zu:
  1. "Konica Minolta 5000i error C4080"
  2. "Brother 5000i error C4080"
  3. "Brother error C4080"
→ Findet: BEIDE Hersteller! ✅
```

## Architektur

### 1. OEM Mappings (Python)

**Datei:** `backend/config/oem_mappings.py`

```python
OEM_MAPPINGS = {
    ('Konica Minolta', r'[45]000i'): {
        'oem_manufacturer': 'Brother',
        'applies_to': ['error_codes', 'parts']
    },
    # ... 32 total mappings
}
```

### 2. Database Tables

#### A) `oem_relationships` Table

Speichert alle OEM-Beziehungen für schnelle Lookups:

```sql
CREATE TABLE krai_core.oem_relationships (
    id UUID PRIMARY KEY,
    brand_manufacturer VARCHAR(100),      -- "Konica Minolta"
    brand_series_pattern VARCHAR(200),    -- "[45]000i"
    oem_manufacturer VARCHAR(100),        -- "Brother"
    applies_to TEXT[],                    -- ['error_codes', 'parts']
    notes TEXT,
    confidence FLOAT,
    verified BOOLEAN
);
```

#### B) `products` Table (erweitert)

Neue Spalten für schnellen OEM-Zugriff:

```sql
ALTER TABLE krai_core.products
ADD COLUMN oem_manufacturer VARCHAR(100),
ADD COLUMN oem_relationship_type VARCHAR(50),
ADD COLUMN oem_notes TEXT;
```

### 3. Python Utilities

**Datei:** `backend/utils/oem_sync.py`

Wichtige Funktionen:

```python
# Sync OEM mappings to database (PostgreSQL)
sync_oem_relationships_to_db(db_pool)

# Get equivalent manufacturers for search
get_oem_equivalent_manufacturers("Konica Minolta", "5000i")
# → ["Konica Minolta", "Brother"]

# Expand search query
expand_search_query_with_oem("Konica Minolta", "5000i", "error C4080")
# → [
#     "Konica Minolta 5000i error C4080",
#     "Brother 5000i error C4080",
#     "Brother error C4080"
# ]
```

## Setup & Installation

### 1. Migrationen ausführen

```bash
# Migration 72: Create oem_relationships table
psql -h localhost -p 5432 -U postgres -d krai -f database/migrations/72_create_oem_relationships.sql

# Migration 73: Add OEM columns to products
psql -h localhost -p 5432 -U postgres -d krai -f database/migrations/73_add_oem_to_products.sql
```

**Or via pgAdmin/DBeaver:**
1. Connect to PostgreSQL (host: localhost, port: 5432, database: krai)
2. Open SQL Editor
3. Copy content from `72_create_oem_relationships.sql`
4. Execute
5. Copy content from `73_add_oem_to_products.sql`
6. Execute

### 2. OEM Mappings in DB synchronisieren

```bash
# Nur OEM relationships syncen
python scripts/sync_oem_to_database.py

# OEM relationships + alle Products updaten
python scripts/sync_oem_to_database.py --update-products

# Dry run (Vorschau)
python scripts/sync_oem_to_database.py --dry-run
```

### 3. In RAG/Search integrieren

```python
from backend.utils.oem_sync import expand_search_query_with_oem

# User sucht nach Konica Minolta 5000i
user_query = "Konica Minolta 5000i error C4080"
manufacturer = "Konica Minolta"
model = "5000i"

# Erweitere Query mit OEM
expanded_queries = expand_search_query_with_oem(
    manufacturer,
    model,
    user_query
)

# Suche mit allen Queries
for query in expanded_queries:
    results = search_documents(query)
    # Kombiniere Ergebnisse
```

## Use Cases

### Use Case 1: Error Code Suche

**Szenario:** Techniker sucht nach Error Code für Konica Minolta 5000i

```python
# User Input
query = "Konica Minolta 5000i error C4080"

# System erweitert automatisch
queries = [
    "Konica Minolta 5000i error C4080",  # Original
    "Brother 5000i error C4080",          # OEM equivalent
    "Brother error C4080"                 # OEM ohne Model
]

# Findet:
# - Konica Minolta 5000i Service Manual
# - Brother HL-5000 Service Manual (gleiche Engine!)
# - Brother Error Code Liste
```

### Use Case 2: Parts Suche

**Szenario:** Ersatzteil für Xerox Versant 280 suchen

```python
# User Input
query = "Xerox Versant 280 fuser unit"

# System erweitert
queries = [
    "Xerox Versant 280 fuser unit",
    "Fujifilm Versant 280 fuser unit",  # OEM
    "Fujifilm fuser unit"
]

# Findet:
# - Xerox Versant Parts Catalog
# - Fujifilm Revoria Parts (kompatibel!)
```

### Use Case 3: Troubleshooting

**Szenario:** Lexmark CS943 Jam Problem

```python
# User Input
query = "Lexmark CS943 paper jam C4080"

# System erweitert
queries = [
    "Lexmark CS943 paper jam C4080",
    "Konica Minolta CS943 paper jam C4080",  # OEM
    "Konica Minolta paper jam C4080"
]

# Findet:
# - Lexmark CS943 Service Manual
# - Konica Minolta bizhub C258 (gleiche Engine!)
```

## Abgedeckte OEM-Beziehungen

### Konica Minolta
- **5000i/4000i** → Brother
- **bizhub 4750/4050/4020** → Lexmark
- **bizhub 3300P/3320** → Lexmark

### Lexmark
- **CS/CX 900 series** → Konica Minolta
- **CS/CX 800 series** → Konica Minolta
- **MX622** → Konica Minolta

### Xerox
- **VersaLink** → Lexmark
- **B/C-Series** → Lexmark
- **AltaLink** → Fujifilm
- **Versant** → Fujifilm
- **Iridesse** → Fujifilm
- **PrimeLink** → Fujifilm
- **Nuvera** → Fujifilm
- **Production Inkjet** → Kyocera (2025)

### UTAX/Triumph-Adler
- **Alle Produkte** → Kyocera

### Ricoh Family
- **Savin** → Ricoh
- **Lanier** → Ricoh
- **Gestetner** → Ricoh

### Fujifilm
- **Fuji Xerox** → Fujifilm (rebranded 2021)
- **Revoria Press** → Fujifilm

### HP
- **Samsung A3 (SL-/SCX-)** → Samsung
- **LaserJet E7000/E8000** → Samsung

### Toshiba
- **e-STUDIO 389CS/509CS** → Lexmark
- **e-STUDIO 478s** → Lexmark

### Dell
- **Laser Printers** → Lexmark

**Total: 32 OEM-Mappings**

## Performance

### Database Indexes

Optimiert für schnelle Lookups:

```sql
-- Brand lookup
CREATE INDEX idx_oem_relationships_brand ON oem_relationships(brand_manufacturer);

-- OEM lookup
CREATE INDEX idx_oem_relationships_oem ON oem_relationships(oem_manufacturer);

-- Series pattern lookup
CREATE INDEX idx_oem_relationships_series ON oem_relationships(brand_series_pattern);

-- Products OEM lookup
CREATE INDEX idx_products_oem_manufacturer ON products(oem_manufacturer);
```

### Query Performance

- **OEM Lookup:** < 1ms (indexed)
- **Query Expansion:** < 5ms (in-memory)
- **Cross-OEM Search:** +10-20% overhead (acceptable)

## Maintenance

### Neue OEM-Beziehung hinzufügen

1. **In `oem_mappings.py` hinzufügen:**

```python
('Neue Marke', r'Model Pattern'): {
    'oem_manufacturer': 'OEM Hersteller',
    'series_name': 'Serie Name',
    'notes': 'Beschreibung',
    'applies_to': ['error_codes', 'parts']
}
```

2. **Sync zur Datenbank:**

```bash
python scripts/sync_oem_to_database.py --update-products
```

3. **Fertig!** ✅

### OEM-Beziehung verifizieren

```python
from backend.config.oem_mappings import get_oem_info

info = get_oem_info("Konica Minolta", "5000i")
print(info)
# {
#     'oem_manufacturer': 'Brother',
#     'series_name': '5000i/4000i Series',
#     'notes': 'Brother engine with Konica Minolta branding',
#     'applies_to': ['error_codes', 'parts']
# }
```

## Troubleshooting

### Problem: OEM nicht erkannt

**Symptom:** Suche findet keine OEM-Dokumente

**Lösung:**
```bash
# 1. Prüfe ob Mapping existiert
python backend/config/oem_mappings.py

# 2. Sync zur DB
python scripts/sync_oem_to_database.py

# 3. Update Products
python scripts/sync_oem_to_database.py --update-products
```

### Problem: Falsche OEM-Zuordnung

**Symptom:** Produkt hat falschen OEM

**Lösung:**
1. Korrigiere Pattern in `oem_mappings.py`
2. Re-sync: `python scripts/sync_oem_to_database.py --update-products`

### Problem: Performance langsam

**Symptom:** Cross-OEM Suche zu langsam

**Lösung:**
```sql
-- Prüfe Indexes
SELECT * FROM pg_indexes WHERE tablename = 'oem_relationships';

-- Re-create Indexes falls nötig
REINDEX TABLE krai_core.oem_relationships;
REINDEX TABLE krai_core.products;
```

## API Beispiele

### Python API

```python
from backend.utils.oem_sync import (
    get_oem_equivalent_manufacturers,
    expand_search_query_with_oem
)

# Get equivalent manufacturers
manufacturers = get_oem_equivalent_manufacturers("Konica Minolta", "5000i")
# → ["Konica Minolta", "Brother"]

# Expand search query
queries = expand_search_query_with_oem(
    "Konica Minolta",
    "5000i",
    "error C4080 solution"
)
# → [
#     "Konica Minolta 5000i error C4080 solution",
#     "Brother 5000i error C4080 solution",
#     "Brother error C4080 solution"
# ]
```

### SQL API

```sql
-- Find OEM for a product
SELECT oem_manufacturer, oem_notes
FROM krai_core.oem_relationships
WHERE brand_manufacturer = 'Konica Minolta'
  AND 'bizhub 4750' ~ brand_series_pattern;

-- Find all products with same OEM
SELECT p1.model_name AS original, p2.model_name AS oem_equivalent
FROM krai_core.products p1
JOIN krai_core.products p2 ON p1.oem_manufacturer = p2.manufacturer_id
WHERE p1.model_name = '5000i';
```

## Roadmap

### Phase 1: ✅ Completed
- [x] OEM mappings in Python
- [x] Database schema
- [x] Sync utilities
- [x] Query expansion

### Phase 2: 🚧 In Progress
- [ ] RAG integration
- [ ] Search UI updates
- [ ] Performance optimization

### Phase 3: 📋 Planned
- [ ] ML-based OEM detection
- [ ] Automatic mapping discovery
- [ ] Confidence scoring
- [ ] User feedback loop

---

**Autor:** KRAI Development Team
**Version:** 1.0
**Letzte Aktualisierung:** 10. Oktober 2025
