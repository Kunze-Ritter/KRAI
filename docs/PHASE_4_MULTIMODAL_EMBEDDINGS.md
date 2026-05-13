# Phase 4: Multi-Modal Embedding Generation - Implementation Complete

## Overview

Phase 4 transforms the KRAI Engine from a text-only embedding system into a comprehensive multi-modal architecture that generates and stores embeddings for text, images, and tables. This enables semantic search across all content types with proper context preservation.

## Architecture

### Unified Multi-Vector Embedding Pipeline

The new architecture introduces:
- **Visual Embeddings**: ColQwen2.5-v0.2 for image understanding
- **Table Extraction**: PyMuPDF for structured table detection
- **Unified Storage**: `krai_intelligence.chunks.embedding` vector column for all content types
- **Backward Compatibility**: Maintains `vw_chunks` table for existing systems

### Database Schema Changes

#### New Tables

1. **`krai_intelligence.chunks` with `embedding` column** - Unified embedding storage
   - `source_id`: References chunk_id, image_id, or table_id
   - `source_type`: 'text', 'image', or 'table'
   - `embedding`: pgvector (768-dim)
   - `model_name`: Model used for embedding
   - `embedding_context`: Context text (500 chars)
   - `metadata`: JSONB with additional info

2. **`krai_intelligence.structured_tables`** - Extracted table data
   - `table_data`: JSONB (raw table data)
   - `table_markdown`: Markdown representation
   - `caption`: Extracted table caption
   - `context_text`: Surrounding text context
   - `table_type`: Detected table type
   - `table_embedding`: Vector embedding (optional)

#### Enhanced Existing Tables

- **`krai_content.images`** - Now supports visual embeddings
- **`krai_intelligence.chunks`** - Legacy storage maintained

## Implementation Details

### 1. Dependencies Added

```python
# backend/requirements.txt
transformers>=4.45.0  # Required for ColQwen2.5
torch>=2.2.0
torchvision>=0.17.0
numpy>=1.24.0
scikit-learn>=1.3.0
colpali-engine>=0.3.7  # ColQwen2.5 for visual document retrieval
pdf2image>=1.17.0  # PDF to PIL Image conversion
```

### 2. AI Configuration Extended

```python
# backend/config/ai_config.py
@dataclass
class ModelConfig:
    # ... existing fields ...
    visual_embeddings: str  # Visual embeddings for images (ColQwen2.5)
    table_embeddings: str   # Table embeddings for structured data
    visual_embedding_dimension: int = 768

# Hardware detection for ColQwen2.5
def _check_colqwen_requirements(self) -> bool:
    # Checks torch >= 2.2.0, transformers >= 4.45.0, GPU VRAM >= 4GB

# Model configurations updated
configs = {
    ModelTier.CONSERVATIVE: ModelConfig(
        # ... existing config ...
        visual_embeddings='vidore/colqwen2.5-v0.2',
        table_embeddings=embedding_model,
        estimated_gpu_usage_gb=6.0  # +2GB for visual embeddings
    ),
    # ... other tiers ...
}
```

### 3. New Processors Created

#### VisualEmbeddingProcessor

- **File**: `backend/processors/visual_embedding_processor.py`
- **Purpose**: Generate visual embeddings using ColQwen2.5
- **Features**:
  - Multi-vector embeddings (768 patches per image)
  - Mean pooling to 768-dim for storage
  - GPU acceleration with CPU fallback
  - Batch processing for performance
  - Integration with the `krai_intelligence.chunks.embedding` column

#### TableProcessor

- **File**: `backend/processors/table_processor.py`
- **Purpose**: Extract tables from PDFs using PyMuPDF
- **Features**:
  - PyMuPDF table detection (lines, text strategies)
  - Markdown export for embeddings
  - JSONB storage for structured queries
  - Context extraction around tables
  - Table type detection (specification, comparison, parts list, etc.)

### 4. Enhanced EmbeddingProcessor

```python
# backend/processors/embedding_processor.py
class EmbeddingProcessor(BaseProcessor):
    def __init__(self, ..., enable_chunk_embeddings: bool = None):
        # ... existing init ...
        self.enable_chunk_embeddings = (
            enable_chunk_embeddings if enable_chunk_embeddings is not None
            else os.getenv('ENABLE_EMBEDDINGS_V2', 'false').lower() == 'true'
        )

    async def process(self, context) -> Dict[str, Any]:
        # ... existing text processing ...

        # NEW: Handle image and table embeddings
        if self.enable_chunk_embeddings:
            if hasattr(context, 'image_embeddings') and context.image_embeddings:
                image_result = await self.store_embeddings_batch(context.image_embeddings)

            if hasattr(context, 'table_embeddings') and context.table_embeddings:
                table_result = await self.store_embeddings_batch(context.table_embeddings)

    def _store_embedding_v2(self, source_id, source_type, embedding, ...):
        # Store in the chunks.embedding column for unified search
```

### 5. Database Adapters Enhanced

#### PostgreSQLAdapter

```python
# backend/services/postgresql_adapter.py
async def create_embedding_v2(
    self, source_id: str, source_type: str,
    embedding: List[float], model_name: str, ...
) -> str:
    """Create embedding in krai_intelligence.chunks.embedding column"""

async def create_chunk_embedding_batch(
    self, embeddings: List[Dict[str, Any]]
) -> List[str]:
    """Batch create embeddings in krai_intelligence.chunks.embedding column"""

async def create_structured_table(
    self, table_data: Dict[str, Any]
) -> str:
    """Create structured table in krai_intelligence.structured_tables"""
```

#### SupabaseAdapter
```python
# backend/services/supabase_adapter.py
async def create_embedding_v2(self, ...):
    """Create embedding via Supabase REST API"""

async def create_chunk_embedding_batch(self, ...):
    """Batch create embeddings via Supabase"""

async def create_structured_table(self, ...):
    """Create structured table via Supabase"""
```

### 6. Pipeline Integration

#### Stage Enum Updates

```python
# backend/core/base_processor.py
class Stage(Enum):
    # ... existing stages ...
    TABLE_EXTRACTION = "table_extraction"  # Stage 2b
    VISUAL_EMBEDDING = "visual_embedding"  # Stage 3b
    EMBEDDING = "embedding"  # Updated to support both legacy and v2
```

#### Master Pipeline Updates
```python
# backend/pipeline/master_pipeline.py
self.processors = {
    # ... existing processors ...
    'table': TableProcessor(self.database_service, self.ai_service),
    'visual_embedding': VisualEmbeddingProcessor(self.database_service),
    # ... rest of processors ...
}

# Processing flow
async def process_single_document(...):
    # Stage 2: Text Processing
    result2 = await self.processors['text'].process(context)

    # Stage 2b: Table Extraction (NEW)
    result2b = await self.processors['table'].process(context)

    # Stage 3: Image Processing
    result3 = await self.processors['image'].process(context)

    # Stage 3b: Visual Embeddings (NEW)
    result3b = await self.processors['visual_embedding'].process(context)

    # ... continue with rest of pipeline ...
```

### 7. Environment Variables

#### .env.example

```bash
# ===========================================
# MULTI-MODAL EMBEDDING CONFIGURATION
# ===========================================
# Visual embeddings (ColQwen2.5)
AI_VISUAL_EMBEDDING_MODEL=vidore/colqwen2.5-v0.2
AI_VISUAL_EMBEDDING_DIMENSION=768
ENABLE_VISUAL_EMBEDDINGS=true

# Table extraction settings
ENABLE_TABLE_EXTRACTION=true
TABLE_EXTRACTION_STRATEGY=lines

# Unified chunk embedding column storage (krai_intelligence.chunks.embedding)
ENABLE_EMBEDDINGS_V2=false
```

#### env_loader.py Updates
```python
# backend/processors/env_loader.py
'ai': {
    # ... existing config ...
    'visual_embedding_model': os.getenv('AI_VISUAL_EMBEDDING_MODEL', 'Not set'),
    'visual_embeddings_enabled': os.getenv('ENABLE_VISUAL_EMBEDDINGS', 'false'),
    'table_extraction_enabled': os.getenv('ENABLE_TABLE_EXTRACTION', 'false'),
    'chunk_embeddings_enabled': os.getenv('ENABLE_EMBEDDINGS_V2', 'false'),
},
```

## Migration Strategy

### Phase 1: Setup (Complete)

- Dependencies installed
- Database schema created
- Processors implemented
- Configuration updated

### Phase 2: Testing (Next)

- Enable `ENABLE_EMBEDDINGS_V2=true` in test environment
- Process sample documents
- Verify embeddings in both tables
- Test search across content types

### Phase 3: Production Rollout

- Gradual enablement of writes to the chunks.embedding column
- Monitor performance impact
- Update search APIs to use the chunks.embedding column
- Eventually deprecate vw_chunks for new embeddings

## Performance Considerations

### Hardware Requirements

- **GPU**: 4GB+ VRAM for ColQwen2.5
- **RAM**: 16GB+ recommended for multi-modal processing
- **Storage**: Additional space for the chunks.embedding vector column

### Optimization Features

- **Batch Processing**: Both visual and table processors support batching
- **Lazy Loading**: Models loaded only when needed
- **Fallback Options**: CPU-only mode when GPU unavailable
- **Adaptive Batching**: Dynamic batch size based on performance

## Usage Examples

### Enable Multi-Modal Embeddings

```python
# In your configuration
ENABLE_EMBEDDINGS_V2=true
ENABLE_VISUAL_EMBEDDINGS=true
ENABLE_TABLE_EXTRACTION=true
```

### Search Across Content Types

```python
# Query krai_intelligence.chunks table (embedding column) for unified search
query = """
SELECT e.*, d.filename
FROM krai_intelligence.chunks e
JOIN krai_core.documents d ON e.metadata->>'document_id' = d.id
WHERE e.source_type = ANY($1)
ORDER BY e.embedding <=> $2::vector
LIMIT 10
"""
results = await conn.fetch(query, ['text', 'image', 'table'], query_embedding)
```

### Access Structured Table Data

```python
# Query structured tables
tables = await conn.fetch("""
SELECT * FROM krai_intelligence.structured_tables
WHERE document_id = $1
ORDER BY page_number, table_index
""", document_id)
```

## Troubleshooting

### Common Issues

1. **ColQwen2.5 Fails to Load**
   - Check torch >= 2.2.0 and transformers >= 4.45.0
   - Verify GPU VRAM >= 4GB if using GPU
   - Set `ENABLE_VISUAL_EMBEDDINGS=false` to disable

2. **Table Extraction Not Working**
   - Ensure PyMuPDF is installed
   - Check PDF is not image-only
   - Try different `TABLE_EXTRACTION_STRATEGY` options

3. **Chunk Embeddings Not Populated**
   - Verify `ENABLE_EMBEDDINGS_V2=true`
   - Check database permissions
   - Review processor logs for errors

### Debug Commands

```python
# Check processor configuration
status = embedding_processor.get_configuration_status()
print(f"Chunk embeddings enabled: {status['chunk_embeddings_enabled']}")

# Verify database tables
tables = await conn.fetch("""
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'krai_intelligence'
AND table_name IN ('chunks', 'structured_tables')
""")
```

## Future Enhancements

### Planned Features

1. **Column-Specific Table Embeddings**: Embed individual columns for precise queries
2. **Visual Question Answering**: Integrate VQA models for image queries
3. **Cross-Modal Retrieval**: Query text to find relevant images/tables
4. **Embedding Compression**: Reduce storage requirements for large deployments

### API Extensions

- `/api/search/multimodal` - Unified search endpoint
- `/api/tables/query` - Natural language table queries
- `/api/images/similar` - Visual similarity search

## Conclusion

Phase 4 successfully transforms the KRAI Engine into a true multi-modal system capable of understanding and searching across text, images, and tables. The implementation maintains backward compatibility while providing a foundation for advanced AI features.

The modular design allows for gradual adoption and future enhancements, making the system ready for the next generation of document intelligence capabilities.
