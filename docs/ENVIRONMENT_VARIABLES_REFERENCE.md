# Environment Variables Reference

## Overview

This document provides a comprehensive reference for all environment variables used in the KRAI system. Environment variables are used to configure services, enable/disable features, and manage deployment settings across different environments.

**Current Configuration Approach:** All environment variables are consolidated in a single root `.env` file. Legacy modular files (`.env.database`, `.env.storage`, etc.) are deprecated.

## Configuration Files

### Primary Configuration

- **`.env`** - Single consolidated configuration file (required)
- **`.env.example`** - Template with all supported variables and documentation
- **`.env.local`** *(optional)* - Developer-specific overrides (gitignored)

### Related Documentation

- [`.env.example`](../.env.example) - Complete variable reference with examples
- [`docs/setup/DEPRECATED_VARIABLES.md`](setup/DEPRECATED_VARIABLES.md) - Legacy variable mappings
- [`DEPLOYMENT.md`](../DEPLOYMENT.md) - Production deployment guide
- [`DOCKER_SETUP.md`](../DOCKER_SETUP.md) - Docker configuration guide

---

## Variable Reference

This section documents all currently supported variables using a consistent schema:
- **Name:** Variable identifier
- **Required:** Whether the variable must be set
- **Default:** Default value if not specified
- **Example:** Sample value
- **Description:** What the variable controls
- **Used by:** Which components consume this variable
- **Notes:** Additional context or warnings

Variables are organized by functional area matching the structure in `.env.example`.

---

## Application Settings

### ENV
- **Required:** False
- **Default:** `production`
- **Example:** `ENV=development`
- **Description:** Runtime environment identifier (production, staging, development)
- **Used by:** Application startup, logging configuration, feature flags
- **Notes:** Affects default log levels and debug behavior
### API_HOST
- **Required:** False
- **Default:** `0.0.0.0`
- **Example:** `API_HOST=0.0.0.0`
- **Description:** Backend API host binding address (0.0.0.0 for Docker, 127.0.0.1 for local only)
- **Used by:** FastAPI/Uvicorn server
- **Notes:** Use 0.0.0.0 in Docker to allow external connections
### API_PORT
- **Required:** False
- **Default:** `8000`
- **Example:** `API_PORT=8000`
- **Description:** Backend API port for FastAPI/Uvicorn
- **Used by:** FastAPI/Uvicorn server, Docker Compose port mapping
- **Notes:** Must match Docker Compose port configuration
### LOG_LEVEL
- **Required:** False
- **Default:** `INFO`
- **Example:** `LOG_LEVEL=DEBUG`
- **Description:** Global log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Used by:** Python logging configuration across all modules
- **Notes:** Use DEBUG for development, INFO for production

## Database Configuration

### DATABASE_TYPE
- **Required:** True
- **Default:** `postgresql`
- **Example:** `DATABASE_TYPE=postgresql`
- **Description:** Database backend type (postgresql or sqlite)
- **Used by:** Database adapter factory
- **Notes:** PostgreSQL recommended for production; sqlite for testing only
### DATABASE_HOST
- **Required:** Yes (for PostgreSQL)
- **Default:** None
- **Example:** `DATABASE_HOST=krai-postgres`
- **Description:** PostgreSQL server hostname (Docker service name or IP)
- **Used by:** Database connection string builder
- **Notes:** Use Docker service name for container networking
### DATABASE_PORT
- **Required:** False
- **Default:** `5432`
- **Example:** `DATABASE_PORT=5432`
- **Description:** PostgreSQL service port
- **Used by:** Database connection string builder
- **Notes:** Standard PostgreSQL port is 5432
### DATABASE_NAME
- **Required:** True
- **Default:** None
- **Example:** `DATABASE_NAME=krai`
- **Description:** PostgreSQL database name
- **Used by:** Database connection string builder
- **Notes:** Must match database created during initialization
### DATABASE_USER
- **Required:** True
- **Default:** None
- **Example:** `DATABASE_USER=krai_user`
- **Description:** PostgreSQL username for application connections
- **Used by:** Database connection string builder
- **Notes:** Should have appropriate schema permissions
### DATABASE_PASSWORD
- **Required:** True
- **Default:** None
- **Example:** `DATABASE_PASSWORD=krai_secure_password`
- **Description:** PostgreSQL password for application user
- **Used by:** Database connection string builder
- **Notes:** Change for production! Use strong passwords
### DATABASE_CONNECTION_URL
- **Required:** No (constructed from above if missing)
- **Default:** `Constructed from DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD`
- **Example:** `DATABASE_CONNECTION_URL=postgresql://krai_user:password@krai-postgres:5432/krai`
- **Description:** Complete PostgreSQL connection string
- **Used by:** Database adapters, migration scripts
- **Notes:** Overrides individual DATABASE_* variables if set

## Object Storage Configuration

### OBJECT_STORAGE_TYPE
- **Required:** True
- **Default:** `s3`
- **Example:** `OBJECT_STORAGE_TYPE=s3`
- **Description:** Object storage implementation (s3-compatible for MinIO or S3-compatible storage)
- **Used by:** Storage adapter factory
- **Notes:** Currently only s3 is supported
### OBJECT_STORAGE_ENDPOINT
- **Required:** True
- **Default:** None
- **Example:** `OBJECT_STORAGE_ENDPOINT=http://krai-minio:9000`
- **Description:** S3-compatible endpoint URL (MinIO or S3-compatible storage)
- **Used by:** Storage adapter, upload handlers
- **Notes:** Use Docker service name for internal connections
### OBJECT_STORAGE_ACCESS_KEY
- **Required:** True
- **Default:** None
- **Example:** `OBJECT_STORAGE_ACCESS_KEY=minioadmin`
- **Description:** S3 access key ID (MinIO or S3-compatible storage)
- **Used by:** Storage adapter authentication
- **Notes:** Change default for production!
### OBJECT_STORAGE_SECRET_KEY
- **Required:** True
- **Default:** None
- **Example:** `OBJECT_STORAGE_SECRET_KEY=minioadmin123`
- **Description:** S3 secret access key (MinIO or S3-compatible storage)
- **Used by:** Storage adapter authentication
- **Notes:** Change default for production!
### OBJECT_STORAGE_REGION
- **Required:** False
- **Default:** `us-east-1`
- **Example:** `OBJECT_STORAGE_REGION=us-east-1`
- **Description:** AWS region identifier (MinIO accepts any string)
- **Used by:** S3 client configuration
- **Notes:** Use 'auto' for S3-compatible storage or specific region for AWS S3
### OBJECT_STORAGE_USE_SSL
- **Required:** False
- **Default:** `false`
- **Example:** `OBJECT_STORAGE_USE_SSL=false`
- **Description:** Enable HTTPS for storage endpoint
- **Used by:** S3 client configuration
- **Notes:** Set true for production with SSL certificates
### OBJECT_STORAGE_PUBLIC_URL
- **Required:** False
- **Default:** None
- **Example:** `OBJECT_STORAGE_PUBLIC_URL=http://localhost:9000`
- **Description:** Public URL for dashboard and API clients to access stored files
- **Used by:** Dashboard image loading, API responses, CDN configuration
- **Notes:** Must be accessible from user browsers
## AI Service Configuration

### AI_SERVICE_TYPE
- **Required:** No
- **Default:** `ollama`
- **Example:** `AI_SERVICE_TYPE=ollama`
- **Description:** AI service provider type (ollama or openai)
- **Used by:** AI service factory
- **Notes:** Currently only ollama is fully supported

### OLLAMA_URL
- **Required:** Yes
- **Default:** None
- **Example:** `OLLAMA_URL=http://krai-ollama:11434`
- **Description:** Ollama server URL for internal backend connections
- **Used by:** Ollama service client, embedding processor, vision processor
- **Notes:** Use Docker service name for container networking

### OLLAMA_MODEL_EMBEDDING
- **Required:** No
- **Default:** `nomic-embed-text:latest`
- **Example:** `OLLAMA_MODEL_EMBEDDING=nomic-embed-text:latest`
- **Description:** Embedding model for vector generation
- **Used by:** Embedding processor, semantic search
- **Notes:** Must be pulled to Ollama before use

### OLLAMA_MODEL_EXTRACTION
- **Required:** No
- **Default:** `qwen2.5:3b`
- **Example:** `OLLAMA_MODEL_EXTRACTION=qwen2.5:3b`
- **Description:** Structured extraction model for product specs as JSON
- **Used by:** Product extraction processor
- **Notes:** Smaller models (3b) work well for structured tasks

### OLLAMA_MODEL_CHAT
- **Required:** No
- **Default:** `llama3.2:3b`
- **Example:** `OLLAMA_MODEL_CHAT=llama3.2:3b`
- **Description:** Conversational model for agent/chat responses
- **Used by:** Agent API, chat endpoints
- **Notes:** Balance model size with response quality

### OLLAMA_MODEL_VISION
- **Required:** No
- **Default:** `llava:7b`
- **Example:** `OLLAMA_MODEL_VISION=llava:7b`
- **Description:** Vision-capable model for diagram/OCR understanding
- **Used by:** Vision processor, image analysis
- **Notes:** Requires significant VRAM (7b+ models)

### OLLAMA_NUM_CTX
- **Required:** No
- **Default:** `8192`
- **Example:** `OLLAMA_NUM_CTX=8192`
- **Description:** Context window tokens for Ollama prompts
- **Used by:** All Ollama model calls
- **Notes:** Higher values require more VRAM

### USE_GPU
- **Required:** No
- **Default:** `false`
- **Example:** `USE_GPU=false`
- **Description:** Enable GPU acceleration for OpenCV/ML pipelines
- **Used by:** OpenCV operations, ML inference
- **Notes:** Requires CUDA drivers and compatible GPU

### CUDA_VISIBLE_DEVICES
- **Required:** No (if USE_GPU=true)
- **Default:** `0`
- **Example:** `CUDA_VISIBLE_DEVICES=0`
- **Description:** CUDA device index to target (0=primary GPU)
- **Used by:** CUDA runtime, GPU operations
- **Notes:** Use comma-separated list for multiple GPUs

---

## Authentication & Security

### JWT_ALGORITHM
- **Required:** No
- **Default:** `RS256`
- **Example:** `JWT_ALGORITHM=RS256`
- **Description:** JWT signing algorithm (RS256 recommended for asymmetric keys)
- **Used by:** Auth service, token validation
- **Notes:** RS256 requires JWT_PRIVATE_KEY and JWT_PUBLIC_KEY

### JWT_ACCESS_TOKEN_EXPIRE_MINUTES
- **Required:** No
- **Default:** `60`
- **Example:** `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60`
- **Description:** Access token lifetime in minutes
- **Used by:** Auth service, token generation
- **Notes:** Shorter lifetimes improve security

### JWT_REFRESH_TOKEN_EXPIRE_DAYS
- **Required:** No
- **Default:** `30`
- **Example:** `JWT_REFRESH_TOKEN_EXPIRE_DAYS=30`
- **Description:** Refresh token lifetime in days
- **Used by:** Auth service, token refresh
- **Notes:** Balance convenience with security

### JWT_PRIVATE_KEY
- **Required:** Yes (if JWT_ALGORITHM=RS256)
- **Default:** None
- **Example:** `JWT_PRIVATE_KEY=<base64-encoded-der>`
- **Description:** Base64-encoded PKCS8 private key (DER format)
- **Used by:** Auth service, token signing
- **Notes:** Generate with setup.sh/setup.bat; keep secret!

### JWT_PUBLIC_KEY
- **Required:** Yes (if JWT_ALGORITHM=RS256)
- **Default:** None
- **Example:** `JWT_PUBLIC_KEY=<base64-encoded-der>`
- **Description:** Base64-encoded SubjectPublicKeyInfo public key (DER format)
- **Used by:** Auth service, token validation
- **Notes:** Can be shared publicly for token verification

### MAX_LOGIN_ATTEMPTS
- **Required:** No
- **Default:** `5`
- **Example:** `MAX_LOGIN_ATTEMPTS=5`
- **Description:** Maximum failed login attempts before account lockout
- **Used by:** Auth service, login handler
- **Notes:** Prevents brute-force attacks

### PASSWORD_MIN_LENGTH
- **Required:** No
- **Default:** `12`
- **Example:** `PASSWORD_MIN_LENGTH=12`
- **Description:** Minimum password length enforced by backend validation
- **Used by:** Password validation
- **Notes:** 12+ characters recommended for security

### PASSWORD_REQUIRE_UPPERCASE
- **Required:** No
- **Default:** `false`
- **Example:** `PASSWORD_REQUIRE_UPPERCASE=false`
- **Description:** Require uppercase letters in passwords
- **Used by:** Password validation
- **Notes:** Part of password complexity requirements

### PASSWORD_REQUIRE_LOWERCASE
- **Required:** No
- **Default:** `false`
- **Example:** `PASSWORD_REQUIRE_LOWERCASE=false`
- **Description:** Require lowercase letters in passwords
- **Used by:** Password validation
- **Notes:** Part of password complexity requirements

### PASSWORD_REQUIRE_NUMBER
- **Required:** No
- **Default:** `false`
- **Example:** `PASSWORD_REQUIRE_NUMBER=false`
- **Description:** Require numbers in passwords
- **Used by:** Password validation
- **Notes:** Part of password complexity requirements

### PASSWORD_REQUIRE_SPECIAL
- **Required:** No
- **Default:** `false`
- **Example:** `PASSWORD_REQUIRE_SPECIAL=false`
- **Description:** Require special characters in passwords
- **Used by:** Password validation
- **Notes:** Part of password complexity requirements

---

## Processing Pipeline Settings

### ENABLE_PRODUCT_EXTRACTION
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_PRODUCT_EXTRACTION=true`
- **Description:** Extract product models from manuals
- **Used by:** Product extraction processor
- **Notes:** Recommended for service manuals

### ENABLE_PARTS_EXTRACTION
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_PARTS_EXTRACTION=true`
- **Description:** Extract spare parts catalogs
- **Used by:** Parts extraction processor
- **Notes:** Recommended for service manuals

### ENABLE_ERROR_CODE_EXTRACTION
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_ERROR_CODE_EXTRACTION=true`
- **Description:** Extract diagnostic error codes
- **Used by:** Error code extraction processor
- **Notes:** Critical for troubleshooting features

### ENABLE_IMAGE_EXTRACTION
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_IMAGE_EXTRACTION=true`
- **Description:** Extract inline images from PDFs
- **Used by:** Image extraction processor
- **Notes:** Required for vision analysis

### ENABLE_OCR
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_OCR=true`
- **Description:** Run OCR on extracted images for searchable text
- **Used by:** OCR processor
- **Notes:** Depends on Tesseract/OpenCV

### ENABLE_VISION_AI
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_VISION_AI=true`
- **Description:** Run AI-based vision analysis on extracted images
- **Used by:** Vision processor
- **Notes:** Set false if low VRAM

### ENABLE_EMBEDDINGS
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_EMBEDDINGS=true`
- **Description:** Generate embeddings for semantic search
- **Used by:** Embedding processor
- **Notes:** Required for vector search

---

## Web Scraping Configuration

### SCRAPING_BACKEND
- **Required:** No
- **Default:** `beautifulsoup`
- **Example:** `SCRAPING_BACKEND=beautifulsoup`
- **Description:** Scraping backend (beautifulsoup or firecrawl)
- **Used by:** Scraping service
- **Notes:** beautifulsoup for local, firecrawl for cloud

### ENABLE_LINK_ENRICHMENT
- **Required:** No
- **Default:** `true`
- **Example:** `ENABLE_LINK_ENRICHMENT=true`
- **Description:** Enable post-processing link enrichment
- **Used by:** Link enrichment processor
- **Notes:** Fetches additional metadata for links

### FIRECRAWL_API_URL
- **Required:** No (if SCRAPING_BACKEND=firecrawl)
- **Default:** `http://krai-firecrawl-api:3002`
- **Example:** `FIRECRAWL_API_URL=http://krai-firecrawl-api:3002`
- **Description:** Firecrawl API base URL
- **Used by:** Firecrawl service client
- **Notes:** Self-hosted or cloud endpoint

### FIRECRAWL_NUM_WORKERS
- **Required:** No
- **Default:** `4`
- **Example:** `FIRECRAWL_NUM_WORKERS=4`
- **Description:** Number of Firecrawl worker threads
- **Used by:** Firecrawl API service
- **Notes:** Adjust based on CPU cores and expected load

---

## External API Keys & Tunnels

### YOUTUBE_API_KEY
- **Required:** No
- **Default:** None
- **Example:** `YOUTUBE_API_KEY=your-youtube-api-key-here`
- **Description:** YouTube Data API key for video metadata
- **Used by:** YouTube integration
- **Notes:** Obtain from Google Cloud Console (10k daily quota)

### OPENAI_API_KEY
- **Required:** No (if using OpenAI)
- **Default:** None
- **Example:** `OPENAI_API_KEY=sk-...`
- **Description:** OpenAI API key for GPT models
- **Used by:** OpenAI service client (if enabled)
- **Notes:** Required if FIRECRAWL_LLM_PROVIDER=openai

### CLOUDFLARE_TUNNEL_TOKEN
- **Required:** No
- **Default:** None
- **Example:** `CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token-here`
- **Description:** Cloudflare Tunnel token for exposing services
- **Used by:** Cloudflare Tunnel daemon
- **Notes:** For exposing n8n or webhook endpoints

---

## Docker Compose Configuration

### N8N_BASIC_AUTH_USER
- **Required:** No
- **Default:** `admin`
- **Example:** `N8N_BASIC_AUTH_USER=admin`
- **Description:** n8n basic auth username
- **Used by:** n8n service
- **Notes:** Change for production!

### N8N_BASIC_AUTH_PASSWORD
- **Required:** No
- **Default:** `changeme`
- **Example:** `N8N_BASIC_AUTH_PASSWORD=changeme`
- **Description:** n8n basic auth password
- **Used by:** n8n service
- **Notes:** Change for production!

### PGADMIN_DEFAULT_EMAIL
- **Required:** No
- **Default:** `admin@krai.local`
- **Example:** `PGADMIN_DEFAULT_EMAIL=admin@krai.local`
- **Description:** pgAdmin default admin email
- **Used by:** pgAdmin service
- **Notes:** Used for pgAdmin login

### PGADMIN_DEFAULT_PASSWORD
- **Required:** No
- **Default:** `changeme`
- **Example:** `PGADMIN_DEFAULT_PASSWORD=changeme`
- **Description:** pgAdmin default admin password
- **Used by:** pgAdmin service
- **Notes:** Change for production!

### MINIO_BROWSER_REDIRECT_URL
- **Required:** No
- **Default:** `http://localhost:9001`
- **Example:** `MINIO_BROWSER_REDIRECT_URL=http://localhost:9001`
- **Description:** MinIO browser console redirect URL
- **Used by:** MinIO service
- **Notes:** For accessing MinIO web console

### REDIS_URL
- **Required:** No
- **Default:** `redis://krai-redis:6379`
- **Example:** `REDIS_URL=redis://krai-redis:6379`
- **Description:** Redis URL for application cache
- **Used by:** Caching service
- **Notes:** Optional performance optimization

---

## Playwright Configuration

### PLAYWRIGHT_MAX_CONCURRENT_SESSIONS
- **Required:** No
- **Default:** `10`
- **Example:** `PLAYWRIGHT_MAX_CONCURRENT_SESSIONS=10`
- **Description:** Maximum concurrent browser sessions for Playwright service
- **Used by:** Playwright/browserless service
- **Notes:** Adjust based on available memory (each session ~200-500MB)

### PLAYWRIGHT_CONNECTION_TIMEOUT
- **Required:** No
- **Default:** `60000`
- **Example:** `PLAYWRIGHT_CONNECTION_TIMEOUT=60000`
- **Description:** Connection timeout in milliseconds for Playwright
- **Used by:** Playwright/browserless service
- **Notes:** Prevents hanging connections

### PLAYWRIGHT_HEALTH_ENABLED
- **Required:** No (for Docker)
- **Default:** `true`
- **Example:** `PLAYWRIGHT_HEALTH_ENABLED=true`
- **Description:** Enable health checks for Playwright service
- **Used by:** Playwright/browserless service
- **Notes:** Required for Docker healthcheck to work

### PLAYWRIGHT_MICROSERVICE_URL
- **Required:** Yes (if using Firecrawl)
- **Default:** `http://krai-playwright:3000`
- **Example:** `PLAYWRIGHT_MICROSERVICE_URL=http://krai-playwright:3000`
- **Description:** Playwright service URL for Firecrawl (internal Docker network)
- **Used by:** Firecrawl API and Worker services
- **Notes:** Do NOT add /scrape suffix - Firecrawl handles routing internally

---

## Test Environment Variables

### TEST_DATABASE_NAME
- **Required:** No (for testing)
- **Default:** `krai_test`
- **Example:** `TEST_DATABASE_NAME=krai_test`
- **Description:** Test database name (separate from production)
- **Used by:** Test suite
- **Notes:** Automatically created/destroyed during tests

### TEST_DATABASE_USER
- **Required:** No (for testing)
- **Default:** `krai_test`
- **Example:** `TEST_DATABASE_USER=krai_test`
- **Description:** Test database user
- **Used by:** Test suite
- **Notes:** Separate from production user

### TEST_DATABASE_PASSWORD
- **Required:** No (for testing)
- **Default:** `krai_test_password`
- **Example:** `TEST_DATABASE_PASSWORD=krai_test_password`
- **Description:** Test database password
- **Used by:** Test suite
- **Notes:** Can use simple password for tests

### TEST_DATABASE_URL
- **Required:** No (for testing)
- **Default:** `postgresql://krai_test:krai_test_password@postgresql-test:5432/krai_test`
- **Example:** `TEST_DATABASE_URL=postgresql://krai_test:krai_test_password@postgresql-test:5432/krai_test`
- **Description:** Test database connection URL
- **Used by:** Test suite
- **Notes:** Points to separate test database

---

## Deprecated Variables

**IMPORTANT:** The following variables are deprecated and should not be used in new deployments.

For complete deprecation information, migration instructions, and variable mappings, see:
- [`docs/setup/DEPRECATED_VARIABLES.md`](setup/DEPRECATED_VARIABLES.md) - Complete deprecation reference

### Deprecated Database Variables

| Variable | Replaced By | Notes |
|----------|-------------|-------|
| `DATABASE_URL` | `DATABASE_CONNECTION_URL` | Renamed for clarity |

### Deprecated Storage Variables

Legacy storage variable mappings were removed from this reference. See `docs/setup/DEPRECATED_VARIABLES.md` for migration details.

### Deprecated AI Service Variables

| Variable | Replaced By | Notes |
|----------|-------------|-------|
| `OLLAMA_BASE_URL` | `OLLAMA_URL` | Simplified naming convention |
| `AI_SERVICE_URL` | `OLLAMA_URL` | Consolidated into single variable |

---

## Configuration Management

### Variable Precedence

1. Environment variables (highest priority)
2. `.env` file
3. Default values in code
4. Configuration templates (lowest priority)

### Loading Order

1. `.env` - Base configuration
2. `.env.local` - Developer overrides (gitignored)
3. System environment variables - Runtime overrides

### Validation

Run validation scripts to ensure configuration is correct:

```bash
# Validate all required variables are set
python scripts/validate_env.py --verbose

# Test database connectivity
python scripts/test_db_connection.py

# Test storage connectivity
python scripts/test_storage_connection.py
```

---

## Best Practices

### Security

1. **Never commit secrets**: Use `.env.example` templates only
2. **Use strong passwords**: Generate cryptographically secure passwords
3. **Rotate secrets regularly**: Update JWT keys and API keys periodically
4. **Use environment-specific configs**: Separate development and production settings
5. **Store production secrets securely**: Use a secrets manager (1Password, Vault, etc.)

### Performance

1. **Tune connection pools**: Adjust based on expected load
2. **Optimize batch sizes**: Balance memory usage and throughput
3. **Enable caching**: Use Redis for frequently accessed data
4. **Monitor resource usage**: Adjust settings based on metrics

### Maintenance

1. **Document changes**: Update this reference when adding variables
2. **Use semantic naming**: Choose descriptive variable names
3. **Group related settings**: Organize variables by service/feature
4. **Provide defaults**: Ensure reasonable default values

---

## Troubleshooting

### Common Issues

1. **Missing variables**: Check `.env.example` for required settings
2. **Invalid values**: Validate variable formats and ranges
3. **Permission issues**: Check file permissions for configuration files
4. **Service connectivity**: Verify network settings and endpoints

```bash
# Check Firecrawl API logs
docker logs krai-firecrawl-api-prod --tail 50

# Check Playwright logs
docker logs krai-playwright-prod --tail 50

# Test Playwright health
curl http://localhost:3000/pressure

# Test Firecrawl API health
curl http://localhost:9002/health
```

**Common Firecrawl Issues:**
- **Playwright unhealthy:** Check `/pressure` endpoint returns 200
- **Firecrawl restart loop:** Verify PLAYWRIGHT_MICROSERVICE_URL has no /scrape suffix
- **Worker not starting:** Ensure Ollama service is healthy and models are pulled

### Debug Commands

```bash
# Check loaded environment variables
docker-compose exec krai-engine env | grep -E "DATABASE|OBJECT_STORAGE|OLLAMA"

# Validate configuration files
docker-compose config

# Test service connectivity
docker-compose exec krai-postgres pg_isready
docker-compose exec krai-minio mc alias list
curl http://localhost:11434/api/tags
```

---

## Additional Resources

- [`.env.example`](../.env.example) - Complete template with all variables
- [`DEPLOYMENT.md`](../DEPLOYMENT.md) - Production deployment guide
- [`DOCKER_SETUP.md`](../DOCKER_SETUP.md) - Docker configuration guide
- [`docs/setup/DEPRECATED_VARIABLES.md`](setup/DEPRECATED_VARIABLES.md) - Deprecation reference
- [`DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md) - Database schema documentation

---

**Last Updated:** 2024-11-19
**Configuration Approach:** Consolidated single `.env` file
**Deprecated:** Legacy modular `.env.*` files
