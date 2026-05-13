# API Adapter Usage Guide

## Übersicht

Dieses Dokument beschreibt die Nutzung des Database Adapter Patterns in der KRAI-API.

## Dependency Injection

### Database Adapter abrufen

```python
from fastapi import Depends
from services.database_adapter import DatabaseAdapter
from api.app import get_database_adapter

@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    adapter: DatabaseAdapter = Depends(get_database_adapter)
):
    doc = await adapter.get_document(document_id)
    return doc
```

### Legacy Supabase Client (für RPC)

Für Code, der Supabase-spezifische Features benötigt (z.B. RPC, StageTracker):

```python
from api.app import get_legacy_supabase_client
from fastapi import HTTPException

@router.get("/stages/{document_id}")
async def get_stages(
    document_id: str,
    adapter: DatabaseAdapter = Depends(get_database_adapter)
):
    # get_legacy_supabase_client() ist eine Funktion, kein Dependency
    legacy_client = get_legacy_supabase_client()

    if not legacy_client:
        raise HTTPException(
            status_code=501,
            detail="Stage tracking requires Supabase (not available in PostgreSQL-only mode)"
        )

    tracker = StageTracker(legacy_client)
    return tracker.get_stage_status(document_id)
```

**Wichtig:** `get_legacy_supabase_client()` ist eine normale Funktion (kein Dependency), die `None` zurückgibt wenn kein Supabase-Client verfügbar ist (z.B. bei reinem PostgreSQL-Betrieb).

## Adapter-Methoden

### Dokumente

```python
# Dokument abrufen
doc = await adapter.get_document(document_id)

# Dokument erstellen
from core.data_models import DocumentModel
doc_model = DocumentModel(
    filename="manual.pdf",
    file_size=1024000,
    file_hash="abc123",
    document_type="service_manual"
)
doc_id = await adapter.create_document(doc_model)

# Dokument aktualisieren
await adapter.update_document(doc_id, {
    "processing_status": "completed"
})
```

### Rohe SQL-Queries

```python
# SELECT-Query
query = """
    SELECT id, filename, processing_status
    FROM krai.documents
    WHERE manufacturer_id = %s
    ORDER BY created_at DESC
    LIMIT %s
"""
results = await adapter.execute_query(query, [manufacturer_id, 10])

# INSERT-Query
query = """
    INSERT INTO krai.audit_log (entity_type, entity_id, action, user_id)
    VALUES (%s, %s, %s, %s)
    RETURNING id
"""
result = await adapter.execute_query(
    query,
    ["document", doc_id, "created", user_id]
)
log_id = result[0]['id']
```

### RPC-Calls (Supabase)

```python
# Prüfe RPC-Unterstützung
if hasattr(adapter, 'rpc'):
    # Supabase RPC
    result = await adapter.rpc('match_documents', {
        'query_embedding': embedding,
        'match_count': 10,
        'filter': {'manufacturer_id': mfr_id}
    })
else:
    # Fallback zu Adapter-Methode
    result = await adapter.search_embeddings(
        query_embedding=embedding,
        limit=10
    )
```

## Error Handling

```python
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    adapter: DatabaseAdapter = Depends(get_database_adapter)
):
    try:
        doc = await adapter.get_document(document_id)
        if not doc:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )
        return doc
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

## Testing

### Unit Tests mit Mock-Adapter

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.database_adapter import DatabaseAdapter

@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=DatabaseAdapter)
    adapter.get_document = AsyncMock(return_value={
        'id': 'test-id',
        'filename': 'test.pdf'
    })
    return adapter

@pytest.mark.asyncio
async def test_get_document(mock_adapter):
    doc = await mock_adapter.get_document('test-id')
    assert doc['filename'] == 'test.pdf'
```

### Integration Tests

```python
import pytest
from services.database_factory import create_database_adapter

@pytest.fixture
async def adapter():
    adapter = create_database_adapter()
    await adapter.connect()
    yield adapter
    # Cleanup

@pytest.mark.asyncio
async def test_document_crud(adapter):
    # Create
    doc_model = DocumentModel(...)
    doc_id = await adapter.create_document(doc_model)

    # Read
    doc = await adapter.get_document(doc_id)
    assert doc is not None

    # Update
    await adapter.update_document(doc_id, {'status': 'completed'})

    # Verify
    updated_doc = await adapter.get_document(doc_id)
    assert updated_doc['status'] == 'completed'
```

## Best Practices

1. **Nutze Adapter-Methoden**: Bevorzuge `adapter.get_document()` statt roher SQL
2. **Async/Await**: Alle Adapter-Methoden sind async - vergiss nicht `await`
3. **Error Handling**: Fange Exceptions ab und gebe aussagekräftige HTTP-Fehler zurück
4. **Logging**: Logge Adapter-Operationen für Debugging
5. **Schema-Präfix**: Nutze `krai.` für PostgreSQL-Tabellen in SQL-Queries
6. **Parametrisierte Queries**: Nutze `%s` Platzhalter statt String-Interpolation

## Häufige Fehler

### Fehler: "coroutine was never awaited"

**Problem:** `await` fehlt bei Adapter-Aufruf

```python
# Falsch
doc = adapter.get_document(doc_id)

# Richtig
doc = await adapter.get_document(doc_id)
```

### Fehler: "relation 'documents' does not exist"

**Problem:** Schema-Präfix fehlt

```python
# Falsch
query = "SELECT * FROM documents"

# Richtig
query = "SELECT * FROM krai.documents"
```

### Fehler: "execute_query() not implemented"

**Problem:** Adapter unterstützt keine rohen SQL-Queries

**Lösung:** Nutze Adapter-Methoden oder aktiviere direkte PostgreSQL-Verbindung

## Weitere Informationen

- [Adapter Migration Guide](../../docs/ADAPTER_MIGRATION.md)
- [Database Adapter Interface](../services/database_adapter.py)
- [Database Factory](../services/database_factory.py)
