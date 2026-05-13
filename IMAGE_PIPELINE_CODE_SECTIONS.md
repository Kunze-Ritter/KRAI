# KRAI IMAGE PROCESSING - CRITICAL CODE SECTIONS

## 1. IMAGE CONTEXT EXTRACTION - WHERE related_error_codes IS POPULATED

### File: backend/services/context_extraction_service.py (lines 84-156)

```python
def extract_image_context(
    self,
    page_text: str,
    page_number: int,
    image_bbox: Optional[tuple] = None,
    page_path: Optional[str] = None
) -> Dict[str, Any]:
    """Extract context for an image from page text."""
    context_data = {
        'context_caption': None,
        'figure_reference': None,
        'page_header': None,
        'related_error_codes': [],  # <-- INITIALIZED HERE
        'related_products': [],
        'surrounding_paragraphs': []
    }

    try:
        # Extract surrounding text
        context_data['context_caption'] = self._extract_surrounding_text(
            page_text, image_bbox, self.context_window_size, page_path, page_number
        )

        # Extract figure reference
        context_data['figure_reference'] = self._extract_figure_reference(page_text)

        # Extract page header
        context_data['page_header'] = self._extract_page_header(
            page_text, page_path, page_number
        )

        # Extract error codes -- THIS EXTRACTS FROM ENTIRE PAGE TEXT
        if self.enable_error_code_extraction:
            context_data['related_error_codes'] = self._extract_error_codes(page_text)

        # Extract products
        if self.enable_product_extraction:
            context_data['related_products'] = self._extract_products(page_text)

        # Extract surrounding paragraphs
        context_data['surrounding_paragraphs'] = self._extract_surrounding_paragraphs(page_text)

        self.logger.debug(
            "Extracted context for image on page %d: %d error codes, %d products",
            page_number,
            len(context_data['related_error_codes']),
            len(context_data['related_products'])
        )

    except Exception as e:
        self.logger.error(
            "Error extracting context for image on page %d: %s",
            page_number, str(e)
        )

    return context_data
```

### Error Code Extraction - The Regex Pattern (line 74)

```python
def _compile_regex_patterns(self):
    """Compile frequently used regex patterns for performance."""
    # Error code pattern (XX.XX.XX format)
    self.error_code_pattern = re.compile(r'\d{2}\.\d{2}\.\d{2}')
```

### Error Code Extraction Implementation (lines 395-409)

```python
def _extract_error_codes(self, text: str) -> List[str]:
    """
    Extract error codes from text.

    Args:
        text: Text to search for error codes

    Returns:
        List of unique error codes found (e.g., ['01.02.03', '44.55.66'])
    """
    if not text:
        return []

    # Find all matches of XX.XX.XX pattern
    matches = self.error_code_pattern.findall(text)
    return list(set(matches))  # Remove duplicates
```

---

## 2. IMAGE PROCESSOR - WHERE CONTEXT IS CALLED

### File: backend/processors/image_processor.py (lines 1333-1402)

```python
async def _extract_image_contexts(
    self,
    images: list[dict],
    page_texts: dict[int, str],
    adapter,
    pdf_path: Path | None = None,
    document_id: UUID | None = None,
) -> list[dict]:
    """
    Extract context for all images using ContextExtractionService.

    Args:
        images: List of image dictionaries
        page_texts: Dict mapping page_number to page_text
        adapter: Logger adapter
        pdf_path: Optional PDF path for bbox-aware extraction
        document_id: Optional document ID for related chunks extraction

    Returns:
        List of images with context metadata added
    """
    images_with_context: list[dict] = []
    related_chunks_cache: dict[int, list[str]] = {}

    for image in images:
        page_number = image.get("page_number")
        if not page_number or page_number not in page_texts:
            adapter.warning("No page text available for image on page %d", page_number)
            images_with_context.append(image)
            continue

        page_text = page_texts[page_number]
        image_bbox = image.get("bbox")  # Optional bounding box

        try:
            # Extract context using ContextExtractionService
            # THIS CALL EXTRACTS related_error_codes FROM PAGE TEXT
            context_data = self.context_service.extract_image_context(
                page_text=page_text,
                page_number=page_number,
                image_bbox=image_bbox,
                page_path=str(pdf_path),
            )

            # Merge context data into image dict
            # related_error_codes is now in the image dict
            image.update(
                {
                    "context_caption": context_data["context_caption"],
                    "page_header": context_data["page_header"],
                    "figure_reference": context_data.get("figure_reference"),
                    "related_error_codes": context_data["related_error_codes"],
                    "related_products": context_data["related_products"],
                    "surrounding_paragraphs": context_data["surrounding_paragraphs"],
                    "related_chunks": related_chunks_cache.get(page_number, []),
                }
            )

            if page_number not in related_chunks_cache:
                related_chunks_cache[page_number] = await self._get_related_chunks(
                    page_number, document_id, adapter
                )
                image["related_chunks"] = related_chunks_cache.get(page_number, [])

            images_with_context.append(image)

        except Exception as e:
            adapter.error("Failed to extract context for image on page %d: %s", page_number, e)
            images_with_context.append(image)

    adapter.info("Extracted context for %d images", len(images_with_context))
    return images_with_context
```

---

## 3. DATABASE PERSISTENCE - WHERE storage_url IS SET

### File: backend/processors/image_processor.py (lines 713-787)

```python
async def _queue_storage_tasks(self, document_id: UUID, images: list[dict[str, Any]], adapter) -> int:
    """
    Persist each processed image to krai_content.images via the database adapter.
    Propagate generated image IDs back into in-memory image dicts.
    """
    if not self.database_service or not hasattr(self.database_service, "create_image"):
        adapter.warning("Database service does not support create_image - skipping persistence")
        return 0

    from backend.core.data_models import ImageModel, ImageType

    def _map_image_type(val: Any) -> str:
        if not val:
            return ImageType.DIAGRAM.value
        s = str(val).lower()
        if s in ("diagram", "screenshot", "photo", "chart", "schematic", "flowchart"):
            return s
        if s == "table":
            return ImageType.DIAGRAM.value
        return ImageType.DIAGRAM.value

    def _compute_file_hash(img: dict[str, Any]) -> str:
        path = img.get("temp_path") or img.get("path") or ""
        size = img.get("size_bytes", 0)
        page = img.get("page_number", 0)
        return hashlib.sha256(f"{path}|{size}|{page}".encode()).hexdigest()

    success_count = 0
    for idx, img in enumerate(images):
        temp_path = img.get("temp_path") or img.get("path")
        if not temp_path or not os.path.exists(temp_path):
            adapter.debug("Skipping image without valid temp_path: %s", img.get("filename"))
            continue

        try:
            file_hash = _compute_file_hash(img)
            storage_path = temp_path
            # STORAGE_URL IS SET TO LOCAL FILE PATH
            storage_url = f"file://{temp_path}"

            # CREATE IMAGE MODEL WITH ALL CONTEXT DATA
            image_model = ImageModel(
                document_id=str(document_id),
                filename=img.get("filename", f"img_{idx}.png"),
                original_filename=img.get("filename", f"img_{idx}.png"),
                storage_path=storage_path,
                storage_url=storage_url,  # <-- SET HERE (local path)
                file_size=img.get("size_bytes", 0),
                image_format=(img.get("format") or "png").upper()[:10],
                width_px=img.get("width", 0),
                height_px=img.get("height", 0),
                page_number=int(img.get("page_number", 1)),
                image_index=idx,
                image_type=_map_image_type(img.get("type") or img.get("image_type")),
                ai_description=img.get("ai_description") or None,
                ai_confidence=float(img.get("ai_confidence", 0.5)),
                contains_text=bool(img.get("contains_text", False)),
                ocr_text=img.get("ocr_text") or None,
                ocr_confidence=float(img.get("ocr_confidence", 0.0)),
                file_hash=file_hash,
                context_caption=img.get("context_caption"),
                page_header=img.get("page_header"),
                figure_reference=img.get("figure_reference"),
                # RELATED_ERROR_CODES FROM CONTEXT EXTRACTION
                related_error_codes=img.get("related_error_codes") or [],
                related_products=img.get("related_products") or [],
                surrounding_paragraphs=img.get("surrounding_paragraphs") or [],
            )

            # INSERT INTO krai_content.images
            db_id = await self.database_service.create_image(image_model)
            img["id"] = db_id
            success_count += 1
            adapter.debug("Persisted image %s -> id=%s", img.get("filename"), db_id)
        except Exception as e:
            adapter.warning("Failed to persist image %s: %s", img.get("filename"), e)

    return success_count
```

---

## 4. MINIO UPLOAD - IMAGE_STORAGE_PROCESSOR

### File: backend/processors/image_storage_processor.py (lines 141-279)

```python
async def upload_image(
    self,
    image_path: Path,
    document_id: UUID,
    page_number: int,
    image_type: str = "diagram",
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Upload single image with deduplication

    Args:
        image_path: Path to image file
        document_id: Document UUID
        page_number: Page number
        image_type: Type of image
        metadata: Additional metadata

    Returns:
        Result dict with storage_url
    """
    if not self.is_configured():
        return {
            'success': False,
            'error': 'Storage not configured',
            'storage_url': None,
            'deduplicated': False
        }

    try:
        # 1. Calculate hash
        file_hash = self.calculate_image_hash(image_path)

        # 2. Check if already exists
        existing = await self.check_image_exists(file_hash)

        if existing:
            # Image already exists - just return existing URL
            self.logger.debug(f"Image deduplicated: {file_hash[:8]}... (already exists)")
            return {
                'success': True,
                'storage_url': existing['storage_url'],
                'storage_path': existing['storage_path'],
                'file_hash': file_hash,
                'deduplicated': True,
                'existing_id': existing['id']
            }

        # 3. New image - upload to object storage (MinIO)
        extension = image_path.suffix.lstrip('.')
        is_svg = extension.lower() == 'svg'
        has_png_derivative = bool(metadata.get('has_png_derivative', not is_svg)) if metadata else (not is_svg)
        storage_path = f"svg/{file_hash}.svg" if is_svg else f"{file_hash}.{extension}"

        # UPLOAD TO MINIO
        with open(image_path, 'rb') as f:
            self.storage_client.upload_fileobj(
                f,
                self.bucket_name,
                storage_path,
                ExtraArgs={
                    'Metadata': {
                        'document-id': str(document_id),
                        'page-number': str(page_number),
                        'image-type': image_type,
                        'file-hash': file_hash,
                        'is-vector-graphic': str(is_svg).lower(),
                        'has-png-derivative': str(has_png_derivative).lower(),
                        'upload-timestamp': datetime.utcnow().isoformat()
                    },
                    'ContentType': 'image/svg+xml' if is_svg else (mimetypes.guess_type(image_path)[0] or 'image/png')
                }
            )

        # Generate public URL
        if self.public_url:
            storage_url = f"{self.public_url}/{storage_path}"
        else:
            storage_url = f"{self.endpoint_url}/{self.bucket_name}/{storage_path}"

        svg_storage_url = storage_url if is_svg else (metadata.get('svg_storage_url') if metadata else None)
        if is_svg and metadata and metadata.get('png_storage_url'):
            storage_url = metadata['png_storage_url']

        # 4. Insert to database using DatabaseAdapter
        from backend.core.data_models import ImageModel

        image_model = ImageModel(
            document_id=str(document_id),
            filename=storage_path,
            original_filename=image_path.name,
            storage_path=storage_path,
            storage_url=storage_url,  # <-- NOW SET TO PUBLIC MINIO URL
            svg_storage_url=svg_storage_url,
            original_svg_content=metadata.get('original_svg_content') if metadata else None,
            is_vector_graphic=is_svg,
            has_png_derivative=has_png_derivative,
            file_hash=file_hash,
            file_size=image_path.stat().st_size,
            image_format=extension.lower(),
            page_number=page_number,
            image_type=image_type,
            width_px=metadata.get('width') if metadata else None,
            height_px=metadata.get('height') if metadata else None,
            ai_description=metadata.get('ai_description') if metadata else None,
            ai_confidence=metadata.get('ai_confidence') if metadata else None,
            contains_text=metadata.get('contains_text') if metadata else None,
            ocr_text=metadata.get('ocr_text') if metadata else None,
            ocr_confidence=metadata.get('ocr_confidence') if metadata else None
        )

        if is_svg and hasattr(self.db_client, 'create_image_with_svg'):
            db_id = await self.db_client.create_image_with_svg(image_model)
        else:
            db_id = await self.db_client.create_image(image_model)

        self.logger.debug(f"Uploaded new image: {file_hash[:8]}... -> {storage_path}")

        return {
            'success': True,
            'storage_url': storage_url,
            'storage_path': storage_path,
            'file_hash': file_hash,
            'deduplicated': False,
            'db_id': db_id
        }

    except Exception as e:
        self.logger.error(f"Failed to upload image: {e}")
        return {
            'success': False,
            'error': str(e),
            'storage_url': None,
            'deduplicated': False
        }
```

---

## 5. MINIO CLIENT INITIALIZATION

### File: backend/processors/image_storage_processor.py (lines 70-95)

```python
def __init__(self, database_adapter=None):
    """Initialize image storage processor"""
    self.logger = get_logger()
    self.db_client = database_adapter

    # Object Storage Configuration
    self.access_key = os.getenv('OBJECT_STORAGE_ACCESS_KEY')
    self.secret_key = os.getenv('OBJECT_STORAGE_SECRET_KEY')
    self.endpoint_url = os.getenv('OBJECT_STORAGE_ENDPOINT')
    if not self.endpoint_url:
        raise ValueError("OBJECT_STORAGE_ENDPOINT must be set in .env")
    self.bucket_name = os.getenv('OBJECT_STORAGE_BUCKET_DOCUMENTS')
    self.public_url = os.getenv('OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS')

    # Initialize S3-compatible client (works with MinIO)
    self.storage_client = None
    if all([self.access_key, self.secret_key, self.endpoint_url, self.bucket_name]):
        try:
            self.storage_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(signature_version='s3v4'),
                region_name='auto'
            )
            self.logger.info("S3-compatible storage client initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize storage client: {e}")
    else:
        self.logger.warning("Object storage credentials incomplete - storage disabled")
```

---

## 6. FLOW DIAGRAM

\\\
PDF Document
    |
    v
image_processor._extract_images()  <- Extract raw images
    |
    v
Images saved to temp directory
    |
    v
_extract_image_contexts()  <- CONTEXT EXTRACTION
    |
    +---> ContextExtractionService.extract_image_context()
    |         |
    |         +---> _extract_error_codes(page_text)  <- REGEX SEARCH
    |         |       Returns: ['01.02.03', '44.55.66'] from entire page
    |         |
    |         +---> _extract_products(page_text)
    |         |       Returns: ['C4080', 'C4070']
    |         |
    |         +---> _extract_surrounding_text()
    |         +---> _extract_page_header()
    |         +---> _extract_figure_reference()
    |         +---> _extract_surrounding_paragraphs()
    |
    v
Image dict updated with:
  - related_error_codes: ['01.02.03', '44.55.66']
  - related_products: ['C4080']
  - context_caption: "..."
  - page_header: "..."
    |
    v
_queue_storage_tasks()  <- DATABASE INSERTION
    |
    +---> ImageModel created
    |       - storage_url = "file:///temp/path/img.png"
    |       - related_error_codes = ['01.02.03', '44.55.66']
    |
    +---> database_service.create_image(image_model)
    |       INSERT INTO krai_content.images
    |
    v
IMAGE RECORD IN DATABASE
  id: UUID
  storage_url: file:///temp/...
  related_error_codes: ['01.02.03', '44.55.66']
  page_number: 5
    |
    v
(ASYNC) ImageStorageProcessor.upload_image()  <- MINIO UPLOAD
    |
    +---> calculate_image_hash(image_path)
    |
    +---> check_image_exists(file_hash)  <- DEDUP CHECK
    |
    +---> storage_client.upload_fileobj()  <- BOTO3/MINIO
    |       Bucket: documents
    |       Key: "a1b2c0d0f.png"
    |
    +---> storage_url = "https://minio.example.com/documents/a1b2c0d0f.png"
    |
    +---> database.update_image(image_id, storage_url)
    |       UPDATE krai_content.images
    |       SET storage_url = 'https://...'
    |
    v
FINAL RECORD IN DATABASE
  storage_url: https://minio.example.com/documents/a1b2c0d0f.png
  related_error_codes: ['01.02.03', '44.55.66']  <- UNCHANGED
\\\

---

## SUMMARY

1. **related_error_codes population:**
   - Source: Page text where image is located
   - Method: Regex pattern \d{2}\.\d{2}\.\d{2} applied to entire page
   - Service: ContextExtractionService._extract_error_codes()
   - ALL error codes on page linked to image on that page
   - Set in: image_processor.py _extract_image_contexts() line 1382

2. **storage_url setting:**
   - Initial: "file://{temp_path}" (image_processor.py line 751)
   - Final: "https://minio.../documents/{hash}.png" (image_storage_processor.py line 219)
   - Updated: DB record updated after MinIO upload completes

3. **MinIO Integration:**
   - boto3 S3 client with S3v4 signature
   - Flat storage: {hash}.{extension} (no folder structure)
   - Deduplication by MD5 hash
   - Metadata stored in MinIO object metadata
   - Public URL from OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS env var
