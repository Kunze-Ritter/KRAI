# Phase 6 Advanced Features

## Overview

Phase 6 introduces advanced multimodal AI capabilities that transform the KRAI system from a simple document processor into a sophisticated knowledge extraction and retrieval platform. These features enable comprehensive analysis of technical documents including service manuals, engineering diagrams, and multimedia content.

## Key Features

### 1. Hierarchical Document Structure Detection

**Purpose**: Automatically detect and preserve document hierarchy for better context understanding and navigation.

**Implementation**:
- Enhanced `SmartChunker` with structure detection algorithms
- Recognition of chapters, sections, subsections, and error code boundaries
- Automatic linking of related chunks with `previous_chunk_id` and `next_chunk_id`
- Metadata enrichment including section levels and hierarchical paths

**Key Components**:
- `backend/processors/chunker.py` - Enhanced with hierarchical chunking
- `krai_intelligence.chunks` table - Stores hierarchical metadata
- Section boundary detection using regex patterns and heuristics

**Configuration**:
```bash
ENABLE_HIERARCHICAL_CHUNKING=true
DETECT_ERROR_CODE_SECTIONS=true
LINK_CHUNKS=true
```

**Benefits**:
- Improved search relevance through context awareness
- Better navigation of large technical documents
- Enhanced error code lookup and troubleshooting workflows

### 2. SVG Vector Graphics Processing

**Purpose**: Extract and analyze vector graphics (Explosionszeichnungen) from PDF documents for technical diagram understanding.

**Implementation**:
- `SVGProcessor` extracts SVG content using PyMuPDF
- Conversion to PNG for Vision AI analysis
- Storage of both original SVG and converted PNG
- Integration with multimodal search for diagram retrieval

**Key Components**:
- `backend/processors/svg_processor.py` - Core SVG processing logic
- `krai_content.images` table - Stores vector graphics metadata
- Vision AI integration for diagram analysis

**Configuration**:
```bash
ENABLE_SVG_EXTRACTION=true
SVG_CONVERSION_DPI=300
SVG_MAX_DIMENSION=2048
```

**Workflow**:
1. Extract SVG from PDF pages
2. Convert SVG to high-resolution PNG
3. Analyze PNG with Vision AI
4. Store both SVG and PNG with context
5. Generate embeddings for multimodal search

**Benefits**:
- Enables search of technical diagrams and illustrations
- Provides detailed analysis of vector graphics content
- Supports exploded view and technical drawing understanding

### 3. Multimodal Search with Context Awareness

**Purpose**: Unified search across all content types with intelligent result ranking and context enrichment.

**Implementation**:
- `MultimodalSearchService` provides unified search interface
- Two-stage retrieval for enhanced image search
- Context-aware result ranking using embeddings
- Support for modality filtering and result enrichment

**Key Components**:
- `backend/services/multimodal_search_service.py` - Core search logic
- RPC functions: `match_multimodal`, `match_images_by_context`
- `krai_intelligence.chunks` table (`embedding` column) - Unified embedding storage

**Search Types**:
- **Unified Search**: Search across text, images, videos, tables, and links
- **Context-Aware Image Search**: Find images using contextual descriptions
- **Two-Stage Retrieval**: Text search followed by relevant image retrieval
- **Modality Filtering**: Search specific content types only

**Configuration**:
```bash
MULTIMODAL_SEARCH_THRESHOLD=0.5
MULTIMODAL_SEARCH_LIMIT=10
ENABLE_TWO_STAGE_RETRIEVAL=true
```

**Benefits**:
- Single interface for all content types
- Intelligent result ranking based on semantic similarity
- Enhanced image search through context understanding

### 4. Advanced Context Extraction

**Purpose**: Extract and store contextual information for all media types to enable intelligent search and retrieval.

**Implementation**:
- `ContextExtractionService` processes images, videos, links, and tables
- Vision AI analysis for image content understanding
- LLM-powered context generation for structured data
- Embedding generation for context-based search

**Key Components**:
- `backend/services/context_extraction_service.py` - Context extraction logic
- Vision AI integration for image analysis
- Database tables: `krai_content.images`, `krai_content.instructional_videos`, `krai_content.links`, `krai_intelligence.structured_tables`

**Media Types Supported**:
- **Images**: Vision AI analysis with detailed descriptions
- **Videos**: YouTube metadata and content extraction
- **Links**: Web page content analysis and summarization
- **Tables**: Structure analysis and content interpretation

**Configuration**:
```bash
ENABLE_CONTEXT_EXTRACTION=true
VISION_AI_MODEL=llava-phi3
CONTEXT_EMBEDDING_MODEL=nomic-embed-text
```

**Benefits**:
- Rich contextual information for all media types
- Enhanced search through context understanding
- Improved content discovery and relevance

## Technical Architecture

### Database Schema Changes

**New Tables**:
- `krai_intelligence.chunks.embedding` column - Unified multimodal embeddings
- `krai_intelligence.structured_tables` - Table structure and context
- Enhanced `krai_content.images` - Vector graphics support
- Enhanced `krai_intelligence.chunks` - Hierarchical metadata

**Key Columns Added**:
```sql
-- krai_intelligence.chunks
section_hierarchy JSONB,
section_level INTEGER,
previous_chunk_id UUID,
next_chunk_id UUID,
error_code TEXT

-- krai_content.images
image_type VARCHAR(50) DEFAULT 'raster',
svg_content TEXT,
vector_graphic BOOLEAN DEFAULT false

-- krai_intelligence.chunks (embedding column)
source_type VARCHAR(20) NOT NULL,
source_id UUID,
context_text TEXT,
metadata JSONB
```

**RPC Functions**:
- `match_multimodal(query_embedding, match_threshold, match_count)` - Unified search
- `match_images_by_context(query_embedding, match_threshold, match_count)` - Context-aware image search
- `get_document_statistics()` - Document analytics
- `search_chunks_by_content(query_text, limit)` - Content-based chunk search

### Service Layer Enhancements

**New Services**:
- `MultimodalSearchService` - Unified search interface
- `ContextExtractionService` - Media context processing
- Enhanced `AIService` - Vision AI and multimodal capabilities

**Enhanced Processors**:
- `SVGProcessor` - Vector graphics extraction and conversion
- `SmartChunker` - Hierarchical structure detection
- `ImageProcessor` - Context-aware image processing

### Integration Points

**AI Services**:
- **Ollama Integration**: Local LLM and embedding models
- **Vision AI**: `llava-phi3` for image analysis
- **Embedding Models**: `nomic-embed-text` for multimodal embeddings

**Storage**:
- **MinIO**: Object storage for images, videos, and documents
- **PostgreSQL**: Vector database with `pgvector` extension
- **Deduplication**: SHA256-based file deduplication

## Configuration Guide

### Environment Variables

**Core Features**:
```bash
# Hierarchical Chunking
ENABLE_HIERARCHICAL_CHUNKING=true
DETECT_ERROR_CODE_SECTIONS=true
LINK_CHUNKS=true

# SVG Processing
ENABLE_SVG_EXTRACTION=true
SVG_CONVERSION_DPI=300
SVG_MAX_DIMENSION=2048

# Multimodal Search
MULTIMODAL_SEARCH_THRESHOLD=0.5
MULTIMODAL_SEARCH_LIMIT=10
ENABLE_TWO_STAGE_RETRIEVAL=true

# Context Extraction
ENABLE_CONTEXT_EXTRACTION=true
VISION_AI_MODEL=llava-phi3
CONTEXT_EMBEDDING_MODEL=nomic-embed-text
```

**Performance Tuning**:
```bash
# Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
MIN_CHUNK_SIZE=30

# AI Service
AI_SERVICE_TIMEOUT=30
EMBEDDING_BATCH_SIZE=10
VISION_AI_MAX_SIZE=2048

# Database
DB_POOL_SIZE=20
DB_MAX_CONNECTIONS=50
VECTOR_INDEX_TYPE=ivfflat
```

### Service Dependencies

**Required Services**:
- PostgreSQL with `pgvector` extension
- MinIO or S3-compatible object storage
- Ollama with `llava-phi3` and `nomic-embed-text` models

**Optional Services**:
- Redis for caching (recommended for production)
- External AI services (OpenAI, Anthropic) for enhanced capabilities

## Usage Examples

### Hierarchical Document Navigation

```python
# Get document structure
document_structure = await database_service.get_document_structure(document_id)

# Navigate to specific section
error_chunks = await database_service.get_chunks_by_error_code(
    document_id, "900.01"
)

# Get linked chunks for context
previous_chunk = await database_service.get_previous_chunk(chunk_id)
next_chunk = await database_service.get_next_chunk(chunk_id)
```

### Multimodal Search

```python
# Unified search across all content types
results = await search_service.search_multimodal(
    query="fuser unit diagram",
    modalities=['text', 'image', 'table'],
    threshold=0.5,
    limit=10
)

# Context-aware image search
images = await search_service.search_images_by_context(
    query="paper jam removal steps",
    threshold=0.6,
    limit=5
)

# Two-stage retrieval
two_stage_results = await search_service.search_two_stage(
    query="error 900.01 troubleshooting",
    max_chunks=5,
    image_threshold=0.5,
    image_limit=3
)
```

### SVG Processing

```python
# Extract SVG from document
svg_processor = SVGProcessor(database_service, storage_service, ai_service)
result = await svg_processor.process(context)

# Access extracted vector graphics
vector_graphics = await database_service.get_vector_graphics(document_id)
for graphic in vector_graphics:
    print(f"SVG: {graphic['svg_content']}")
    print(f"PNG: {graphic['png_path']}")
    print(f"Analysis: {graphic['vision_analysis']}")
```

### Context Extraction

```python
# Extract image context
context_service = ContextExtractionService(database_service, ai_service)
image_context = await context_service.extract_image_context(
    image_base64=base64_data,
    image_filename="diagram.png"
)

# Extract video context
video_context = await context_service.extract_video_context(
    video_url="https://www.youtube.com/watch?v=example",
    video_title="Maintenance Procedure"
)

# Generate context embeddings
embedding = await context_service.generate_context_embedding(
    context_text=image_context
)
```

## Performance Considerations

### Optimization Strategies

**Database Optimization**:
- Use `ivfflat` vector indexes for faster similarity search
- Implement proper connection pooling
- Enable query result caching for frequently accessed content

**AI Service Optimization**:
- Batch embedding generation for improved throughput
- Implement model caching and warm-up strategies
- Use appropriate model sizes for your use case

**Storage Optimization**:
- Implement file deduplication to reduce storage costs
- Use appropriate compression for image storage
- Consider CDN integration for improved content delivery

### Scaling Guidelines

**Horizontal Scaling**:
- Multiple AI service instances for load distribution
- Database read replicas for improved query performance
- Distributed object storage for scalability

**Vertical Scaling**:
- GPU acceleration for Vision AI processing
- Increased memory for embedding operations
- Fast storage for database operations

## Troubleshooting

### Common Issues

**SVG Extraction Issues**:
- Ensure PyMuPDF is installed and updated
- Check PDF file permissions and accessibility
- Verify sufficient disk space for temporary files

**Multimodal Search Issues**:
- Verify `pgvector` extension is installed
- Check embedding dimension consistency
- Ensure RPC functions are properly created

**Context Extraction Issues**:
- Verify Vision AI model is available in Ollama
- Check image format and size limitations
- Ensure sufficient AI service resources

### Debugging Tools

**Test Scripts**:
- `scripts/test_hierarchical_chunking.py` - Validate chunking
- `scripts/test_svg_extraction.py` - Test SVG processing
- `scripts/test_multimodal_search.py` - Verify search functionality
- `scripts/test_context_extraction_integration.py` - Test context extraction

**Monitoring**:
- Database query performance metrics
- AI service response times and error rates
- Storage utilization and access patterns

## Migration Notes

### From Phase 5

**Database Changes**:
- Run migrations 116-119 for Phase 6 features
- Update existing chunks with hierarchical metadata
- Migrate embeddings to unified `chunks.embedding` column

**Configuration Updates**:
- Enable new feature flags in environment variables
- Update AI service configuration for Vision AI
- Adjust search parameters for multimodal capabilities

### Backwards Compatibility

**API Compatibility**:
- Existing search endpoints continue to work
- New multimodal search endpoints added
- Enhanced response formats with additional metadata

**Data Compatibility**:
- Existing documents automatically processed with new features
- Legacy embeddings supported during transition period
- Gradual migration of existing content to new formats

## Best Practices

### Document Processing

**Optimal Document Types**:
- Technical service manuals with diagrams
- Engineering documents with vector graphics
- Training materials with multimedia content
- Troubleshooting guides with error codes

**Quality Guidelines**:
- Ensure PDFs are text-searchable for best results
- Use high-resolution images for Vision AI analysis
- Include proper document structure and headings
- Provide descriptive alt text for images

### Search Optimization

**Query Best Practices**:
- Use specific technical terms and error codes
- Include context for better image search results
- Combine text and visual concepts in queries
- Use appropriate search thresholds for your use case

**Result Processing**:
- Implement result ranking based on relevance scores
- Use context information for result presentation
- Filter results by modality when appropriate
- Cache frequently accessed search results

### Content Management

**Organization Strategies**:
- Use consistent document naming conventions
- Implement proper metadata tagging
- Organize content by technical domains
- Maintain document versioning

**Quality Assurance**:
- Validate extracted context for accuracy
- Monitor search result relevance
- Regular testing of SVG extraction quality
- Continuous improvement of context prompts

## Future Enhancements

### Planned Features

**Advanced AI Capabilities**:
- Multi-language support for document processing
- Advanced diagram understanding and analysis
- Real-time video content analysis
- Enhanced error code resolution suggestions

**Performance Improvements**:
- GPU-accelerated embedding generation
- Advanced vector indexing strategies
- Distributed processing for large documents
- Intelligent caching and precomputation

**User Experience**:
- Interactive document navigation interface
- Visual search with sketch input
- Advanced filtering and faceted search
- Personalized search recommendations

### Integration Opportunities

**External Systems**:
- Integration with ticketing systems
- Connection to inventory management
- Link to knowledge management platforms
- API for third-party applications

**AI Ecosystem**:
- Integration with advanced language models
- Connection to specialized vision models
- Support for custom embedding models
- Integration with external AI services

---

## Conclusion

Phase 6 Advanced Features represent a significant evolution of the KRAI platform, transforming it into a comprehensive multimodal AI system for technical document processing and knowledge retrieval. The combination of hierarchical structure detection, SVG processing, multimodal search, and advanced context extraction provides unprecedented capabilities for technical documentation management and troubleshooting.

These features enable organizations to:
- Extract maximum value from technical documentation
- Provide intelligent search across all content types
- Automate context understanding for multimedia content
- Enable advanced troubleshooting and maintenance workflows

The modular architecture and comprehensive testing ensure reliable operation while providing flexibility for future enhancements and customizations.
