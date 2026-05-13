"""
Version Information for KRAI Processing Pipeline
Auto-updated with each significant release
"""

__version__ = "0.50.0"
__commit__ = "9bb106e"
__date__ = "2026-05-13"

# Version History:
# 2.1.3 (b676d3e) - Fix: Product logging noise + parts catalog constraint migration
# 2.1.2 (9400c54) - Fix: Parts inherit manufacturer from document + Complete manufacturer seed data
# 2.1.1 (0ae41d6) - Fix: multifunction → laser_multifunction + Import fixes + Retry logic
# 2.1.0 (79e8dfe) - MAJOR: Modular .env structure + Pipeline settings + Series detection (12 manufacturers)
# 2.0.43 (TBD) - Fix: exec_sql parameter name + ensure image_id exists in Migration 23
# 2.0.42 (7cb6b00) - Fix: Embedding processor dict/object mismatch + scope error
# 2.0.41 (77b174f) - Fix: ULTIMATE - Use RPC Function to bypass PostgREST cache!
# 2.0.40 (ad934a4) - Fix: DROP + RECREATE columns to reset PostgREST cache!
# 2.0.39 (4445d62) - Fix: ONLY use BASE SCHEMA - PostgREST cache broken for Migration 09 columns
# 2.0.38 (803eec1) - Fix: Remove ai_extracted field (Supabase cache issue)
# 2.0.37 (c745775) - Feat: SMART image matching via Vision AI descriptions!
# 2.0.36 (1cc51e7) - Feat: Link error codes to chunks & images (N8N Agent integration!)
# 2.0.35 (71ca96e) - Feat: Re-add metadata + context_text + ai_extracted fields
# 2.0.34 (b2a4763) - Fix: Remove metadata field - column doesn't exist in schema
# 2.0.33 (53dcb99) - Fix: Schema mismatch - documents.manufacturer not manufacturer_id
# 2.0.32 (a1ec31f) - Feat: Save error codes IMMEDIATELY after extraction (no waiting!)
# 2.0.31 (96582f0) - Feat: Version tracking + banner
# 2.0.30 (ac6c400) - Fix: Error codes manufacturer_id + severity_level
# 2.0.29 (9ef0e2b) - Feat: Auto-link images to chunks after embedding
# 2.0.28 (b027d40) - Fix: Images chunk_id FK to krai_intelligence.chunks
# 2.0.27 (d4f5776) - Fix: CRITICAL - Preserve chunk metadata in embedding
# 2.0.26 (8ce7054) - Fix: Handle .pdfz files (uncompressed PDFs)
# 2.0.25 (524c066) - Fix: HP header detection + URL product extraction
