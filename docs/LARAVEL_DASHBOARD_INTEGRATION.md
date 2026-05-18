# Laravel Dashboard Integration with Stage-Based Pipeline

## Overview

The Laravel Filament dashboard provides comprehensive document management and pipeline control capabilities. It integrates with the FastAPI backend (KRAI Engine) to enable stage-based processing, video enrichment, thumbnail generation, and detailed status tracking.

**Reference**: `docs/processor/PIPELINE_ARCHITECTURE.md` for detailed pipeline architecture.
**Reference**: `docs/api/STAGE_BASED_PROCESSING.md` for API endpoint documentation.

### Architecture

```text
Laravel Dashboard → FastAPI Backend → PostgreSQL/MinIO
     (Filament)        (KRAI Engine)    (Storage)
```

### Key Features

- **Document Upload**: PDF upload with optional stage selection
- **Stage-Based Processing**: Individual or multiple stage processing
- **Video Enrichment**: YouTube/Vimeo/Brightcove video processing
- **Thumbnail Generation**: PDF page rendering to PNG
- **Status Tracking**: Real-time stage status visualization
- **Bulk Operations**: Batch processing across multiple documents
- **Visual Feedback**: Color-coded status indicators and progress bars

## Configuration

### Environment Variables

```env
# KRAI Engine Configuration
KRAI_ENGINE_URL=http://krai-engine:8000
KRAI_ENGINE_SERVICE_JWT=<generated-jwt-token>
```

Generate JWT token:
```bash
openssl rand -base64 32
```

### Stage Configuration

All stage definitions are in `config/krai.php`:

```php
'stages' => [
    'upload' => [
        'label' => 'Upload',
        'description' => 'Dokument hochladen und validieren',
        'icon' => 'heroicon-o-arrow-up-tray',
        'group' => 'initialization',
        'order' => 1
    ],
    'text_extraction' => [
        'label' => 'Text-Extraktion',
        'description' => 'Text aus PDF extrahieren',
        'icon' => 'heroicon-o-document-text',
        'group' => 'extraction',
        'order' => 2
    ],
    // ... 13 more stages
]
```

### Service Registration

The `KraiEngineService` is registered as a singleton in `AppServiceProvider`:

```php
$this->app->singleton(KraiEngineService::class, function ($app) {
    return new KraiEngineService(
        config('krai.engine_url'),
        config('krai.service_jwt')
    );
});
```

## KraiEngineService

### Purpose

Centralized FastAPI client that eliminates code duplication and provides consistent error handling and logging for all backend communications.

### Methods

#### `processStage(string $documentId, string $stageName): array`

Process a single stage for a document.

```php
$service = app(KraiEngineService::class);
$result = $service->processStage($documentId, 'text_extraction');

if ($result['success']) {
    echo "Stage processed in {$result['processing_time']}s";
} else {
    echo "Error: {$result['error']}";
}
```

**Returns:**
```php
[
    'success' => bool,
    'stage' => string,
    'data' => array,
    'processing_time' => float,
    'error' => ?string
]
```

#### `processMultipleStages(string $documentId, array $stages, bool $stopOnError = true): array`

Process multiple stages sequentially.

```php
$stages = ['text_extraction', 'table_extraction', 'svg_processing'];
$result = $service->processMultipleStages($documentId, $stages, true);

echo "Success rate: " . ($result['success_rate'] * 100) . "%";
```

**Returns:**
```php
[
    'success' => bool,
    'total_stages' => int,
    'successful' => int,
    'failed' => int,
    'stage_results' => array,
    'success_rate' => float
]
```

#### `processVideo(string $documentId, string $videoUrl, ?string $manufacturerId = null): array`

Process video enrichment for a document.

```php
$result = $service->processVideo($documentId, 'https://www.youtube.com/watch?v=...', $manufacturerId);

if ($result['success']) {
    echo "Video '{$result['title']}' linked successfully";
}
```

**Returns:**
```php
[
    'success' => bool,
    'video_id' => ?string,
    'title' => ?string,
    'platform' => ?string,
    'thumbnail_url' => ?string,
    'duration' => ?int,
    'channel_title' => ?string,
    'error' => ?string
]
```

#### `generateThumbnail(string $documentId, array $size = [300, 400], int $page = 0): array`

Generate thumbnail for a document page.

```php
$result = $service->generateThumbnail($documentId, [600, 800], 0);

if ($result['success']) {
    echo "Thumbnail: {$result['thumbnail_url']}";
}
```

**Returns:**
```php
[
    'success' => bool,
    'thumbnail_url' => ?string,
    'size' => ?array,
    'file_size' => ?int,
    'error' => ?string
]
```

#### `getStageStatus(string $documentId): array`

Get current stage status for a document.

```php
$result = $service->getStageStatus($documentId);

if ($result['found']) {
    foreach ($result['stage_status'] as $stage => $status) {
        echo "$stage: $status\n";
    }
}
```

**Returns:**
```php
[
    'success' => bool,
    'document_id' => string,
    'stage_status' => array,
    'found' => bool,
    'error' => ?string
]
```

#### `getAvailableStages(string $documentId): array`

Get available stages for a document.

#### `getDocumentStatus(string $documentId): array`

Get overall document processing status.

#### `reprocessDocument(string $documentId): array`

Reprocess document with full pipeline.

## Document Upload Flow

### Basic Upload

```php
// File upload via Filament form
$file = $request->file('file');
$documentType = $request->input('document_type');
$language = $request->input('language', 'en');

// Upload to FastAPI
$response = Http::withHeaders([
    'Authorization' => 'Bearer ' . $serviceToken,
    'X-Uploader-Username' => $user->name,
    'X-Uploader-UserId' => $user->id,
    'X-Uploader-Source' => 'laravel-admin'
])
->attach('file', fopen($file->getRealPath(), 'rb'), $file->getClientOriginalName())
->post($endpoint, [
    'document_type' => $documentType,
    'language' => $language,
]);
```

### Upload with Custom Stages

```php
// Upload file first
$documentId = $uploadResponse['document_id'];

// Process selected stages
if (!empty($selectedStages)) {
    $stageResult = $service->processMultipleStages(
        $documentId,
        $selectedStages,
        $stopOnError
    );

    // Show results to user
    Notification::make()
        ->title('Upload completed')
        ->body(sprintf('%d/%d stages completed', $stageResult['successful'], $stageResult['total_stages']))
        ->success()
        ->send();
} else {
    // Default: background processing
    Notification::make()
        ->title('Upload started')
        ->body('Document will be processed in background')
        ->success()
        ->send();
}
```

## Stage-Based Processing

### Available Stages (15 total)

1. **UPLOAD** - Document upload and validation
2. **TEXT_EXTRACTION** - Extract text from PDF
3. **TABLE_EXTRACTION** - Extract structured tables
4. **SVG_PROCESSING** - Convert vector graphics to PNG
5. **IMAGE_PROCESSING** - Extract and process images
6. **VISUAL_EMBEDDING** - Generate image embeddings
7. **LINK_EXTRACTION** - Extract URLs and references
8. **CHUNK_PREP** - Split text into chunks
9. **CLASSIFICATION** - Detect document type and manufacturer
10. **METADATA_EXTRACTION** - Extract error codes and metadata
11. **PARTS_EXTRACTION** - Extract spare parts and part numbers
12. **SERIES_DETECTION** - Detect product series
13. **STORAGE** - Store data in object storage
14. **EMBEDDING** - Generate text embeddings
15. **SEARCH_INDEXING** - Update search index

### Stage Groups

- **initialization**: UPLOAD
- **extraction**: TEXT_EXTRACTION, TABLE_EXTRACTION, SVG_PROCESSING, IMAGE_PROCESSING, LINK_EXTRACTION
- **processing**: CHUNK_PREP, CLASSIFICATION, METADATA_EXTRACTION, PARTS_EXTRACTION, SERIES_DETECTION
- **enrichment**: VISUAL_EMBEDDING, EMBEDDING
- **finalization**: STORAGE, SEARCH_INDEXING

### Single Stage Processing

```php
// In EditDocument action
Action::make('processSingleStage')
    ->form([
        Select::make('stage')
            ->label('Stage auswählen')
            ->options(krai_stage_options())
            ->required()
    ])
    ->action(function (array $data) {
        $result = $service->processStage($record->id, $data['stage']);

        if ($result['success']) {
            Notification::make()
                ->title('Stage processed successfully')
                ->body(sprintf('Stage "%s" completed in %.2fs',
                    krai_stage_label($data['stage']),
                    $result['processing_time']))
                ->success()
                ->send();
        }
    });
```

### Multiple Stage Processing

```php
Action::make('processMultipleStages')
    ->form([
        CheckboxList::make('stages')
            ->label('Stages auswählen')
            ->options(krai_stage_options())
            ->columns(3)
            ->required(),
        Toggle::make('stop_on_error')
            ->label('Bei Fehler stoppen')
            ->default(true)
    ])
    ->action(function (array $data) {
        $result = $service->processMultipleStages(
            $record->id,
            $data['stages'],
            $data['stop_on_error']
        );

        if ($result['success']) {
            Notification::make()
                ->title('Stages processed successfully')
                ->body(sprintf('%d of %d stages (%.1f%%)',
                    $result['successful'],
                    $result['total_stages'],
                    $result['success_rate'] * 100))
                ->success()
                ->send();
        }
    });
```

### Bulk Stage Processing

```php
// In DocumentsTable bulk action
BulkAction::make('processStageBulk')
    ->form([
        Select::make('stage')
            ->label('Stage auswählen')
            ->options(krai_stage_options())
            ->required()
    ])
    ->action(function (Collection $records, array $data) {
        $success = 0;
        $failed = 0;

        foreach ($records as $record) {
            $result = $service->processStage($record->id, $data['stage']);
            $result['success'] ? $success++ : $failed++;
        }

        Notification::make()
            ->title('Bulk processing completed')
            ->body(sprintf('%d successful, %d failed', $success, $failed))
            ->success()
            ->send();
    });
```

## Video Processing

### Supported Platforms

- YouTube
- Vimeo
- Brightcove

### Video Processing Implementation

```php
Action::make('processVideo')
    ->form([
        TextInput::make('video_url')
            ->label('Video URL')
            ->url()
            ->required()
            ->placeholder('https://www.youtube.com/watch?v=...'),
        Select::make('manufacturer_id')
            ->label('Hersteller (optional)')
            ->relationship('manufacturer', 'name')
            ->searchable()
    ])
    ->action(function (array $data) {
        $result = $service->processVideo(
            $record->id,
            $data['video_url'],
            $data['manufacturer_id'] ?? null
        );

        if ($result['success']) {
            Notification::make()
                ->title('Video processed successfully')
                ->body(sprintf('Video "%s" (%s) linked',
                    $result['title'],
                    $result['platform']))
                ->success()
                ->send();
        }
    });
```

## Thumbnail Generation

### Thumbnail Generation Implementation

```php
Action::make('generateThumbnail')
    ->form([
        TextInput::make('page')
            ->label('Seite')
            ->numeric()
            ->default(0)
            ->minValue(0),
        Select::make('size')
            ->label('Größe')
            ->options([
                '300x400' => 'Standard (300x400)',
                '600x800' => 'Groß (600x800)',
                '150x200' => 'Klein (150x200)'
            ])
            ->default('300x400')
    ])
    ->action(function (array $data) {
        $sizeArray = explode('x', $data['size']);
        $result = $service->generateThumbnail(
            $record->id,
            [(int)$sizeArray[0], (int)$sizeArray[1]],
            (int)$data['page']
        );

        if ($result['success']) {
            Notification::make()
                ->title('Thumbnail generated')
                ->body(sprintf('Thumbnail URL: %s', $result['thumbnail_url']))
                ->success()
                ->send();
        }
    });
```

## Stage Status Display

### Table Column

```php
TextColumn::make('stage_status')
    ->label('Stage Status')
    ->getStateUsing(function ($record) {
        $stageStatus = $record->stage_status ?? [];
        if (empty($stageStatus)) return 'Keine Stages';

        $completed = collect($stageStatus)->filter(fn($s) => $s === 'completed')->count();
        $failed = collect($stageStatus)->filter(fn($s) => $s === 'failed')->count();
        $total = count($stageStatus);

        return sprintf('%d/%d ✓ | %d ✗', $completed, $total, $failed);
    })
    ->badge()
    ->color(fn($record) => {
        $stageStatus = $record->stage_status ?? [];
        if (empty($stageStatus)) return 'gray';

        $failed = collect($stageStatus)->filter(fn($s) => $s === 'failed')->count();
        if ($failed > 0) return 'danger';

        $completed = collect($stageStatus)->filter(fn($s) => $s === 'completed')->count();
        $total = count($stageStatus);

        return $completed === $total ? 'success' : 'warning';
    });
```

### Form Section

```php
Section::make('Stage Verarbeitungsstatus')
    ->schema([
        ViewField::make('stage_status_display')
            ->view('filament.forms.components.stage-status-display')
            ->columnSpanFull()
    ])
    ->collapsible()
    ->visible(fn($record) => $record && !empty($record->stage_status));
```

### Modal Grid View

```php
Action::make('viewStageStatus')
    ->modalContent(function () {
        $record = $this->getRecord();
        $service = app(KraiEngineService::class);
        $statusData = $service->getStageStatus($record->id);

        return view('filament.components.stage-status-grid', [
            'stageStatus' => $statusData['stage_status'],
            'stages' => config('krai.stages')
        ]);
    })
    ->modalWidth('5xl')
    ->slideOver();
```

### Blade View Components

#### `stage-status-display.blade.php`

Compact grid view for form section:
- Groups stages by stage_group
- Color-coded badges: green (completed), red (failed), yellow (pending), gray (not_started)
- Icons for each status
- Responsive layout (2-4 columns)

#### `stage-status-grid.blade.php`

Detailed modal view:
- Stage cards with icons, labels, descriptions, and status badges
- Grouped by stage_group with section headers
- Color-coded borders and backgrounds
- Summary statistics and progress bar
- Empty state for documents without stage data

#### `stage-status-empty.blade.php`

Empty state for modal when document not found.

## API Endpoints Reference

### Authentication

All API calls use Bearer token authentication:

```php
$headers = [
    'Authorization' => 'Bearer ' . $serviceToken,
    'Content-Type' => 'application/json',
    'Accept' => 'application/json'
];
```

### Upload Document

```http
POST /documents/upload
Content-Type: multipart/form-data

{
  "file": <binary>,
  "document_type": "service_manual",
  "language": "en"
}
```

**Response:**
```json
{
  "document_id": "uuid",
  "filename": "manual.pdf",
  "status": "uploaded"
}
```

### Process Single Stage

```http
POST /documents/{id}/process/stage/{stage}
Authorization: Bearer {token}

{
  "user_context": {
    "username": "admin",
    "user_id": "123"
  }
}
```

**Response:**
```json
{
  "success": true,
  "stage": "text_extraction",
  "processing_time": 2.34,
  "data": {
    "extracted_text": "...",
    "metadata": {}
  }
}
```

### Process Multiple Stages

```http
POST /documents/{id}/process/stages
Authorization: Bearer {token}

{
  "stages": ["text_extraction", "table_extraction", "svg_processing"],
  "stop_on_error": true
}
```

**Response:**
```json
{
  "success": true,
  "total_stages": 3,
  "successful": 2,
  "failed": 1,
  "success_rate": 0.667,
  "stage_results": {
    "text_extraction": {
      "success": true,
      "processing_time": 2.34
    },
    "table_extraction": {
      "success": true,
      "processing_time": 1.56
    },
    "svg_processing": {
      "success": false,
      "error": "No SVG content found"
    }
  }
}
```

### Process Video

```http
POST /documents/{id}/process/video
Authorization: Bearer {token}

{
  "video_url": "https://www.youtube.com/watch?v=...",
  "manufacturer_id": "uuid"
}
```

**Response:**
```json
{
  "success": true,
  "video_id": "uuid",
  "title": "Product Demo Video",
  "platform": "youtube",
  "thumbnail_url": "https://cdn.example.com/thumbnail.jpg",
  "duration": 300,
  "channel_title": "Official Channel"
}
```

### Generate Thumbnail

```http
POST /documents/{id}/process/thumbnail
Authorization: Bearer {token}

{
  "size": [300, 400],
  "page": 0
}
```

**Response:**
```json
{
  "success": true,
  "thumbnail_url": "https://cdn.example.com/thumbnail.jpg",
  "size": [300, 400],
  "file_size": 45678
}
```

### Get Stage Status

```http
GET /documents/{id}/stages/status
Authorization: Bearer {token}
```

**Response:**
```json
{
  "document_id": "uuid",
  "stage_status": {
    "upload": "completed",
    "text_extraction": "completed",
    "table_extraction": "failed",
    "svg_processing": "pending",
    "image_processing": "not_started"
  }
}
```

### Get Available Stages

```http
GET /documents/{id}/stages
Authorization: Bearer {token}
```

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

### Get Document Status

```http
GET /documents/{id}/status
Authorization: Bearer {token}
```

**Response:**
```json
{
  "document_status": "processing",
  "queue_position": 3,
  "total_queue_items": 10
}
```

### Reprocess Document

```http
POST /documents/{id}/reprocess
Authorization: Bearer {token}
```

**Response:**
```json
{
  "message": "Document reprocessing started",
  "document_id": "uuid",
  "status": "queued"
}
```

## Testing Guide

### Upload Document with Custom Stages

1. Navigate to Documents page
2. Click "Dokument hochladen"
3. Select PDF file
4. Choose document type and language
5. Select specific stages (optional)
6. Set "Bei Fehler stoppen" toggle
7. Submit form
8. Verify notification shows stage results

### Process Individual Stage

1. Go to document edit page
2. Click "Stage verarbeiten"
3. Select stage from dropdown
4. Submit form
5. Verify success notification with processing time

### Process Multiple Stages

1. Go to document edit page
2. Click "Mehrere Stages verarbeiten"
3. Select multiple stages (checkbox list)
4. Set error handling preference
5. Submit form
6. Verify success rate in notification

### Process Video

1. Go to document edit page
2. Click "Video verarbeiten"
3. Enter YouTube/Vimeo URL
4. Select manufacturer (optional)
5. Submit form
6. Verify video linking notification

### Generate Thumbnail

1. Go to document edit page
2. Click "Thumbnail generieren"
3. Set page number and size
4. Submit form
5. Verify thumbnail URL in notification

### View Stage Status

1. Go to document edit page
2. Click "Stage Status anzeigen"
3. Review detailed stage grid
4. Check progress bar and statistics

### Bulk Operations

1. Go to Documents table
2. Select multiple documents
3. Click "Stage verarbeiten" bulk action
4. Select stage
5. Submit form
6. Verify bulk processing results

## Troubleshooting

### Common Errors

#### 404 Document Not Found

**Cause:** Document ID invalid or document deleted
**Solution:** Verify document exists in database
```php
$document = Document::find($documentId);
if (!$document) {
    throw new Exception('Document not found');
}
```

#### 503 Service Unavailable

**Cause:** KRAI Engine not running or network issues
**Solution:** Check KRAI_ENGINE_URL and service status
```bash
# Check if service is running
curl http://krai-engine:8000/health

# Verify Docker containers
docker ps | grep krai-engine
```

#### 500 Processing Failed

**Cause:** Stage processing error, invalid data, or backend issues
**Solution:** Check backend logs and stage_status JSONB
```sql
-- Check stage status in database
SELECT stage_status FROM documents WHERE id = $documentId;

-- Check processing logs
SELECT * FROM processing_logs WHERE document_id = $documentId ORDER BY created_at DESC;
```

#### Authentication Issues

**Cause:** Missing or invalid KRAI_ENGINE_SERVICE_JWT
**Solution:** Generate and set JWT token
```bash
# Generate new token
openssl rand -base64 32

# Update .env file
KRAI_ENGINE_SERVICE_JWT=<generated-token>
```

#### Video Processing Failures

**Cause:** Invalid URL, unsupported platform, or network issues
**Solution:** Verify URL format and platform support
```php
// Validate URL
if (!filter_var($videoUrl, FILTER_VALIDATE_URL)) {
    throw new Exception('Invalid URL format');
}

// Check platform
$platform = detectVideoPlatform($videoUrl);
if (!in_array($platform, ['youtube', 'vimeo', 'brightcove'])) {
    throw new Exception('Unsupported platform: ' . $platform);
}
```

#### Thumbnail Generation Failures

**Cause:** PDF not found, page out of range, or rendering issues
**Solution:** Verify document exists and page number is valid
```php
// Check document
$document = Document::find($documentId);
if (!$document || !file_exists($document->file_path)) {
    throw new Exception('Document file not found');
}

// Validate page number
if ($page < 0 || $page >= $document->page_count) {
    throw new Exception('Page out of range');
}
```

### Debugging Tips

1. **Enable Debug Logging**
```php
// In KraiEngineService
Log::channel('krai-engine')->debug('API call', [
    'method' => $method,
    'endpoint' => $endpoint,
    'document_id' => $documentId,
    'response_status' => $response->status()
]);
```

2. **Check Database State**
```sql
-- Document overview
SELECT id, filename, processing_status, stage_status, created_at
FROM documents
WHERE id = $documentId;

-- Stage status details
SELECT jsonb_each_text(stage_status) as stage_status
FROM documents
WHERE id = $documentId;
```

3. **Verify API Connectivity**
```bash
# Test basic connectivity
curl -I http://krai-engine:8000/health

# Test with authentication
curl -H "Authorization: Bearer $JWT_TOKEN" \
     http://krai-engine:8000/documents/$documentId/status
```

4. **Monitor Processing Queue**
```sql
-- Queue status
SELECT COUNT(*) as queue_size,
       AVG(processing_time) as avg_time
FROM processing_queue
WHERE status = 'pending';

-- Failed jobs
SELECT document_id, stage, error_message, created_at
FROM processing_logs
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 10;
```

## Development Notes

### Adding New Stages

1. **Update Backend Stage Enum**
```python
# backend/core/base_processor.py
class Stage(str, Enum):
    # existing stages...
    NEW_STAGE = "new_stage"
```

2. **Update Laravel Config**
```php
// config/krai.php
'stages' => [
    // existing stages...
    'new_stage' => [
        'label' => 'New Stage',
        'description' => 'Description of new stage',
        'icon' => 'heroicon-o-cog',
        'group' => 'processing',
        'order' => 16
    ]
]
```

3. **Update FastAPI Endpoint**
```python
# backend/api/document_api.py
@app.post("/documents/{document_id}/process/stage/{stage_name}")
async def process_stage(document_id: str, stage_name: str):
    # Handle new stage logic
```

### Customizing Stage Display

1. **Modify Blade Views**
```blade
<!-- resources/views/filament/components/stage-status-grid.blade.php -->
<div class="flex items-start space-x-3 p-4 rounded-lg border-2 border-{{ $badgeColor }}-200">
    <!-- Custom stage display logic -->
</div>
```

2. **Add New Status Colors**
```php
// In blade views
$badgeColor = match($status) {
    'completed' => 'success',
    'failed' => 'danger',
    'pending', 'in_progress' => 'warning',
    'new_status' => 'info',  // Add new status
    default => 'gray'
};
```

### Extending KraiEngineService

```php
class KraiEngineService
{
    public function newMethod(string $documentId): array
    {
        $endpoint = "/documents/{$documentId}/new-endpoint";

        try {
            $client = $this->createHttpClient();
            $response = $client->post($this->baseUrl . $endpoint);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data' => $response->json()
                ];
            } else {
                return [
                    'success' => false,
                    'error' => $response->json('detail', 'Unknown error')
                ];
            }
        } catch (\Exception $e) {
            return [
                'success' => false,
                'error' => 'Connection error: ' . $e->getMessage()
            ];
        }
    }
}
```

### Adding New Actions

```php
// In EditDocument.php
Action::make('newAction')
    ->label('New Action')
    ->icon('heroicon-o-star')
    ->form([
        // Form fields
    ])
    ->action(function (array $data) {
        $service = app(KraiEngineService::class);
        $result = $service->newMethod($record->id);

        if ($result['success']) {
            Notification::make()
                ->title('Action completed')
                ->success()
                ->send();
        } else {
            Notification::make()
                ->title('Action failed')
                ->body($result['error'])
                ->danger()
                ->send();
        }
    });
```

### Testing with Local FastAPI

```bash
# Start FastAPI locally
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Update Laravel config
# config/krai.php
'engine_url' => env('KRAI_ENGINE_URL', 'http://localhost:8000'),

# Test API endpoints
curl http://localhost:8000/docs
```

### Performance Optimization

1. **Cache Stage Status**
```php
// In Document model
protected $casts = [
    'stage_status' => 'json',
    'stage_status_cached_at' => 'datetime'
];

public function getStageStatusAttribute($value)
{
    $cacheKey = "document_stage_status_{$this->id}";
    return Cache::remember($cacheKey, 300, function () use ($value) {
        return $value;
    });
}
```

2. **Batch API Calls**
```php
// Process multiple documents in single request
$documentIds = $records->pluck('id')->toArray();
$results = $service->batchProcessStages($documentIds, $stage);
```

3. **Queue Heavy Operations**
```php
// Dispatch video processing to queue
ProcessVideoJob::dispatch($documentId, $videoUrl);
```

## Security Considerations

### JWT Token Management

```php
// Generate secure token
$token = bin2hex(random_bytes(32));

// Store in environment (not in code)
// .env
KRAI_ENGINE_SERVICE_JWT=your_secure_token_here

// Rotate tokens periodically
```

### Input Validation

```php
// Validate video URLs
$videoUrl = $data['video_url'];
if (!filter_var($videoUrl, FILTER_VALIDATE_URL)) {
    throw ValidationException::withMessages([
        'video_url' => 'Invalid URL format'
    ]);
}

// Sanitize file names
$fileName = basename($file->getClientOriginalName());
if (preg_match('/[^a-zA-Z0-9._-]/', $fileName)) {
    throw ValidationException::withMessages([
        'file' => 'Invalid file name'
    ]);
}
```

### User Permissions

```php
// Check user permissions before actions
->visible(function () {
    $user = auth()->user();
    return $user && $user->canManageContent();
})

// Add user context to API calls
$headers['X-Uploader-UserId'] = $user->id;
$headers['X-Uploader-Username'] = $user->name;
```

### Rate Limiting

```php
// Implement rate limiting for API calls
Route::middleware('throttle:60,1')->group(function () {
    // API routes
});
```

This comprehensive documentation covers all aspects of the Laravel Dashboard integration with stage-based pipeline processing, providing developers with the information needed to understand, use, and extend the system.
