"""
KR-AI-Engine Main Application
FastAPI application with all endpoints and services
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Configure logger
logger = logging.getLogger("krai.api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Ensure project root is on sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from multiple .env files
# Priority: Later files override earlier ones
try:
    from pathlib import Path

    from dotenv import load_dotenv

    # Determine project root (parent of backend/)
    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent

    # Load all .env files in priority order (later overrides earlier)
    env_files = [
        ".env",  # Base config (lowest priority)
        ".env.database",  # Database credentials
        ".env.storage",  # R2/Storage config
        ".env.external",  # External APIs (YouTube, etc.)
        ".env.pipeline",  # Pipeline settings
        ".env.ai",  # AI settings (LLM_MAX_PAGES, OLLAMA models)
    ]

    loaded_files = []
    for env_file in env_files:
        env_path = PROJECT_ROOT / env_file
        if env_path.exists():
            load_dotenv(env_path, override=True)
            loaded_files.append(env_file)
            logger.info("Loaded configuration from %s", env_file)

    if not loaded_files:
        logger.warning("No .env files found - falling back to system environment variables")
    else:
        logger.info("Loaded %s configuration file(s)", len(loaded_files))

except ImportError:
    logger.warning("python-dotenv not installed, using system environment variables only")

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.content_management_api import ContentManagementAPI
from api.defect_detection_api import DefectDetectionAPI

# Import APIs
from api.document_api import DocumentAPI
from api.features_api import FeaturesAPI
from api.openai_compatible_api import OpenAICompatibleAPI
from api.search_api import SearchAPI
from services.ai_service import AIService
from services.config_service import ConfigService
from services.database_factory import create_database_adapter
from services.features_service import FeaturesService
from services.link_checker_service import LinkCheckerService

# Import services
from services.storage_factory import create_storage_service
from services.video_enrichment_service import VideoEnrichmentService

# Global services
database_service = None
storage_service = None
ai_service = None
config_service = None
features_service = None
video_enrichment_service = None
link_checker_service = None

# Global APIs (initialized in lifespan)
document_api = None
search_api = None
defect_detection_api = None
features_api = None
content_management_api = None
openai_api = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup event handler"""
    global database_service, storage_service, ai_service, config_service, features_service
    global video_enrichment_service, link_checker_service
    global document_api, search_api, defect_detection_api, features_api, content_management_api, openai_api

    # Startup
    logger.info("🚀 Starting KR-AI-Engine…")

    try:
        # Initialize configuration service
        config_service = ConfigService()
        logger.info("✅ Configuration service initialized")

        # Initialize database service
        database_service = create_database_adapter()
        # Factory automatically selects adapter based on DATABASE_TYPE environment variable
        await database_service.connect()
        database_type = os.getenv("DATABASE_TYPE", "postgresql")
        logger.info(f"✅ Database service connected ({database_type})")
        if database_service.pg_pool:
            logger.info("✅ PostgreSQL connection pool initialized")

        # Initialize object storage service
        storage_service = create_storage_service()
        # Factory supports MinIO and S3-compatible storage
        await storage_service.connect()
        storage_type = os.getenv("OBJECT_STORAGE_TYPE", "s3")
        logger.info(f"✅ Object storage service connected ({storage_type})")

        # Initialize AI service
        ai_service = AIService(ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"))
        await ai_service.connect()
        logger.info("✅ AI service connected")

        # Initialize features service
        features_service = FeaturesService(ai_service, database_service)
        logger.info("✅ Features service initialized")

        # Initialize video enrichment service
        video_enrichment_service = VideoEnrichmentService()
        logger.info("✅ Video enrichment service initialized")

        # Initialize link checker service
        link_checker_service = LinkCheckerService()
        logger.info("✅ Link checker service initialized")

        # NOW initialize APIs with services
        document_api = DocumentAPI(database_service, storage_service, ai_service)
        search_api = SearchAPI(database_service, ai_service)
        defect_detection_api = DefectDetectionAPI(ai_service, database_service)
        features_api = FeaturesAPI(database_service, features_service)
        content_management_api = ContentManagementAPI(
            database_service=database_service,
            video_enrichment_service=video_enrichment_service,
            link_checker_service=link_checker_service,
        )
        openai_api = OpenAICompatibleAPI(database_service, ai_service)

        # Include routers
        app.include_router(document_api.router)
        app.include_router(search_api.router)
        app.include_router(defect_detection_api.router)
        app.include_router(features_api.router)
        app.include_router(content_management_api.router)
        app.include_router(openai_api.router)
        logger.info("✅ API routers registered (including OpenAI-compatible)")

        logger.info("🎯 KR-AI-Engine ready!")

    except Exception:
        logger.exception("❌ Startup failed")
        raise

    # Yield control to the application
    yield

    # Shutdown
    logger.info("🛑 Shutting down KR-AI-Engine…")
    if database_service:
        logger.info("✅ Database service disconnected")
    if storage_service:
        logger.info("✅ Storage service disconnected")
    if ai_service:
        logger.info("✅ AI service disconnected")
    logger.info("👋 KR-AI-Engine stopped")


# Create FastAPI application with lifespan
app = FastAPI(
    title="KR-AI-Engine",
    description="AI-powered document processing system for technical documentation",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "KR-AI-Engine API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "documents": "/documents",
            "search": "/search",
            "defect_detection": "/defect-detection",
            "features": "/features",
            "content_management": "/content",
            "openai_compatible": "/v1/chat/completions",
            "health": "/health",
        },
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """System health check"""
    try:
        health_status = {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "services": {}}

        # Check database service
        if database_service:
            db_health = await database_service.health_check()
            health_status["services"]["database"] = db_health
        else:
            health_status["services"]["database"] = {"status": "not_initialized"}

        # Check storage service
        if storage_service:
            storage_health = await storage_service.health_check()
            health_status["services"]["storage"] = storage_health
        else:
            health_status["services"]["storage"] = {"status": "not_initialized"}

        # Check AI service
        if ai_service:
            ai_health = await ai_service.health_check()
            health_status["services"]["ai"] = ai_health
        else:
            health_status["services"]["ai"] = {"status": "not_initialized"}

        # Check config service
        if config_service:
            config_health = config_service.health_check()
            health_status["services"]["config"] = config_health
        else:
            health_status["services"]["config"] = {"status": "not_initialized"}

        # Determine overall status
        all_healthy = all(service.get("status") == "healthy" for service in health_status["services"].values())

        if not all_healthy:
            health_status["status"] = "degraded"

        return health_status

    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


# System info endpoint
@app.get("/info")
async def system_info():
    """System information"""
    try:
        return {
            "application": "KR-AI-Engine",
            "version": "1.0.0",
            "environment": {
                "python_version": "3.11+",
                "fastapi_version": "0.104+",
                "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
                "database_url": os.getenv("DATABASE_URL", "Not configured"),
                "storage_provider": os.getenv("OBJECT_STORAGE_TYPE", "s3"),
                "database_type": os.getenv("DATABASE_TYPE", "postgresql"),
            },
            "features": {
                "document_processing": True,
                "semantic_search": True,
                "defect_detection": True,
                "features_management": True,
                "vector_search": True,
                "ai_classification": True,
                "video_enrichment": True,
                "link_checking": True,
            },
            "processing_pipeline": [
                "Upload Processor",
                "Text Processor",
                "Image Processor",
                "Classification Processor",
                "Metadata Processor",
                "Storage Processor",
                "Embedding Processor",
                "Search Processor",
            ],
            "content_management": {
                "video_enrichment": {
                    "platforms": ["YouTube", "Vimeo", "Brightcove"],
                    "features": ["metadata", "thumbnails", "duration", "deduplication"],
                },
                "link_checking": {"features": ["validation", "redirect_following", "auto_fixing", "url_cleaning"]},
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """404 error handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested resource was not found",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """500 error handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An internal server error occurred",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Run the application
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
