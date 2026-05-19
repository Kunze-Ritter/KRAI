"""
PostgreSQL Database Adapter

Pure asyncpg implementation for direct PostgreSQL connections.
Pure PostgreSQL implementation - uses only asyncpg for database access.
"""

import json
import logging
import re
from datetime import datetime
from types import SimpleNamespace
from typing import Any

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    raise ImportError("asyncpg not available. Please install: pip install asyncpg")

from backend.core.data_models import (
    AuditLogModel,
    ChunkModel,
    DocumentModel,
    EmbeddingModel,
    ErrorCodeModel,
    ImageModel,
    IntelligenceChunkModel,
    ManufacturerModel,
    PrintDefectModel,
    ProcessingQueueModel,
    ProductModel,
    ProductSeriesModel,
    SearchAnalyticsModel,
)

from .database_adapter import DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):
    """
    PostgreSQL Database Adapter

    Pure asyncpg implementation for direct PostgreSQL connections.
    Uses schema prefix for multi-tenant support (e.g., krai_core, krai_content).
    """

    # Regex patterns for placeholder conversion
    _NAMED_PARAM_RE = re.compile(r"(?<!:):(?!:)([a-zA-Z0-9_]+)")
    _POSITIONAL_PARAM_RE = re.compile(r"%s")

    def __init__(self, postgres_url: str, schema_prefix: str = "krai"):
        """Initialize PostgreSQL adapter with connection string."""
        super().__init__()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", schema_prefix):
            raise ValueError(
                f"Invalid schema_prefix '{schema_prefix}': must start with a letter and contain only letters, digits, or underscores."
            )
        self.postgres_url = postgres_url
        self.schema_prefix = schema_prefix
        self.pg_pool: asyncpg.Pool | None = None

        # Query cache: original_query -> (formatted_query, param_names_or_is_positional)
        self._query_cache: dict[str, tuple[str, Any]] = {}

        # Schema names
        self._core_schema = f"{schema_prefix}_core"
        self._content_schema = f"{schema_prefix}_content"
        self._intelligence_schema = f"{schema_prefix}_intelligence"
        self._parts_schema = f"{schema_prefix}_parts"
        self._system_schema = f"{schema_prefix}_system"
        self._users_schema = f"{schema_prefix}_users"

        self.logger = logging.getLogger("krai.database.postgresql")
        self.logger.info(f"PostgreSQLAdapter initialized with schema prefix: {schema_prefix}")

    async def initialize(self):
        """Initialize database connection pool."""
        try:
            self.pg_pool = await asyncpg.create_pool(self.postgres_url, min_size=2, max_size=10, command_timeout=60)
            self.logger.info("PostgreSQL connection pool initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise

    def _ensure_pool(self) -> asyncpg.Pool:
        if self.pg_pool is None:
            raise RuntimeError("PostgreSQL connection pool is not initialized. Call connect() first.")
        return self.pg_pool

    def _prepare_query(self, query: str, params: Any | None) -> tuple[str, list[Any]]:
        """Convert named (":param") or psycopg-style ("%s") placeholders to asyncpg positional ones."""

        if params is None:
            return query, []

        # Handle sequence parameters (assume positional order)
        if isinstance(params, list | tuple):
            values = list(params)
            # Convert psycopg %s placeholders to $1, $2, ...
            if "%s" in query:
                # Check cache
                if query in self._query_cache:
                    cached_query, cache_data = self._query_cache[query]
                    if cache_data is True:  # True indicates positional mapping
                        return cached_query, values

                index = 0

                def repl(_):
                    nonlocal index
                    index += 1
                    return f"${index}"

                formatted_query = self._POSITIONAL_PARAM_RE.sub(repl, query)
                # Store in cache
                if len(self._query_cache) < 1000:
                    self._query_cache[query] = (formatted_query, True)
                return formatted_query, values

            return query, values

        # Handle single scalar parameter
        if not isinstance(params, dict):
            # Convert %s to $1 if present
            if "%s" in query:
                # Check cache
                if query in self._query_cache:
                    cached_query, cache_data = self._query_cache[query]
                    if cache_data is True:  # True indicates positional mapping
                        return cached_query, [params]

                # Replace first %s with $1
                formatted_query = query.replace("%s", "$1", 1)
                # Store in cache
                if len(self._query_cache) < 1000:
                    self._query_cache[query] = (formatted_query, True)
                return formatted_query, [params]
            return query, [params]

        # Handle named parameters (dict)
        # Check cache
        if query in self._query_cache:
            formatted_query, param_names = self._query_cache[query]
            if isinstance(param_names, list):
                try:
                    return formatted_query, [params[name] for name in param_names]
                except KeyError:
                    # In case params changed keys for same query, re-prepare
                    pass

        # Named parameters (ignore PostgreSQL type casts like '::text', '::uuid')
        # We only treat a single ':' followed by an identifier as a parameter,
        # not a double-colon type cast.
        param_names: list[str] = []
        index_map: dict[str, int] = {}
        values: list[Any] = []

        def replace(match: re.Match) -> str:
            name = match.group(1)
            if name not in params:
                raise KeyError(f"Parameter '{name}' not provided for query")
            if name not in index_map:
                index_map[name] = len(param_names) + 1
                param_names.append(name)
                values.append(params[name])
            return f"${index_map[name]}"

        formatted_query = self._NAMED_PARAM_RE.sub(replace, query)

        # Store in cache
        if len(self._query_cache) >= 1000:
            self._query_cache.clear()
        self._query_cache[query] = (formatted_query, param_names)

        return formatted_query, values

    async def fetch_one(self, query: str, params: Any | None = None):
        """Execute query and return a single row."""
        pool = self._ensure_pool()
        formatted_query, values = self._prepare_query(query, params)
        async with pool.acquire() as conn:
            return await conn.fetchrow(formatted_query, *values)

    async def fetch_all(self, query: str, params: Any | None = None) -> list[Any]:
        """Execute query and return all rows."""
        pool = self._ensure_pool()
        formatted_query, values = self._prepare_query(query, params)
        async with pool.acquire() as conn:
            return await conn.fetch(formatted_query, *values)

    async def execute_query(self, query: str, params: Any | None = None):
        """Execute arbitrary SQL query supporting SELECT and mutation statements."""
        pool = self._ensure_pool()
        formatted_query, values = self._prepare_query(query, params)
        lower_query = formatted_query.lstrip().lower()

        async with pool.acquire() as conn:
            # Return rows for SELECT/RETURNING/CTE statements
            if lower_query.startswith(("select", "with")) or " returning " in lower_query:
                rows = await conn.fetch(formatted_query, *values)
                return [dict(row) for row in rows]

            status = await conn.execute(formatted_query, *values)

            # Extract rowcount from command tag (e.g., "UPDATE 1")
            rowcount = 0
            try:
                parts = status.split()
                if parts and parts[-1].isdigit():
                    rowcount = int(parts[-1])
            except Exception:  # pragma: no cover - fallback safety
                rowcount = 0

            return SimpleNamespace(status=status, rowcount=rowcount)

    async def rpc(self, function_name: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a PostgreSQL stored procedure.

        Args:
            function_name: Name of the stored procedure (with schema prefix)
            params: Named parameters for the procedure

        Returns:
            Procedure result
        """
        if not self.pg_pool:
            await self.connect()

        # Build function call with named parameters
        list(params.keys()) if params else []
        param_values = list(params.values()) if params else []

        # Create placeholders: $1, $2, $3, ...
        placeholders = ", ".join([f"${i+1}" for i in range(len(param_values))])

        # Build query: SELECT * FROM schema.function_name($1, $2, ...)
        # If function_name already has schema prefix, use it as-is
        if "." in function_name:
            query = f"SELECT * FROM {function_name}({placeholders})"
        else:
            query = f"SELECT * FROM {self.schema_prefix}.{function_name}({placeholders})"

        async with self.pg_pool.acquire() as conn:
            try:
                rows = await conn.fetch(query, *param_values)

                # Return single value if only one row and one column
                if len(rows) == 1 and len(rows[0]) == 1:
                    return rows[0][0]

                # Return list of dicts for multiple rows
                return [dict(row) for row in rows]

            except Exception as e:
                self.logger.error(f"RPC call failed: {function_name}")
                self.logger.error(f"Params: {params}")
                self.logger.error(f"Error: {e}")
                raise

    def _prepare_insert(self, data: dict[str, Any]) -> tuple[list[str], list[str], list[Any]]:
        columns = list(data.keys())
        placeholders = [f"${idx + 1}" for idx in range(len(columns))]
        # asyncpg requires JSONB dict values as JSON strings;
        # list values are PostgreSQL arrays and must stay as native Python lists.
        values = [json.dumps(v) if isinstance(v, dict) else v for v in (data[column] for column in columns)]
        return columns, placeholders, values

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{v:.8f}" for v in values) + "]"

    async def connect(self) -> None:
        """Establish PostgreSQL connection pool"""
        try:
            self.pg_pool = await asyncpg.create_pool(self.postgres_url, min_size=2, max_size=10, command_timeout=60)
            self.logger.info("Connected to PostgreSQL database (asyncpg pool)")
            await self.test_connection()
        except Exception as e:
            self.logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise RuntimeError(f"Cannot connect to PostgreSQL database: {e}")

    async def disconnect(self) -> None:
        """Close PostgreSQL connection pool"""
        if self.pg_pool is not None:
            await self.pg_pool.close()
            self.pg_pool = None
            self.logger.info("PostgreSQL connection pool closed")

    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            if self.pg_pool is None:
                raise RuntimeError("Database pool not connected")

            async with self.pg_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                self.logger.info("PostgreSQL connection test successful")
                return True
        except Exception as e:
            self.logger.warning(f"PostgreSQL connection test failed: {e}")
            return False

    # Document Operations
    async def create_document(self, document: DocumentModel) -> str:
        """Create a new document"""
        async with self.pg_pool.acquire() as conn:
            document_id = await conn.fetchval(
                f"""
                INSERT INTO {self.schema_prefix}_core.documents
                (filename, file_size, file_hash, document_type, language, processing_status, storage_path, storage_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                document.filename,
                document.file_size,
                document.file_hash,
                document.document_type,
                document.language,
                document.processing_status,
                getattr(document, "storage_path", None),
                getattr(document, "storage_url", None),
            )
            self.logger.info(f"Created document {document_id}")
            return str(document_id)

    async def get_document(self, document_id: str) -> DocumentModel | None:
        """Get document by ID"""
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(f"SELECT * FROM {self.schema_prefix}_core.documents WHERE id = $1", document_id)
            if not row:
                return None

            # Normalize row for Pydantic DocumentModel
            row_dict = dict(row)

            # Ensure UUID fields are strings (asyncpg returns UUID objects)
            for uuid_field in ("id", "manufacturer_id", "product_id", "series_id"):
                if row_dict.get(uuid_field) is not None and not isinstance(row_dict[uuid_field], str):
                    row_dict[uuid_field] = str(row_dict[uuid_field])

            # Drop unknown columns so Pydantic doesn't raise validation errors
            known_fields = DocumentModel.model_fields.keys()
            row_dict = {k: v for k, v in row_dict.items() if k in known_fields}

            # Ensure models is always a list (database may store NULL)
            if "models" in row_dict and row_dict["models"] is None:
                row_dict["models"] = []

            return DocumentModel(**row_dict)

    async def get_document_by_hash(self, file_hash: str) -> dict[str, Any] | None:
        """Get document by file hash for deduplication"""
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self.schema_prefix}_core.documents WHERE file_hash = $1", file_hash
            )
            return dict(row) if row else None

    async def update_document(self, document_id: str, updates: dict[str, Any]) -> bool:
        """Update document"""
        # Build dynamic UPDATE query
        set_clauses = [f"{key} = ${i+2}" for i, key in enumerate(updates.keys())]
        query = f"""
            UPDATE {self.schema_prefix}_core.documents
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = $1
        """

        async with self.pg_pool.acquire() as conn:
            await conn.execute(query, document_id, *updates.values())
            self.logger.info(f"Updated document {document_id}")
            return True

    async def get_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Get all chunks for a document (alias for get_intelligence_chunks_by_document)"""
        return await self.get_intelligence_chunks_by_document(document_id)

    async def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """Get a single chunk by ID, preferring intelligence chunks."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._intelligence_schema}.chunks WHERE id = $1::uuid LIMIT 1",
                chunk_id,
            )
            if row:
                return dict(row)

            # Backward-compatible fallback for legacy content chunks.
            legacy_row = await conn.fetchrow(
                f"SELECT * FROM {self._content_schema}.chunks WHERE id = $1::uuid LIMIT 1",
                chunk_id,
            )
            return dict(legacy_row) if legacy_row else None

    async def get_intelligence_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Get all intelligence chunks for a document"""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM krai_intelligence.chunks WHERE document_id = $1 ORDER BY chunk_index", document_id
            )
            return [dict(row) for row in rows]

    async def update_chunk(
        self,
        chunk_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        char_count: int | None = None,
    ) -> bool:
        """Update chunk content and/or metadata."""
        if content is None and metadata is None:
            return False
        pool = self._ensure_pool()
        set_parts = []
        params = []
        idx = 1
        if content is not None:
            set_parts.append(f"text_chunk = ${idx}")
            params.append(content)
            idx += 1
        if metadata is not None:
            set_parts.append(f"metadata = ${idx}::jsonb")
            params.append(json.dumps(metadata, ensure_ascii=False))
            idx += 1
        set_parts.append("updated_at = NOW()")
        params.append(chunk_id)
        sql = f"UPDATE {self._intelligence_schema}.chunks " f"SET {', '.join(set_parts)} WHERE id = ${idx}::uuid"
        async with pool.acquire() as conn:
            result = await conn.execute(sql, *params)
            updated = result.upper().startswith("UPDATE")
            if updated:
                self.logger.info(f"Updated chunk {chunk_id}")
            return updated

    async def insert_chunk(self, chunk_data: dict[str, Any]) -> str:
        """Insert a text chunk into krai_intelligence.chunks.

        Expected keys in chunk_data:
        - document_id (UUID or str)
        - text_chunk (str)
        - chunk_index (int)
        - page_start (int | None)
        - page_end (int | None)
        - fingerprint (str)
        - metadata (dict)
        """
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            chunk_id = await conn.fetchval(
                f"""
                INSERT INTO {self._intelligence_schema}.chunks
                    (document_id, text_chunk, chunk_index, page_start, page_end, fingerprint, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING id
                """,
                chunk_data["document_id"],
                chunk_data["text_chunk"],
                chunk_data["chunk_index"],
                chunk_data.get("page_start"),
                chunk_data.get("page_end"),
                chunk_data["fingerprint"],
                json.dumps(chunk_data.get("metadata") or {}, ensure_ascii=False),
            )
            self.logger.info(f"Created intelligence chunk {chunk_id}")
            return str(chunk_id)

    async def create_manufacturer(self, manufacturer: ManufacturerModel) -> str:
        pool = self._ensure_pool()
        manufacturer_data = manufacturer.model_dump(mode="python", exclude_none=True)
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                f"SELECT id FROM {self._core_schema}.manufacturers WHERE LOWER(name) = LOWER($1) LIMIT 1",
                manufacturer.name,
            )
            if existing:
                manufacturer_id = str(existing["id"])
                self.logger.info(f"Manufacturer '{manufacturer.name}' already exists: {manufacturer_id}")
                return manufacturer_id

            columns, placeholders, values = self._prepare_insert(manufacturer_data)
            sql = (
                f"INSERT INTO {self._core_schema}.manufacturers "
                f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
            )
            manufacturer_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created manufacturer {manufacturer_id}")
            return str(manufacturer_id)

    async def get_manufacturer_by_name(self, name: str) -> dict[str, Any] | None:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._core_schema}.manufacturers WHERE LOWER(name) = LOWER($1) LIMIT 1", name
            )
            return dict(row) if row else None

    async def create_product_series(self, series: ProductSeriesModel) -> str:
        pool = self._ensure_pool()
        series_data = series.model_dump(mode="python", exclude_none=True)
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                f"""
                SELECT id FROM {self._core_schema}.product_series
                WHERE manufacturer_id = $1 AND LOWER(series_name) = LOWER($2)
                LIMIT 1
                """,
                series.manufacturer_id,
                series.series_name,
            )
            if existing:
                series_id = str(existing["id"])
                self.logger.info(
                    f"Product series '{series.series_name}' already exists (manufacturer {series.manufacturer_id})"
                )
                return series_id

            columns, placeholders, values = self._prepare_insert(series_data)
            sql = (
                f"INSERT INTO {self._core_schema}.product_series "
                f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
            )
            series_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created product series {series_id}")
            return str(series_id)

    async def get_product_series_by_name(self, name: str, manufacturer_id: str) -> dict[str, Any] | None:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT * FROM {self._core_schema}.product_series
                WHERE manufacturer_id = $1 AND LOWER(series_name) = LOWER($2)
                LIMIT 1
                """,
                manufacturer_id,
                name,
            )
            return dict(row) if row else None

    async def create_product(self, product: ProductModel) -> str:
        pool = self._ensure_pool()
        product_data = product.model_dump(mode="python", exclude_none=True)
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                f"""
                SELECT id FROM {self._core_schema}.products
                WHERE manufacturer_id = $1 AND LOWER(model_number) = LOWER($2)
                LIMIT 1
                """,
                product.manufacturer_id,
                product.model_number,
            )
            if existing:
                product_id = str(existing["id"])
                self.logger.info(
                    f"Product '{product.model_number}' (manufacturer {product.manufacturer_id}) already exists"
                )
                return product_id

            columns, placeholders, values = self._prepare_insert(product_data)
            sql = (
                f"INSERT INTO {self._core_schema}.products "
                f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
            )
            product_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created product {product_id}")
            return str(product_id)

    async def get_product_by_model(self, model_number: str, manufacturer_id: str) -> dict[str, Any] | None:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT * FROM {self._core_schema}.products
                WHERE manufacturer_id = $1 AND LOWER(model_number) = LOWER($2)
                LIMIT 1
                """,
                manufacturer_id,
                model_number,
            )
            return dict(row) if row else None

    async def create_chunk(self, chunk: ChunkModel) -> str:
        chunk_data = chunk.model_dump(mode="python", exclude_none=True)
        return await self.create_chunk_async(chunk_data)

    async def create_chunk_async(self, chunk_data: dict[str, Any]) -> str:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            columns, placeholders, values = self._prepare_insert(chunk_data)
            sql = (
                f"INSERT INTO {self._content_schema}.chunks "
                f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
            )
            chunk_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created chunk {chunk_id}")
            return str(chunk_id)

    async def get_chunk_by_document_and_index(self, document_id: str, chunk_index: int) -> dict[str, Any] | None:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT * FROM {self._content_schema}.chunks
                WHERE document_id = $1 AND chunk_index = $2
                LIMIT 1
                """,
                document_id,
                chunk_index,
            )
            return dict(row) if row else None

    async def create_image(self, image: ImageModel) -> str:
        pool = self._ensure_pool()
        image_data = image.model_dump(mode="python", exclude_none=True)
        async with pool.acquire() as conn:
            existing = None
            if image.file_hash:
                existing = await conn.fetchrow(
                    f"SELECT id FROM {self._content_schema}.images WHERE file_hash = $1 LIMIT 1", image.file_hash
                )
            if existing:
                image_id = str(existing["id"])
                self.logger.info(f"Image with hash {image.file_hash[:16]}... already exists: {image_id}")
                return image_id

            columns, placeholders, values = self._prepare_insert(image_data)
            sql = (
                f"INSERT INTO {self._content_schema}.images "
                f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
            )
            image_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created image {image_id}")
            return str(image_id)

    async def create_image_with_svg(self, image: ImageModel) -> str:
        """Create image record with SVG metadata fields populated."""
        pool = self._ensure_pool()
        image_data = image.model_dump(mode="python", exclude_none=True)
        image_data["is_vector_graphic"] = bool(image_data.get("is_vector_graphic", True))

        async with pool.acquire() as conn:
            existing = None
            if image.file_hash:
                existing = await conn.fetchrow(
                    f"SELECT id FROM {self._content_schema}.images WHERE file_hash = $1 LIMIT 1", image.file_hash
                )
            if existing:
                image_id = str(existing["id"])
                self.logger.info(f"SVG image with hash {image.file_hash[:16]}... already exists: {image_id}")
                return image_id

            columns, placeholders, values = self._prepare_insert(image_data)
            sql = (
                f"INSERT INTO {self._content_schema}.images "
                f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
            )
            image_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created SVG image {image_id}")
            return str(image_id)

    async def get_image_by_hash(self, image_hash: str) -> dict[str, Any] | None:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._content_schema}.images WHERE file_hash = $1 LIMIT 1", image_hash
            )
            return dict(row) if row else None

    async def get_images_by_document(self, document_id: str) -> list[dict[str, Any]]:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM {self._content_schema}.images
                WHERE document_id = $1
                ORDER BY page_number, image_index
                """,
                document_id,
            )
            return [dict(row) for row in rows]

    async def update_image_svg_storage(
        self,
        image_id: str,
        svg_storage_url: str,
        original_svg_content: str | None = None,
        is_vector_graphic: bool = True,
    ) -> bool:
        """Update SVG storage metadata for an existing image."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"""
                UPDATE {self._content_schema}.images
                SET svg_storage_url = $2,
                    original_svg_content = $3,
                    is_vector_graphic = $4,
                    updated_at = NOW()
                WHERE id = $1
                """,
                image_id,
                svg_storage_url,
                original_svg_content,
                is_vector_graphic,
            )
            updated = result == "UPDATE 1"
            if updated:
                self.logger.info(f"Updated SVG storage metadata for image {image_id}")
            return updated

    async def create_svg_queue_entry(self, queue_data: dict[str, Any]) -> str:
        """Create a processing queue entry for SVG/image storage tasks."""
        pool = self._ensure_pool()
        payload = queue_data.get("payload") or {}
        document_id = queue_data.get("document_id") or payload.get("document_id")
        if not document_id:
            raise ValueError("create_svg_queue_entry requires document_id")

        stage = str(queue_data.get("stage") or payload.get("stage") or "storage")
        task_type = queue_data.get("task_type")
        if not task_type:
            task_type = str(queue_data.get("artifact_type") or payload.get("artifact_type") or stage)

        priority = queue_data.get("priority", 5)
        status = queue_data.get("status", "pending")
        max_retries = queue_data.get("max_retries", 3)
        retry_count = queue_data.get("retry_count", 0)
        chunk_id = queue_data.get("chunk_id") or payload.get("chunk_id")
        image_id = queue_data.get("image_id") or payload.get("image_id")
        video_id = queue_data.get("video_id") or payload.get("video_id")

        async with pool.acquire() as conn:
            queue_id = await conn.fetchval(
                f"""
                INSERT INTO {self._system_schema}.processing_queue
                    (document_id, chunk_id, image_id, video_id, stage, task_type, priority, status, retry_count, max_retries, payload)
                VALUES
                    ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8, $9, $10, $11::jsonb)
                RETURNING id
                """,
                str(document_id),
                str(chunk_id) if chunk_id else None,
                str(image_id) if image_id else None,
                str(video_id) if video_id else None,
                stage,
                task_type,
                int(priority),
                status,
                int(retry_count),
                int(max_retries),
                json.dumps(payload, ensure_ascii=False),
            )
            self.logger.info("Created SVG queue entry %s (stage=%s task_type=%s)", queue_id, stage, task_type)
            return str(queue_id)

    async def get_images_by_vector_flag(self, is_vector_graphic: bool = True) -> list[dict[str, Any]]:
        """Retrieve images filtered by vector graphic flag."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM {self._content_schema}.images
                WHERE is_vector_graphic = $1
                ORDER BY created_at DESC
                """,
                is_vector_graphic,
            )
            return [dict(row) for row in rows]

    # Phase 5: Context extraction update methods
    async def update_image_context(self, image_id: str, context_data: dict[str, Any]) -> bool:
        """Update context fields for an image."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            try:
                # Handle vector field separately
                vector_value = None
                if "context_embedding" in context_data:
                    vector_value = context_data.pop("context_embedding")

                # Build SET clause for non-vector fields
                set_clauses = []
                values = []
                param_idx = 1

                for key, value in context_data.items():
                    set_clauses.append(f"{key} = ${param_idx}")
                    values.append(value)
                    param_idx += 1

                # Add vector field if present
                if vector_value is not None:
                    set_clauses.append(f"context_embedding = ${param_idx}::vector")
                    values.append(self._vector_literal(vector_value))
                    param_idx += 1

                values.append(image_id)  # WHERE clause parameter

                sql = f"""
                UPDATE {self._content_schema}.images
                SET {', '.join(set_clauses)}
                WHERE id = ${param_idx}
                """

                result = await conn.execute(sql, *values)
                success = result == "UPDATE 1"

                if success:
                    self.logger.info(f"Updated context for image {image_id}")
                else:
                    self.logger.warning(f"Failed to update context for image {image_id}")

                return success

            except Exception as e:
                self.logger.error(f"Error updating image context {image_id}: {e}")
                return False

    async def update_video_context(self, video_id: str, context_data: dict[str, Any]) -> bool:
        """Update context fields for a video."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            try:
                # Handle vector field separately
                vector_value = None
                if "context_embedding" in context_data:
                    vector_value = context_data.pop("context_embedding")

                # Build SET clause for non-vector fields
                set_clauses = []
                values = []
                param_idx = 1

                for key, value in context_data.items():
                    set_clauses.append(f"{key} = ${param_idx}")
                    values.append(value)
                    param_idx += 1

                # Add vector field if present
                if vector_value is not None:
                    set_clauses.append(f"context_embedding = ${param_idx}::vector")
                    values.append(self._vector_literal(vector_value))
                    param_idx += 1

                values.append(video_id)  # WHERE clause parameter

                sql = f"""
                UPDATE {self._content_schema}.instructional_videos
                SET {', '.join(set_clauses)}
                WHERE id = ${param_idx}
                """

                result = await conn.execute(sql, *values)
                success = result == "UPDATE 1"

                if success:
                    self.logger.info(f"Updated context for video {video_id}")
                else:
                    self.logger.warning(f"Failed to update context for video {video_id}")

                return success

            except Exception as e:
                self.logger.error(f"Error updating video context {video_id}: {e}")
                return False

    async def update_link_context(self, link_id: str, context_data: dict[str, Any]) -> bool:
        """Update context fields for a link."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            try:
                # Handle vector field separately
                vector_value = None
                if "context_embedding" in context_data:
                    vector_value = context_data.pop("context_embedding")

                # Build SET clause for non-vector fields
                set_clauses = []
                values = []
                param_idx = 1

                for key, value in context_data.items():
                    set_clauses.append(f"{key} = ${param_idx}")
                    values.append(value)
                    param_idx += 1

                # Add vector field if present
                if vector_value is not None:
                    set_clauses.append(f"context_embedding = ${param_idx}::vector")
                    values.append(self._vector_literal(vector_value))
                    param_idx += 1

                values.append(link_id)  # WHERE clause parameter

                sql = f"""
                UPDATE {self._content_schema}.links
                SET {', '.join(set_clauses)}
                WHERE id = ${param_idx}
                """

                result = await conn.execute(sql, *values)
                success = result == "UPDATE 1"

                if success:
                    self.logger.info(f"Updated context for link {link_id}")
                else:
                    self.logger.warning(f"Failed to update context for link {link_id}")

                return success

            except Exception as e:
                self.logger.error(f"Error updating link context {link_id}: {e}")
                return False

    async def update_media_contexts_batch(self, updates: list[dict[str, Any]]) -> dict[str, int]:
        """Update context fields for multiple media items in a batch."""
        success_count = 0
        failed_count = 0

        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            try:
                async with conn.transaction():
                    for update in updates:
                        media_type = update.get("media_type")
                        media_id = update.get("media_id")
                        context_data = update.get("context_data", {})

                        if not media_type or not media_id:
                            failed_count += 1
                            continue

                        try:
                            if media_type == "image":
                                success = await self.update_image_context(media_id, context_data)
                            elif media_type == "video":
                                success = await self.update_video_context(media_id, context_data)
                            elif media_type == "link":
                                success = await self.update_link_context(media_id, context_data)
                            else:
                                success = False

                            if success:
                                success_count += 1
                            else:
                                failed_count += 1

                        except Exception as e:
                            self.logger.error(f"Error in batch update for {media_type} {media_id}: {e}")
                            failed_count += 1

            except Exception as e:
                self.logger.error(f"Transaction failed in batch context update: {e}")
                failed_count += len(updates)

        self.logger.info(f"Batch context update completed: {success_count} success, {failed_count} failed")
        return {"success_count": success_count, "failed_count": failed_count}

    async def get_media_without_context(self, media_type: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get media items without context extraction for backfill."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            try:
                if media_type == "image":
                    sql = f"""
                    SELECT id, document_id, page_number
                    FROM {self._content_schema}.images
                    WHERE context_caption IS NULL
                    ORDER BY created_at DESC
                    LIMIT ${limit}
                    """
                elif media_type == "video":
                    sql = f"""
                    SELECT id, document_id, page_number
                    FROM {self._content_schema}.instructional_videos
                    WHERE context_description IS NULL
                    ORDER BY created_at DESC
                    LIMIT ${limit}
                    """
                elif media_type == "link":
                    sql = f"""
                    SELECT id, document_id, page_number
                    FROM {self._content_schema}.links
                    WHERE context_description IS NULL
                    ORDER BY created_at DESC
                    LIMIT ${limit}
                    """
                else:
                    return []

                rows = await conn.fetch(sql, limit)
                return [dict(row) for row in rows]

            except Exception as e:
                self.logger.error(f"Error getting media without context for {media_type}: {e}")
                return []

    async def create_intelligence_chunk(self, chunk: IntelligenceChunkModel) -> str:
        pool = self._ensure_pool()
        chunk_data = chunk.model_dump(mode="python", exclude_none=True)
        if isinstance(chunk_data.get("metadata"), dict):
            chunk_data["metadata"] = json.dumps(chunk_data.get("metadata") or {}, ensure_ascii=False)
        async with pool.acquire() as conn:
            columns = list(chunk_data.keys())
            placeholders = []
            values = []
            for idx, column in enumerate(columns):
                placeholder = f"${idx + 1}"
                if column == "metadata":
                    placeholder = f"{placeholder}::jsonb"
                placeholders.append(placeholder)
                values.append(chunk_data[column])
            sql = (
                f"INSERT INTO {self._intelligence_schema}.chunks "
                f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
            )
            chunk_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created intelligence chunk {chunk_id}")
            return str(chunk_id)

    async def create_embedding(self, embedding: EmbeddingModel) -> str:
        pool = self._ensure_pool()
        embedding_data = embedding.model_dump(mode="python", exclude_none=True)
        embedding_vector = embedding_data.pop("embedding")
        columns, placeholders, values = self._prepare_insert(embedding_data)
        vector_placeholder = f"${len(values) + 1}::vector"
        columns.insert(2, "embedding")
        placeholders.insert(2, vector_placeholder)
        values.insert(2, self._vector_literal(embedding_vector))
        sql = (
            f"INSERT INTO {self._intelligence_schema}.embeddings "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            embedding_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created embedding {embedding_id}")
            return str(embedding_id)

    async def create_unified_embedding(
        self,
        source_id: str,
        source_type: str,
        embedding: list[float],
        model_name: str,
        embedding_context: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        pool = self._ensure_pool()

        vector_literal = self._vector_literal([float(v) for v in embedding])
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        sql = (
            f"INSERT INTO {self._intelligence_schema}.unified_embeddings "
            "(source_id, source_type, embedding, model_name, embedding_context, metadata) "
            "VALUES ($1::uuid, $2, $3::vector, $4, $5, $6::jsonb) "
            "RETURNING id"
        )

        async with pool.acquire() as conn:
            embedding_id = await conn.fetchval(
                sql,
                source_id,
                source_type,
                vector_literal,
                model_name,
                embedding_context,
                metadata_json,
            )
            self.logger.info(f"Created unified embedding {embedding_id} (type={source_type})")
            return str(embedding_id)

    async def insert_table(self, table_data: dict[str, Any]) -> str:
        """Insert a table record."""
        return await self.create_structured_table(table_data)

    async def create_structured_table(self, table_data: dict[str, Any]) -> str:
        """Create structured table in krai_intelligence.structured_tables"""
        pool = self._ensure_pool()

        # Handle JSONB fields
        if "table_data" in table_data and isinstance(table_data["table_data"], list | dict):
            table_data["table_data"] = json.dumps(table_data["table_data"])
        if "metadata" in table_data and isinstance(table_data["metadata"], dict):
            table_data["metadata"] = json.dumps(table_data["metadata"])

        # Handle vector field (table_embedding)
        table_embedding = table_data.pop("table_embedding", None)
        context_embedding = table_data.pop("context_embedding", None)

        columns, placeholders, values = self._prepare_insert(table_data)

        # Add vector fields if present
        if table_embedding:
            columns.append("table_embedding")
            placeholders.append(f"${len(values) + 1}::vector")
            values.append(self._vector_literal(table_embedding))
        if context_embedding:
            columns.append("context_embedding")
            placeholders.append(f"${len(values) + 1}::vector")
            values.append(self._vector_literal(context_embedding))

        sql = (
            f"INSERT INTO {self._intelligence_schema}.structured_tables "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )

        async with pool.acquire() as conn:
            table_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created structured table {table_id}")
            return str(table_id)

    async def get_embedding_by_chunk_id(self, chunk_id: str) -> dict[str, Any] | None:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._intelligence_schema}.embeddings WHERE chunk_id = $1 LIMIT 1", chunk_id
            )
            return dict(row) if row else None

    async def get_embeddings_by_chunk_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {self._intelligence_schema}.embeddings WHERE chunk_id = ANY($1::uuid[])", chunk_ids
            )
            return [dict(row) for row in rows]

    async def search_embeddings(
        self, query_embedding: list[float], limit: int = 10, match_threshold: float = 0.7, match_count: int = 10
    ) -> list[dict[str, Any]]:
        pool = self._ensure_pool()
        vector_literal = self._vector_literal(query_embedding)
        effective_limit = max(limit, match_count)
        sql = f"""
            SELECT
                e.id,
                e.chunk_id,
                e.model_name,
                e.model_version,
                e.created_at,
                (1 - (e.embedding <=> {vector_literal}::vector)) AS similarity
            FROM {self._intelligence_schema}.embeddings e
            WHERE (1 - (e.embedding <=> {vector_literal}::vector)) >= $1
            ORDER BY similarity DESC
            LIMIT $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, match_threshold, effective_limit)
            return [dict(row) for row in rows]

    async def create_error_code(self, error_code: ErrorCodeModel) -> str:
        pool = self._ensure_pool()
        error_code_data = error_code.model_dump(mode="python", exclude_none=True)
        columns, placeholders, values = self._prepare_insert(error_code_data)
        sql = (
            f"INSERT INTO {self._intelligence_schema}.error_codes "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            error_code_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created error code {error_code_id}")
            return str(error_code_id)

    async def get_error_codes_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Return all error codes for a document."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *
                FROM {self._intelligence_schema}.error_codes
                WHERE document_id = $1::uuid
                ORDER BY created_at ASC, id ASC
                """,
                document_id,
            )
            return [dict(row) for row in rows]

    async def create_error_code_part_link(self, link_data: dict[str, Any]) -> bool:
        """Create or keep an error-code/part link (idempotent)."""
        pool = self._ensure_pool()
        error_code_id = link_data.get("error_code_id")
        part_id = link_data.get("part_id")
        if not error_code_id or not part_id:
            raise ValueError("link_data must contain error_code_id and part_id")

        relevance_score = link_data.get("relevance_score", 1.0)
        extraction_source = link_data.get("extraction_source")

        async with pool.acquire() as conn:
            status = await conn.execute(
                f"""
                INSERT INTO {self._intelligence_schema}.error_code_parts
                    (error_code_id, part_id, relevance_score, extraction_source)
                VALUES ($1::uuid, $2::uuid, $3, $4)
                ON CONFLICT (error_code_id, part_id) DO NOTHING
                """,
                error_code_id,
                part_id,
                relevance_score,
                extraction_source,
            )
            return status.endswith("1")

    async def log_search_analytics(self, analytics: SearchAnalyticsModel) -> str:
        pool = self._ensure_pool()
        analytics_data = analytics.model_dump(mode="python", exclude_none=True)
        columns, placeholders, values = self._prepare_insert(analytics_data)
        sql = (
            f"INSERT INTO {self._intelligence_schema}.search_analytics "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            analytics_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Logged search analytics {analytics_id}")
            return str(analytics_id)

    async def create_processing_queue_item(self, item: ProcessingQueueModel) -> str:
        pool = self._ensure_pool()
        item_data = item.model_dump(mode="python", exclude_none=True)

        # Map processor_name to task_type for database compatibility
        if "processor_name" in item_data:
            item_data["task_type"] = item_data.pop("processor_name")

        columns, placeholders, values = self._prepare_insert(item_data)
        sql = (
            f"INSERT INTO {self._system_schema}.processing_queue "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            item_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created processing queue item {item_id}")
            return str(item_id)

    async def update_processing_queue_item(self, item_id: str, updates: dict[str, Any]) -> bool:
        if not updates:
            return False
        pool = self._ensure_pool()
        set_clauses = [f"{key} = ${index + 2}" for index, key in enumerate(updates.keys())]
        sql = (
            f"UPDATE {self._system_schema}.processing_queue "
            f"SET {', '.join(set_clauses)}, updated_at = NOW() "
            f"WHERE id = $1"
        )
        async with pool.acquire() as conn:
            result = await conn.execute(sql, item_id, *updates.values())
            updated = result.upper().startswith("UPDATE")
            if updated:
                self.logger.info(f"Updated processing queue item {item_id}")
            return updated

    async def log_audit_event(self, event: AuditLogModel) -> str:
        pool = self._ensure_pool()
        event_data = event.model_dump(mode="python", exclude_none=True)
        columns, placeholders, values = self._prepare_insert(event_data)
        sql = (
            f"INSERT INTO {self._system_schema}.audit_log "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            event_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Logged audit event {event.action} ({event_id})")
            return str(event_id)

    async def get_embeddings_by_source(self, source_id: str, source_type: str | None = None) -> list[dict[str, Any]]:
        """Get embeddings from unified_embeddings by source_id and optional source_type"""
        pool = self._ensure_pool()

        table_name = f"{self._intelligence_schema}.unified_embeddings"
        async with pool.acquire() as conn:
            if source_type:
                sql = f"""
                    SELECT * FROM {table_name}
                    WHERE source_id = $1 AND source_type = $2
                    ORDER BY created_at DESC
                """
                rows = await conn.fetch(sql, source_id, source_type)
            else:
                sql = f"""
                    SELECT * FROM {table_name}
                    WHERE source_id = $1
                    ORDER BY created_at DESC
                """
                rows = await conn.fetch(sql, source_id)
            return [dict(row) for row in rows]

    async def get_system_status(self) -> dict[str, Any]:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            document_counts = await conn.fetch(
                f"SELECT processing_status, COUNT(*) AS cnt FROM {self._core_schema}.documents GROUP BY processing_status"
            )
            total_documents = await conn.fetchval(f"SELECT COUNT(*) FROM {self._core_schema}.documents")
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "connected",
                "total_documents": total_documents or 0,
            }
            for row in document_counts:
                status[str(row["processing_status"])] = row["cnt"]
            return status

    async def count_chunks_by_document(self, document_id: str) -> int:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self._intelligence_schema}.chunks WHERE document_id = $1", document_id
            )
            return count or 0

    async def count_images_by_document(self, document_id: str) -> int:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self._content_schema}.images WHERE document_id = $1", document_id
            )
            return count or 0

    async def check_embedding_exists(self, chunk_id: str) -> bool:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                f"""
                SELECT EXISTS(
                    SELECT 1 FROM {self._intelligence_schema}.embeddings
                    WHERE chunk_id = $1
                )
                """,
                chunk_id,
            )
            return bool(exists)

    async def count_links_by_document(self, document_id: str) -> int:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self._content_schema}.links WHERE document_id = $1", document_id
            )
            return count or 0

    async def create_link(self, link_data: dict[str, Any]) -> str:
        pool = self._ensure_pool()
        link_record = {k: v for k, v in link_data.items() if v is not None}
        columns, placeholders, values = self._prepare_insert(link_record)
        sql = (
            f"INSERT INTO {self._content_schema}.links "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            link_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created link {link_id} ({link_data.get('link_type')})")
            return str(link_id)

    async def insert_link(self, link_data: dict[str, Any]) -> str:
        """Insert a link record (alias for create_link)."""
        return await self.create_link(link_data)

    # Parts operations (krai_parts.parts_catalog)
    async def insert_part(self, part_data: dict[str, Any]) -> str:
        """Insert a part record into krai_parts.parts_catalog."""
        pool = self._ensure_pool()
        record = {
            k: v
            for k, v in part_data.items()
            if v is not None
            and k in ("manufacturer_id", "product_id", "part_number", "part_name", "part_description", "part_category")
        }
        columns, placeholders, values = self._prepare_insert(record)
        sql = (
            f"INSERT INTO {self._parts_schema}.parts_catalog "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            part_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Inserted part {part_id} ({part_data.get('part_number')})")
            return str(part_id)

    async def create_part(self, part_data: dict[str, Any]) -> str:
        """Create a part record (alias for insert_part)."""
        return await self.insert_part(part_data)

    async def get_part_by_number(self, part_number: str) -> dict[str, Any] | None:
        """Get a part by part number (any manufacturer)."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._parts_schema}.parts_catalog WHERE part_number = $1 LIMIT 1", part_number
            )
            return dict(row) if row else None

    async def get_part_by_number_and_manufacturer(
        self, part_number: str, manufacturer_id: str
    ) -> dict[str, Any] | None:
        """Get a part by part number and manufacturer."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._parts_schema}.parts_catalog "
                f"WHERE part_number = $1 AND manufacturer_id = $2 LIMIT 1",
                part_number,
                manufacturer_id,
            )
            return dict(row) if row else None

    async def update_part(self, part_id: str, part_data: dict[str, Any]) -> bool:
        """Update an existing part."""
        pool = self._ensure_pool()
        allowed = ("part_name", "part_description", "part_category", "product_id")
        updates = {k: v for k, v in part_data.items() if k in allowed and v is not None}
        if not updates:
            return True
        n = len(updates)
        set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(updates))
        values = [*list(updates.values()), part_id]
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE {self._parts_schema}.parts_catalog SET {set_clause} WHERE id = ${n + 1}::uuid", *values
            )
            return True

    async def create_video(self, video_data: dict[str, Any]) -> str:
        pool = self._ensure_pool()
        columns = list(video_data.keys())
        update_set = [f"{col} = EXCLUDED.{col}" for col in columns if col not in {"id"}]
        placeholders = [f"${idx + 1}" for idx in range(len(columns))]
        sql = (
            f"INSERT INTO {self._content_schema}.videos ({', '.join(columns)}) "
            f"VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT (link_id) DO UPDATE SET {', '.join(update_set)} "
            f"RETURNING id"
        )
        async with pool.acquire() as conn:
            video_id = await conn.fetchval(sql, *video_data.values())
            self.logger.info(f"Upserted video {video_id}")
            return str(video_id)

    async def get_videos_needing_enrichment(
        self,
        document_id: str,
        limit: int = 100,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch Brightcove videos that still need enrichment for a document."""
        pool = self._ensure_pool()
        where_force = "" if force else "AND (enriched_at IS NULL OR metadata->>'enrichment_error' IS NOT NULL)"
        query = f"""
            SELECT id, video_url, platform, metadata, enriched_at
            FROM {self._content_schema}.videos
            WHERE document_id = $1::uuid
              AND platform IN ('brightcove', 'youtube', 'vimeo')
              AND (
                COALESCE((metadata->>'needs_enrichment')::boolean, false) = true
                OR COALESCE(BTRIM(title), '') = ''
                OR COALESCE(BTRIM(context_description), '') = ''
              )
              {where_force}
            ORDER BY created_at ASC
            LIMIT $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, document_id, limit)
            return [dict(row) for row in rows]

    async def update_video_enrichment(self, video_id: str, metadata_dict: dict[str, Any]) -> bool:
        """Update a video record with enriched metadata fields."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            # Merge non-column fields (tags, enrichment_error) into metadata JSONB.
            # krai_content.videos has no standalone tags or enrichment_error columns.
            extra_meta: dict[str, Any] = {}
            if metadata_dict.get("tags") is not None:
                extra_meta["tags"] = metadata_dict["tags"]
            if metadata_dict.get("enrichment_error"):
                extra_meta["enrichment_error"] = metadata_dict["enrichment_error"]
            elif "enrichment_error" in metadata_dict:
                extra_meta["enrichment_error"] = None  # will be merged out

            base_meta = metadata_dict.get("metadata") or {}
            merged_meta = {**base_meta, **extra_meta}

            await conn.execute(
                f"""
                UPDATE {self._content_schema}.videos
                SET
                    title = COALESCE($2, title),
                    description = COALESCE($3, description),
                    duration = COALESCE($4, duration),
                    thumbnail_url = COALESCE($5, thumbnail_url),
                    published_at = COALESCE($6, published_at),
                    metadata = COALESCE(metadata, '{{}}'::jsonb) || COALESCE($7::jsonb, '{{}}'::jsonb),
                    enriched_at = COALESCE($8, enriched_at),
                    updated_at = NOW()
                WHERE id = $1::uuid
                """,
                video_id,
                metadata_dict.get("title"),
                metadata_dict.get("description"),
                metadata_dict.get("duration"),
                metadata_dict.get("thumbnail_url"),
                metadata_dict.get("published_at"),
                json.dumps(merged_meta) if merged_meta else None,
                metadata_dict.get("enriched_at"),
            )
            return True

    async def mark_video_enrichment_failed(self, video_id: str, error_message: str) -> bool:
        """Persist enrichment failure details and keep needs_enrichment=true for retries."""
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {self._content_schema}.videos
                SET
                    metadata = COALESCE(metadata, '{{}}'::jsonb) || $2::jsonb,
                    updated_at = NOW()
                WHERE id = $1::uuid
                """,
                video_id,
                json.dumps(
                    {
                        "needs_enrichment": True,
                        "enrichment_error": (error_message or "Unknown enrichment error")[:1000],
                    }
                ),
            )
            return True

    async def create_print_defect(self, defect: PrintDefectModel) -> str:
        pool = self._ensure_pool()
        defect_data = defect.model_dump(mode="python", exclude_none=True)
        columns, placeholders, values = self._prepare_insert(defect_data)
        sql = (
            f"INSERT INTO {self._content_schema}.print_defects "
            f"({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
        )
        async with pool.acquire() as conn:
            defect_id = await conn.fetchval(sql, *values)
            self.logger.info(f"Created print defect {defect_id}")
            return str(defect_id)

    async def execute_rpc_function(
        self, function_name: str, params: dict[str, Any] | None = None, schema: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute PostgreSQL function (RPC equivalent)

        Args:
            function_name: Name of the function to execute
            params: Parameters to pass to the function
            schema: Schema name (default: intelligence schema)

        Returns:
            List of results as dictionaries
        """
        try:
            pool = self._ensure_pool()
            schema = schema or self._intelligence_schema
            params = params or {}

            # Build parameter list and placeholders
            param_values = list(params.values())
            param_placeholders = [f"${i+1}" for i in range(len(param_values))]

            # Build function call
            if param_values:
                sql = f"SELECT * FROM {schema}.{function_name}({', '.join(param_placeholders)})"
            else:
                sql = f"SELECT * FROM {schema}.{function_name}()"

            async with pool.acquire() as conn:
                results = await conn.fetch(sql, *param_values)

                # Convert to list of dicts
                return [dict(result) for result in results]

        except Exception as e:
            self.logger.error(f"Failed to execute RPC function {function_name}: {e}")
            return []

    async def execute_rpc(self, function_name: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a PostgreSQL function for side effects (VOID-returning).

        Supports both fully-qualified names (e.g. "krai_core.start_stage") and
        unqualified names (defaulting to the core schema).
        """
        pool = self._ensure_pool()
        params = params or {}

        if "." in function_name:
            schema, func_name = function_name.split(".", 1)
        else:
            schema, func_name = self._core_schema, function_name

        stage_rpc_arg_types = {
            "start_stage": {
                "p_document_id": "uuid",
                "p_stage_name": "text",
            },
            "update_stage_progress": {
                "p_document_id": "uuid",
                "p_stage_name": "text",
                "p_progress": "numeric",
                "p_metadata": "jsonb",
            },
            "complete_stage": {
                "p_document_id": "uuid",
                "p_stage_name": "text",
                "p_metadata": "jsonb",
            },
            "fail_stage": {
                "p_document_id": "uuid",
                "p_stage_name": "text",
                "p_error": "text",
                "p_metadata": "jsonb",
            },
            "skip_stage": {
                "p_document_id": "uuid",
                "p_stage_name": "text",
                "p_reason": "text",
            },
            "get_document_progress": {
                "p_document_id": "uuid",
            },
            "get_current_stage": {
                "p_document_id": "uuid",
            },
            "can_start_stage": {
                "p_document_id": "uuid",
                "p_stage_name": "text",
            },
        }

        param_names = list(params.keys())
        arg_type_map = stage_rpc_arg_types.get(func_name) if schema.endswith("_core") else None

        param_values = []
        for param_name in param_names:
            value = params[param_name]
            cast = arg_type_map.get(param_name) if arg_type_map else None
            if cast in ("json", "jsonb") and isinstance(value, dict | list | tuple):
                value = json.dumps(value, ensure_ascii=False)
            param_values.append(value)

        placeholders = []
        for idx, param_name in enumerate(param_names):
            cast = None
            if arg_type_map:
                cast = arg_type_map.get(param_name)
            if cast:
                placeholders.append(f"${idx + 1}::{cast}")
            else:
                placeholders.append(f"${idx + 1}")

        if param_values:
            sql = f"SELECT {schema}.{func_name}({', '.join(placeholders)})"
        else:
            sql = f"SELECT {schema}.{func_name}()"

        async with pool.acquire() as conn:
            await conn.execute(sql, *param_values)

    async def match_multimodal(
        self, query_embedding: list[float], match_threshold: float = 0.5, match_count: int = 10
    ) -> list[dict[str, Any]]:
        """
        Wrapper for match_multimodal RPC function

        Args:
            query_embedding: Query embedding vector
            match_threshold: Similarity threshold
            match_count: Maximum number of results

        Returns:
            List of multimodal search results
        """
        try:
            pool = self._ensure_pool()
            vector_literal = self._vector_literal(query_embedding)

            async with pool.acquire() as conn:
                results = await conn.fetch(
                    f"SELECT * FROM {self._intelligence_schema}.match_multimodal($1::vector, $2, $3)",
                    vector_literal,
                    match_threshold,
                    match_count,
                )

                return [dict(result) for result in results]

        except Exception as e:
            self.logger.error(f"Failed to execute match_multimodal: {e}")
            return []

    async def match_images_by_context(
        self, query_embedding: list[float], match_threshold: float = 0.5, match_count: int = 5
    ) -> list[dict[str, Any]]:
        """
        Wrapper for match_images_by_context RPC function

        Args:
            query_embedding: Query embedding vector
            match_threshold: Similarity threshold
            match_count: Maximum number of results

        Returns:
            List of image search results
        """
        try:
            pool = self._ensure_pool()
            vector_literal = self._vector_literal(query_embedding)

            async with pool.acquire() as conn:
                results = await conn.fetch(
                    f"SELECT * FROM {self._intelligence_schema}.match_images_by_context($1::vector, $2, $3)",
                    vector_literal,
                    match_threshold,
                    match_count,
                )

                return [dict(result) for result in results]

        except Exception as e:
            self.logger.error(f"Failed to execute match_images_by_context: {e}")
            return []

    async def store_image_context(self, document_id: str, context_data: dict[str, Any]) -> bool:
        """Store image context for a document"""
        try:
            pool = self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self._intelligence_schema}.image_contexts
                    (document_id, context_data, created_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (document_id) DO UPDATE SET
                    context_data = $2, updated_at = $3
                    """,
                    document_id,
                    json.dumps(context_data),
                    datetime.now(),
                )
                return True
        except Exception as e:
            self.logger.error(f"Failed to store image context: {e}")
            return False

    async def store_video_context(self, document_id: str, context_data: dict[str, Any]) -> bool:
        """Store video context for a document"""
        try:
            pool = self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self._intelligence_schema}.video_contexts
                    (document_id, context_data, created_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (document_id) DO UPDATE SET
                    context_data = $2, updated_at = $3
                    """,
                    document_id,
                    json.dumps(context_data),
                    datetime.now(),
                )
                return True
        except Exception as e:
            self.logger.error(f"Failed to store video context: {e}")
            return False

    async def store_link_context(self, document_id: str, context_data: dict[str, Any]) -> bool:
        """Store link context for a document"""
        try:
            pool = self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self._intelligence_schema}.link_contexts
                    (document_id, context_data, created_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (document_id) DO UPDATE SET
                    context_data = $2, updated_at = $3
                    """,
                    document_id,
                    json.dumps(context_data),
                    datetime.now(),
                )
                return True
        except Exception as e:
            self.logger.error(f"Failed to store link context: {e}")
            return False

    async def store_table_context(self, document_id: str, context_data: dict[str, Any]) -> bool:
        """Store table context for a document"""
        try:
            pool = self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self._intelligence_schema}.table_contexts
                    (document_id, context_data, created_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (document_id) DO UPDATE SET
                    context_data = $2, updated_at = $3
                    """,
                    document_id,
                    json.dumps(context_data),
                    datetime.now(),
                )
                return True
        except Exception as e:
            self.logger.error(f"Failed to store table context: {e}")
            return False

    async def get_image_contexts_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Get all image contexts for a document"""
        try:
            pool = self._ensure_pool()
            async with pool.acquire() as conn:
                results = await conn.fetch(
                    f"""
                    SELECT document_id, context_data, created_at, updated_at
                    FROM {self._intelligence_schema}.image_contexts
                    WHERE document_id = $1
                    ORDER BY created_at DESC
                    """,
                    document_id,
                )
                return [dict(result) for result in results]
        except Exception as e:
            self.logger.error(f"Failed to get image contexts: {e}")
            return []

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and all related data"""
        try:
            pool = self._ensure_pool()
            async with pool.acquire() as conn:
                # Delete from all tables in reverse order of dependencies
                await conn.execute(
                    f"DELETE FROM {self._intelligence_schema}.chunks WHERE document_id = $1", document_id
                )
                await conn.execute(
                    f"DELETE FROM {self._intelligence_schema}.image_contexts WHERE document_id = $1", document_id
                )
                await conn.execute(
                    f"DELETE FROM {self._intelligence_schema}.video_contexts WHERE document_id = $1", document_id
                )
                await conn.execute(
                    f"DELETE FROM {self._intelligence_schema}.link_contexts WHERE document_id = $1", document_id
                )
                await conn.execute(
                    f"DELETE FROM {self._intelligence_schema}.table_contexts WHERE document_id = $1", document_id
                )
                await conn.execute(f"DELETE FROM {self._content_schema}.documents WHERE id = $1", document_id)
                await conn.execute(f"DELETE FROM {self._parts_schema}.products WHERE document_id = $1", document_id)
                return True
        except Exception as e:
            self.logger.error(f"Failed to delete document: {e}")
            return False

    # ========== STAGE TRACKING METHODS ==========

    async def start_stage(self, document_id: str, stage: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start processing stage for a document"""
        try:
            result = await self.rpc(
                "krai_core.start_stage",
                {
                    "p_document_id": document_id,
                    "p_stage_name": stage,
                },
            )
            return result or {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to start stage {stage} for document {document_id}: {e}")
            return {"success": False, "error": str(e)}

    async def update_stage_progress(
        self, document_id: str, stage: str, progress: int, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Update progress for a processing stage"""
        try:
            result = await self.rpc(
                "krai_core.update_stage_progress",
                {
                    "p_document_id": document_id,
                    "p_stage_name": stage,
                    "p_progress": progress,
                    "p_metadata": metadata or {},
                },
            )
            return result or {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to update progress for stage {stage}: {e}")
            return {"success": False, "error": str(e)}

    async def complete_stage(
        self, document_id: str, stage: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Mark a processing stage as completed"""
        try:
            result = await self.rpc(
                "krai_core.complete_stage",
                {"p_document_id": document_id, "p_stage_name": stage, "p_metadata": metadata or {}},
            )
            return result or {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to complete stage {stage}: {e}")
            return {"success": False, "error": str(e)}

    async def fail_stage(
        self, document_id: str, stage: str, error: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Mark a processing stage as failed"""
        try:
            result = await self.rpc(
                "krai_core.fail_stage",
                {"p_document_id": document_id, "p_stage_name": stage, "p_error": error, "p_metadata": metadata or {}},
            )
            return result or {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to mark stage {stage} as failed: {e}")
            return {"success": False, "error": str(e)}

    async def skip_stage(
        self, document_id: str, stage: str, reason: str | None = None, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Skip a processing stage"""
        try:
            result = await self.rpc(
                "krai_core.skip_stage",
                {
                    "p_document_id": document_id,
                    "p_stage_name": stage,
                    "p_reason": reason or "",
                },
            )
            return result or {"success": True}
        except Exception as e:
            self.logger.error(f"Failed to skip stage {stage}: {e}")
            return {"success": False, "error": str(e)}

    async def get_document_progress(self, document_id: str) -> dict[str, Any]:
        """Get current progress for a document"""
        try:
            result = await self.rpc("krai_core.get_document_progress", {"document_id": document_id})
            return result or {}
        except Exception as e:
            self.logger.error(f"Failed to get document progress: {e}")
            return {}

    async def get_current_stage(self, document_id: str) -> str | None:
        """Get the current processing stage for a document"""
        try:
            result = await self.rpc("krai_core.get_current_stage", {"document_id": document_id})
            return result.get("current_stage") if result else None
        except Exception as e:
            self.logger.error(f"Failed to get current stage: {e}")
            return None

    async def can_start_stage(self, document_id: str, stage: str) -> bool:
        """Check if a stage can be started for a document"""
        try:
            result = await self.rpc("krai_core.can_start_stage", {"document_id": document_id, "stage": stage})
            return result.get("can_start", False) if result else False
        except Exception as e:
            self.logger.error(f"Failed to check if stage can start: {e}")
            return False

    async def release_all_locks(self) -> bool:
        """Release all advisory locks held by the current session."""
        try:
            await self.execute_query("SELECT pg_advisory_unlock_all()")
            return True
        except Exception as e:
            self.logger.error(f"Failed to release advisory locks: {e}")
            return False

    async def get_stage_status(self, document_id: str, stage_name: str) -> dict[str, Any]:
        """Get status for a specific stage (from document stage_status JSON; no dedicated RPC)."""
        try:
            row = await self.fetch_one(
                f"SELECT stage_status FROM {self._core_schema}.documents WHERE id = :id", {"id": document_id}
            )
            if row is None:
                return {}
            row_dict = dict(row)
            stage_status = row_dict.get("stage_status")
            if stage_status is None:
                return {}
            st = stage_status if isinstance(stage_status, dict) else {}
            stage_data = st.get(stage_name)
            return dict(stage_data) if isinstance(stage_data, dict) else {}
        except Exception as e:
            self.logger.error(f"Failed to get stage status: {e}")
            return {}

    async def get_stage_statistics(self) -> dict[str, Any]:
        """Get overall stage statistics"""
        try:
            result = await self.execute_query("SELECT * FROM public.vw_stage_statistics LIMIT 1")
            return result[0] if result else {}
        except Exception as e:
            self.logger.error(f"Failed to get stage statistics: {e}")
            return {}
