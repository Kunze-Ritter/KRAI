# Video System Documentation

## Overview
Multi-platform video enrichment with auto-create manufacturers, products, and thumbnail generation.

## Supported Formats (11 Total)

### Modern
- **MP4** (H.264/H.265) - Most common
- **WebM** (VP8/VP9) - Web standard
- **MOV** (QuickTime) - Apple
- **MKV** (Matroska) - Open source

### Legacy
- **AVI**, **WMV**, **FLV**, **MPEG/MPG**

### Mobile
- **M4V** (iTunes), **3GP**

## Supported Platforms

1. **YouTube** - API metadata extraction
2. **Vimeo** - API metadata extraction
3. **Brightcove** - API metadata extraction
4. **Direct MP4/WebM/etc.** - OpenCV extraction + thumbnail generation

## Features

- ✅ Auto-create manufacturers (18 supported)
- ✅ Auto-create products
- ✅ Thumbnail generation (5 seconds)
- ✅ Model extraction from title/description
- ✅ Video ↔ Product linking (many-to-many)
- ✅ Video ↔ Error Code linking
- ✅ Deduplication across all flows

## Database Schema

```sql
CREATE TABLE videos (
  id UUID PRIMARY KEY,
  platform TEXT,              -- youtube/vimeo/brightcove/direct
  video_url TEXT,
  youtube_id TEXT,
  title TEXT,
  description TEXT,
  thumbnail_url TEXT,
  duration INT,
  manufacturer_id UUID,
  document_id UUID,
  metadata JSONB
);
```

## Migrations

- **Migration 38**: videos table
- **Migration 39**: videos view
- **Migration 40**: video_products junction

## N8N Tool

**File**: `TOOL_Video_Enrichment.json`

**Input**: `{"url": "https://youtube.com/..."}`

**Output**: Formatted video metadata with thumbnail, duration, models, etc.

---

**Last Updated**: 2025-10-07
