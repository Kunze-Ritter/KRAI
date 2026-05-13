# KRAI Pipeline - Modular Document Processing System

## Overview

The KRAI Pipeline is a modular document processing system that orchestrates all stages from upload to semantic search enablement. The system has been refactored to provide individual stage execution, comprehensive stage tracking, and a powerful CLI interface.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                  KRAI MODULAR PIPELINE                     │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Upload   │→ │ Text     │→ │ Tables   │→ │ SVG      │  │
│  │Processor │  │Extractor │  │Extractor │  │Processor │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Images   │→ │ Visual   │→ │ Links    │→ │ Chunks   │  │
│  │Processor │  │Embeddings│  │Extractor │  │Processor │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Classify  │→ │Metadata  │→ │ Parts    │→ │ Storage  │  │
│  │Processor │  │Processor │  │Extractor │  │Processor │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐                              │
│  │ Embed    │→ │ Search   │  Full Pipeline Complete!      │
│  │Processor │  │Processor │                              │
│  └──────────┘  └──────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Stage Tracking System

- **File**: `backend/processors/stage_tracker.py`
- **Database**: PostgreSQL with async RPC calls
- **Features**: Real-time progress tracking, stage status management, error handling

### 2. Master Pipeline

- **File**: `backend/pipeline/master_pipeline.py`
- **Features**: Individual stage execution, batch processing, hardware monitoring

### 3. CLI Interface

- **File**: `scripts/pipeline_processor.py`
- **Features**: Run individual stages, smart processing, status monitoring

## Processing Stages

### Stage 1: Upload & Validation

- File validation (format, size)
- Duplicate detection (hash-based)
- Database record creation
- **Input:** PDF file path
- **Output:** Document ID

### Stage 2: Text Extraction

- Extract text from all pages
- PyMuPDF + pdfplumber engines
- Preserve page structure
- **Output:** Page texts dictionary

### Stage 3: Image Processing

- Extract images from PDF
- Filter relevant images (skip logos, headers)
- OCR text extraction (Tesseract)
- Vision AI analysis (LLaVA)
- Image classification (diagram, chart, table)
- **Output:** Filtered images with metadata

### Stage 4: Product Extraction

- Pattern-based extraction
- Model/serial number detection
- Specification parsing
- **Output:** Product entities

### Stage 5: Error Code Extraction

- Error code pattern matching
- Description extraction
- Solution/cause detection
- **Output:** Error code entities

### Stage 6: Version Extraction
- Version pattern matching (8 patterns)
- Document revision detection
- **Output:** Version entities

### Stage 7: Chunking
- Smart text chunking (1000 chars default)
- Overlap for context preservation
- Chunk type classification
- Deduplication
- **Output:** Text chunks

### Stage 8: Image Storage (Optional)
- Upload images to object storage (MinIO)
- Generate presigned URLs
- File organization by document
- **Output:** Object storage URLs

### Stage 9: Embedding Generation (Optional)
- Generate 768-dim vectors (embeddinggemma)
- Batch processing (100 chunks/batch)
- Store in Supabase with pgvector
- Enable semantic search
- **Output:** Vector embeddings

## Usage

### Basic Usage

```python
from pathlib import Path
from master_pipeline import MasterPipeline
from supabase import create_client

# Initialize Supabase
supabase = create_client(
    supabase_url="YOUR_URL",
    supabase_key="YOUR_KEY"
)

# Create pipeline
pipeline = MasterPipeline(
    supabase_client=supabase,
    manufacturer="HP",
    enable_images=True,
    enable_ocr=True,
    enable_vision=True,
    # storage upload disabled
    enable_embeddings=True
)

# Process document
result = pipeline.process_document(
    file_path=Path("service_manual.pdf"),
    document_type="service_manual"
)

if result['success']:
    print(f"Document processed: {result['document_id']}")
    print(f"Processing time: {result['processing_time']:.1f}s")
else:
    print(f"Error: {result['error']}")
```

### Batch Processing

```python
# Process multiple documents
file_paths = [
    Path("manual1.pdf"),
    Path("manual2.pdf"),
    Path("manual3.pdf")
]

result = pipeline.process_batch(
    file_paths=file_paths,
    document_type="service_manual",
    manufacturer="HP"
)

print(f"Processed: {result['successful']}/{result['total']}")
print(f"Total time: {result['processing_time']:.1f}s")
```

### Configuration Options

```python
pipeline = MasterPipeline(
    supabase_client=supabase,

    # Manufacturer detection
    manufacturer="AUTO",  # or "HP", "Canon", "Xerox", etc.

    # Image processing
    enable_images=True,   # Extract images
    enable_ocr=True,      # OCR on images
    enable_vision=True,   # Vision AI analysis

    # Optional stages
    # storage upload disabled
    enable_embeddings=True,   # Generate embeddings

    # Error handling
    max_retries=2  # Retry failed stages
)
```

## Features

### Error Handling & Retry
- Automatic retry on stage failure (max 2 retries by default)
- Optional stages don't stop pipeline on failure
- Detailed error logging

### Progress Tracking
- Per-stage status tracking in database
- Real-time progress updates
- Performance metrics

### Performance

**Average Processing Times** (4000-page manual):
- Text Extraction: ~30s
- Image Extraction: ~15s (50 images)
- Product Extraction: ~5s
- Error Code Extraction: ~3s
- Chunking: ~2s
- Embeddings: ~60s (600 chunks @ 10 emb/s)

**Total: ~2 minutes for full pipeline**

### Scalability

- Sequential processing (default)
- Batch processing support
- Configurable batch sizes
- Database connection pooling

## Requirements

### System Requirements
- Python 3.10+
- 4GB RAM minimum
- 8GB RAM recommended for large documents

### External Services
- **PostgreSQL**: Database + pgvector
- **Ollama**: embeddinggemma model (optional)
- **MinIO Object Storage**: Image storage (optional)

### Python Dependencies
```
supabase>=2.0.0
PyMuPDF>=1.23.0
pdfplumber>=0.10.0
Pillow>=10.0.0
pytesseract>=0.3.10
numpy>=1.24.0
boto3>=1.28.0
```

## Database Schema

### Required Tables
- `documents`: Main document records
- `chunks`: Text chunks with embeddings
- `products`: Extracted products
- `error_codes`: Extracted error codes
- `versions`: Document versions
- `stage_status`: Per-stage tracking

### Required Extensions
- `pgvector`: Vector similarity search
- `uuid-ossp`: UUID generation

## Configuration

### Environment Variables

```bash
# PostgreSQL
DATABASE_CONNECTION_URL=postgresql://krai_user:password@krai-postgres:5432/krai_db
DATABASE_PASSWORD=your_database_password

# Ollama (for embeddings)
OLLAMA_URL=http://localhost:11434

# MinIO (optional)
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=your-secret-key
OBJECT_STORAGE_BUCKET_DOCUMENTS=your-bucket
```

### Ollama Setup

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama
ollama serve

# Pull embedding model
ollama pull embeddinggemma

# Verify
ollama list
```

## Testing

### Run Tests

```bash
# Test individual processors
python test_upload_processor.py
python test_image_processor.py
python test_embedding_processor.py

# Test master pipeline
python test_master_pipeline.py
```

### Expected Output
```
Results: 5/5 passed
  ✅ configuration
  ✅ processors
  ✅ stage_logic
  ✅ end_to_end
  ✅ batch

🎉 ALL TESTS PASSED!
```

## Monitoring

### Stage Status Tracking

Query current processing status:

```python
# Get stage status for document
result = supabase.table('stage_status').select('*').eq(
    'document_id', document_id
).execute()

for stage in result.data:
    print(f"{stage['stage_name']}: {stage['status']}")
```

### Performance Metrics

All stages record:
- Start time
- End time
- Processing duration
- Success/failure status
- Error messages (if failed)
- Custom metadata

## Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Install all dependencies
pip install -r requirements.txt
```

**2. Ollama Not Available**
```bash
# Start Ollama service
ollama serve

# Verify model is installed
ollama list
```

**3. Database Connection Failed**
- Check Supabase credentials in `.env`
- Verify network connectivity
- Check service role key permissions

**4. Out of Memory**
- Reduce batch size in embeddings
- Process smaller documents first
- Increase system RAM

### Debug Mode

Enable detailed logging:

```python
pipeline = MasterPipeline(
    supabase_client=supabase,
    manufacturer="AUTO"
)

# All logs will show in console
```

## Best Practices

### 1. Start Simple
Begin with minimal configuration:
```python
pipeline = MasterPipeline(
    supabase_client=supabase,
    # storage upload disabled
    enable_embeddings=False
)
```

### 2. Test with Small Documents
Test pipeline with 10-20 page documents before processing large manuals.

### 3. Monitor Performance
Track processing times and optimize bottlenecks:
- Large images slow down extraction
- Many chunks increase embedding time
- Complex PDFs take longer to parse

### 4. Handle Failures Gracefully
Use try-catch and check result status:
```python
result = pipeline.process_document(file_path)
if not result['success']:
    logger.error(f"Failed: {result['error']}")
    # Handle failure
```

### 5. Batch Processing
Process multiple documents in batches for efficiency:
```python
# Good: Process in batches
result = pipeline.process_batch(file_paths)

# Less efficient: Process individually in loop
for path in file_paths:
    result = pipeline.process_document(path)
```

## CLI Usage

The new CLI interface provides powerful command-line access to the pipeline system.

### Installation

```bash
# From project root
cd scripts
python pipeline_processor.py --help
```

### Common Commands

#### List Available Stages

```bash
python pipeline_processor.py --list-stages
```

#### Run Single Stage

```bash
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stage 5
# or by name
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stage image_processing
```

#### Run Multiple Stages

```bash
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stages 1,2,3
# or by names
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stages upload,text_extraction,image_processing
```

#### Run All Stages
```bash
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --all
```

#### Smart Processing (Recommended)
Automatically determines which stages need to run based on current status:
```bash
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --smart
```

#### Check Document Status
```bash
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --status
```

### Advanced Features

#### Verbose Output
```bash
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stage 5 --verbose
```

#### File Path for Upload Stage
```bash
python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stage upload --file-path /path/to/document.pdf
```

## Migration from Old System

### Deprecated Components
- `document_processor.py` - Marked as deprecated, use modular system instead
- Old synchronous stage tracking - Replaced with async PostgreSQL adapter

### Migration Steps
1. Use `scripts/pipeline_processor.py` for CLI operations
2. Use `backend/pipeline/master_pipeline.py` for programmatic access
3. Update existing code to use async stage tracking methods

### Example Migration

```python
# Old way (deprecated)
from backend.processors.document_processor import DocumentProcessor
processor = DocumentProcessor()
result = processor.process_document(file_path)

# New way (recommended)
from backend.pipeline.master_pipeline import KRMasterPipeline
pipeline = KRMasterPipeline()
await pipeline.initialize_services()
result = await pipeline.run_stages(document_id, [Stage.UPLOAD, Stage.TEXT_EXTRACTION])
```

## Performance Optimization

### 1. Embedding Generation
- Use batch processing (default: 100 chunks)
- Consider GPU acceleration for Ollama
- Use faster models for prototyping

### 2. Image Processing
- Adjust `min_image_size` to filter more aggressively
- Set `max_images_per_doc` to limit extraction
- Disable Vision AI if not needed

### 3. Database Operations
- Use connection pooling
- Batch inserts where possible
- Index frequently queried fields

## Roadmap

### Future Enhancements
- [ ] Parallel document processing
- [ ] GPU-accelerated embeddings
- [ ] Advanced error recovery
- [ ] Progress webhooks
- [ ] Real-time status updates
- [ ] Distributed processing
- [ ] Custom stage plugins

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify all requirements are met
3. Test individual processors
4. Review configuration settings

## License

Internal use only - Kunze-Ritter AI Project
