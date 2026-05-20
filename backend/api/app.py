"""
KRAI Processing Pipeline API

FastAPI app for monitoring, managing, and controlling the document processing pipeline.
"""

# ruff: noqa: E402  # imports follow logging setup below

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from pydantic import BaseModel, ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from slowapi.errors import RateLimitExceeded

from backend.api import websocket as websocket_api

# Import API routers
from backend.api.agent_api import KRAIAgent, create_agent_api
from backend.api.dependencies.auth import set_auth_service
from backend.api.dependencies.auth_factory import create_and_initialize_auth_service
from backend.api.middleware.auth_middleware import AuthMiddleware, require_permission
from backend.api.middleware.rate_limit_middleware import (
    APIKeyValidationMiddleware,
    IPFilterMiddleware,
    limiter,
    rate_limit_exception_handler,
    rate_limit_health_dynamic,
    rate_limit_standard_dynamic,
    rate_limit_upload_dynamic,
)
from backend.api.middleware.request_validation_middleware import RequestValidationMiddleware
from backend.api.routes import documents, products
from backend.api.routes.api_keys import router as api_keys_router
from backend.api.routes.batch import router as batch_router
from backend.api.routes.configuration import router as configuration_router
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.document_processing import router as document_processing_router
from backend.api.routes.error_codes import router as error_codes_router
from backend.api.routes.foliant import router as foliant_router
from backend.api.routes.images import router as images_router
from backend.api.routes.openai_compat import router as openai_compat_router
from backend.api.routes.search import router as search_router
from backend.api.routes.videos import router as videos_router
from backend.config.security_config import get_cors_config, get_security_config
from backend.core.base_processor import ProcessingContext
from backend.processors.env_loader import load_all_env_files
from backend.processors.stage_tracker import StageTracker
from backend.processors.upload_processor import BatchUploadProcessor, UploadProcessor
from backend.services.ai_service import AIService
from backend.services.alert_service import AlertService
from backend.services.auth_service import AuthenticationError, AuthService
from backend.services.batch_task_service import BatchTaskService
from backend.services.database_adapter import DatabaseAdapter
from backend.services.database_factory import create_database_adapter
from backend.services.db_pool import get_pool
from backend.services.metrics_service import MetricsService
from backend.services.performance_service import PerformanceCollector
from backend.services.reranking_service import RerankingService
from backend.services.transaction_manager import TransactionManager

# Load consolidated environment configuration
project_root = Path(__file__).parent.parent.parent
load_all_env_files(project_root)

# Security configuration
security_config = get_security_config()
cors_config = get_cors_config(security_config)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
    )
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Default admin configuration
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_FIRST_NAME = os.getenv("DEFAULT_ADMIN_FIRST_NAME", "System")
DEFAULT_ADMIN_LAST_NAME = os.getenv("DEFAULT_ADMIN_LAST_NAME", "Administrator")

# Initialize FastAPI with security settings
app = FastAPI(
    title="KRAI Processing Pipeline API",
    description="Document processing pipeline with monitoring and management",
    version="0.50.0",
    docs_url=None,  # Disable default docs to add auth
    redoc_url=None,  # Disable default redoc to add auth
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config["allow_origins"],
    allow_credentials=cors_config["allow_credentials"],
    allow_methods=cors_config["allow_methods"],
    allow_headers=cors_config["allow_headers"],
    expose_headers=cors_config["expose_headers"],
    max_age=cors_config["max_age"],
)

# API key validation (must run before rate limiting)
app.add_middleware(APIKeyValidationMiddleware)

# IP blacklist/whitelist enforcement
app.add_middleware(IPFilterMiddleware)

# Request validation middleware
app.add_middleware(RequestValidationMiddleware)

# Rate limit configuration
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)

# Import validation error handling
from backend.api.validation_error_codes import ValidationErrorCode, create_validation_error_response


# Custom Pydantic validation exception handlers
@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle FastAPI request validation errors with detailed field-level context.

    Extracts field-level errors from Pydantic validation and returns a standardized
    error response with error codes and contextual information.
    """
    field_errors = []
    missing_fields = []

    for error in exc.errors():
        # Extract field path (e.g., "body.email" or "query.page")
        field_path = ".".join(str(loc) for loc in error["loc"])

        # Extract error details
        error_type = error["type"]
        message = error["msg"]

        # Extract constraints from context if available
        constraints = {}
        ctx = error.get("ctx", {})

        # Common constraint types
        if "limit_value" in ctx:
            constraints["max_length"] = ctx["limit_value"]
        if "min_length" in ctx:
            constraints["min_length"] = ctx["min_length"]
        if "ge" in ctx:
            constraints["ge"] = ctx["ge"]
        if "le" in ctx:
            constraints["le"] = ctx["le"]
        if "gt" in ctx:
            constraints["gt"] = ctx["gt"]
        if "lt" in ctx:
            constraints["lt"] = ctx["lt"]
        if "pattern" in ctx:
            constraints["pattern"] = ctx["pattern"]

        # Derive expected type/constraint from schema or error context
        expected = None
        if "expected_type" in ctx:
            expected = ctx["expected_type"]
        elif "pattern" in ctx:
            expected = f"string matching pattern: {ctx['pattern']}"
        elif "ge" in ctx and "le" in ctx:
            expected = f"number between {ctx['ge']} and {ctx['le']}"
        elif "ge" in ctx:
            expected = f"number >= {ctx['ge']}"
        elif "le" in ctx:
            expected = f"number <= {ctx['le']}"
        elif "limit_value" in ctx:
            expected = f"string with max length {ctx['limit_value']}"
        elif "min_length" in ctx:
            expected = f"string with min length {ctx['min_length']}"
        elif "allowed" in ctx:
            expected = ctx["allowed"]
        elif error_type.startswith("type_error"):
            # Extract expected type from error type (e.g., "type_error.integer" -> "integer")
            expected = error_type.split(".")[-1] if "." in error_type else "valid type"

        # Extract received value from exc.body or error input if available
        received = None
        try:
            # Try to get the actual value from the request body
            if hasattr(exc, "body") and exc.body:
                import json

                body_data = json.loads(exc.body) if isinstance(exc.body, str | bytes) else exc.body
                # Navigate to the field using the location path
                field_parts = [str(loc) for loc in error["loc"] if str(loc) not in ["body", "query", "path", "header"]]
                current = body_data
                for part in field_parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        break
                if current != body_data:
                    received = current
        except Exception:
            pass

        # Fallback to input from error context
        if received is None and "input" in error:
            received = error["input"]

        # Check if this is a missing field error
        if error_type == "value_error.missing" or error_type == "missing":
            # Extract location (body, query, path, header)
            location = error["loc"][0] if error["loc"] else "unknown"
            field_name = error["loc"][-1] if len(error["loc"]) > 1 else "unknown"

            # Collect missing field instead of returning immediately
            missing_fields.append(
                {
                    "field": str(field_name),
                    "location": str(location),
                    "constraints": constraints if constraints else None,
                }
            )
            continue

        # Build field error with expected/received context
        field_error = {
            "field": field_path,
            "type": error_type,
            "message": message,
            "constraints": constraints if constraints else None,
        }

        # Add expected/received context when available
        if expected is not None:
            field_error["expected"] = expected
        if received is not None:
            field_error["received"] = received

        field_errors.append(field_error)

    # If we have missing fields, return them all in a single response
    if missing_fields:
        if len(missing_fields) == 1:
            # Single missing field - use original format for backward compatibility
            missing = missing_fields[0]
            return create_validation_error_response(
                error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
                detail=f"Required field '{missing['field']}' is missing from request {missing['location']}. Please provide this field.",
                context=missing,
                status_code=422,
            )
        # Multiple missing fields - return all in context
        field_names = [f["field"] for f in missing_fields]
        return create_validation_error_response(
            error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
            detail=f"Required fields are missing from request: {', '.join(field_names)}. Please provide all required fields.",
            context={"fields": missing_fields},
            status_code=422,
        )

    # Return standardized error response for field validation errors
    error_count = len(field_errors)
    detail = f"Request validation failed for {error_count} field(s). Please check the field errors in context."

    return create_validation_error_response(
        error_code=ValidationErrorCode.FIELD_VALIDATION_ERROR,
        detail=detail,
        context={"fields": field_errors},
        status_code=422,
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """
    Handle direct Pydantic validation errors with detailed field-level context.

    Similar to RequestValidationError handler but for direct Pydantic model validation.
    """
    field_errors = []

    for error in exc.errors():
        # Extract field path
        field_path = ".".join(str(loc) for loc in error["loc"])

        # Extract error details
        error_type = error["type"]
        message = error["msg"]

        # Extract constraints from context
        constraints = {}
        ctx = error.get("ctx", {})

        if "limit_value" in ctx:
            constraints["max_length"] = ctx["limit_value"]
        if "min_length" in ctx:
            constraints["min_length"] = ctx["min_length"]
        if "ge" in ctx:
            constraints["ge"] = ctx["ge"]
        if "le" in ctx:
            constraints["le"] = ctx["le"]
        if "gt" in ctx:
            constraints["gt"] = ctx["gt"]
        if "lt" in ctx:
            constraints["lt"] = ctx["lt"]
        if "pattern" in ctx:
            constraints["pattern"] = ctx["pattern"]

        # Derive expected type/constraint from schema or error context
        expected = None
        if "expected_type" in ctx:
            expected = ctx["expected_type"]
        elif "pattern" in ctx:
            expected = f"string matching pattern: {ctx['pattern']}"
        elif "ge" in ctx and "le" in ctx:
            expected = f"number between {ctx['ge']} and {ctx['le']}"
        elif "ge" in ctx:
            expected = f"number >= {ctx['ge']}"
        elif "le" in ctx:
            expected = f"number <= {ctx['le']}"
        elif "limit_value" in ctx:
            expected = f"string with max length {ctx['limit_value']}"
        elif "min_length" in ctx:
            expected = f"string with min length {ctx['min_length']}"
        elif "allowed" in ctx:
            expected = ctx["allowed"]
        elif error_type.startswith("type_error"):
            # Extract expected type from error type (e.g., "type_error.integer" -> "integer")
            expected = error_type.split(".")[-1] if "." in error_type else "valid type"

        # Extract received value from error input if available
        received = None
        if "input" in error:
            received = error["input"]

        # Build field error with expected/received context
        field_error = {
            "field": field_path,
            "type": error_type,
            "message": message,
            "constraints": constraints if constraints else None,
        }

        # Add expected/received context when available
        if expected is not None:
            field_error["expected"] = expected
        if received is not None:
            field_error["received"] = received

        field_errors.append(field_error)

    # Return standardized error response
    error_count = len(field_errors)
    detail = f"Validation failed for {error_count} field(s). Please check the field errors in context."

    return create_validation_error_response(
        error_code=ValidationErrorCode.FIELD_VALIDATION_ERROR,
        detail=detail,
        context={"fields": field_errors},
        status_code=422,
    )


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = security_config.CSP_POLICY
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    if request.url.scheme == "https":
        hsts_value = f"max-age={security_config.HSTS_MAX_AGE}"
        if security_config.HSTS_INCLUDE_SUBDOMAINS:
            hsts_value += "; includeSubDomains"
        if security_config.HSTS_PRELOAD:
            hsts_value += "; preload"
        response.headers["Strict-Transport-Security"] = hsts_value

    return response


security_scheme = HTTPBearer(auto_error=False)

# Global state
# Connection pool is managed by db_pool.get_pool()
upload_processor = None
document_processor = None
agent_app = None
auth_service: AuthService | None = None
batch_task_service: BatchTaskService | None = None
transaction_manager: TransactionManager | None = None
metrics_service: MetricsService | None = None
alert_service: AlertService | None = None
performance_collector: PerformanceCollector | None = None
websocket_manager: websocket_api.WebSocketManager | None = None

# Locks for async-safe singleton initialization
_agent_app_lock = asyncio.Lock()
_auth_service_lock = asyncio.Lock()
_batch_task_service_lock = asyncio.Lock()
_transaction_manager_lock = asyncio.Lock()
_metrics_service_lock = asyncio.Lock()
_alert_service_lock = asyncio.Lock()
_performance_collector_lock = asyncio.Lock()


# === AUTH SERVICE INITIALIZATION ===


async def ensure_auth_service() -> AuthService:
    """Ensure the singleton AuthService is available and registered."""
    global auth_service
    if auth_service is None:
        async with _auth_service_lock:
            if auth_service is None:
                auth_service = await create_and_initialize_auth_service()
    return auth_service


# === DEPENDENCY INJECTION ===


async def get_database_pool():
    """Provide shared asyncpg connection pool."""
    return await get_pool()


async def get_upload_processor(request: Request):
    """Get Upload Processor instance"""
    global upload_processor
    if upload_processor is None:
        db_adapter = getattr(request.app.state, "db_adapter", None)
        if db_adapter is None:
            db_adapter = create_database_adapter()
            await db_adapter.connect()
            request.app.state.db_adapter = db_adapter
        upload_processor = UploadProcessor(database_adapter=db_adapter)
    return upload_processor


async def get_agent_app():
    """Get Agent API app"""
    global agent_app
    if agent_app is None:
        async with _agent_app_lock:
            if agent_app is None:
                pool = await get_pool()
                agent_app = create_agent_api(pool)
    return agent_app


async def get_batch_task_service() -> BatchTaskService:
    """Return singleton BatchTaskService."""
    global batch_task_service
    if batch_task_service is None:
        async with _batch_task_service_lock:
            if batch_task_service is None:
                pool = await get_pool()
                batch_task_service = BatchTaskService(pool)
    return batch_task_service


async def get_transaction_manager() -> TransactionManager:
    """Return singleton TransactionManager."""
    global transaction_manager
    if transaction_manager is None:
        async with _transaction_manager_lock:
            if transaction_manager is None:
                pool = await get_pool()
                transaction_manager = TransactionManager(pool)
    return transaction_manager


async def get_metrics_service() -> MetricsService:
    """Return singleton MetricsService. Uses DatabaseAdapter for StageTracker and same connection source for metrics."""
    global metrics_service
    if metrics_service is None:
        async with _metrics_service_lock:
            if metrics_service is None:
                adapter = create_database_adapter()
                await adapter.connect()
                stage_tracker = StageTracker(adapter)
                pool = getattr(adapter, "pg_pool", None) or await get_pool()
                metrics_service = MetricsService(pool, stage_tracker)
    return metrics_service


async def get_alert_service() -> AlertService:
    """Return singleton AlertService."""
    global alert_service
    if alert_service is None:
        async with _alert_service_lock:
            if alert_service is None:
                adapter = create_database_adapter()
                await adapter.connect()
                metrics_svc = await get_metrics_service()
                alert_service = AlertService(adapter, metrics_svc)
    return alert_service


async def get_performance_collector() -> PerformanceCollector:
    """Return singleton PerformanceCollector."""
    global performance_collector
    if performance_collector is None:
        async with _performance_collector_lock:
            if performance_collector is None:
                performance_collector = PerformanceCollector(None, logger)  # Temporary fix
    return performance_collector


def get_websocket_manager() -> websocket_api.WebSocketManager:
    """Return singleton WebSocketManager."""
    global websocket_manager
    if websocket_manager is None:
        websocket_manager = websocket_api.WebSocketManager()
    return websocket_manager


async def get_database_adapter(request: Request) -> DatabaseAdapter:
    """Provide the shared DatabaseAdapter from app state (initialized at startup)."""
    adapter = getattr(request.app.state, "db_adapter", None)
    if adapter is None:
        raise RuntimeError("Database adapter has not been initialized")
    return adapter


# === PYDANTIC MODELS ===


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: dict[str, Any]


class UploadResponse(BaseModel):
    success: bool
    document_id: str | None
    status: str
    message: str
    metadata: dict[str, Any] | None


class ProcessingStatus(BaseModel):
    document_id: str
    status: str
    current_stage: str
    progress: float
    started_at: str | None
    completed_at: str | None
    error: str | None
    stage_status: dict[str, Any] | None = None  # Detailed per-stage status


class StageStatistics(BaseModel):
    stage_name: str
    total_documents: int
    successful: int
    failed: int
    pending: int
    average_processing_time: float | None


# === AUTHENTICATION ===

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


# Custom docs endpoints with auth
@app.get("/docs", include_in_schema=False)
async def get_documentation(request: Request):
    """Custom Swagger UI secured by bearer authentication."""
    credentials = await security_scheme(request)
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    auth_svc = await ensure_auth_service()
    claims = await AuthMiddleware(auth_svc)(request, allow_expired=True)
    if claims.get("role") not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return get_swagger_ui_html(
        openapi_url="/openapi.json", title=app.title, swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
    )


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(request: Request):
    """Custom ReDoc secured by bearer authentication."""
    credentials = await security_scheme(request)
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    auth_svc = await ensure_auth_service()
    claims = await AuthMiddleware(auth_svc)(request, allow_expired=True)
    if claims.get("role") not in {"admin", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - ReDoc",
        swagger_ui_parameters={"docExpansion": "none"},
        swagger_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )


# === HEALTH & STATUS ===


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information"""
    return {"name": "KRAI Processing Pipeline", "version": "0.50.0", "status": "operational"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
@limiter.limit(rate_limit_health_dynamic)
async def health_check(request: Request, response: Response):
    """
    Health check endpoint

    Checks:
    - API status
    - Database connectivity
    - Ollama status
    - Storage access
    """
    services = {
        "api": {"status": "healthy", "message": "API is running"},
        "database": {"status": "unknown", "message": ""},
        "ollama": {"status": "unknown", "message": ""},
        "storage": {"status": "unknown", "message": ""},
        "batch_operations": {"status": "unknown", "message": ""},
    }

    # Check database
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        services["database"] = {"status": "healthy", "message": "Database connected"}
    except Exception as e:
        services["database"] = {"status": "unhealthy", "message": f"Database error: {e!s}"}

    # Check Ollama
    try:
        import requests

        response = requests.get(  # noqa: ASYNC210
            f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/tags", timeout=5
        )
        if response.status_code == 200:
            models = response.json().get("models", [])
            services["ollama"] = {"status": "healthy", "message": f"{len(models)} models available"}
        else:
            services["ollama"] = {"status": "unhealthy", "message": "Ollama not responding"}
    except Exception as e:
        services["ollama"] = {"status": "unhealthy", "message": f"Ollama error: {e!s}"}

    # Check storage (Object Storage)
    try:
        # Test object storage credentials exist
        storage_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY")
        storage_secret = os.getenv("OBJECT_STORAGE_SECRET_KEY")
        storage_type = os.getenv("OBJECT_STORAGE_TYPE", "s3")

        if storage_key and storage_secret:
            services["storage"] = {
                "status": "configured",
                "message": f"Object storage credentials present ({storage_type})",
                "type": storage_type,
            }
        else:
            services["storage"] = {"status": "unconfigured", "message": "Object storage credentials missing"}
    except Exception as e:
        services["storage"] = {"status": "error", "message": f"Storage error: {e!s}"}

    # Batch operations health
    transaction_support = False
    try:
        await get_batch_task_service()
        await get_transaction_manager()
        transaction_support = True
        services["batch_operations"] = {
            "status": "healthy",
            "message": "Task service initialized",
            "transaction_support": transaction_support,
        }
    except Exception as exc:
        services["batch_operations"] = {
            "status": "unhealthy",
            "message": f"Batch services unavailable: {exc}",
            "transaction_support": transaction_support,
        }

    # Monitoring services health
    try:
        await get_metrics_service()
        await get_alert_service()
        ws_mgr = get_websocket_manager()

        services["monitoring"] = {
            "status": "healthy",
            "message": "Monitoring services active",
            "metrics_service": "initialized",
            "alert_service": "initialized",
            "websocket_connections": len(ws_mgr.active_connections),
        }
    except Exception as exc:
        services["monitoring"] = {
            "status": "unhealthy",
            "message": f"Monitoring services unavailable: {exc}",
            "websocket_connections": 0,
        }

    # Overall status
    overall_status = "healthy"
    if any(s["status"] == "unhealthy" for s in services.values()):
        overall_status = "unhealthy"
    elif any(s["status"] == "unknown" for s in services.values()):
        overall_status = "degraded"

    return {"status": overall_status, "timestamp": datetime.utcnow().isoformat(), "services": services}


# === UPLOAD ENDPOINTS ===


@app.post("/upload", response_model=UploadResponse, tags=["Upload"])
@limiter.limit(rate_limit_standard_dynamic)
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    document_type: str = Form("service_manual"),
    language: str = Form("en"),
    manufacturer: str | None = Form(None),
    series: str | None = Form(None),
    model: str | None = Form(None),
    force_reprocess: bool = Form(False),
    processor: UploadProcessor = Depends(get_upload_processor),
    current_user: dict = Depends(require_permission("documents:write")),
):
    """
    Upload a document for processing

    Args:
        file: PDF file to upload
        document_type: Type of document (service_manual, parts_catalog, user_guide)
        manufacturer: Optional manufacturer override from the admin upload form
        series: Optional product series override from the admin upload form
        model: Optional model override from the admin upload form
        force_reprocess: Force reprocessing if document already exists

    Returns:
        Upload result with document ID and status
    """
    # Save uploaded file temporarily
    import tempfile

    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / file.filename

    try:
        with open(temp_path, "wb") as f:  # noqa: ASYNC230
            content = await file.read()
            f.write(content)

        context = ProcessingContext(
            document_id="",
            file_path=str(temp_path),
            file_hash="",
            document_type=document_type,
            manufacturer=manufacturer or None,
            model=model or None,
            series=series or None,
            version=None,
            language=language or "en",
        )
        context.force_reprocess = force_reprocess

        result = await processor.process(context)
        result_data = result.data if isinstance(result.data, dict) else {}

        return UploadResponse(
            success=result.success,
            document_id=result_data.get("document_id"),
            status=result_data.get("status", "error"),
            message=(
                "Upload successful" if result.success else (result.error.message if result.error else "Upload failed")
            ),
            metadata=result_data.get("metadata"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()


@app.on_event("startup")
async def startup_events():
    """Initialize shared services and verify default admin user."""
    service = await ensure_auth_service()
    set_auth_service(service)
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")

    try:
        await service.ensure_default_admin(
            email=DEFAULT_ADMIN_EMAIL,
            username=DEFAULT_ADMIN_USERNAME,
            first_name=DEFAULT_ADMIN_FIRST_NAME,
            last_name=DEFAULT_ADMIN_LAST_NAME,
            password=admin_password,
        )
    except AuthenticationError as exc:
        if "already exists" in str(exc):
            logger.info("Default admin user already exists: %s", exc)
        else:
            logger.error("Failed to ensure default admin user: %s", exc)
            raise

    pool = await get_pool()

    # Initialize db_pool in app.state for API key validation middleware
    app.state.db_pool = pool

    # Initialize shared DatabaseAdapter for status/upload endpoints
    db_adapter = create_database_adapter()
    await db_adapter.connect()
    app.state.db_adapter = db_adapter

    # Services for document_processing router
    from backend.pipeline.master_pipeline import KRMasterPipeline
    from backend.services.storage_factory import create_storage_service

    try:
        app.state.storage_service = create_storage_service()
    except Exception as exc:
        logger.warning("Object storage not available: %s — thumbnail endpoint will fail", exc)
        app.state.storage_service = None
    app.state.pipeline = KRMasterPipeline(
        database_adapter=db_adapter,
        force_continue_on_errors=True,
    )
    await app.state.pipeline.initialize_services()

    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as exc:  # pragma: no cover - startup logging
        logger.warning("Database pool connection failed: %s", exc)

    await get_batch_task_service()
    await get_transaction_manager()
    logger.info("Batch services initialized with asyncpg pool")

    # Initialize Agent API router with the live pool
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ai_svc = AIService(ollama_url=ollama_url)
    reranking_svc = RerankingService()
    krai_agent = KRAIAgent(pool, ai_service=ai_svc, reranking_service=reranking_svc)
    app.state.krai_agent = krai_agent  # shared with openai_compat router
    agent_router = create_agent_api(pool, agent=krai_agent)
    app.include_router(agent_router)

    # Initialize monitoring services
    metrics_svc = await get_metrics_service()
    alert_svc = await get_alert_service()
    get_websocket_manager()

    # Start background tasks (refs kept on app.state so tasks aren't GC'd)
    app.state.alert_monitor_task = asyncio.create_task(alert_svc.start_alert_monitoring())
    app.state.metrics_broadcast_task = asyncio.create_task(websocket_api.start_periodic_broadcast(metrics_svc))

    logger.info("Monitoring services initialized (metrics, alerts, websocket)")
    logger.info(
        "Security: CORS origins=%s, Rate limiting=%s, Request validation=%s",
        cors_config["allow_origins"],
        security_config.RATE_LIMIT_ENABLED,
        security_config.REQUEST_VALIDATION_ENABLED,
    )


@app.on_event("shutdown")
async def shutdown_events():
    """Clean up resources on shutdown."""
    from backend.services.db_pool import close_pool

    if hasattr(app.state, "db_adapter"):
        try:
            await app.state.db_adapter.disconnect()
        except Exception as exc:
            logger.warning("Error closing db_adapter on shutdown: %s", exc)

    try:
        await close_pool()
    except Exception as exc:
        logger.warning("Error closing db_pool on shutdown: %s", exc)

    logger.info("Application shutdown complete")


@app.post("/upload/directory", tags=["Upload"])
@limiter.limit(rate_limit_upload_dynamic)
async def upload_directory(
    request: Request,
    directory_path: str,
    document_type: str = "service_manual",
    recursive: bool = False,
    force_reprocess: bool = False,
    current_user: dict = Depends(require_permission("documents:write")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
):
    """
    Upload all PDFs from a directory

    Args:
        directory_path: Path to directory containing PDFs
        document_type: Type of documents
        recursive: Scan subdirectories
        force_reprocess: Force reprocessing existing documents

    Returns:
        Batch upload results
    """
    directory = Path(directory_path)

    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    batch_processor = BatchUploadProcessor(adapter, max_file_size_mb=500)

    return await batch_processor.process_directory(
        directory=directory, document_type=document_type, recursive=recursive, force_reprocess=force_reprocess
    )


# === PROCESSING STATUS ===


@app.get("/status/{document_id}", response_model=ProcessingStatus, tags=["Status"])
@limiter.limit(rate_limit_standard_dynamic)
async def get_document_status(
    request: Request,
    document_id: str,
    current_user: dict = Depends(require_permission("documents:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
):
    """
    Get processing status for a document

    Args:
        document_id: Document UUID

    Returns:
        Current processing status
    """
    try:
        doc = await adapter.get_document(document_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # DocumentModel or dict-like from adapter
        status_val = (
            getattr(doc, "processing_status", None)
            or (doc.get("processing_status") if isinstance(doc, dict) else None)
            or "unknown"
        )
        if hasattr(status_val, "value"):
            status_val = status_val.value
        created = getattr(doc, "created_at", None) or (doc.get("created_at") if isinstance(doc, dict) else None)
        updated = getattr(doc, "updated_at", None) or (doc.get("updated_at") if isinstance(doc, dict) else None)
        started_at = created.isoformat() if created else None
        completed_at = updated.isoformat() if (updated and status_val == "completed") else None

        return ProcessingStatus(
            document_id=document_id,
            status=str(status_val),
            current_stage="unknown",
            progress=100.0 if status_val == "completed" else 0.0,
            started_at=started_at,
            completed_at=completed_at,
            error=None,
            stage_status={},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/pipeline", tags=["Status"])
async def get_pipeline_status(
    current_user: dict = Depends(require_permission("documents:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
):
    """
    Get overall pipeline status

    Returns:
        Statistics for all pipeline stages
    """
    try:
        prefix = getattr(adapter, "schema_prefix", "krai")
        core_schema = f"{prefix}_core"
        system_schema = f"{prefix}_system"
        documents = await adapter.execute_query(
            f"SELECT id, filename, processing_status, created_at FROM {core_schema}.documents",
            None,
        )
        queue = await adapter.execute_query(
            f"SELECT * FROM {system_schema}.processing_queue",
            None,
        )
        doc_list = documents if isinstance(documents, list) else []
        queue_list = queue if isinstance(queue, list) else []
        by_status = {}
        for d in doc_list:
            row = d if isinstance(d, dict) else (getattr(d, "__dict__", None) or {})
            ps = row.get("processing_status") if isinstance(row, dict) else getattr(d, "processing_status", None)
            if hasattr(ps, "value"):
                ps = ps.value
            by_status[ps] = by_status.get(ps, 0) + 1
        task_types = [
            "text_extraction",
            "image_processing",
            "classification",
            "metadata_extraction",
            "storage",
            "embedding",
            "search",
        ]
        by_task_type = {
            t: sum(
                1
                for q in queue_list
                if (q.get("task_type") if isinstance(q, dict) else getattr(q, "task_type", None)) == t
            )
            for t in task_types
        }
        return {
            "total_documents": len(doc_list),
            "in_queue": by_status.get("pending", 0) + len(queue_list),
            "processing": by_status.get("processing", 0),
            "completed": by_status.get("completed", 0),
            "failed": by_status.get("failed", 0),
            "by_task_type": by_task_type,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === LOGS & MONITORING ===


@app.get("/logs/{document_id}", tags=["Monitoring"])
async def get_document_logs(document_id: str, current_user: dict = Depends(require_permission("monitoring:read"))):
    """
    Get processing logs for a document

    Args:
        document_id: Document UUID

    Returns:
        Processing logs
    """
    try:
        # TODO: Replace with direct PostgreSQL connection
        # Get audit logs using adapter
        # logs = await adapter.execute_query(
        #     """SELECT * FROM krai_core.audit_log
        #        WHERE entity_type = %s AND entity_id = %s
        #        ORDER BY created_at DESC
        #        LIMIT 100""",
        #     ["document", document_id]
        # )

        # For now, return empty logs
        logs = []

        return {"document_id": document_id, "log_count": len(logs), "logs": logs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stages/statistics", tags=["Monitoring"])
async def get_stage_statistics(current_user: dict = Depends(require_permission("monitoring:read"))):
    """
    Get statistics for all processing stages

    Returns:
        Stage-wise statistics including pending, processing, completed counts
    """
    try:
        # Stage statistics require PostgreSQL functions
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stage statistics require PostgreSQL functions (not implemented yet)",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitoring/system", tags=["Monitoring"])
async def get_system_metrics(current_user: dict = Depends(require_permission("monitoring:read"))):
    """
    Get system performance metrics

    Returns:
        Performance statistics
    """
    try:
        # TODO: Replace with direct PostgreSQL connection
        # Get metrics from direct table
        # metrics = await adapter.execute_query(
        #     """SELECT timestamp, cpu_usage, memory_usage, disk_usage, query_count
        #        FROM krai_system.system_metrics
        #        ORDER BY timestamp DESC
        #        LIMIT 1""",
        #     []
        # )

        # For now, return empty metrics
        metrics = None

        if metrics:
            return metrics[0]
        return {"message": "No metrics available yet", "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e!s}")


# Include API routes
from backend.api.routes import pipeline_errors, scraping

# Note: Auth routes and dashboard will need pool-based initialization
# Temporarily commented out until refactored
# auth_router = auth_routes.initialize_auth_routes(pool)
# app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(foliant_router, prefix="/api/v1")
app.include_router(configuration_router, prefix="/api/v1")
app.include_router(error_codes_router, prefix="/api/v1")
app.include_router(videos_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(images_router, prefix="/api/v1")
app.include_router(batch_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(scraping.router, prefix="/api/v1")
app.include_router(pipeline_errors.router, prefix="/api/v1")

# Mount Monitoring API
from backend.api import monitoring_api

app.include_router(monitoring_api.router, prefix="/api/v1/monitoring", tags=["Monitoring"])

app.include_router(document_processing_router, prefix="/api/v1")

# OpenAI-compatible wrapper — used by OpenWebUI and other OpenAI clients
app.include_router(openai_compat_router)

# Mount WebSocket API
app.include_router(websocket_api.router, tags=["WebSocket"])


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }

    # Secure all endpoints by default
    for path in openapi_schema.get("paths", {}).values():
        for method in path.values():
            if method.get("tags") != ["authentication"]:
                method["security"] = [{"HTTPBearer": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
