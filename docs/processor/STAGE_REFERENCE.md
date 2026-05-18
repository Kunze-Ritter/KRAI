# Stage Reference Documentation

This document provides detailed reference information for all 15 pipeline stages in the KRAI document processing system.

## Table of Contents

1. [UPLOAD (Stage 1)](#upload-stage-1)
2. [TEXT_EXTRACTION (Stage 2)](#text_extraction-stage-2)
3. [TABLE_EXTRACTION (Stage 3)](#table_extraction-stage-3)
4. [SVG_PROCESSING (Stage 4)](#svg_processing-stage-4)
5. [IMAGE_PROCESSING (Stage 5)](#image_processing-stage-5)
6. [VISUAL_EMBEDDING (Stage 6)](#visual_embedding-stage-6)
7. [LINK_EXTRACTION (Stage 7)](#link_extraction-stage-7)
8. [CHUNK_PREP (Stage 8)](#chunk_prep-stage-8)
9. [CLASSIFICATION (Stage 9)](#classification-stage-9)
10. [METADATA_EXTRACTION (Stage 10)](#metadata_extraction-stage-10)
11. [PARTS_EXTRACTION (Stage 11)](#parts_extraction-stage-11)
12. [SERIES_DETECTION (Stage 12)](#series_detection-stage-12)
13. [STORAGE (Stage 13)](#storage-stage-13)
14. [EMBEDDING (Stage 14)](#embedding-stage-14)
15. [SEARCH_INDEXING (Stage 15)](#search_indexing-stage-15)

---

## UPLOAD (Stage 1)

### Purpose
File upload, validation, hash calculation, and initial database record creation. This is the entry point for all document processing.

### Processor
`backend/processors/upload_processor.py`

### Inputs
- **file**: PDF file (multipart/form-data)
- **document_type**: Type of document (service_manual, parts_catalog, etc.)
- **language**: Document language (en, de, etc.)
- **manufacturer**: Manufacturer name (optional, auto-detected if not provided)

### Outputs
- **document_id**: UUID for the uploaded document
- **file_hash**: SHA-256 hash of the file content
- **storage_path**: Temporary storage location
- **file_metadata**: File size, pages, creation date

### Database Operations
```sql
INSERT INTO krai_core.documents (
    id, filename, file_hash, file_size, page_count,
    document_type, language, manufacturer, upload_date,
    stage_status
) VALUES (
    uuid, filename, hash, size, pages,
    type, language, manufacturer, now(),
    '{"upload": {"status": "completed", "timestamp": "..."}}'::jsonb
);
```

### Storage Operations
- **Temporary Storage**: `/tmp/uploads/` directory
- **MinIO Upload**: Final storage in `documents` bucket
- **File Validation**: PDF format, size limits, corruption check

### Dependencies
- **None** (entry point stage)

### Typical Processing Time
1-2 seconds

### Error Conditions
- **Invalid File Format**: Non-PDF files rejected
- **Duplicate Hash**: File already exists in database
- **Storage Failure**: Disk space or permission issues
- **File Corruption**: PDF cannot be opened/read

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --file /path/to/document.pdf \
  --document-type service_manual --language en
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf" \
  -F "document_type=service_manual" \
  -F "language=en"
```

#### Python SDK
```python
from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.config.database_config import get_database_adapter

db_adapter = get_database_adapter()
pipeline = KRMasterPipeline(database_adapter=db_adapter)
result = await pipeline.run_single_stage(
    document_id="uuid",
    stage_name="upload",
    file_path="/path/to/document.pdf",
    document_type="service_manual",
    language="en"
)
```

---

## TEXT_EXTRACTION (Stage 2)

### Purpose
Extract text content from PDF pages using OCR and text extraction libraries.

### Processor
`backend/processors/text_processor.py`

### Inputs
- **document_id**: UUID from UPLOAD stage
- **file_path**: Path to the PDF file

### Outputs
- **page_texts**: Dictionary mapping page numbers to extracted text
- **total_text_length**: Total characters extracted
- **ocr_used**: Boolean indicating if OCR was required
- **extraction_method**: Method used (pymupdf, tesseract, etc.)

### Database Operations
```sql
INSERT INTO krai_content.chunks (
    id, document_id, page_number, text_chunk,
    chunk_type, content_hash, created_at
) VALUES (
    uuid, document_id, page_num, extracted_text,
    'text', hash, now()
);
```

### Dependencies
- **UPLOAD** (needs file_path and document_id)

### Typical Processing Time
2-5 seconds

### Technologies
- **PyMuPDF**: Primary PDF text extraction
- **Tesseract OCR**: Fallback for scanned documents
- **PDFMiner**: Alternative extraction method
- **Language Detection**: Auto-detect document language

### Error Conditions
- **Corrupted PDF**: File cannot be opened by PyMuPDF
- **Password Protected**: PDF requires password to access
- **OCR Failure**: Tesseract not available or fails to process
- **Memory Issues**: Large PDF causes memory exhaustion

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage text_extraction
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/text_extraction \
  -H "Authorization: Bearer $TOKEN"
```

#### Python SDK
```python
result = await pipeline.run_single_stage(
    document_id="uuid",
    stage_name="text_extraction"
)
```

---

## TABLE_EXTRACTION (Stage 3)

### Purpose
Extract structured tables from PDF documents and convert them to machine-readable format.

### Processor
`backend/processors/table_processor.py`

### Inputs
- **document_id**: UUID from UPLOAD stage
- **file_path**: Path to the PDF file

### Outputs
- **tables**: List of extracted tables with cell content
- **table_count**: Number of tables found
- **table_locations**: Page numbers and coordinates for each table
- **extraction_quality**: Confidence scores for table detection

### Database Operations
```sql
INSERT INTO krai_intelligence.structured_tables (
    id, document_id, page_number, table_index,
    table_data, row_count, column_count,
    extraction_confidence, created_at
) VALUES (
    uuid, document_id, page_num, table_idx,
    json_data, rows, cols,
    confidence, now()
);
```

### Dependencies
- **UPLOAD** (needs file_path and document_id)

### Typical Processing Time
3-8 seconds

### Technologies
- **PyMuPDF Table Detection**: Identify table structures
- **Pandas DataFrame**: Convert tables to structured format
- **Tabula**: Alternative table extraction method
- **OpenCV**: Image-based table detection for complex layouts

### Error Conditions
- **No Tables Found**: Document contains no detectable tables
- **Malformed Tables**: Tables with irregular structure
- **Complex Layouts**: Tables merged with other content
- **Low Quality**: Poor scan quality affects detection

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage table_extraction
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/table_extraction \
  -H "Authorization: Bearer $TOKEN"
```

---

## SVG_PROCESSING (Stage 4)

### Purpose
Convert vector graphics (SVG) and diagrams to PNG format for Vision AI processing.

### Processor
`backend/processors/svg_processor.py`

### Inputs
- **document_id**: UUID from UPLOAD stage
- **file_path**: Path to the PDF file

### Outputs
- **converted_images**: List of PNG files generated from SVGs
- **svg_count**: Number of SVG elements found
- **conversion_results**: Success/failure status for each conversion
- **image_metadata**: Dimensions, file sizes for converted images

### Database Operations
```sql
INSERT INTO krai_content.images (
    id, document_id, page_number, image_type,
    file_path, file_size, width, height,
    extraction_method, created_at
) VALUES (
    uuid, document_id, page_num, 'svg_converted',
    minio_path, size, width, height,
    'cairosvg', now()
);
```

### Storage Operations
- **MinIO Storage**: PNG files stored in `images` bucket
- **File Naming**: `{document_id}_page_{num}_svg_{idx}.png`

### Dependencies
- **UPLOAD** (needs file_path and document_id)

### Typical Processing Time
2-6 seconds

### Technologies
- **CairoSVG**: Convert SVG to PNG
- **PIL/Pillow**: Image processing and validation
- **PyMuPDF**: Extract SVG elements from PDF
- **MinIO**: Store converted images

### Error Conditions
- **Invalid SVG**: Malformed SVG markup
- **Conversion Failure**: CairoSVG cannot process complex SVG
- **Memory Issues**: Large SVG causes conversion failure
- **Storage Error**: MinIO upload failure

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage svg_processing
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/svg_processing \
  -H "Authorization: Bearer $TOKEN"
```

---

## IMAGE_PROCESSING (Stage 5)

### Purpose
Extract images from PDF pages and analyze them with Vision AI to generate descriptions and metadata.

### Processor
`backend/processors/image_processor.py`

### Inputs
- **document_id**: UUID from UPLOAD stage
- **file_path**: Path to the PDF file

### Outputs
- **images**: List of extracted images with metadata
- **image_count**: Number of images found
- **ai_descriptions**: Vision AI generated descriptions for each image
- **image_analysis**: Object detection, text recognition results

### Database Operations
```sql
INSERT INTO krai_content.images (
    id, document_id, page_number, image_type,
    file_path, file_size, width, height,
    ai_description, confidence_score, created_at
) VALUES (
    uuid, document_id, page_num, 'extracted',
    minio_path, size, width, height,
    description, confidence, now()
);
```

### Storage Operations
- **MinIO Storage**: Original images stored in `images` bucket
- **File Naming**: `{document_id}_page_{num}_img_{idx}.png`

### Dependencies
- **UPLOAD** (needs file_path and document_id)

### Typical Processing Time
5-15 seconds (depends on image count)

### Technologies
- **PyMuPDF**: Extract images from PDF pages
- **PIL/Pillow**: Image processing and format conversion
- **Ollama LLaVA**: Vision AI for image analysis
- **OpenCV**: Image preprocessing and enhancement

### Error Conditions
- **No Images Found**: Document contains no extractable images
- **Vision AI Failure**: LLaVA model unavailable or errors
- **Large Images**: Memory issues with high-resolution images
- **Storage Failure**: MinIO upload problems

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage image_processing
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/image_processing \
  -H "Authorization: Bearer $TOKEN"
```

---

## VISUAL_EMBEDDING (Stage 6)

### Purpose
Generate vector embeddings for extracted images to enable visual similarity search and retrieval.

### Processor
`backend/processors/visual_embedding_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **images**: Image list from IMAGE_PROCESSING stage

### Outputs
- **embeddings**: List of vector embeddings for each image
- **embedding_count**: Number of embeddings generated
- **embedding_model**: Model used for embedding generation
- **embedding_dimensions**: Vector dimensions (typically 512 or 768)

### Database Operations
```sql
INSERT INTO krai_intelligence.chunks (
    id, document_id, source_type, source_id,
    embedding, model_name,
    created_at
) VALUES (
    uuid, document_id, 'image', image_id,
    embedding_vector, 'clip-vit-base-patch32',
    now()
);
```

### Dependencies
- **IMAGE_PROCESSING** (needs extracted images)

### Typical Processing Time
3-10 seconds

### Technologies
- **Ollama**: Local embedding models (clip-vit, etc.)
- **NumPy**: Vector operations and normalization
- **PIL/Pillow**: Image preprocessing for embedding models
- **PostgreSQL pgvector**: Store and index embeddings

### Error Conditions
- **Missing Images**: No images from IMAGE_PROCESSING stage
- **Model Unavailable**: Embedding model not loaded in Ollama
- **GPU Memory**: Insufficient GPU memory for batch processing
- **Embedding Failure**: Model errors or timeouts

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage visual_embedding
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/visual_embedding \
  -H "Authorization: Bearer $TOKEN"
```

---

## LINK_EXTRACTION (Stage 7)

### Purpose
Extract hyperlinks, URLs, and references from document content for navigation and analysis.

### Processor
`backend/processors/link_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **file_path**: Path to the PDF file
- **page_texts**: Text content from TEXT_EXTRACTION stage

### Outputs
- **links**: List of extracted links with metadata
- **link_count**: Number of links found
- **link_types**: Categorization (internal, external, email, etc.)
- **link_validation**: Status of link accessibility checks

### Database Operations
```sql
INSERT INTO krai_content.links (
    id, document_id, page_number, link_text,
    link_url, link_type, is_valid,
    validation_status, created_at
) VALUES (
    uuid, document_id, page_num, text,
    url, type, is_valid,
    status, now()
);
```

### Dependencies
- **TEXT_EXTRACTION** (needs page_texts for context)
- **UPLOAD** (needs file_path for direct PDF link extraction)

### Typical Processing Time
1-3 seconds

### Technologies
- **PyMuPDF**: Extract annotations and links from PDF
- **Regex Patterns**: Find URLs in text content
- **URL Validation**: Check link accessibility
- **Link Classification**: Categorize link types

### Error Conditions
- **No Links Found**: Document contains no hyperlinks
- **Invalid URLs**: Malformed or broken links
- **Network Issues**: Link validation failures
- **Permission Issues**: PDF access restrictions

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage link_extraction
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/link_extraction \
  -H "Authorization: Bearer $TOKEN"
```

---

## CHUNK_PREP (Stage 8)

### Purpose
Split document text into semantic chunks optimized for search indexing and retrieval.

### Processor
`backend/processors/chunk_preprocessor.py`

### Inputs
- **document_id**: UUID from previous stages
- **page_texts**: Text content from TEXT_EXTRACTION stage

### Outputs
- **chunks**: List of text chunks with metadata
- **chunk_count**: Number of chunks generated
- **chunk_strategy**: Method used for chunking
- **chunk_statistics**: Size distribution and overlap information

### Database Operations
```sql
INSERT INTO krai_intelligence.chunks (
    id, document_id, page_number, chunk_index,
    text_chunk, chunk_type, content_hash,
    start_char, end_char, word_count, created_at
) VALUES (
    uuid, document_id, page_num, chunk_idx,
    text_chunk, 'semantic', hash,
    start_pos, end_pos, word_count, now()
);
```

### Dependencies
- **TEXT_EXTRACTION** (needs page_texts)

### Typical Processing Time
2-5 seconds

### Technologies
- **Semantic Chunking**: AI-powered text segmentation
- **Error Code Boundaries**: Respect error code boundaries
- **Overlap Strategy**: Maintain context between chunks
- **Size Optimization**: Target chunk sizes for embedding models

### Error Conditions
- **Empty Text**: No text content to chunk
- **Chunking Failure**: Algorithm errors or edge cases
- **Memory Issues**: Large documents cause memory problems
- **Size Limits**: Chunks too large for embedding models

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage chunk_prep
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/chunk_prep \
  -H "Authorization: Bearer $TOKEN"
```

---

## CLASSIFICATION (Stage 9)

### Purpose
Automatically detect document type, manufacturer, product series, and models using AI and pattern matching.

### Processor
`backend/processors/classification_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **page_texts**: Text content from TEXT_EXTRACTION stage

### Outputs
- **manufacturer**: Detected manufacturer name
- **series**: Product series identification
- **models**: List of model numbers found
- **document_type**: Document type classification
- **confidence_scores**: Confidence levels for each classification

### Database Operations
```sql
UPDATE krai_core.documents SET
    manufacturer = detected_manufacturer,
    product_series = detected_series,
    models = detected_models,
    document_type = detected_type,
    extracted_metadata = jsonb_set(
        extracted_metadata,
        '{classification}',
        classification_data
    )
WHERE id = document_id;

-- Insert new manufacturers if needed
INSERT INTO krai_core.manufacturers (name, created_at)
VALUES (manufacturer, now())
ON CONFLICT (name) DO NOTHING;

-- Insert new series if needed
INSERT INTO krai_core.product_series (name, manufacturer_id, created_at)
VALUES (series, manufacturer_id, now())
ON CONFLICT (name, manufacturer_id) DO NOTHING;
```

### Dependencies
- **TEXT_EXTRACTION** (needs page_texts for analysis)

### Typical Processing Time
3-8 seconds

### Technologies
- **Ollama LLM**: AI-powered classification
- **Regex Patterns**: Manufacturer and model detection
- **Fuzzy Matching**: Handle variations and typos
- **Database Lookup**: Cross-reference with known data

### Error Conditions
- **Unknown Manufacturer**: Cannot identify manufacturer
- **Low Confidence**: Classification confidence below threshold
- **Multiple Manufacturers**: Ambiguous manufacturer detection
- **Pattern Failure**: Regex patterns don't match known formats

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage classification
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/classification \
  -H "Authorization: Bearer $TOKEN"
```

---

## METADATA_EXTRACTION (Stage 10)

### Purpose
Extract error codes, specifications, technical parameters, and other structured metadata from document content.

### Processor
`backend/processors/metadata_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **page_texts**: Text content from TEXT_EXTRACTION stage
- **chunks**: Processed chunks from CHUNK_PREP stage

### Outputs
- **error_codes**: List of extracted error codes with context
- **specifications**: Technical specifications found
- **metadata**: General metadata dictionary
- **extraction_quality**: Quality metrics for extracted data

### Database Operations
```sql
INSERT INTO krai_intelligence.error_codes (
    id, document_id, page_number, error_code,
    error_message, context_text, manufacturer,
    confidence_score, created_at
) VALUES (
    uuid, document_id, page_num, code,
    message, context, manufacturer,
    confidence, now()
);

UPDATE krai_core.documents SET
    extracted_metadata = jsonb_set(
        extracted_metadata,
        '{metadata_extraction}',
        metadata_results
    )
WHERE id = document_id;
```

### Dependencies
- **TEXT_EXTRACTION** (needs page_texts)
- **CHUNK_PREP** (needs chunks for context)

### Typical Processing Time
4-10 seconds

### Technologies
- **17 Manufacturer-Specific Patterns**: Custom regex for each manufacturer
- **Ollama LLM**: Enrich and validate extracted metadata
- **Context Analysis**: Understand surrounding text for accuracy
- **Quality Scoring**: Rate confidence of extracted information

### Error Conditions
- **No Error Codes**: Document contains no error codes
- **Pattern Mismatch**: Manufacturer patterns don't match
- **Context Issues**: Insufficient context for accurate extraction
- **LLM Failure**: AI enrichment unavailable or errors

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage metadata_extraction
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/metadata_extraction \
  -H "Authorization: Bearer $TOKEN"
```

---

## PARTS_EXTRACTION (Stage 11)

### Purpose
Extract spare parts information, part numbers, and compatibility data from parts catalogs and service manuals.

### Processor
`backend/processors/parts_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **page_texts**: Text content from TEXT_EXTRACTION stage
- **manufacturer**: Manufacturer from CLASSIFICATION stage

### Outputs
- **parts**: List of extracted parts with metadata
- **part_count**: Number of parts found
- **compatibility_info**: Part compatibility relationships
- **extraction_quality**: Quality metrics for part data

### Database Operations
```sql
INSERT INTO krai_parts.parts (
    id, document_id, part_number, part_name,
    manufacturer, description, compatibility,
    price_info, availability, created_at
) VALUES (
    uuid, document_id, part_num, name,
    manufacturer, description, compatibility,
    price, availability, now()
);
```

### Dependencies
- **CLASSIFICATION** (needs manufacturer for pattern matching)
- **TEXT_EXTRACTION** (needs page_texts)

### Typical Processing Time
3-8 seconds

### Technologies
- **Part Number Patterns**: Manufacturer-specific part number formats
- **Compatibility Detection**: Identify compatible models
- **Price Extraction**: Extract pricing information when available
- **Normalization**: Standardize part number formats

### Error Conditions
- **No Parts Found**: Document contains no part information
- **Invalid Part Numbers**: Patterns don't match known formats
- **Compatibility Issues**: Cannot determine model compatibility
- **Manufacturer Unknown**: No manufacturer classification available

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage parts_extraction
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/parts_extraction \
  -H "Authorization: Bearer $TOKEN"
```

---

## SERIES_DETECTION (Stage 12)

### Purpose
Detect product series and establish relationships between different models and product families.

### Processor
`backend/processors/series_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **manufacturer**: Manufacturer from CLASSIFICATION stage
- **models**: Model list from CLASSIFICATION stage

### Outputs
- **series**: Detected product series
- **series_id**: Database ID for the series
- **model_relationships**: Relationships between models
- **confidence_scores**: Confidence in series detection

### Database Operations
```sql
INSERT INTO krai_core.product_series (
    id, name, manufacturer_id, description,
    created_at, updated_at
) VALUES (
    uuid, series_name, manufacturer_id, description,
    now(), now()
)
ON CONFLICT (name, manufacturer_id)
DO UPDATE SET updated_at = now();

UPDATE krai_core.documents SET
    product_series_id = series_id
WHERE id = document_id;
```

### Dependencies
- **CLASSIFICATION** (needs manufacturer and models)

### Typical Processing Time
2-5 seconds

### Technologies
- **Series Pattern Matching**: Identify series naming conventions
- **Database Lookup**: Cross-reference with known series
- **Model Grouping**: Group related models into series
- **Relationship Mapping**: Establish model-series relationships

### Error Conditions
- **No Series Detected**: Cannot identify product series
- **Unknown Series**: Series not found in database
- **Multiple Series**: Ambiguous series assignment
- **Database Issues**: Series lookup failures

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage series_detection
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/series_detection \
  -H "Authorization: Bearer $TOKEN"
```

---

## STORAGE (Stage 13)

### Purpose
Upload processed files and assets to object storage (MinIO) for long-term storage and access.

### Processor
`backend/processors/storage_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **file_path**: Original file path from UPLOAD stage
- **images**: Extracted images from IMAGE_PROCESSING stage

### Outputs
- **storage_urls**: Dictionary of MinIO URLs for all stored files
- **storage_stats**: Storage usage statistics
- **backup_info**: Backup and redundancy information
- **access_urls**: Public and private access URLs

### Storage Operations
- **Document Storage**: Original PDF in `documents` bucket
- **Image Storage**: Extracted images in `images` bucket
- **Thumbnail Storage**: Generated thumbnails in `thumbnails` bucket
- **Metadata Storage**: JSON metadata in `metadata` bucket

### Dependencies
- **IMAGE_PROCESSING** (for images to store)
- **UPLOAD** (for original file)

### Typical Processing Time
2-8 seconds (depends on file size)

### Technologies
- **MinIO S3 API**: Object storage interface
- **File Compression**: Optimize storage space
- **CDN Integration**: Optional CDN for faster access
- **Backup Strategies**: Redundancy and backup policies

### Error Conditions
- **Storage Full**: Insufficient storage space
- **Network Issues**: MinIO connectivity problems
- **Permission Errors**: Access denied to storage buckets
- **File Corruption**: Upload corruption or verification failures

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage storage
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/storage \
  -H "Authorization: Bearer $TOKEN"
```

---

## EMBEDDING (Stage 14)

### Purpose
Generate vector embeddings for text chunks to enable semantic search and similarity matching.

### Processor
`backend/processors/embedding_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **chunks**: Text chunks from CHUNK_PREP stage

### Outputs
- **embeddings**: List of vector embeddings
- **embedding_count**: Number of embeddings generated
- **embedding_model**: Model used for generation
- **embedding_metadata**: Model parameters and statistics

### Database Operations
```sql
INSERT INTO krai_intelligence.chunks (
    id, document_id, source_type, source_id,
    embedding, model_name,
    created_at
) VALUES (
    uuid, document_id, 'text', chunk_id,
    embedding_vector, 'nomic-embed-text',
    now()
);
```

### Dependencies
- **CHUNK_PREP** (needs chunks to embed)

### Typical Processing Time
3-8 seconds

### Technologies
- **Ollama**: Local embedding models (nomic-embed-text, etc.)
- **NumPy**: Vector operations and normalization
- **PostgreSQL pgvector**: Store and index embeddings
- **Batch Processing**: Optimize GPU utilization

### Error Conditions
- **Missing Chunks**: No chunks from CHUNK_PREP stage
- **Model Unavailable**: Embedding model not loaded
- **GPU Memory**: Insufficient GPU memory
- **Embedding Failure**: Model errors or timeouts

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage embedding
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/embedding \
  -H "Authorization: Bearer $TOKEN"
```

---

## SEARCH_INDEXING (Stage 15)

### Purpose
Update search indexes and prepare document for full-text and semantic search queries.

### Processor
`backend/processors/search_processor.py`

### Inputs
- **document_id**: UUID from previous stages
- **chunks**: Text chunks from CHUNK_PREP stage
- **embeddings**: Vector embeddings from EMBEDDING stage

### Outputs
- **indexed_count**: Number of chunks indexed
- **search_stats**: Search index statistics
- **index_quality**: Quality metrics for search readiness
- **completion_status**: Overall pipeline completion status

### Database Operations
```sql
-- Update full-text search indexes
UPDATE krai_intelligence.chunks SET
    search_vector = to_tsvector('english', text_chunk)
WHERE document_id = document_id;

-- Update pgvector indexes
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_vector
ON krai_intelligence.chunks
USING ivfflat (embedding vector_cosine_ops);

-- Mark document as fully processed
UPDATE krai_core.documents SET
    processing_status = 'completed',
    completed_at = now(),
    stage_status = jsonb_set(
        stage_status,
        '{search_indexing}',
        '{"status": "completed", "timestamp": "' || now() || '"}'::jsonb
    )
WHERE id = document_id;
```

### Dependencies
- **EMBEDDING** (needs embeddings for vector indexing)
- **CHUNK_PREP** (needs chunks for text indexing)

### Typical Processing Time
1-3 seconds

### Technologies
- **PostgreSQL Full-Text Search**: tsvector indexes
- **pgvector**: Vector similarity search indexes
- **Index Optimization**: Balance search speed vs. storage
- **Statistics Collection**: Search performance metrics

### Error Conditions
- **Index Creation Failure**: Database index errors
- **Missing Dependencies**: Required data from previous stages
- **Database Locks**: Index creation blocked by other operations
- **Storage Issues**: Insufficient space for indexes

### Code Examples

#### CLI Usage
```bash
python scripts/pipeline_processor.py --document-id <uuid> --stage search_indexing
```

#### API Usage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/search_indexing \
  -H "Authorization: Bearer $TOKEN"
```

---

## Common Code Patterns

### Stage Execution via CLI
```bash
# Single stage
python scripts/pipeline_processor.py --document-id <uuid> --stage <stage_name>

# Multiple stages
python scripts/pipeline_processor.py --document-id <uuid> --stages <stage_list>

# Full pipeline
python scripts/pipeline_processor.py --file /path/to/document.pdf

# Smart processing (skip completed)
python scripts/pipeline_processor.py --document-id <uuid> --smart
```

### Stage Execution via API
```bash
# Single stage
POST /documents/{id}/process/stage/{stage_name}

# Multiple stages
POST /documents/{id}/process/stages
{
  "stages": ["stage1", "stage2"],
  "stop_on_error": true
}

# Get status
GET /documents/{id}/stages/status
```

### Stage Execution via Python SDK
```python
from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.core.base_processor import Stage
from backend.config.database_config import get_database_adapter

db_adapter = get_database_adapter()
pipeline = KRMasterPipeline(database_adapter=db_adapter)

# Single stage
result = await pipeline.run_single_stage(
    document_id="uuid",
    stage_name=Stage.TEXT_EXTRACTION.value
)

# Multiple stages
stages = [Stage.TEXT_EXTRACTION.value, Stage.IMAGE_PROCESSING.value]
result = await pipeline.run_stages(document_id="uuid", stages=stages)

# Get status
status = await pipeline.get_stage_status(document_id="uuid")
```

### Error Handling Pattern
```python
try:
    result = await processor.process(document_id, **kwargs)
    await update_stage_status(document_id, stage_name, 'completed')
    return result
except Exception as e:
    await update_stage_status(document_id, stage_name, 'failed', str(e))
    logger.error(f"Stage {stage_name} failed for document {document_id}: {e}")
    raise
```

## Related Documentation

- **Pipeline Architecture**: `docs/processor/PIPELINE_ARCHITECTURE.md`
- **Quick Start**: `docs/processor/QUICK_START.md`
- **API Documentation**: `docs/api/STAGE_BASED_PROCESSING.md`
- **Implementation**: `backend/processors/` directory
- **CLI Tools**: `scripts/pipeline_processor.py`
