# Integration Tests Documentation

Comprehensive integration tests for KRAI services with real backend integrations.

## Overview

This directory contains real end-to-end integration tests that use live services:
- **Firecrawl** for web scraping (with BeautifulSoup fallback)
- **Ollama** for LLM analysis
- **PostgreSQL/Supabase** for database operations
- **Tavily** for web search (optional)

Tests are designed to be **CI-friendly** with automatic skipping when services are unavailable.

---

## Setup

### 1. Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Optional: Firecrawl SDK
pip install firecrawl-py

# Optional: Tavily SDK
pip install tavily-python

# Test dependencies
pip install pytest pytest-asyncio pytest-benchmark
```

### 2. Configure Environment Variables

Create `.env.test` in project root:

```bash
# Database (required)
DATABASE_URL=postgresql://user:password@localhost:5432/krai_test
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Firecrawl (optional - tests skip if not configured)
FIRECRAWL_API_URL=http://krai-firecrawl-api:3002
FIRECRAWL_API_KEY=your-api-key
FIRECRAWL_TIMEOUT=30.0
FIRECRAWL_CRAWL_TIMEOUT=300.0

# Ollama (required for LLM tests)
OLLAMA_URL=http://krai-ollama:11434
MODEL_NAME=llama3.2:latest
EMBEDDING_MODEL=nomic-embed-text:latest

# Tavily (optional - for web search tests)
TAVILY_API_KEY=your-tavily-key

# Test configuration
TESTING=true
LOG_LEVEL=DEBUG
```

### 3. Setup Ollama (for LLM tests)

```bash
# Pull required models
docker exec krai-ollama ollama pull llama3.2:latest
docker exec krai-ollama ollama pull nomic-embed-text:latest

# Verify models
docker exec krai-ollama ollama list
```

### 4. Setup Firecrawl (optional)

```bash
# Start Firecrawl service
docker-compose up -d krai-firecrawl-api

# Verify service
curl http://localhost:3002/health
```

---

## Running Tests

### All Integration Tests

```bash
# Run all integration tests
pytest backend/tests/integration/ -v -m integration

# With detailed output
pytest backend/tests/integration/ -v -s -m integration
```

### Specific Test Suites

```bash
# LinkEnrichmentService E2E tests
pytest backend/tests/integration/test_link_enrichment_e2e.py -v

# LinkEnrichmentService error handling
pytest backend/tests/integration/test_link_enrichment_error_handling.py -v

# ProductResearcher integration tests
pytest backend/tests/integration/test_product_researcher_real.py -v
```

### Tests by Category

```bash
# Only database tests
pytest backend/tests/integration/ -v -m "integration and database"

# Only Firecrawl tests (skip if unavailable)
pytest backend/tests/integration/ -v -m "integration and firecrawl"

# Only benchmark/performance tests
pytest backend/tests/integration/ -v -m "integration and benchmark"

# Exclude slow tests
pytest backend/tests/integration/ -v -m "integration and not slow"
```

### Tests Without Firecrawl

```bash
# Run only BeautifulSoup-based tests
pytest backend/tests/integration/ -v -m "integration and not firecrawl"

# This automatically uses BeautifulSoup fallback
```

### Specific Test Classes

```bash
# Single link workflows
pytest backend/tests/integration/test_link_enrichment_e2e.py::TestLinkEnrichmentRealE2E -v

# Batch processing
pytest backend/tests/integration/test_link_enrichment_e2e.py::TestLinkEnrichmentBatchProcessing -v

# Error handling
pytest backend/tests/integration/test_link_enrichment_error_handling.py::TestLinkEnrichmentErrorHandling -v

# Complete workflows
pytest backend/tests/integration/test_product_researcher_real.py::TestProductResearcherCompleteWorkflows -v
```

---

## Test Structure

### LinkEnrichmentService Tests

#### `test_link_enrichment_e2e.py`
- **TestLinkEnrichmentRealE2E**: Single link enrichment workflows
  - Firecrawl success scenarios
  - BeautifulSoup fallback
  - Content hash consistency
  - Metadata extraction
  - Skip already enriched
  - Force refresh

- **TestLinkEnrichmentBatchProcessing**: Batch operations
  - Concurrent link processing
  - Mixed status handling
  - Partial failures
  - Custom concurrency limits
  - Force refresh batch
  - Performance baselines (5 links < 30s)
  - Stress tests (50 links < 120s)

#### `test_link_enrichment_error_handling.py`
- **TestLinkEnrichmentErrorHandling**: Error scenarios
  - Timeout handling
  - 404 errors
  - Network errors
  - Empty content
  - Retry logic (retry_count < 3)
  - Retry budget exceeded
  - Retry time thresholds

- **TestLinkEnrichmentFirecrawlFallback**: Fallback mechanisms
  - Firecrawl unavailable
  - Rate limit handling
  - Timeout fallback

- **TestLinkEnrichmentDocumentLinks**: Document workflows
  - Enrich all document links
  - No pending links
  - Refresh stale links (>90 days)

### ProductResearcher Tests

#### `test_product_researcher_real.py`
- **TestProductResearcherWebSearch**: Search workflows
  - Tavily API search
  - Direct URL construction
  - URL discovery with Firecrawl

- **TestProductResearcherScraping**: Scraping operations
  - Firecrawl scraping (Markdown output)
  - BeautifulSoup fallback
  - Async concurrent scraping
  - Timeout handling

- **TestProductResearcherLLMAnalysis**: LLM workflows
  - Ollama analysis
  - Markdown content analysis
  - Insufficient data handling
  - Timeout handling

- **TestProductResearcherCaching**: Cache operations
  - Cache hit/miss
  - Cache expiry (>90 days)
  - Force refresh

- **TestProductResearcherCompleteWorkflows**: End-to-end
  - Complete workflow with Firecrawl
  - Complete workflow with BeautifulSoup
  - Multiple manufacturers
  - Different product types
  - Error recovery (search, scraping, LLM)
  - Performance baseline (single < 60s)
  - Concurrent requests

---

## Test Markers

Tests use pytest markers for categorization:

```python
@pytest.mark.integration      # All integration tests
@pytest.mark.database          # Requires database
@pytest.mark.firecrawl         # Requires Firecrawl
@pytest.mark.benchmark         # Performance tests
@pytest.mark.slow              # Long-running tests (>30s)
```

### Running by Marker

```bash
# Only integration tests
pytest -m integration

# Integration + database
pytest -m "integration and database"

# Exclude slow tests
pytest -m "integration and not slow"

# Only benchmarks
pytest -m "integration and benchmark"
```

---

## CI Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-benchmark

      - name: Setup Ollama
        run: |
          docker run -d --name ollama -p 11434:11434 ollama/ollama
          docker exec ollama ollama pull llama3.2:latest

      - name: Run integration tests (without Firecrawl)
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/krai_test
          OLLAMA_URL: http://localhost:11434
          TESTING: true
        run: |
          pytest backend/tests/integration/ -v -m "integration and not firecrawl"

      - name: Run integration tests (with Firecrawl)
        if: ${{ secrets.FIRECRAWL_API_KEY }}
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/krai_test
          OLLAMA_URL: http://localhost:11434
          FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}
          FIRECRAWL_API_URL: ${{ secrets.FIRECRAWL_API_URL }}
          TESTING: true
        run: |
          pytest backend/tests/integration/ -v -m integration
```

---

## Performance Baselines

### LinkEnrichmentService
- **Single link**: < 5s per link
- **Batch (5 links)**: < 30s total
- **Batch (50 links)**: < 120s total
- **Throughput**: > 0.5 links/second
- **Concurrency**: 3-10 concurrent requests

### ProductResearcher
- **Single research**: < 60s
- **Concurrent (3 products)**: No race conditions
- **Cache hit**: < 1s
- **LLM analysis**: < 30s

---

## Troubleshooting

### Firecrawl Connection Errors

```bash
# Check Firecrawl service
curl http://localhost:3002/health

# Check logs
docker logs krai-firecrawl-api

# Restart service
docker-compose restart krai-firecrawl-api
```

**Solution**: Tests automatically skip if Firecrawl unavailable. Check `FIRECRAWL_API_URL` and `FIRECRAWL_API_KEY`.

### Ollama Connection Errors

```bash
# Check Ollama service
curl http://localhost:11434/api/tags

# Check models
docker exec krai-ollama ollama list

# Pull missing models
docker exec krai-ollama ollama pull llama3.2:latest
```

**Solution**: Ensure Ollama is running and models are pulled.

### Database Connection Errors

```bash
# Check database
psql -h localhost -U postgres -d krai_test -c "SELECT 1"

# Check schemas
psql -h localhost -U postgres -d krai_test -c "\dn"
```

**Solution**: Verify `DATABASE_URL` and ensure KRAI schemas exist.

### Timeout Issues

**Symptoms**: Tests timeout after 30-60s

**Solutions**:
1. Increase timeout in test: `timeout=60`
2. Check network connectivity
3. Use BeautifulSoup fallback: `-m "integration and not firecrawl"`
4. Skip slow tests: `-m "integration and not slow"`

### Rate Limiting

**Symptoms**: Firecrawl/Tavily rate limit errors

**Solutions**:
1. Add delays between tests
2. Use smaller test batches
3. Configure rate limits in `.env.test`
4. Use BeautifulSoup fallback

---

## Test Data Management

### Isolation
- All test data uses `test-*` prefixes
- Automatic cleanup after each test
- Unique IDs per test run

### Cleanup
```python
@pytest.fixture(autouse=True)
async def cleanup_link_enrichment_data(test_database):
    """Auto-cleanup after each test."""
    yield
    await test_database.execute_query(
        "DELETE FROM krai_content.links WHERE id LIKE 'test-link-%'"
    )
```

### Manual Cleanup
```bash
# Clean test data
psql -h localhost -U postgres -d krai_test -c "
  DELETE FROM krai_content.links WHERE id LIKE 'test-%';
  DELETE FROM krai_system.crawled_pages WHERE id LIKE 'test-%';
"
```

---

## Best Practices

### 1. Test Isolation
- Use unique IDs per test
- Clean up after each test
- Don't rely on test execution order

### 2. Timeouts
- Set reasonable timeouts (30-60s)
- Use shorter timeouts for unit tests
- Allow longer for integration tests

### 3. Assertions
- Verify success/failure
- Check database state
- Validate data quality
- Test error messages

### 4. Mocking
- Mock external APIs when appropriate
- Use real services for integration tests
- Provide fallback mechanisms

### 5. Performance
- Monitor test duration
- Use benchmarks for baselines
- Optimize slow tests
- Run slow tests separately

---

## Coverage Goals

| Component | Current | Target | Status |
|-----------|---------|--------|--------|
| LinkEnrichmentService Unit | 95% | 98% | ✅ |
| LinkEnrichmentService E2E | 95% | 95% | ✅ |
| ProductResearcher Integration | 95% | 95% | ✅ |
| WebScrapingService Fallback | 95% | 95% | ✅ |
| Error Recovery | 90% | 90% | ✅ |
| Performance/Concurrency | 80% | 80% | ✅ |

---

## Contributing

### Adding New Tests

1. **Choose appropriate test file**:
   - E2E workflows → `test_*_e2e.py`
   - Error handling → `test_*_error_handling.py`
   - Integration → `test_*_real.py`

2. **Use proper markers**:
   ```python
   @pytest.mark.integration
   @pytest.mark.database
   @pytest.mark.skipif(not firecrawl_available, reason="Firecrawl not available")
   ```

3. **Follow naming conventions**:
   - `test_real_*` for real integration tests
   - `test_*_workflow` for complete workflows
   - `test_*_error` for error scenarios

4. **Add documentation**:
   - Docstring explaining test purpose
   - Comments for complex logic
   - Update this README if needed

### Running Before Commit

```bash
# Run all integration tests
pytest backend/tests/integration/ -v -m integration

# Run fast tests only
pytest backend/tests/integration/ -v -m "integration and not slow"

# Check coverage
pytest backend/tests/integration/ --cov=services --cov-report=html
```

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review test logs: `pytest -v -s`
3. Check service logs: `docker logs <container>`
4. Consult main project documentation

---

**Last Updated**: 2024-12-06
**Test Count**: ~80 integration tests
**Coverage**: 95%+ for critical paths
