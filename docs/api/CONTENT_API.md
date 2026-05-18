# Content Management API

The Content Management API provides structured access to service knowledge assets including error codes, instructional videos, and document images. All endpoints are exposed under the `/api/v1` prefix and require authentication.

## Authentication & Permissions

Authentication uses bearer tokens issued by the `/api/v1/auth` routes. Authorization is enforced via the `require_permission` middleware.

| Resource      | Read Permission      | Write Permission     | Delete Permission     |
|---------------|----------------------|----------------------|-----------------------|
| Error Codes   | `error_codes:read`   | `error_codes:write`  | `error_codes:delete`  |
| Videos        | `videos:read`        | `videos:write`       | `videos:delete`       |
| Images        | `images:read`        | `images:write`       | `images:delete`       |

> **Roles**
>
> - `admin` receives all permissions.
> - `editor` can read/write Error Codes, Videos, and Images (no delete).
> - `viewer` can read all content.
> - `api_user` can read all content.

---

## Error Codes API

Base path: `/api/v1/error_codes`

### List Error Codes

```http
GET /api/v1/error_codes
```

Query parameters combine pagination (`page`, `page_size`), filtering, and sorting:

- `manufacturer_id`, `document_id`, `chunk_id`
- `error_code`, `severity_level`, `requires_technician`, `requires_parts`
- `search` (full-text across code, description, solution)
- `sort_by`, `sort_order`

Returns `SuccessResponse<ErrorCodeListResponse>`.

### Retrieve Error Code

```http
GET /api/v1/error_codes/{error_code_id}?include_relations=false
```

Returns `SuccessResponse<ErrorCodeWithRelationsResponse>` including optional document, manufacturer, and chunk excerpts when `include_relations=true`.

### Create Error Code

```http
POST /api/v1/error_codes
Content-Type: application/json
```

Body: `ErrorCodeCreateRequest`

- Requires at least one relation (`chunk_id`, `document_id`, or `manufacturer_id`).
- Duplicate error codes within the same document are rejected (`409 Conflict`).

### Update Error Code

```http
PUT /api/v1/error_codes/{error_code_id}
```

Body: `ErrorCodeUpdateRequest` (partial updates)

### Delete Error Code

```http
DELETE /api/v1/error_codes/{error_code_id}
```

Returns `SuccessResponse<MessagePayload>`.

### Multi-Source Search

```http
POST /api/v1/error_codes/search
```

Body: `ErrorCodeSearchRequest`

- `query` required; `search_in` defaults to `error_code`, `error_description`, `solution_text`.
- Optional filters: `manufacturer_id`, `severity_level`, `limit`.
- Response: `SuccessResponse<ErrorCodeSearchResponse>` with duration metrics.

### Convenience Filters

```http
GET /api/v1/error_codes/by-document/{document_id}
GET /api/v1/error_codes/by-manufacturer/{manufacturer_id}
```

Both endpoints support pagination and sorting and return `SuccessResponse<ErrorCodeListResponse>`.

---

## Videos API

Base path: `/api/v1/videos`

### List Videos

```http
GET /api/v1/videos
```

Filters: `manufacturer_id`, `series_id`, `document_id`, `platform`, `youtube_id`, `search`.

### Retrieve Video

```http
GET /api/v1/videos/{video_id}?include_relations=false
```

Returns `SuccessResponse<VideoWithRelationsResponse>` including manufacturer, product series, linked products, and document when requested.

### Create Video

```http
POST /api/v1/videos
```

Body: `VideoCreateRequest`

- Deduplicates by `youtube_id` (for YouTube) or `video_url`.
- Validates manufacturer, series, and document foreign keys.

### Update Video

```http
PUT /api/v1/videos/{video_id}
```

Body: `VideoUpdateRequest`

### Delete Video

```http
DELETE /api/v1/videos/{video_id}
```

Returns `SuccessResponse<{"message": str}>`.

### Enrich Video

```http
POST /api/v1/videos/enrich
```

Body: `VideoEnrichmentRequest`

- Invokes the asynchronous enrichment service to fetch metadata and persist the video if not already stored.
- Response: `SuccessResponse<VideoEnrichmentResponse>` including enrichment status, created video ID, and detected platform.

### Link & Unlink Products

```http
POST /api/v1/videos/{video_id}/link-products
DELETE /api/v1/videos/{video_id}/unlink-products/{product_id}
```

Link body: `VideoProductLinkRequest { product_ids: [str, ...] }`

### Retrieve Linked Products

```http
GET /api/v1/videos/{video_id}/products
```

Returns `SuccessResponse<ProductListResponse>`.

### Videos by Product

```http
GET /api/v1/videos/by-product/{product_id}
```

Combines pagination and sorting and returns `SuccessResponse<VideoListResponse>`.

---

## Images API

Base path: `/api/v1/images`

### List Images

```http
GET /api/v1/images
```

Filters: `document_id`, `chunk_id`, `page_number`, `image_type`, `contains_text`, `file_hash`, `search`.

### Retrieve Image

```http
GET /api/v1/images/{image_id}?include_relations=false
```

Returns `SuccessResponse<ImageWithRelationsResponse>` including document and chunk context.

### Download Image

```http
GET /api/v1/images/{image_id}/download
```

Streams the binary image from object storage. Optional query `download=true` is implied; response headers include `Content-Disposition` with the stored filename.

### Create Image Metadata

```http
POST /api/v1/images
```

Body: `ImageCreateRequest`

### Update Image Metadata

```http
PUT /api/v1/images/{image_id}
```

Body: `ImageUpdateRequest`

### Delete Image

```http
DELETE /api/v1/images/{image_id}
```

Optional query: `delete_from_storage=true` removes the backing object from object storage in addition to the database record.

Returns `SuccessResponse<MessagePayload>` with fields:

- `message`: confirmation text
- `deleted_from_storage`: boolean reflecting object-store deletion outcome (false when skipped or unavailable)

### Upload Image to Object Storage

```http
POST /api/v1/images/upload
Content-Type: multipart/form-data
```

Parameters:

- `file` (required): image binary upload.
- `bucket`: optional bucket selector (`document_images`, `error_images`, `parts_images`).
- `document_id`, `chunk_id`: optional associations validated prior to persistence.

The endpoint uploads to object storage via `ObjectStorageService`, deduplicates by SHA-256 hash, and persists metadata when unique. Returns `SuccessResponse<ImageUploadResponse>`.

### Images by Document

```http
GET /api/v1/images/by-document/{document_id}
```

Supports pagination and sorting.

### Image Statistics

```http
GET /api/v1/images/stats
```

Returns aggregated summaries via `ImageStatsResponse` (totals by type/document, OCR & AI coverage).

---

## Response Wrapper

Every endpoint responds with the unified `SuccessResponse[T]` model introduced in `backend/api/routes/response_models.py`. Errors are surfaced as `HTTPException` payloads containing `ErrorResponse` with `error`, `detail`, and optional `error_code` identifiers.

---

## Audit Logging

Create, update, and delete operations write to `krai_system.audit_log` with the responsible user ID and before/after snapshots, ensuring traceability of all content changes.

---

## Rate Limiting & Error Handling

- Validation errors return `422 Unprocessable Entity` with Pydantic detail.
- Duplicate detections respond with `409 Conflict` (`ERROR_CODE_DUPLICATE`, `VIDEO_DUPLICATE`, `IMAGE_DUPLICATE`).
- Missing relations return `400 Bad Request` with specific error codes (`DOCUMENT_NOT_FOUND`, `MANUFACTURER_NOT_FOUND`, etc.).
- Generic failures raise `500 Internal Server Error` after structured logging.

---

## Environment Configuration

Ensure the following environment variables are configured:

```env
# Video enrichment service integration
VIDEO_ENRICHMENT_API_URL=
VIDEO_ENRICHMENT_API_KEY=

# Object storage for image uploads
OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=
OBJECT_STORAGE_PUBLIC_URL=
```

The enrichment service is optional; when disabled or unavailable, `/videos/enrich` will respond with an error payload.

---

## Changelog

- **2025-11-01** — Initial publication of Content API documentation covering error codes, videos, and images with enrichment and object storage upload workflows.
