# Storage Processor - MinIO Object Storage Integration

## 🎯 Overview

Stage 6 of the processing pipeline handles document storage in MinIO (S3-compatible object storage).

---

## ✨ Features

- ✅ **Upload documents to object storage** with organized paths
- ✅ **Generate presigned URLs** for temporary access
- ✅ **Download documents** from object storage
- ✅ **Delete documents** with cleanup
- ✅ **List documents** with filtering
- ✅ **Storage statistics** (total size, by type)
- ✅ **Stage tracking integration** for progress monitoring
- ✅ **File organization** by manufacturer/year/type

---

## 📁 File Organization

Documents are stored in organized paths:

```
Format: {document_type}/{manufacturer}/{year}/{document_id}/{filename}

Examples:
  service_manual/hp/2024/abc-123-def/LaserJet_M234_SM.pdf
  service_manual/lexmark/2024/xyz-789/CX833_Service_Manual.pdf
  parts_catalog/konica_minolta/2024/aaa-bbb/AccurioPress_Parts.pdf
```

---

## ⚙️ Configuration

### Environment Variables (.env):

```env
# Object Storage (MinIO)
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=your_secret_key
OBJECT_STORAGE_BUCKET_DOCUMENTS=krai-documents-images
```

### Getting MinIO Credentials:

1. Open your MinIO Console
2. Create or use an existing access key
3. Ensure bucket access allows required read/write operations
4. Copy access key and secret key
6. Create a bucket (e.g., "krai-documents")

---

## 🚀 Usage

### Basic Upload:

```python
from backend.processors.storage_processor import StorageProcessor
from uuid import uuid4
from pathlib import Path

# Initialize
storage = StorageProcessor()

# Check configuration
if storage.is_configured():
    # Upload document
    result = storage.upload_document(
        document_id=uuid4(),
        file_path=Path("document.pdf"),
        manufacturer="HP",
        document_type="service_manual",
        metadata={'version': '1.0'}
    )

    if result['success']:
        print(f"Uploaded to: {result['storage_url']}")
        print(f"Storage path: {result['storage_path']}")
```

### Generate Presigned URL:

```python
# Generate temporary access URL (1 hour)
url = storage.generate_presigned_url(
    storage_path=result['storage_path'],
    expiration=3600  # seconds
)

print(f"Temporary URL: {url}")
# Share this URL for temporary access
```

### Download Document:

```python
# Download from object storage
success = storage.download_document(
    storage_path="service_manual/hp/2024/abc-123/manual.pdf",
    local_path=Path("downloads/manual.pdf")
)

if success:
    print("Downloaded successfully!")
```

### List Documents:

```python
# List all documents
documents = storage.list_documents(max_keys=100)

for doc in documents:
    print(f"{doc['key']} - {doc['size']} bytes")

# List with prefix filter
hp_documents = storage.list_documents(
    prefix="service_manual/hp/",
    max_keys=50
)
```

### Get Statistics:

```python
stats = storage.get_storage_statistics()

print(f"Total Documents: {stats['total_documents']}")
print(f"Total Size: {stats['total_size_mb']} MB")

for doc_type, info in stats['by_type'].items():
    print(f"{doc_type}: {info['count']} documents ({info['size'] / (1024*1024):.1f} MB)")
```

---

## 🧪 Testing

### Run Tests:

```bash
cd backend
python processors/test_storage.py
```

### Test Coverage:

1. ✅ **Configuration Check** - Validates object storage credentials
2. ✅ **Storage Statistics** - Gets bucket info
3. ✅ **Upload Document** - Uploads test PDF
4. ✅ **Presigned URL** - Generates and validates URL
5. ✅ **Download Document** - Downloads and verifies file
6. ✅ **List Documents** - Lists bucket contents

---

## 🔧 Integration with Pipeline

### With Stage Tracker:

```python
from backend.processors.storage_processor import StorageProcessor
from supabase import create_client
import os

# Initialize with Supabase for stage tracking
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# (historical: supabase_client parameter removed)
storage = StorageProcessor()

# Upload will automatically update stage_status
result = storage.upload_document(
    document_id=document_id,
    file_path=pdf_path,
    manufacturer="HP",
    document_type="service_manual"
)

# Stage tracking automatically records:
# - Stage start time
# - Upload progress
# - Storage path & URL
# - File size
# - Completion time or error
```

### In Main Pipeline:

```python
class DocumentPipeline:
    def __init__(self):
        # (historical: supabase_client parameter removed)
        self.storage = StorageProcessor()

    def process_document(self, document_id, file_path):
        # ... text extraction, product extraction, etc.

        # Stage 6: Storage
        storage_result = self.storage.upload_document(
            document_id=document_id,
            file_path=file_path,
            manufacturer=extracted_manufacturer,
            document_type="service_manual"
        )

        if storage_result['success']:
            # Update database with storage URL
            self.supabase.table("documents").update({
                'storage_url': storage_result['storage_url'],
                'storage_path': storage_result['storage_path']
            }).eq('id', document_id).execute()

        # Continue to next stages...
```

---

## 📊 Storage Best Practices

### 1. File Naming

✅ **Good:**
- `LaserJet_M234_Service_Manual.pdf`
- `CX833_Parts_Catalog_2024.pdf`

❌ **Bad:**
- `document (1).pdf`
- `temp_file_123.pdf`

### 2. Metadata

Always include metadata:
```python
metadata = {
    'document_type': 'service_manual',
    'manufacturer': 'HP',
    'model': 'LaserJet M234',
    'version': '1.0',
    'page_count': 450,
    'uploaded_by': 'system'
}
```

### 3. Organization

Use manufacturer-based organization for easy filtering:
```
service_manual/hp/         → All HP service manuals
service_manual/lexmark/    → All Lexmark manuals
parts_catalog/hp/          → HP parts catalogs
```

### 4. Presigned URLs

- Use short expiration times (1-24 hours)
- Generate new URLs for each access
- Don't store presigned URLs in database
- Log URL generation for security

---

## 🔒 Security

### Access Control:

- ✅ Use presigned URLs for temporary access
- ✅ Keep object storage credentials in `.env` (never commit)
- ✅ Use separate buckets for different access levels
- ✅ Enable bucket versioning for recovery
- ✅ Set up lifecycle rules for old files

### Bucket Policies:

Recommended bucket setup:
- **Private by default** - No public access
- **Presigned URLs only** - Temporary access
- **CORS enabled** - If serving to frontend
- **Versioning enabled** - Backup & recovery

---

## 📈 Performance

### Upload Performance:

- **Small files (<10MB)**: ~1-2 seconds
- **Medium files (10-100MB)**: ~5-15 seconds
- **Large files (100-500MB)**: ~30-120 seconds

Upload time depends on:
- File size
- Network speed
- storage region proximity
- Concurrent uploads

### Optimization Tips:

1. **Multipart uploads** for files >100MB (future enhancement)
2. **Compression** before upload (if beneficial)
3. **Parallel uploads** for multiple files
4. **Chunked uploads** for progress tracking

---

## 🐛 Troubleshooting

### "Object storage not configured"

✅ **Solution:** Set environment variables in `.env`:
```env
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=your_key
OBJECT_STORAGE_SECRET_KEY=your_secret
```

### "Access Denied" errors

✅ **Solutions:**
- Check API token has "Object Read & Write" permissions
- Verify bucket name is correct
- Check endpoint URL matches your account

### "Bucket does not exist"

✅ **Solution:** Create bucket in MinIO

### Slow uploads

✅ **Solutions:**
- Check network speed
- Use a closer storage region
- Implement multipart upload for large files
- Check if compression would help

---

## 🚀 Future Enhancements

Planned features:
- [ ] Multipart uploads for large files (>100MB)
- [ ] Upload progress callbacks
- [ ] Automatic compression
- [ ] Duplicate detection in object storage
- [ ] Lifecycle management (auto-delete old files)
- [ ] CDN integration for faster downloads
- [ ] Image optimization for thumbnails
- [ ] Batch operations (upload/download multiple)

---

## 📝 API Reference

### `StorageProcessor()`

```python
storage = StorageProcessor(
    # (historical: supabase_client parameter removed)
    bucket_name=None,           # Optional: Override bucket
    endpoint_url=None,          # Optional: Override endpoint
    access_key=None,            # Optional: Override key
    secret_key=None             # Optional: Override secret
)
```

### `upload_document()`

```python
result = storage.upload_document(
    document_id: UUID,          # Document UUID
    file_path: Path,            # Local file path
    manufacturer: str = None,   # Manufacturer name
    document_type: str = "service_manual",
    metadata: Dict = None       # Custom metadata
) -> Dict[str, Any]
```

**Returns:**
```python
{
    'success': True,
    'storage_url': 'https://...',
    'storage_path': 'service_manual/hp/2024/...',
    'bucket': 'krai-documents',
    'file_size': 12345678
}
```

### `generate_presigned_url()`

```python
url = storage.generate_presigned_url(
    storage_path: str,          # Path in bucket
    expiration: int = 3600      # Seconds (default: 1 hour)
) -> Optional[str]
```

### `download_document()`

```python
success = storage.download_document(
    storage_path: str,          # Path in bucket
    local_path: Path            # Download destination
) -> bool
```

### `list_documents()`

```python
documents = storage.list_documents(
    prefix: str = None,         # Filter by prefix
    max_keys: int = 1000        # Max results
) -> List[Dict]
```

### `get_storage_statistics()`

```python
stats = storage.get_storage_statistics() -> Dict[str, Any]
```

**Returns:**
```python
{
    'configured': True,
    'total_documents': 150,
    'total_size_bytes': 52428800,
    'total_size_mb': 50.0,
    'by_type': {
        'service_manual': {'count': 100, 'size': 41943040},
        'parts_catalog': {'count': 50, 'size': 10485760}
    },
    'bucket': 'krai-documents'
}
```

---

## ✅ Checklist

Before deploying to production:

- [ ] Object storage credentials configured in `.env`
- [ ] Bucket created in MinIO
- [ ] API token has correct permissions
- [ ] Test upload/download works
- [ ] Presigned URLs generate correctly
- [ ] Stage tracking integrated
- [ ] Error handling tested
- [ ] Cleanup policies configured
- [ ] Monitoring set up
- [ ] Backup strategy defined

---

**Stage 6: Storage Processor - Ready for Production! 🚀**
