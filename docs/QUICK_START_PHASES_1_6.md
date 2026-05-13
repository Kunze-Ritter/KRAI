# KRAI Quick Start Guide - Phases 1-6
# =====================================

Get KRAI up and running in 5 minutes with this streamlined setup guide. This guide covers the local-first architecture with Docker Compose, MinIO storage, and PostgreSQL database.

## 🚀 5-Minute Setup

### Prerequisites

- **Docker & Docker Compose** (installed and running)
- **Git** (for cloning the repository)
- **8GB+ RAM** (recommended for optimal performance)
- **10GB+ free disk space**

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/KRAI-minimal.git
cd KRAI-minimal

# Copy environment configuration
cp .env.example .env

# Quick configuration script
python scripts/quick_setup.py
```

### Step 2: Start Services

```bash
# Start all services with Docker Compose
docker-compose up -d

# Wait for services to be ready (automated)
python scripts/wait_for_services.py
```

### Step 3: Initialize Database

```bash
# Apply database migrations
python scripts/apply_migrations.py

# Verify setup
python scripts/health_check.py
```

### Step 3a: Optional - Setup Firecrawl (Advanced Web Scraping)

Firecrawl provides advanced web scraping with JavaScript rendering and LLM-based structured extraction. This is optional but recommended for production use.

**Prerequisites:**
- Additional 2GB RAM for Firecrawl services
- Docker Compose already running

**Quick Setup:**

```bash
# Start Firecrawl services
docker-compose up -d krai-redis krai-playwright krai-firecrawl-api krai-firecrawl-worker

# Wait for services to be ready
sleep 10

# Verify Firecrawl is running
curl http://localhost:3002/health

# Expected response: {"status":"healthy"}
```

**Enable Firecrawl in Configuration:**

Edit `.env` file:

```bash
# Change scraping backend from beautifulsoup to firecrawl
SCRAPING_BACKEND=firecrawl

# Optional: Enable advanced features
ENABLE_LINK_ENRICHMENT=true
ENABLE_MANUFACTURER_CRAWLING=true
```

**What You Get:**
- ✅ JavaScript rendering for dynamic websites
- ✅ LLM-ready Markdown output (better for AI analysis)
- ✅ Structured data extraction (product specs, error codes)
- ✅ Automatic fallback to BeautifulSoup if Firecrawl unavailable

**Access Points:**

- **Firecrawl API**: <http://localhost:3002>
- **Firecrawl Admin UI**: <http://localhost:3002/admin/@/queues> (password: changeme_firecrawl_admin)

**Skip This Step If:**
- You're just testing KRAI
- You don't need advanced web scraping
- You have limited RAM (< 16GB)

The system works perfectly with BeautifulSoup (default) for basic HTML scraping.

**Learn More:**
- Full documentation: `docs/PRODUCT_RESEARCH.md`
- Example scripts: `examples/firecrawl_*.py`
- Firecrawl vs BeautifulSoup comparison: See Product Research docs

### Step 4: Test the System

```bash
# Run quick validation test
python scripts/quick_test.py

# Test document processing
python scripts/test_single_document.py service_documents/sample.pdf
```

### Step 5: Access the System

- **API Documentation**: http://localhost:8000/docs
- **Laravel Dashboard**: http://localhost:9100
- **MinIO Console**: http://localhost:9001 (admin/password123)
- **Database**: localhost:5432 (krai_user/krai_password)

**Note:** Port 3000 is used internally by Playwright service for web scraping (Firecrawl). The user-facing dashboard is Laravel/Filament at port 9100.

🎉 **KRAI is now running!** You can start processing documents and using the search functionality.

## 📋 What You Get

This setup includes:

### Core Services
- **PostgreSQL Database** with all Phase 1-6 schemas
- **MinIO Object Storage** for documents and media
- **Ollama AI Service** for embeddings and LLM
- **FastAPI Backend** with REST API
- **Firecrawl Services** (optional) for advanced web scraping

### Phase 1-6 Features
- **Multimodal Processing**: Text, images, tables, videos, links
- **Hierarchical Chunking**: Smart document structure analysis
- **SVG Extraction**: Vector graphics processing and conversion
- **Context Extraction**: AI-powered media context analysis
- **Embedding Generation**: Cross-modal semantic embeddings
- **Advanced Search**: Unified multimodal search capabilities

### Development Tools
- **Automatic Migrations**: Database schema management
- **Health Monitoring**: Service status and metrics
- **Test Suites**: Comprehensive validation tests
- **Documentation**: API docs and user guides

## 🔧 Configuration Options

### Basic Configuration

Edit `.env` file for basic customization:

```bash
# Database Configuration
POSTGRES_DB=krai_db
POSTGRES_USER=krai_user
POSTGRES_PASSWORD=your_secure_password

# Storage Configuration
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key

# AI Service Configuration
OPENAI_API_KEY=your_openai_key  # Optional - uses Ollama by default
OLLAMA_MODEL=llama2  # Local AI model
```

### Feature Flags

Enable/disable specific features:

```bash
# Core Features
ENABLE_HIERARCHICAL_CHUNKING=true
ENABLE_SVG_EXTRACTION=true
ENABLE_TABLE_EXTRACTION=true
ENABLE_CONTEXT_EXTRACTION=true
ENABLE_MULTIMODAL_SEARCH=true

# Advanced Features
ENABLE_TWO_STAGE_SEARCH=true
ENABLE_CONTEXT_AWARE_IMAGES=true
ENABLE_ERROR_CODE_DETECTION=true

# Web Scraping Features (Optional - requires Firecrawl)
SCRAPING_BACKEND=firecrawl  # or 'beautifulsoup'
ENABLE_LINK_ENRICHMENT=false
ENABLE_MANUFACTURER_CRAWLING=false
```

### Performance Tuning

Optimize for your hardware:

```bash
# For High-Performance Systems
EMBEDDING_BATCH_SIZE=50
MAX_CONCURRENT_PROCESSES=8
DATABASE_POOL_SIZE=20

# For Resource-Constrained Systems
EMBEDDING_BATCH_SIZE=10
MAX_CONCURRENT_PROCESSES=2
DATABASE_POOL_SIZE=5
```

## 📁 Directory Structure

```
KRAI-minimal/
├── backend/                 # Python backend services
│   ├── api/                # REST API endpoints
│   ├── services/           # Core business logic
│   ├── pipeline/           # Document processing pipeline
│   └── models/             # Data models and schemas
├── database/               # Database schemas and migrations
│   ├── migrations/         # SQL migration files
│   ├── seeds/              # Initial data
│   └── initdb/             # Initialization scripts
├── scripts/                # Utility and management scripts
│   ├── test_*.py          # Test and validation scripts
│   ├── quick_setup.py     # Quick configuration utility
│   └── health_check.py    # System health monitoring
├── docs/                   # Documentation and guides
├── tests/                  # Test suites and fixtures
├── service_documents/      # Sample documents for testing
├── docker-compose.simple.yml      # Minimal development setup
├── docker-compose.with-firecrawl.yml  # Development with Firecrawl
├── docker-compose.production.yml   # Production deployment
├── .env.example           # Environment template
└── README.md              # This file
```

## 🧪 Testing Your Setup

### Quick Validation

```bash
# Test all services
python scripts/quick_test.py

# Expected output:
# ✅ Database: Connected
# ✅ Storage: Connected
# ✅ AI Service: Connected
```

### Document Processing Test

```bash
# Process a sample document
python scripts/test_single_document.py service_documents/sample.pdf

# Expected output:
# Processing: sample.pdf (2.3MB)
# Upload completed
# Text processing: 45 chunks generated
# Hierarchical structure: 12 sections detected
# SVG extraction: 3 vector graphics found
# Table extraction: 2 tables processed
# Context extraction: 8 media items analyzed
# Embeddings generated: 55 total embeddings
# Document processed successfully!
```

### Search Functionality Test

```bash
# Test multimodal search
python scripts/test_search.py --query "fuser unit error"

# Expected output:
# 🔍 Searching: "fuser unit error"
# 📊 Results found: 12
# 📄 Text chunks: 8
# 🖼️ Images: 2
# 📊 Tables: 1
# 🎥 Videos: 1
# ⏱️ Search time: 45ms
# 🎉 Search completed successfully!
```

## 🔍 Common Issues & Solutions

### Port Conflicts

**Problem**: Services fail to start due to port conflicts

**Solution**: Change ports in `docker-compose.yml`:
```yaml
# Change API port in docker-compose.yml
# (No service defined in minimal compose - refer to full compose files)

# Change Laravel dashboard port
# Edit docker-compose.yml, find laravel-nginx service:
services:
  laravel-nginx:
    ports:
      - "9101:80"  # Change from 9100:80

# Change database port
services:
  krai-postgres:
    ports:
      - "5433:5432"  # Change from 5432:5432
```

### Memory Issues

**Problem**: System runs out of memory during processing

**Solution**: Reduce resource usage:
```bash
# Lower batch sizes
EMBEDDING_BATCH_SIZE=5
MAX_CONCURRENT_PROCESSES=1

# Use smaller test documents
MAX_FILE_SIZE_MB=10
```

### Permission Issues

**Problem**: File permission errors on document uploads

**Solution**: Fix permissions:
```bash
# Set proper permissions
sudo chown -R $USER:$USER service_documents/
chmod -R 755 service_documents/

# Or use Docker volumes for storage
docker-compose down -v
docker-compose up -d
```

### Firecrawl Connection Issues

**Problem**: Cannot connect to Firecrawl API

**Solution**: Check Firecrawl services:
```bash
# Check if Firecrawl services are running
docker-compose ps | grep firecrawl

# Restart Firecrawl services
docker-compose restart krai-firecrawl-api krai-firecrawl-worker

# Check Firecrawl logs
docker-compose logs krai-firecrawl-api

# Verify health endpoint
curl http://localhost:3002/health

# If still failing, use BeautifulSoup fallback
SCRAPING_BACKEND=beautifulsoup
```

### Database Connection Issues

**Problem**: Cannot connect to PostgreSQL

**Solution**: Check database status:
```bash
# Check if database is running
docker-compose ps postgresql

# Restart database service
docker-compose restart postgresql

# Check database logs
docker-compose logs postgresql
```

## 📚 Next Steps

### 1. Add Your Documents

```bash
# Place documents in service directory
cp your_documents/*.pdf service_documents/

# Process documents
python scripts/process_documents.py service_documents/
```

### 2. Explore the API

```bash
# View API documentation
open http://localhost:8000/docs

# Test API endpoints
curl http://localhost:8000/api/health
curl http://localhost:8000/api/documents
curl http://localhost:8000/api/search?q=test

# Test Firecrawl scraping (if enabled)
curl http://localhost:8000/api/scraping/health
```

### 3. Use the Web Interface

```bash
# Open Laravel dashboard
open http://localhost:9100

# Features available:
# - Document upload and management
# - Processing status monitoring
# - Search interface with Laravel/Filament
# - Results visualization
```

### 4. Run Comprehensive Tests

```bash
# Full test suite
python scripts/test_full_pipeline_phases_1_6.py

# Integration tests
pytest tests/integration/ -v

# Performance tests
python scripts/test_multimodal_search.py --performance
```

## 🛠️ Advanced Configuration

### Custom AI Models

```bash
# Use different Ollama models
OLLAMA_MODEL=mistral
OLLAMA_MODEL=codellama

# Configure OpenAI
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4

# Use local embedding models
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Database Optimization

```bash
# Enable vector indexes
ENABLE_VECTOR_INDEX=true
VECTOR_INDEX_TYPE=ivfflat

# Configure connection pooling
DATABASE_POOL_SIZE=50
MAX_CONNECTIONS=100

# Enable query caching
ENABLE_QUERY_CACHE=true
CACHE_TTL=3600
```

### Storage Configuration

```bash
# Use external S3 instead of MinIO
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_BUCKET_NAME=krai-documents
AWS_REGION=us-west-2

# Configure storage lifecycle
STORAGE_RETENTION_DAYS=365
AUTO_CLEANUP_TEMP_FILES=true
```

## 📖 Additional Resources

### Documentation
- [📖 Full Documentation](docs/README.md)
- [🔧 Installation Guide](docs/setup/INSTALLATION_GUIDE.md)
- [🧪 Testing Guide](docs/TESTING_GUIDE_PHASES_1_6.md)
- [🏗️ Architecture Overview](docs/architecture/KRAI_PROCESSING_ARCHITECTURE_PLAN.md)
- [🌐 Web Scraping Guide](docs/PRODUCT_RESEARCH.md)
- [📝 Firecrawl Examples](examples/README.md)

### API Reference
- [📚 API Documentation](http://localhost:8000/docs)
- [🔍 Search API Guide](docs/api/SEARCH_API.md)
- [📤 Upload API Guide](docs/api/CONTENT_API.md)
- [🔐 Authentication Guide](docs/api/AUTHENTICATION.md)

### Development
- [🐛 Bug Reports](https://github.com/your-org/KRAI-minimal/issues)
- [💡 Feature Requests](https://github.com/your-org/KRAI-minimal/discussions)
- [🤝 Contributing Guide](CONTRIBUTING.md)
- [📋 Project Roadmap](docs/ROADMAP.md)

### Community
- [💬 Discord Community](https://discord.gg/krai)
- [📧 Mailing List](https://groups.google.com/g/krai-users)
- [🐦 Twitter Updates](https://twitter.com/krai_project)
- [📺 YouTube Tutorials](https://youtube.com/c/krai-tutorials)

## 🎯 Need Help?

If you encounter any issues during setup:

1. **Check the logs**: `docker-compose logs [service-name]`
2. **Run health check**: `python scripts/health_check.py`
3. **Review troubleshooting**: [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
4. **Ask the community**: [GitHub Discussions](https://github.com/your-org/KRAI-minimal/discussions)
5. **Report issues**: [GitHub Issues](https://github.com/your-org/KRAI-minimal/issues)

---

**🎉 Congratulations!** You now have a fully functional KRAI system with all Phase 1-6 features ready for document processing, multimodal search, and intelligent content analysis.

**Next**: Check out the [Testing Guide](docs/TESTING_GUIDE_PHASES_1_6.md) to validate your setup and explore advanced features.
