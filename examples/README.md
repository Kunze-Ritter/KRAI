# KRAI Firecrawl Integration Examples

Practical examples demonstrating web scraping, site crawling, structured extraction, link enrichment, and manufacturer crawling using Firecrawl and BeautifulSoup backends.

## 📋 Table of Contents

- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Example Scripts Overview](#-example-scripts-overview)
- [Example 1: Basic Web Scraping](#-example-1-basic-web-scraping)
- [Example 2: Site Crawling](#-example-2-site-crawling)
- [Example 3: Structured Extraction](#-example-3-structured-extraction)
- [Example 4: Link Enrichment](#-example-4-link-enrichment)
- [Example 5: Manufacturer Crawler](#-example-5-manufacturer-crawler)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Performance Tips](#performance-tips)
- [Cost Considerations](#cost-considerations)
- [Next Steps](#next-steps)
- [Additional Resources](#additional-resources)
- [Support](#support)
- [License](#license)

## 🚀 Prerequisites

- Docker Compose running with Firecrawl services (optional for BeautifulSoup)
- Python 3.9+
- Required packages: `pip install -r requirements.txt`
- Environment variables configured in `.env`

### Required Python Packages

```bash
# Core dependencies
pip install asyncio httpx beautifulsoup4

# Rich output (recommended for better experience)
pip install rich

# For structured extraction with OpenAI (optional)
pip install openai

# Firecrawl client (optional - fallback to BeautifulSoup)
pip install firecrawl-py
```

## ⚡ Quick Start

1. **Copy environment configuration:**
   ```bash
   cp .env.example .env
   ```

2. **Start Firecrawl services (optional but recommended):**
   ```bash
   docker-compose up -d krai-redis krai-playwright krai-firecrawl-api krai-firecrawl-worker
   ```

3. **Verify setup:**
   ```bash
   # Check if Firecrawl is running
   curl http://localhost:3002/health

   # Expected response: {"status":"healthy"}
   ```

4. **Run your first example:**
   ```bash
   # Basic scraping with auto-detect backend
   python examples/firecrawl_basic_scraping.py --url https://example.com
   ```

## 📊 Example Scripts Overview

| Script | Purpose | Difficulty | Prerequisites |
|--------|---------|------------|---------------|
| `firecrawl_basic_scraping.py` | Basic web scraping | Beginner | None |
| `firecrawl_site_crawling.py` | Multi-page crawling | Intermediate | Firecrawl recommended |
| `firecrawl_structured_extraction.py` | Schema-based extraction | Advanced | Firecrawl required |
| `firecrawl_link_enrichment.py` | Link enrichment workflow | Advanced | Database access |
| `firecrawl_manufacturer_crawler.py` | Scheduled crawling | Advanced | Database access |

## 🔍 Example 1: Basic Web Scraping

**Description:** Learn how to scrape a single URL with automatic backend selection

**Key concepts:** Backend selection, fallback behavior, content formats

### Usage Examples

```bash
# Auto-detect backend
python examples/firecrawl_basic_scraping.py --url https://example.com

# Force Firecrawl backend
python examples/firecrawl_basic_scraping.py --url https://example.com --backend firecrawl

# Compare both backends
python examples/firecrawl_basic_scraping.py --url https://example.com --compare

# Check backend health
python examples/firecrawl_basic_scraping.py --health
```

### Expected Output

```text
=== Scraping Configuration ===
Backend: Firecrawl
API URL: http://localhost:3002
LLM Provider: ollama

🔍 Scraping URL: https://example.com
📋 Using backend: firecrawl

✅ **Success**
📊 Backend: firecrawl
📝 Format: markdown
⏱️ Duration: 3.45s
📏 Content Length: 1,234 chars

--- Content Preview (markdown) ---
# Example Domain
This domain is for use in illustrative examples...
```

### What You'll Learn

- How to initialize `WebScrapingService`
- Difference between Firecrawl (Markdown) and BeautifulSoup (plain text) output
- Automatic fallback behavior when Firecrawl is unavailable
- Backend health checking
- Configuration via environment variables

## 🕷️ Example 2: Site Crawling

**Description:** Crawl multiple pages from a manufacturer website

**Key concepts:** Depth control, URL filtering, progress tracking

### Usage Examples

```bash
# Basic crawl
python examples/firecrawl_site_crawling.py --url https://example.com --max-pages 20

# Manufacturer shortcut
python examples/firecrawl_site_crawling.py --manufacturer "Konica Minolta" --max-pages 50

# Filter and analyze
python examples/firecrawl_site_crawling.py --url https://example.com --filter ".*product.*" --analyze

# Export results
python examples/firecrawl_site_crawling.py --url https://example.com --export json
```

### Expected Output

```text
=== Crawling Configuration ===
Backend: firecrawl
Max Pages: 20
Max Depth: 2

🕷️ Starting crawl: https://example.com
📊 Options: {'limit': 20, 'maxDepth': 2, 'allowBackwardLinks': False}

✅ **Crawl Successful**
📄 Pages Discovered: 18
⏱️ Duration: 45.23s
📊 Average Content Length: 2,156 chars

🌳 Crawl Tree (URL Hierarchy)
├── 📄 https://example.com (1,234 chars)
│   ├── 📄 https://example.com/about (856 chars)
│   ├── 📄 https://example.com/products (2,345 chars)
│   └── 📄 https://example.com/contact (567 chars)

📊 Page Type Distribution
Type        Count    Percentage
product     6        33.3%
support     4        22.2%
other       8        44.4%
```

### What You'll Learn

- How to crawl multiple pages with depth control
- URL filtering and pattern matching
- Progress tracking for long-running crawls
- Content analysis and page type detection
- Exporting results in multiple formats (JSON, CSV, Markdown)
- Manufacturer-specific crawling strategies

## 🎯 Example 3: Structured Extraction

**Description:** Extract structured data using LLM-based schemas

**Key concepts:** JSON schemas, LLM providers, confidence scoring

### Usage Examples

```bash
# Extract product specs
python examples/firecrawl_structured_extraction.py --url https://example.com/product --type product_specs

# Extract error codes
python examples/firecrawl_structured_extraction.py --url https://example.com/support --type error_codes

# Custom schema extraction
python examples/firecrawl_structured_extraction.py --url https://example.com --schema custom_schema.json

# Batch extraction
python examples/firecrawl_structured_extraction.py --batch urls.txt --type product_specs --export results.json
```

### Expected Output

```text
=== Structured Extraction Configuration ===
Backend: firecrawl
LLM Provider: ollama
Confidence Threshold: 0.7

🏭 Extracting product specs from: https://example.com/product

✅ **Product Specs Extracted**
🏭 Model: bizhub C750i
📊 Series: bizhub i-Series
🖨️ Type: laser_multifunction
⚡ Speed Mono: 75 ppm
🌈 Speed Color: 75 ppm
📏 Resolution: 1200x1200 dpi
📊 Confidence: 0.85
🤖 LLM Provider: ollama
⏱️ Duration: 12.34s

--- Extracted Data (JSON) ---
{
  "model_number": "bizhub C750i",
  "series_name": "bizhub i-Series",
  "product_type": "laser_multifunction",
  "speed_mono": 75,
  "speed_color": 75,
  "resolution": "1200x1200 dpi",
  "paper_sizes": ["A4", "A3", "Letter"],
  "connectivity": ["USB 2.0", "Ethernet", "WiFi"]
}
```

### Available Schemas

- `product_specs`: Product specifications (model, speed, resolution, etc.)
- `error_codes`: Error code list with solutions and severity
- `service_manual`: Manual metadata (type, page count, version)
- `parts_list`: Parts catalog information
- `troubleshooting`: Troubleshooting guides and steps

### What You'll Learn

- How to use JSON schemas for structured extraction
- Difference between Ollama and OpenAI LLM providers
- Confidence scoring and validation
- Batch processing for multiple URLs
- Custom schema creation and usage
- Cost considerations (OpenAI vs Ollama)

## 🔗 Example 4: Link Enrichment

**Description:** Complete link enrichment pipeline from PDF to structured data

**Key concepts:** Document integration, batch processing, retry logic

### Usage Examples

```bash
# Enrich document links
python examples/firecrawl_link_enrichment.py --document-id abc-123-def

# Enrich single link
python examples/firecrawl_link_enrichment.py --link-id xyz-789-uvw

# Batch enrichment
python examples/firecrawl_link_enrichment.py --batch link_ids.txt

# Retry failed links
python examples/firecrawl_link_enrichment.py --retry-failed

# Show statistics
python examples/firecrawl_link_enrichment.py --stats

# Complete workflow
python examples/firecrawl_link_enrichment.py --document-id abc-123-def --workflow
```

### Expected Output

```text
=== Link Enrichment Configuration ===
Enable Link Enrichment: true
Backend: firecrawl
Max Concurrent: 3

📄 Found 3 links to enrich for document: abc-123-def

🔗 Enriching link: https://example.com/product/specs
✅ Link enriched successfully
📊 Backend: firecrawl, Content length: 2,345 chars

🔗 Enriching link: https://example.com/support/error-codes
✅ Link enriched successfully
📊 Backend: firecrawl, Content length: 1,876 chars

✅ **Batch Enrichment Complete**
📊 Total Links: 3
✅ Successful: 3
❌ Failed: 0
⏱️ Duration: 15.67s
📊 Average per link: 5.22s

🔍 Processing enriched links for document: abc-123-def
✅ Extracted product_specs from link
✅ Extracted error_codes from link
✅ Extracted service_manual from link

✅ **Complete Workflow Successful**
📄 Document: abc-123-def
🔗 Links Enriched: 3
🔍 Links Processed: 3
📋 Extractions Found: product_specs(1), error_codes(1), service_manual(1)
🎯 Pipeline: PDF → Links → Scraping → Extraction → Database
```

### What You'll Learn

- Complete link enrichment pipeline
- Integration with document processing
- Batch processing strategies with concurrency control
- Retry logic for failed links
- Stale content detection and refresh
- Post-enrichment structured extraction
- Database integration patterns

## 🏭 Example 5: Manufacturer Crawler

**Description:** Set up and manage scheduled manufacturer website crawling

**Key concepts:** Cron schedules, job monitoring, content change detection

### Usage Examples

```bash
# Create crawl schedule
python examples/firecrawl_manufacturer_crawler.py --create-schedule \
  --manufacturer "Konica Minolta" --crawl-type support_pages \
  --schedule "0 2 * * 0"

# Start manual crawl
python examples/firecrawl_manufacturer_crawler.py --start-crawl schedule-id

# Monitor crawl job
python examples/firecrawl_manufacturer_crawler.py --job-id job-id

# Process crawled pages
python examples/firecrawl_manufacturer_crawler.py --process-pages job-id

# List all schedules
python examples/firecrawl_manufacturer_crawler.py --list-schedules

# View crawl history
python examples/firecrawl_manufacturer_crawler.py --history schedule-id

# Show statistics
python examples/firecrawl_manufacturer_crawler.py --stats

# Check scheduled crawls (for cron/n8n)
python examples/firecrawl_manufacturer_crawler.py --check-scheduled
```

### Expected Output

```text
=== Manufacturer Crawler Configuration ===
Enable Manufacturer Crawling: true
Max Concurrent Jobs: 1
Default Max Pages: 100

✅ Created crawl schedule: abc-123-def
🏭 Manufacturer: Konica Minolta
📋 Type: support_pages
🌐 Start URL: https://kmbs.konicaminolta.us/support/
⏰ Schedule: 0 2 * * 0
📊 Next run: 2025-11-09T02:00:00

🚀 Started crawl job: xyz-789-uvw
📋 Schedule: abc-123-def
🏭 Manufacturer: Konica Minolta
🌐 URL: https://kmbs.konicaminolta.us/support/
📊 Status: queued

🕷️ Executing crawl job: xyz-789-uvw
🌐 Crawling: https://kmbs.konicaminolta.us/support/

✅ **Crawl Job Complete**
🆔 Job ID: xyz-789-uvw
📄 Pages Discovered: 85
✅ Pages Scraped: 82
❌ Pages Failed: 3
⏱️ Duration: 125.45s
📊 Success Rate: 96.5%

🔍 Processing 82 crawled pages from job: xyz-789-uvw

✅ **Page Processing Complete**
📄 Pages Processed: 82
🏭 Product Specs: 25
⚠️ Error Codes: 48
📚 Service Manuals: 12
🔧 Parts Catalogs: 8

✅ **Complete Workflow Successful**
📄 Document: Konica Minolta
🔗 Links Enriched: 82
🔍 Links Processed: 82
📋 Extractions Found: product_specs(25), error_codes(48), service_manual(12)
🎯 Pipeline: Schedule → Crawl → Extract → Database
```

### Supported Manufacturers

- **Konica Minolta**: bizhub, accurio series
- **HP**: LaserJet, OfficeJet series
- **Canon**: imageRUNNER, imageCLASS series
- **Lexmark**: Various printer series

### What You'll Learn

- How to set up crawl schedules with cron expressions
- Manual vs scheduled crawling
- Real-time progress monitoring
- Content change detection
- Post-crawl processing pipeline
- Integration with external schedulers (n8n, cron)
- Manufacturer-specific crawl strategies

## ⚙️ Configuration

### Environment Variables

```bash
# Web Scraping Configuration
SCRAPING_BACKEND=firecrawl          # or 'beautifulsoup'
FIRECRAWL_API_URL=http://localhost:3002
FIRECRAWL_LLM_PROVIDER=ollama       # or 'openai'
FIRECRAWL_MODEL_NAME=llama3.1:8b
OPENAI_API_KEY=your_openai_key_here

# Crawling Configuration
FIRECRAWL_MAX_PAGES=10
FIRECRAWL_MAX_DEPTH=2
FIRECRAWL_MAX_CONCURRENCY=3
FIRECRAWL_BLOCK_MEDIA=true

# Link Enrichment Configuration
ENABLE_LINK_ENRICHMENT=false
LINK_ENRICHMENT_MAX_CONCURRENT=3
LINK_ENRICHMENT_RETRY_LIMIT=3
LINK_ENRICHMENT_STALE_DAYS=90

# Manufacturer Crawler Configuration
ENABLE_MANUFACTURER_CRAWLING=false
CRAWLER_MAX_CONCURRENT_JOBS=1
CRAWLER_DEFAULT_MAX_PAGES=100
CRAWLER_DEFAULT_MAX_DEPTH=2

# Structured Extraction Configuration
EXTRACTION_CONFIDENCE_THRESHOLD=0.7
```

### Complete `.env.example`

See the main `.env.example` file in the project root for all available options, including proxy settings, rate limiting, and advanced configurations.

## 🔧 Troubleshooting

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

### LLM Provider Issues

**Problem**: Structured extraction failing with LLM errors

**Solution**: Check LLM configuration:

```bash
# For Ollama (default)
docker-compose ps | grep ollama
curl http://localhost:11434/api/tags

# For OpenAI
export OPENAI_API_KEY=your_key_here
python -c "import openai; print(openai.api_key)"

# Switch providers in .env
FIRECRAWL_LLM_PROVIDER=openai  # or ollama
```

### Memory Issues

**Problem**: Out of memory errors during crawling

**Solution**: Reduce concurrency and limits:

```bash
# Reduce concurrent operations
FIRECRAWL_MAX_CONCURRENCY=1
LINK_ENRICHMENT_MAX_CONCURRENT=1

# Reduce page limits
FIRECRAWL_MAX_PAGES=5
CRAWLER_DEFAULT_MAX_PAGES=50
```

### Database Connection Issues

**Problem**: Connection errors in link enrichment or crawler examples

**Solution**: Check database configuration:

```bash
# Verify database URL
echo $DATABASE_URL

# Test connection
python -c "
import asyncpg
import asyncio
async def test():
    conn = await asyncpg.connect('$DATABASE_URL')
    print('✅ Database connected')
    await conn.close()
asyncio.run(test())
"
```

## 💡 Best Practices

### Development vs Production

- **Development**: Use BeautifulSoup for testing, Ollama for extraction
- **Production**: Use Firecrawl for scraping, OpenAI for better extraction quality

### Performance Optimization

- Start with BeautifulSoup for testing, use Firecrawl for production
- Use Ollama for development (free), OpenAI for production (better quality)
- Set reasonable crawl limits (max_pages, max_depth) to avoid overload
- Monitor fallback rate - too many fallbacks indicate Firecrawl issues

### Quality Assurance

- Validate extraction confidence - manually verify low-confidence results
- Use batch processing for multiple URLs to improve efficiency
- Schedule crawls during off-peak hours (e.g., 2am)
- Implement retry logic for failed operations

### Security Considerations

- Use environment variables for API keys and sensitive data
- Implement rate limiting to avoid overwhelming target websites
- Respect robots.txt and website terms of service
- Use appropriate user agents

## ⚡ Performance Tips

### Timing Benchmarks

- **Firecrawl**: ~3-5 seconds per URL (JavaScript rendering)
- **BeautifulSoup**: ~1-2 seconds per URL (static HTML)
- **Structured extraction**: ~10-20 seconds per URL (LLM processing)

### Concurrency Guidelines

- **Firecrawl scraping**: Max 3 concurrent URLs
- **BeautifulSoup scraping**: Max 5 concurrent URLs
- **Structured extraction**: Max 2 concurrent (LLM is slow)
- **Crawling**: Respect rate limits, add delays between requests

### Memory Management

- Monitor RAM usage during large crawls
- Use streaming for large result sets
- Implement pagination for batch operations
- Clear temporary data between operations

## 💰 Cost Considerations

### Service Costs

- **Firecrawl (self-hosted)**: FREE (infrastructure costs only)
- **Ollama (local)**: FREE (no API costs)
- **OpenAI**: ~$0.001 per extraction (optional, for better quality)
- **Tavily API**: ~$0.002 per search (used by ProductResearcher)

### Infrastructure Costs

- **Minimum RAM**: 8GB (BeautifulSoup only)
- **Recommended RAM**: 16GB+ (Firecrawl + Ollama)
- **Storage**: 10GB+ for crawled content and embeddings
- **CPU**: 4+ cores for concurrent processing

### Total Cost per Operation

- **Basic scraping**: ~$0.000 (infrastructure only)
- **Structured extraction with Ollama**: ~$0.000 (infrastructure only)
- **Structured extraction with OpenAI**: ~$0.001-0.003 per URL
- **Full product research**: ~$0.002-0.005 per product

## 🎯 Next Steps

### Learning Path

1. **Start with basic scraping** - Try `firecrawl_basic_scraping.py`
2. **Explore crawling** - Use `firecrawl_site_crawling.py` for multi-page sites
3. **Add structured extraction** - Extract specific data with `firecrawl_structured_extraction.py`
4. **Integrate with documents** - Use `firecrawl_link_enrichment.py` for PDF workflows
5. **Automate with scheduling** - Set up `firecrawl_manufacturer_crawler.py` for regular updates

### Integration Options

- **API Integration**: Use the REST API endpoints at `http://localhost:8000/docs`
- **Python Integration**: Import services directly into your code
- **n8n Workflows**: Use the provided n8n nodes for visual automation
- **Cron Jobs**: Schedule regular crawling with system cron

### Advanced Features

- **Custom Schemas**: Create your own extraction schemas
- **Manufacturer Templates**: Add new manufacturer configurations
- **Content Change Detection**: Monitor website updates
- **Batch Processing**: Process large datasets efficiently
- **Export Formats**: Generate reports in various formats

## 📚 Additional Resources

### Documentation

- **Product Research Guide**: `docs/PRODUCT_RESEARCH.md` - Comprehensive Firecrawl documentation
- **API Documentation**: `http://localhost:8000/docs` - Interactive API reference
- **Database Schema**: `DATABASE_SCHEMA.md` - Complete database structure
- **Architecture**: `docs/architecture/` - System design and patterns

### External Resources

- **Firecrawl Documentation**: <https://github.com/firecrawl/firecrawl>
- **JSON Schema Reference**: <https://json-schema.org/>
- **Cron Expression Generator**: <https://crontab.guru/>
- **Ollama Models**: <https://ollama.ai/library>
- **Rich Library**: <https://rich.readthedocs.io/>

### Community

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Discord Server**: Real-time chat and support (if available)

## 🆘 Support

### Getting Help

1. **Check the logs**: Look for detailed error messages
2. **Review troubleshooting**: See the [Troubleshooting](#troubleshooting) section
3. **Search issues**: Check existing GitHub issues
4. **Create issue**: Provide detailed error description and environment info

### Bug Reports

When reporting bugs, please include:

- Python version and OS
- Docker Compose status
- Environment configuration (sanitized)
- Complete error messages and logs
- Steps to reproduce the issue

### Feature Requests

We welcome feature requests! Please:

- Describe the use case clearly
- Provide examples of expected behavior
- Consider contributing to the implementation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

### Contributing

Contributions are welcome! Please read the contributing guidelines and submit pull requests to the main repository.

---

**Happy scraping! 🕷️✨**

If you find these examples useful, please consider giving the project a ⭐ on GitHub!
