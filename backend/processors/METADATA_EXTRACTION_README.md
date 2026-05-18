# PDF Metadata Extraction

## Overview

Das System extrahiert automatisch **PDF-Metadaten** und nutzt sie für die Hersteller-Erkennung und Dokumentklassifizierung.

## Extrahierte Metadaten

### 1. **Basis-Metadaten** (aus PDF)

| Feld | Quelle | Beschreibung |
|------|--------|--------------|
| **Title** | PDF Metadata | Dokumenttitel (z.B. "Lexmark CS943 Service Manual") |
| **Author** | PDF Metadata | Autor/Ersteller (z.B. "Lexmark International") |
| **Creation Date** | PDF Metadata | Erstellungsdatum |
| **Page Count** | PDF | Anzahl der Seiten |
| **File Size** | Dateisystem | Dateigröße in Bytes |
| **MIME Type** | Dateisystem | Immer "application/pdf" |
| **Language** | Automatisch | Erkannte Sprache (z.B. "en", "de") |
| **Document Type** | Automatisch | Klassifiziert (Service Manual, User Guide, etc.) |

### 2. **Verwendung in Hersteller-Erkennung**

Die Metadaten werden aktiv für die **Weighted Scoring** Hersteller-Erkennung verwendet:

```python
# Source 1: Filename (10 Punkte)
filename_lower = pdf_path.stem.lower()

# Source 2: PDF Metadata Title (5 Punkte) ← HIER!
title_lower = (metadata.title or "").lower()

# Source 3: Document Text (1-3 Punkte)
first_pages_text = ' '.join([page_texts[p] for p in first_page_keys])
```

## Implementierung

### TextExtractor - Metadaten-Extraktion

#### PyMuPDF (Standard)
```python
def _extract_metadata_pymupdf(doc, pdf_path, document_id):
    pdf_metadata = doc.metadata

    return DocumentMetadata(
        document_id=document_id,
        title=pdf_metadata.get('title') or pdf_path.stem,
        author=pdf_metadata.get('author'),
        creation_date=parse_date(pdf_metadata.get('creationDate')),
        page_count=len(doc),
        file_size_bytes=pdf_path.stat().st_size,
        mime_type="application/pdf",
        language=detect_language(doc),
        document_type=classify_document_type(title, filename)
    )
```

#### pdfplumber (Alternative)
```python
def _extract_metadata_pdfplumber(pdf, pdf_path, document_id):
    pdf_metadata = pdf.metadata or {}

    return DocumentMetadata(
        document_id=document_id,
        title=pdf_metadata.get('Title') or pdf_path.stem,
        author=pdf_metadata.get('Author'),
        creation_date=parse_date(pdf_metadata.get('CreationDate')),
        page_count=len(pdf.pages),
        file_size_bytes=pdf_path.stat().st_size,
        mime_type="application/pdf",
        language="en",
        document_type=classify_document_type(title, filename)
    )
```

## Beispiele

### Beispiel 1: Lexmark Service Manual

**PDF Metadaten:**
```
Title: "Lexmark CS943 Service Manual"
Author: "Lexmark International"
CreationDate: "D:20230515120000+00'00'"
```

**Hersteller-Erkennung:**
```
Filename: lexmark_cs943_service.pdf
Title: "Lexmark CS943 Service Manual"  ← Metadata!
Text: "Lexmark CS943..."

Scoring:
- Filename: 10 (lexmark)
- Title: 5 (Lexmark)  ← Metadata wird verwendet!
- Text: 2 (lexmark 2x)
Total: 17 Punkte → Lexmark ✅
```

### Beispiel 2: Konica Minolta bizhub

**PDF Metadaten:**
```
Title: "bizhub C454e User Guide"
Author: "Konica Minolta"
CreationDate: "D:20220310093000+00'00'"
```

**Hersteller-Erkennung:**
```
Filename: bizhub_c454e_manual.pdf
Title: "bizhub C454e User Guide"  ← Metadata!
Text: "Konica Minolta bizhub..."

Scoring:
- Filename: 0 (kein direkter Match)
- Title: 5 (bizhub)  ← Metadata wird verwendet!
- Text: 3 (konica/minolta 3x)
Total: 8 Punkte → Konica Minolta ✅
```

### Beispiel 3: HP LaserJet

**PDF Metadaten:**
```
Title: "HP LaserJet M479fdw Service Manual"
Author: "HP Inc."
CreationDate: "D:20210820140000+00'00'"
```

**Hersteller-Erkennung:**
```
Filename: hp_m479_service.pdf
Title: "HP LaserJet M479fdw Service Manual"  ← Metadata!
Text: "HP LaserJet..."

Scoring:
- Filename: 10 (hp)
- Title: 5 (HP + LaserJet)  ← Metadata wird verwendet!
- Text: 2 (hp 2x)
Total: 17 Punkte → Hewlett Packard ✅
```

## Dokumenttyp-Klassifizierung

Das System klassifiziert Dokumente automatisch basierend auf **Title** und **Filename**:

```python
def _classify_document_type(title: str, filename: str) -> str:
    text = f"{title} {filename}".lower()

    if any(kw in text for kw in ['service', 'repair', 'maintenance']):
        return 'service_manual'
    elif any(kw in text for kw in ['user', 'guide', 'manual', 'handbook']):
        return 'user_guide'
    elif any(kw in text for kw in ['parts', 'catalog', 'list']):
        return 'parts_catalog'
    elif any(kw in text for kw in ['quick', 'start', 'setup']):
        return 'quick_start'
    elif any(kw in text for kw in ['specification', 'spec', 'datasheet']):
        return 'specification'
    else:
        return 'unknown'
```

## Metadaten-Formate

### PyMuPDF Format
```python
{
    'title': 'Lexmark CS943 Service Manual',
    'author': 'Lexmark International',
    'creationDate': 'D:20230515120000+00\'00\'',  # PDF format
    'modDate': 'D:20230515120000+00\'00\'',
    'producer': 'Adobe PDF Library 15.0',
    'creator': 'Adobe InDesign CC 2019'
}
```

### pdfplumber Format
```python
{
    'Title': 'Lexmark CS943 Service Manual',
    'Author': 'Lexmark International',
    'CreationDate': 'D:20230515120000+00\'00\'',
    'ModDate': 'D:20230515120000+00\'00\'',
    'Producer': 'Adobe PDF Library 15.0',
    'Creator': 'Adobe InDesign CC 2019'
}
```

## Datum-Parsing

Das System unterstützt verschiedene PDF-Datumsformate:

```python
# PyMuPDF Format: D:20240101120000+00'00'
date_str = pdf_metadata['creationDate']
if date_str.startswith('D:'):
    date_str = date_str[2:16]  # YYYYMMDDHHMMSS
    creation_date = datetime.strptime(date_str, '%Y%m%d%H%M%S')

# Alternative Formate
for fmt in ['%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S']:
    try:
        creation_date = datetime.strptime(date_str[:14], fmt)
        break
    except ValueError:
        continue
```

## Sprach-Erkennung

Die Sprache wird aus dem Dokumenttext erkannt:

```python
def _detect_language(doc) -> str:
    # Sample first page
    first_page_text = doc[0].get_text() if len(doc) > 0 else ""

    # Simple heuristics
    if any(word in first_page_text.lower() for word in ['the', 'and', 'of', 'to']):
        return 'en'
    elif any(word in first_page_text.lower() for word in ['der', 'die', 'das', 'und']):
        return 'de'
    # ... weitere Sprachen

    return 'en'  # Default
```

## Vorteile der Metadaten-Nutzung

### 1. **Höhere Genauigkeit**
- Title enthält oft den Hersteller-Namen
- Zuverlässiger als Text-Parsing allein

### 2. **Schnellere Verarbeitung**
- Metadaten sind sofort verfügbar
- Kein Text-Parsing nötig für erste Erkennung

### 3. **Bessere Klassifizierung**
- Title gibt Hinweise auf Dokumenttyp
- Author kann Hersteller bestätigen

### 4. **Fallback-Mechanismus**
```python
# Title aus Metadaten oder Fallback auf Filename
title = pdf_metadata.get('title') or pdf_path.stem
```

## Logging

Das System loggt die Metadaten-Extraktion:

```
📄 Extracting text from document...
   Engine: pymupdf
   Pages: 245
   Title: "Lexmark CS943 Service Manual"  ← Metadata
   Author: "Lexmark International"  ← Metadata

🔍 Auto-detected manufacturer: Lexmark
   Confidence score: 17 (filename, title, text(2x))
   ✅ Very high confidence (multiple sources)
```

## Best Practices

1. **Immer Metadaten prüfen**: Title ist oft die zuverlässigste Quelle
2. **Fallback verwenden**: Wenn keine Metadaten, Filename nutzen
3. **Kombinieren**: Metadaten + Filename + Text für beste Ergebnisse
4. **Validieren**: Metadaten können leer oder falsch sein

## Zusammenfassung

✅ **Metadaten werden vollständig genutzt!**

- **Title** wird für Hersteller-Erkennung verwendet (5 Punkte)
- **Author** wird extrahiert (könnte zusätzlich genutzt werden)
- **Creation Date** wird gespeichert
- **Document Type** wird klassifiziert
- **Language** wird erkannt

Die Metadaten sind ein **wichtiger Teil** des Weighted Scoring Systems und erhöhen die Genauigkeit der Hersteller-Erkennung erheblich!
