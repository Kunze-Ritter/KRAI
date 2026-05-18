# Stage-Based Document Processing API

## Overview

The stage-based processing API provides granular control over document processing pipelines. Instead of processing entire documents in one batch, you can now execute individual stages or custom stage sequences on-demand. This enables the Laravel Dashboard to trigger specific processing steps based on user actions and requirements.

The API exposes the 15-stage pipeline from `KRMasterPipeline` with individual stage execution, status tracking, video processing integration, and thumbnail generation capabilities.

**Reference**: `docs/processor/PIPELINE_ARCHITECTURE.md` for detailed pipeline architecture.

## Available Stages

The pipeline consists of 15 stages that can be executed individually or in sequences:

1. **upload** - File upload and validation
2. **text_extraction** - Extract text content from PDF documents
3. **table_extraction** - Extract structured tables from documents
4. **svg_processing** - Convert vector graphics to PNG format
5. **image_processing** - Extract and analyze images from documents
6. **visual_embedding** - Generate embeddings for extracted images
7. **link_extraction** - Extract hyperlinks and references
8. **chunk_prep** - Preprocess text into searchable chunks
9. **classification** - Classify document type and category
10. **metadata_extraction** - Extract metadata (error codes, specifications, etc.)
11. **parts_extraction** - Extract parts information and compatibility data
12. **series_detection** - Detect product series and relationships
13. **storage** - Upload processed files to object storage
14. **embedding** - Generate text embeddings for search
15. **search_indexing** - Index content for full-text search

## Stage Dependencies

Some stages depend on previous stages having completed successfully:

- `image_processing` requires `upload` (needs file path)
- `visual_embedding` requires `image_processing` (needs extracted images)
- `embedding` requires `text_extraction` (needs text chunks)
- `search_indexing` requires `embedding` (needs embeddings for indexing)

The API will return an error if dependencies are not met.

**Note**: For detailed stage descriptions, see `docs/processor/STAGE_REFERENCE.md` for comprehensive documentation of each stage's purpose, inputs, outputs, and implementation details.

## Endpoints

### 1. Process Single Stage

**Endpoint:** `POST /api/v1/documents/{document_id}/process/stage/{stage_name}`

**Description:** Execute a single processing stage for a document.

**Parameters:**

- `document_id` (path): Document UUID
- `stage_name` (path): Name of the stage to execute (from the 15 available stages)

**Response:**

```json
{
  "success": true,
  "stage": "text_extraction",
  "data": {
    "chunks_created": 150,
    "text_length": 25000
  },
  "processing_time": 2.5,
  "error": null
}
```

**Example (curl):**

```bash
curl -X POST "http://localhost:8000/api/v1/documents/123e4567-e89b-12d3-a456-426614174000/process/stage/text_extraction" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Example (Laravel HTTP Client):**

```php
$response = Http::withToken($token)
    ->post("http://krai-engine:8000/api/v1/documents/{$documentId}/process/stage/text_extraction");

if ($response->successful()) {
    $data = $response->json();
    $chunksCreated = $data['data']['chunks_created'];
}
```

### 2. Process Multiple Stages

**Endpoint:** `POST /api/v1/documents/{document_id}/process/stages`

**Description:** Execute multiple stages in sequence for a document.

**Request Body:**
```json
{
  "stages": ["text_extraction", "image_processing", "embedding"],
  "stop_on_error": true
}
```

**Parameters:**
- `stages`: Array of stage names to execute
- `stop_on_error`: Whether to stop processing on first error (default: true)

**Response:**
```json
{
  "success": true,
  "total_stages": 3,
  "successful": 3,
  "failed": 0,
  "success_rate": 100.0,
  "stage_results": [
    {
      "stage": "text_extraction",
      "success": true,
      "data": {"chunks_created": 150},
      "error": null,
      "processing_time": 2.5
    },
    {
      "stage": "image_processing",
      "success": true,
      "data": {"images_extracted": 5},
      "error": null,
      "processing_time": 5.2
    },
    {
      "stage": "embedding",
      "success": true,
      "data": {"embeddings_generated": 150},
      "error": null,
      "processing_time": 3.1
    }
  ]
}
```

**Example (Laravel):**
```php
$response = Http::withToken($token)
    ->post("http://krai-engine:8000/api/v1/documents/{$documentId}/process/stages", [
        'stages' => ['text_extraction', 'image_processing'],
        'stop_on_error' => true
    ]);
```

### 3. Get Available Stages

**Endpoint:** `GET /api/v1/documents/{document_id}/stages`

**Description:** Get list of all available processing stages.

**Response:**
```json
{
  "stages": [
    "upload",
    "text_extraction",
    "table_extraction",
    "svg_processing",
    "image_processing",
    "visual_embedding",
    "link_extraction",
    "chunk_prep",
    "classification",
    "metadata_extraction",
    "parts_extraction",
    "series_detection",
    "storage",
    "embedding",
    "search_indexing"
  ],
  "total": 15
}
```

### 4. Get Stage Status

**Endpoint:** `GET /api/v1/documents/{document_id}/stages/status`

**Description:** Get processing status for all stages of a document.

**Response:**
```json
{
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "stage_status": {
    "upload": "completed",
    "text_extraction": "completed",
    "image_processing": "in_progress",
    "embedding": "pending",
    "search_indexing": "pending"
  },
  "found": true,
  "error": null
}
```

**Status Values:**
- `pending` - Stage has not been executed
- `in_progress` - Stage is currently running
- `completed` - Stage completed successfully
- `failed` - Stage failed with an error

### 5. Process Video

**Endpoint:** `POST /api/v1/documents/{document_id}/process/video`

**Description:** Enrich video from URL and link to document.

**Request Body:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "manufacturer_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Parameters:**
- `video_url`: YouTube, Vimeo, or Brightcove video URL
- `manufacturer_id`: Optional manufacturer UUID for linking

**Response:**
```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Product Installation Guide",
  "platform": "youtube",
  "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "duration": 180,
  "channel_title": "Manufacturer Channel",
  "error": null
}
```

**Supported Platforms:**
- YouTube (youtube.com, youtu.be)
- Vimeo (vimeo.com)
- Brightcove (players.brightcove.net)

### 6. Generate Thumbnail

**Endpoint:** `POST /api/v1/documents/{document_id}/process/thumbnail`

**Description:** Generate thumbnail from PDF document page.

**Request Body:**
```json
{
  "size": [300, 400],
  "page": 0
}
```

**Parameters:**
- `size`: Thumbnail dimensions [width, height] (default: [300, 400])
- `page`: Page number to render (0-indexed, default: 0)

**Response:**
```json
{
  "success": true,
  "thumbnail_url": "https://storage.example.com/thumbnails/123e4567_300x400.png",
  "size": [300, 400],
  "file_size": 45678,
  "error": null
}
```

**Thumbnail Generation Process:**
1. Renders PDF page to high-quality pixmap (2x zoom)
2. Resizes to specified dimensions using Lanczos resampling
3. Saves as PNG format
4. Uploads to object storage
5. Updates document record with thumbnail URL

## Laravel Dashboard Integration

### Complete Document Processing Workflow

```php
// 1. Upload document
$response = Http::attach(
    'file', file_get_contents($pdfPath), 'document.pdf'
)->post('http://krai-engine:8000/api/v1/documents/upload');

$documentId = $response->json('document_id');

// 2. Process specific stages based on user needs
if ($userWantsTextOnly) {
    // Process text extraction only
    Http::post(
        "http://krai-engine:8000/api/v1/documents/{$documentId}/process/stage/text_extraction"
    );
} elseif ($userWantsFullProcessing) {
    // Process multiple stages
    Http::post(
        "http://krai-engine:8000/api/v1/documents/{$documentId}/process/stages",
        [
            'stages' => ['text_extraction', 'image_processing', 'embedding'],
            'stop_on_error' => true
        ]
    );
}

// 3. Check processing status
$status = Http::get(
    "http://krai-engine:8000/api/v1/documents/{$documentId}/stages/status"
)->json();

// 4. Generate thumbnail for UI
Http::post(
    "http://krai-engine:8000/api/v1/documents/{$documentId}/process/thumbnail",
    ['size' => [200, 250]]
);

// 5. Process associated videos
if ($videoUrl) {
    Http::post(
        "http://krai-engine:8000/api/v1/documents/{$documentId}/process/video",
        [
            'video_url' => $videoUrl,
            'manufacturer_id' => $manufacturerId
        ]
    );
}
```

### Progressive Processing Pattern

```php
class DocumentProcessor
{
    public function processDocumentProgressively($documentId, $userRequirements)
    {
        $stages = $this->determineRequiredStages($userRequirements);

        foreach ($stages as $stage) {
            $response = Http::post(
                "http://krai-engine:8000/api/v1/documents/{$documentId}/process/stage/{$stage}"
            );

            if (!$response->successful()) {
                Log::error("Stage {$stage} failed: " . $response->json('error'));
                if ($userRequirements['strict_mode']) {
                    throw new Exception("Processing failed at stage: {$stage}");
                }
                continue;
            }

            // Update UI with progress
            $this->broadcastProgress($documentId, $stage, $response->json());
        }
    }

    private function determineRequiredStages($requirements)
    {
        $stages = ['text_extraction']; // Always need text

        if ($requirements['images_needed']) {
            $stages[] = 'image_processing';
        }

        if ($requirements['search_enabled']) {
            $stages[] = 'embedding';
            $stages[] = 'search_indexing';
        }

        if ($requirements['parts_catalog']) {
            $stages[] = 'parts_extraction';
            $stages[] = 'series_detection';
        }

        return $stages;
    }
}
```

## Error Handling

### Common Error Responses

**404 Not Found - Document not found:**
```json
{
  "detail": "Document not found"
}
```

**400 Bad Request - Invalid stage name:**
```json
{
  "detail": "Invalid stage: invalid_stage_name. Valid stages: ['upload', 'text_extraction', ...]"
}
```

**400 Bad Request - Missing file path:**
```json
{
  "detail": "Document has no file path for thumbnail generation"
}
```

**503 Service Unavailable - Video service not available:**
```json
{
  "detail": "Video enrichment service not available"
}
```

**500 Internal Server Error - Processing failure:**
```json
{
  "detail": "Stage processing failed for document: Internal error during processing"
}
```

### Error Recovery Strategies

1. **Retry Logic:** Implement exponential backoff for transient errors
2. **Dependency Checking:** Verify prerequisite stages before execution
3. **Partial Success:** Handle multi-stage failures gracefully
4. **Status Monitoring:** Use stage status endpoint to track progress

```php
function processWithRetry($documentId, $stage, $maxRetries = 3)
{
    $attempts = 0;

    while ($attempts < $maxRetries) {
        $response = Http::post(
            "http://krai-engine:8000/api/v1/documents/{$documentId}/process/stage/{$stage}"
        );

        if ($response->successful()) {
            return $response->json();
        }

        $attempts++;
        if ($attempts < $maxRetries) {
            sleep(pow(2, $attempts)); // Exponential backoff
        }
    }

    throw new Exception("Stage {$stage} failed after {$maxRetries} attempts");
}
```

## Performance Considerations

### Processing Times

- **Single Stage:** 1-10 seconds depending on complexity
- **Text Extraction:** 2-5 seconds for typical documents
- **Image Processing:** 5-15 seconds depending on image count
- **Embedding Generation:** 3-8 seconds for text chunks
- **Multiple Stages:** Sequential execution, total time = sum of individual stages

### Optimization Tips

1. **Batch Processing:** Use `/process/stages` for multiple stages to reduce overhead
2. **Selective Processing:** Only process required stages based on user needs
3. **Background Processing:** For long operations, use existing `/documents/upload` endpoint
4. **Caching:** Stage results are cached - re-running completed stages is fast

### Resource Usage

- **Memory:** 100-500MB per stage depending on document size
- **CPU:** High during image processing and embedding generation
- **Storage:** Thumbnails stored in configured object storage (MinIO or S3-compatible storage)
- **Network:** Video enrichment requires external API calls

## Monitoring and Logging

### Request Tracking

All stage-based processing requests are logged with:
- Document ID and stage name
- Processing time and success status
- Error details for failed operations
- User context and permissions

### Performance Metrics

Monitor these key metrics:
- Average processing time per stage
- Success/failure rates by stage
- Concurrent processing limits
- Storage usage for thumbnails

```php
// Example monitoring integration
function logProcessingMetrics($documentId, $stage, $processingTime, $success)
{
    Metrics::increment('document.stage.processed', [
        'stage' => $stage,
        'success' => $success
    ]);

    Metrics::histogram('document.stage.duration', $processingTime, [
        'stage' => $stage
    ]);
}
```

## Security Considerations

### Authentication and Authorization

- All endpoints require valid authentication tokens
- Permission-based access control:
  - `documents:read` for GET endpoints
  - `documents:write` for POST endpoints
- Document-level access control enforced

### Input Validation

- Stage names validated against allowed values
- Document IDs verified as valid UUIDs
- File paths checked for directory traversal
- Video URLs validated against allowed domains

### Rate Limiting

- Stage processing endpoints subject to rate limiting
- Concurrent processing limits per user
- Resource quotas to prevent abuse

## Troubleshooting

### Common Issues

1. **Stage Not Found:** Check stage name spelling and case
2. **Document Not Found:** Verify document ID exists in database
3. **Permission Denied:** Ensure user has required permissions
4. **Processing Timeout:** Check document size and system resources
5. **Video Processing Fails:** Verify video URL is accessible and supported

### Debug Information

Enable debug logging to get detailed error information:

```bash
# Set log level to DEBUG
export LOG_LEVEL=DEBUG

# Check application logs
docker logs krai-engine | grep "stage processing"
```

### Health Checks

Monitor service health:

```bash
# Check API health
curl http://localhost:8000/health

# Verify specific stage availability
curl http://localhost:8000/api/v1/documents/{doc_id}/stages
```

## Reference Implementation

### Complete Example Service

```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class DocumentStageService
{
    private $baseUrl;
    private $apiToken;

    public function __construct()
    {
        $this->baseUrl = config('services.krai_engine.url');
        $this->apiToken = config('services.krai_engine.token');
    }

    public function processStages(string $documentId, array $stages, bool $stopOnError = true): array
    {
        $response = Http::withToken($this->apiToken)
            ->post("{$this->baseUrl}/api/v1/documents/{$documentId}/process/stages", [
                'stages' => $stages,
                'stop_on_error' => $stopOnError
            ]);

        if (!$response->successful()) {
            Log::error("Stage processing failed", [
                'document_id' => $documentId,
                'stages' => $stages,
                'error' => $response->json('detail')
            ]);

            throw new \Exception("Stage processing failed: " . $response->json('detail'));
        }

        return $response->json();
    }

    public function generateThumbnail(string $documentId, array $size = [300, 400]): array
    {
        $response = Http::withToken($this->apiToken)
            ->post("{$this->baseUrl}/api/v1/documents/{$documentId}/process/thumbnail", [
                'size' => $size
            ]);

        return $response->json();
    }

    public function processVideo(string $documentId, string $videoUrl, ?string $manufacturerId = null): array
    {
        $response = Http::withToken($this->apiToken)
            ->post("{$this->baseUrl}/api/v1/documents/{$documentId}/process/video", [
                'video_url' => $videoUrl,
                'manufacturer_id' => $manufacturerId
            ]);

        return $response->json();
    }

    public function getStageStatus(string $documentId): array
    {
        $response = Http::withToken($this->apiToken)
            ->get("{$this->baseUrl}/api/v1/documents/{$documentId}/stages/status");

        return $response->json();
    }
}
```

This comprehensive API enables fine-grained control over document processing, allowing the Laravel Dashboard to provide responsive, user-driven document analysis capabilities.
