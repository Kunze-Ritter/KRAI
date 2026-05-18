# KRAI Image Processing Pipeline - Complete Analysis

## 1. IMAGE EXTRACTION & STORAGE (image_processor.py)

### Image Extraction (_extract_images method, lines 576-664)
- Uses PyMuPDF (fitz) to extract images from PDF
- Saves images to local temp directory
- Creates image dict with metadata:
  - path, filename, page_number, width, height, format, size_bytes, bbox
  - extracted_at timestamp

### Image Context Extraction (_extract_image_contexts, lines 1333-1402)
Uses ContextExtractionService.extract_image_context() which:
- Extracts surrounding text (±200 chars)
- Extracts figure references (Figure X.X, Abb., etc.)
- Extracts page headers
- **EXTRACTS ERROR CODES** via regex pattern \d{2}\.\d{2}\.\d{2}
- Extracts product codes (C4080, AccurioPress, etc.)
- Extracts surrounding paragraphs

### Database Persistence (_queue_storage_tasks, lines 713-787)
Converts image dict to ImageModel with:
- storage_url = "file://{temp_path}" (local file path)
- storage_path = temp_path
- related_error_codes = img.get("related_error_codes") or []
- related_products = img.get("related_products") or []
- surrounding_paragraphs = img.get("surrounding_paragraphs") or []

Calls: await self.database_service.create_image(image_model)

## 2. CONTEXT EXTRACTION SERVICE (context_extraction_service.py)

### Error Code Extraction Pattern (line 74)
error_code_pattern = re.compile(r'\d{2}\.\d{2}\.\d{2}')
Matches: 01.02.03, 44.55.66, etc.

### extract_image_context Method (lines 84-156)
Returns dict with:
{
    'context_caption': None,
    'figure_reference': None,
    'page_header': None,
    'related_error_codes': [],  # <-- POPULATED HERE
    'related_products': [],
    'surrounding_paragraphs': []
}

Related error codes are extracted from the ENTIRE PAGE TEXT using:
context_data['related_error_codes'] = self._extract_error_codes(page_text)

### _extract_error_codes Method (lines 395-409)
matches = self.error_code_pattern.findall(text)
return list(set(matches))  # Remove duplicates

This searches the FULL PAGE TEXT, not just near the image.
All error codes on that page are linked to ALL images on that page.

## 3. IMAGE STORAGE PROCESSOR (image_storage_processor.py)

This is a SEPARATE component for MinIO uploads. Key features:

### Upload with Deduplication (upload_image, lines 141-279)
1. Calculate MD5 hash of image
2. Check if image already exists in DB via hash
3. If exists: Return existing storage_url (deduplicated=True)
4. If new: Upload to MinIO + Insert to DB

### MinIO Configuration (lines 70-95)
self.access_key = os.getenv('OBJECT_STORAGE_ACCESS_KEY')
self.secret_key = os.getenv('OBJECT_STORAGE_SECRET_KEY')
self.endpoint_url = os.getenv('OBJECT_STORAGE_ENDPOINT')
self.bucket_name = os.getenv('OBJECT_STORAGE_BUCKET_DOCUMENTS')
self.public_url = os.getenv('OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS')

Uses boto3 S3 client (compatible with MinIO):
self.storage_client = boto3.client(
    's3',
    endpoint_url=self.endpoint_url,
    aws_access_key_id=self.access_key,
    aws_secret_access_key=self.secret_key,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

### Upload to MinIO (lines 197-227)
storage_path = f"svg/{file_hash}.svg" if is_svg else f"{file_hash}.{extension}"

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

### Database Record Creation (lines 228-258)
image_model = ImageModel(
    storage_url=storage_url,  # PUBLIC URL
    storage_path=storage_path,  # S3 object key
    file_hash=file_hash,  # MD5 hash
    page_number=page_number,
    image_type=image_type,
    related_error_codes=[]  # NOT SET BY ImageStorageProcessor
)

## 4. OBJECT STORAGE SERVICE (object_storage_service.py)

### Generic S3-Compatible Service (lines 29-365)
Supports MinIO, AWS S3, Wasabi, Backblaze B2
Used by: upload_processor, parts_processor, etc.

### Upload Methods
- upload_svg_file() - SVG with content-type: image/svg+xml
- upload_image() - General image upload
- Both support deduplication via check_duplicate()

### Storage Path Generation (lines 180-197)
prefix_map = {
    'document_images': 'images',
    'error_images': 'error',
    'parts_images': 'parts'
}
storage_path = f"{prefix}/{file_hash}"  # or just {file_hash} for dedicated buckets

### Public URL Resolution (lines 204-220)
base_url = self.public_urls.get('images') or self.public_urls['documents']
public_url = f"{base_url}/{storage_path}"

## 5. FLOW SUMMARY

### Image Pipeline:
1. image_processor.py extracts images from PDF -> temp files
2. _extract_image_contexts() enriches with context:
   - Calls ContextExtractionService.extract_image_context()
   - EXTRACTS related_error_codes from PAGE TEXT (regex pattern)
   - Updates image dict with all context fields
3. _queue_storage_tasks() persists to krai_content.images with:
   - storage_url = "file://{temp_path}"
   - related_error_codes = extracted from page
4. ImageStorageProcessor (separate, async task) uploads to MinIO:
   - Calculates hash, checks dedup
   - Uploads to MinIO bucket
   - Updates DB with real storage_url and storage_path

### Error Code Linking:
- **Source**: Page text on the same page as the image
- **Pattern**: \d{2}\.\d{2}\.\d{2} (e.g., 01.02.03)
- **Extraction**: Done by ContextExtractionService._extract_error_codes()
- **Scope**: ALL error codes found on page are linked to image
- **DB Field**: krai_content.images.related_error_codes (text[] array)
- **Flow**: image_processor -> context_service -> database

### Storage URL Setting:
- **Initial**: storage_url = "file://{temp_path}" (image_processor.py line 751)
- **Final**: storage_url = f"{public_url}/{storage_path}" (image_storage_processor.py line 219)
- **Public URL**: Comes from OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS env var
- **Storage Path**: "{file_hash}.{extension}" (flat structure in MinIO)

## 6. KEY ENVIRONMENT VARIABLES

Object Storage:
- OBJECT_STORAGE_ENDPOINT: MinIO/S3 endpoint URL
- OBJECT_STORAGE_ACCESS_KEY: AWS/MinIO access key
- OBJECT_STORAGE_SECRET_KEY: AWS/MinIO secret key
- OBJECT_STORAGE_BUCKET_DOCUMENTS: Bucket name (default: documents)
- OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS: Public URL prefix

Image Processing:
- ENABLE_CONTEXT_EXTRACTION: Enable context extraction (true/false)
- OCR_PREPROCESSING_ENABLED: Enable OCR preprocessing
- VISION_MAX_IMAGE_MB: Max image size for Vision AI

## 7. DATABASE SCHEMA (krai_content.images)

Key columns set by image_processor:
- id (generated by DB)
- document_id: Document UUID
- storage_url: File path initially, becomes public URL after MinIO upload
- storage_path: File path in temp dir, later becomes S3 object key
- file_hash: SHA256 (computed by image_processor.py, line 739)
- page_number: Page where image was found
- image_type: Type (diagram, table, photo, chart, etc.)
- related_error_codes: TEXT[] array of error codes found on page
- related_products: TEXT[] array of products found on page
- context_caption: Surrounding text
- page_header: Header from page
- figure_reference: Figure reference if found
- ai_description: LLaVA vision AI description
- ocr_text: Tesseract OCR results
- contains_text: Boolean if text detected
