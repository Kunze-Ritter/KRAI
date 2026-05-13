# Phase 5: Context-Aware Media Processing

## Overview

Phase 5 introduces context-aware media processing to the KR-AI-Engine, enabling intelligent extraction of contextual information from images, videos, and links within technical documents. This enhancement significantly improves search relevance and user experience by providing rich metadata around media content.

## Features

### 🎯 Core Capabilities

- **Image Context Extraction**: Extract captions, figure references, and surrounding text
- **Video Context Extraction**: Analyze video descriptions and related content
- **Link Context Extraction**: Understand the context and relevance of external links
- **Error Code Detection**: Automatically identify and extract error codes from media context
- **Product Recognition**: Detect product models and series mentioned in media context
- **Context Embeddings**: Generate semantic embeddings for improved search

### 🔄 Pipeline Integration

Context extraction is integrated into the existing processing pipeline:

```text
Stage 3: Text Processing → Stage 4: Image Processing → Stage 5: Link Extraction
                                      ↓                           ↓
                              Context Extraction ← Context Extraction
                                      ↓                           ↓
                              Storage Processing → Stage 7: Embedding Generation
                                                             ↓
                                                    Context Embedding Generation
```

## Architecture

### ContextExtractionService

The centralized service responsible for extracting context from various media types:

```python
from backend.services.context_extraction_service import ContextExtractionService

service = ContextExtractionService()

# Extract image context
image_context = service.extract_image_context(
    page_text="Page text content",
    page_number=1,
    image_metadata={"width": 800, "height": 600}
)

# Extract video context
video_context = service.extract_video_context(
    page_text="Video description page",
    page_number=2,
    video_url="https://youtube.com/watch?v=example"
)

# Extract link context
link_context = service.extract_link_context(
    page_text="Documentation with links",
    page_number=3,
    link_url="https://example.com/manual"
)
```

### Data Models

Enhanced data models support context extraction:

```python
class ImageModel(BaseModel):
    # ... existing fields ...

    # Phase 5: Context extraction fields
    context_caption: Optional[str] = None
    page_header: Optional[str] = None
    figure_reference: Optional[str] = None
    related_error_codes: List[str] = Field(default_factory=list)
    related_products: List[str] = Field(default_factory=list)
    surrounding_paragraphs: List[str] = Field(default_factory=list)
    context_embedding: Optional[List[float]] = None
```

## Configuration

### Environment Variables

Configure context extraction using environment variables:

```bash
# Main configuration
ENABLE_CONTEXT_EXTRACTION=true
CONTEXT_EXTRACTION_MODE=enhanced  # disabled/basic/enhanced/comprehensive

# Media-specific settings
ENABLE_IMAGE_CONTEXT=true
ENABLE_VIDEO_CONTEXT=true
ENABLE_LINK_CONTEXT=true

# Context embeddings
ENABLE_CONTEXT_EMBEDDINGS=true
CONTEXT_EMBEDDING_DIMENSION=768
CONTEXT_EMBEDDING_MODEL=nomic-embed-text:latest

# Quality control
MIN_CONTEXT_QUALITY_SCORE=0.3
ENABLE_CONTEXT_VALIDATION=true
FILTER_DUPLICATE_CONTEXTS=true
```

### Configuration File

Use the dedicated configuration module:

```python
from backend.config.context_extraction_config import get_context_config

config = get_context_config()
print(f"Context extraction enabled: {config.enable_context_extraction}")
print(f"Extraction mode: {config.extraction_mode}")
```

## Implementation Details

### TextProcessor Integration

The TextProcessor attaches `page_texts` to ProcessingContext for downstream processors:

```python
# In text_processor_optimized.py
context.page_texts = page_texts  # Dict[int, str]
context.page_texts_attached = True
```

### ImageProcessor Integration

Context extraction happens after image enrichment:

```python
# In image_processor.py
if self.enable_context_extraction and context.page_texts:
    images = self._extract_image_contexts(images, context.page_texts, adapter)
```

### LinkExtractionProcessorAI Integration

Links and videos get context extracted after enrichment:

```python
# In link_extraction_processor_ai.py
if self.enable_context_extraction and context.page_texts:
    links = self._extract_link_contexts(links, context.page_texts, adapter)
    videos = self._extract_video_contexts(videos, context.page_texts, adapter)
```

### EmbeddingProcessor Integration

Context embeddings are generated after main embeddings:

```python
# In embedding_processor.py
if self.enable_context_embeddings and self.enable_chunk_embeddings:
    context_embeddings_created = self._generate_context_embeddings(
        document_id=document_id,
        adapter=adapter
    )
```

## Database Schema

### Context Fields

New fields added to media tables:

#### Images Table (`krai_content.images`)

- `context_caption` - Extracted caption/description
- `page_header` - Page header text
- `figure_reference` - Figure reference like "Fig. 1.2"
- `related_error_codes` - Array of error codes in context
- `related_products` - Array of product models in context
- `surrounding_paragraphs` - Text paragraphs around image
- `context_embedding` - Vector embedding of context

#### Videos Table (`krai_content.instructional_videos`)

- `context_description` - Video context description
- `page_header` - Page header text
- `related_error_codes` - Array of error codes
- `related_products` - Array of product models
- `page_number` - Page where video was found

#### Links Table (`krai_content.links`)

- `context_description` - Link context description
- `page_header` - Page header text
- `related_products` - Array of product models

### Database Adapter Methods

New methods for updating context fields:

```python
# PostgreSQL adapter
await adapter.update_image_context(image_id, context_data)
await adapter.update_video_context(video_id, context_data)
await adapter.update_link_context(link_id, context_data)
await adapter.update_media_contexts_batch(updates)

# Supabase adapter (backward compatibility)
await adapter.update_image_context(image_id, context_data)
await adapter.update_video_context(video_id, context_data)
await adapter.update_link_context(link_id, context_data)
```

## Storage Processing

### Enhanced Storage Payloads

StorageProcessor now includes context fields in database payloads:

```python
# Image storage payload
image_record = {
    # ... existing fields ...
    "context_caption": payload.get("context_caption"),
    "page_header": payload.get("page_header"),
    "figure_reference": payload.get("figure_reference"),
    "related_error_codes": payload.get("related_error_codes", []),
    "related_products": payload.get("related_products", []),
    "surrounding_paragraphs": payload.get("surrounding_paragraphs", []),
}
```

## Context Embedding Generation

### Embedding Strategy

Context embeddings combine multiple context elements:

```python
def _generate_context_embeddings(self, document_id: UUID, adapter) -> int:
    # Process images with context
    for image in images_with_context:
        context_parts = [
            image.get('context_caption'),
            image.get('page_header'),
            image.get('figure_reference'),
            # ... related entities
        ]
        context_text = ' | '.join(filter(None, context_parts))
        embedding = self._generate_embedding(context_text)
```

### Embedding Storage

Context embeddings are stored in the `embedding` column of the `krai_intelligence.chunks` table with `source_type='context'`:

```python
embedding_data = {
    'source_id': media_id,
    'source_type': 'context',
    'embedding': embedding_vector,
    'embedding_context': context_text,
    'metadata': {
        'media_type': 'image|video|link',
        'media_id': media_id,
        'document_id': str(document_id)
    }
}
```

## Usage Examples

### Search with Context

Enhanced search capabilities using context embeddings:

```python
# Search for images related to error codes
results = await embedding_processor.similarity_search(
    query_text="error 900.01 paper jam",
    similarity_threshold=0.7,
    limit=10
)

# Results include context information
for result in results:
    print(f"Media: {result['media_type']}")
    print(f"Context: {result['context_description']}")
    print(f"Error codes: {result['related_error_codes']}")
```

### API Integration

Context data available through API endpoints:

```python
# Get image with context
GET /api/images/{image_id}
Response:
{
    "id": "image_id",
    "storage_url": "https://storage.url/image.jpg",
    "context_caption": "Figure showing paper jam removal",
    "page_header": "Troubleshooting Section",
    "related_error_codes": ["900.01", "900.02"],
    "related_products": ["HP LaserJet Pro M404n"],
    "surrounding_paragraphs": ["If paper jam occurs...", "Remove jammed paper..."]
}
```

## Performance Considerations

### Processing Impact

- **Context Extraction**: ~50-100ms per media item
- **Embedding Generation**: ~200-500ms per context
- **Storage Overhead**: ~1KB per media item for context fields
- **Index Overhead**: ~768 bytes per context embedding

### Optimization Strategies

1. **Batch Processing**: Process multiple media items together
2. **Caching**: Cache extracted context for repeated processing
3. **Selective Extraction**: Enable/disable specific context types
4. **Quality Filtering**: Filter low-quality context extractions

## Monitoring and Metrics

### Stage Tracking

Context extraction metrics included in stage tracking:

```python
metadata = {
    'embeddings_created': total_embedded,
    'context_embeddings_created': context_embeddings_created,
    'processing_time': processing_time,
    # ... other metrics
}
```

### Quality Metrics

Track context extraction quality:

```python
# Context extraction success rate
context_success_rate = successful_extractions / total_media_items

# Average context quality score
avg_quality_score = sum(quality_scores) / len(quality_scores)

# Embedding generation success rate
embedding_success_rate = successful_embeddings / total_contexts
```

## Troubleshooting

### Common Issues

1. **Missing Context**: Check if `page_texts` are available in ProcessingContext
2. **Low Quality Context**: Adjust confidence thresholds in configuration
3. **Embedding Failures**: Verify Ollama service is running and accessible
4. **Storage Errors**: Check database schema includes new context fields

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
ENABLE_DETAILED_CONTEXT_LOGGING=true
LOG_CONTEXT_EXTRACTION_SAMPLES=true
```

### Validation Commands

```python
# Check context extraction configuration
from backend.config.context_extraction_config import get_context_config
config = get_context_config()
print(f"Context extraction enabled: {config.enable_context_extraction}")

# Validate database schema
from backend.services.postgresql_adapter import PostgreSQLAdapter
adapter = PostgreSQLAdapter()
media_without_context = await adapter.get_media_without_context('image', limit=10)
print(f"Images without context: {len(media_without_context)}")
```

## Migration Guide

### Existing Documents

For existing documents without context:

1. **Backfill Script**: Use the provided backfill script
2. **Reprocessing**: Reprocess documents through the pipeline
3. **Selective Update**: Update specific media items as needed

### Backfill Script

```bash
# Run context backfill for existing documents
python scripts/backfill_media_context.py --media-type image --limit 1000
python scripts/backfill_media_context.py --media-type video --limit 500
python scripts/backfill_media_context.py --media-type link --limit 2000
```

## Future Enhancements

### Planned Features

1. **Multi-language Context**: Support for context extraction in multiple languages
2. **Advanced NLP**: Use transformer models for better context understanding
3. **Cross-document Context**: Link context across related documents
4. **User Feedback**: Allow users to improve context extraction quality
5. **Context Analytics**: Analytics on context extraction usage and effectiveness

### Extension Points

The architecture supports easy extension:

```python
# Custom context extractors
class CustomContextExtractor(BaseContextExtractor):
    def extract_context(self, page_text, media_metadata):
        # Custom extraction logic
        pass

# Register custom extractor
context_service.register_extractor('custom_media', CustomContextExtractor())
```

## Testing

### Unit Tests

```bash
# Run context extraction tests
python -m pytest tests/test_context_extraction.py -v

# Test specific components
python -m pytest tests/test_context_extraction_service.py -v
python -m pytest tests/test_context_embedding_generation.py -v
```

### Integration Tests

```bash
# Test full pipeline integration
python -m pytest tests/integration/test_context_aware_pipeline.py -v

# Test with sample documents
python scripts/test_context_extraction_sample.py --document-id sample_id
```

## Conclusion

Phase 5 context-aware media processing significantly enhances the KR-AI-Engine's ability to understand and process technical documents. By extracting rich contextual information from media content, we enable more intelligent search, better user experience, and improved document understanding.

The modular architecture ensures easy maintenance and extension, while the comprehensive configuration system allows fine-tuning for different use cases and performance requirements.
