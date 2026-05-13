# KRAI Backend Tests

This directory contains comprehensive test suites for the KRAI backend services, including unit tests, integration tests, and end-to-end scenarios.

## 📁 Test Structure

```text
backend/tests/                    # Test directory (moved from tests/)
├── services/                    # Unit tests for individual services
│   ├── conftest.py             # Shared fixtures and test configuration
│   ├── test_web_scraping_service.py
│   ├── test_link_enrichment_service.py
│   ├── test_structured_extraction_service.py
│   ├── test_manufacturer_crawler.py
│   ├── test_fallback_behavior.py
│   └── test_llm_provider_switching.py
├── integration/                 # Integration and end-to-end tests
│   ├── test_product_researcher_integration.py
│   ├── test_link_enrichment_e2e.py
│   └── test_manufacturer_crawler_e2e.py
├── api/                         # API endpoint tests
├── auth/                        # Authentication tests
├── performance/                 # Performance and load tests
├── POSTGRESQL_MIGRATION.md      # PostgreSQL migration verification report
└── README.md                    # This file
```

> **Note**: Tests have been moved from `tests/` to `backend/tests/` to improve project organization and import paths.

> **Database Migration**: The test suite has been fully migrated to PostgreSQL-native testing. See [`POSTGRESQL_MIGRATION.md`](./POSTGRESQL_MIGRATION.md) for details on the migration, verification steps, and test infrastructure changes.

## 🧪 Test Categories

### Unit Tests (`backend/tests/services/`)

Unit tests focus on individual service components in isolation:

- **WebScrapingService**: Tests URL scraping, site crawling, structured extraction, and fallback behavior
- **LinkEnrichmentService**: Tests link enrichment, batch processing, and content validation
- **StructuredExtractionService**: Tests schema-based extraction and confidence thresholds
- **ManufacturerCrawler**: Tests crawl scheduling, job execution, and page processing
- **FallbackBehavior**: Tests graceful degradation when primary services fail
- **LLMProviderSwitching**: Tests dynamic switching between LLM providers

### Integration Tests (`backend/tests/integration/`)

Integration tests verify end-to-end workflows:

- **ProductResearcher**: Tests complete product research pipeline
- **LinkEnrichmentE2E**: Tests full link enrichment workflows
- **ManufacturerCrawlerE2E**: Tests complete crawling workflows

## 🚀 Running Tests

### Prerequisites

Ensure all test dependencies are installed:

```bash
pip install -r requirements-test.txt
```

### Environment Setup

Configure the test environment by editing `.env.test` with your local settings:

```bash
# .env.test
FIRECRAWL_API_KEY=your-test-firecrawl-key
OLLAMA_BASE_URL=http://localhost:11435
MINIO_ENDPOINT=localhost:9001
DATABASE_CONNECTION_URL=postgresql://krai_test:krai_test_password@localhost:5433/krai_test
DATABASE_URL=postgresql://krai_test:krai_test_password@localhost:5433/krai_test
```

> **Important**: Test environment uses different ports than production to avoid conflicts:

- **Database**: Port 5433 (vs 5432 in production)
- **MinIO**: Port 9001 (vs 9000 in production)
- **Ollama**: Port 11435 (vs 11434 in production)

### Running All Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run with verbose output
pytest -v
```

### Running Specific Test Categories

```bash
# Run only unit tests
pytest backend/tests/services/

# Run only integration tests
pytest backend/tests/integration/

# Run specific test file
pytest backend/tests/services/test_web_scraping_service.py

# Run specific test class
pytest backend/tests/services/test_web_scraping_service.py::TestWebScrapingService

# Run specific test method
pytest backend/tests/services/test_web_scraping_service.py::TestWebScrapingService::test_scrape_url_success
```

### Running Tests with Different Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only performance tests
pytest -m performance

# Skip slow tests
pytest -m "not slow"
```

## 🔧 Test Configuration

### Fixtures

The test suite uses shared fixtures defined in `backend/tests/services/conftest.py`:

- `mock_db_client`: Mock PostgreSQL database client
- `mock_database_service`: Mock database service wrapper
- `mock_scraper`: Mock web scraping service
- `mock_batch_task_service`: Mock batch task service
- `mock_structured_extraction_service`: Mock structured extraction service

### Environment Variables

Tests respect the following environment variables:

- `SCRAPING_MOCK_MODE`: Enable mock mode for scraping tests
- `FIRECRAWL_API_KEY`: Firecrawl API key for integration tests
- `FIRECRAWL_LLM_PROVIDER`: LLM provider for Firecrawl (ollama, openai, anthropic)
- `OLLAMA_BASE_URL`: Ollama service URL (default: <http://localhost:11435>)
- `MINIO_ENDPOINT`: MinIO service endpoint (default: localhost:9001)
- `DATABASE_URL`: PostgreSQL connection URL (default: `postgresql://krai_test:krai_test_password@localhost:5433/krai_test`)
- `TEST_TIMEOUT`: Default timeout for async operations
- `SKIP_INTEGRATION_TESTS`: Skip integration tests if set

### Test Database

Tests use a separate test database schema to avoid affecting production data:

```sql
-- Test schema setup
CREATE SCHEMA IF NOT EXISTS krai_test;
-- Test tables are created with _test suffix
```

## 🐳 Docker Test Environment

### Test Services

The test environment uses `docker-compose.test.yml` with isolated services. This file has been moved to `archive/docker/docker-compose.test.yml` but is still available for testing:

```bash
# Start basic test services
docker-compose -f archive/docker/docker-compose.test.yml up -d

# Start test services with Firecrawl support
docker-compose -f archive/docker/docker-compose.test.yml --profile firecrawl up -d

# View test service status
docker-compose -f archive/docker/docker-compose.test.yml ps

# Stop test services
docker-compose -f archive/docker/docker-compose.test.yml down
```

> **Note:** The test environment compose file is still available but has been archived as it's not a primary deployment configuration. For basic testing, you can also use `docker-compose.simple.yml` with manual port adjustments.

### Test Service Ports

| Service | Test Port | Production Port | Purpose |
|---------|-----------|-----------------|---------|
| PostgreSQL | 5433 | 5432 | Test database |
| MinIO | 9001 | 9000 | Test object storage |
| MinIO Console | 9002 | 9001 | Test storage console |
| Redis | 6380 | 6379 | Test cache |
| Redis (Firecrawl) | 6381 | 6379 | Test Firecrawl cache |
| Playwright | 3001 | N/A | Test browser automation |
| Firecrawl API | 3003 | 3001 | Test scraping backend |
| Ollama | 11435 | 11434 | Test LLM service |

### Firecrawl Services

Firecrawl services require the `firecrawl` profile:

```bash
# Start services with Firecrawl support
docker-compose -f archive/docker/docker-compose.test.yml --profile firecrawl up -d

# Start only Firecrawl services (if basic services already running)
docker-compose -f archive/docker/docker-compose.test.yml --profile firecrawl up -d firecrawl-api-test firecrawl-worker-test
```

### Health Checks

All test services include health checks using CMD-SHELL syntax. For example, the Playwright service:

```yaml
healthcheck:
  test: ["CMD-SHELL", "wget -qO- http://localhost:3000 || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
```

Note: Health checks use internal container ports (e.g., 3000 for Playwright), while external access uses mapped ports (e.g., 3001 for Playwright).

### Service Dependencies

Test services properly depend on each other's health status:

```yaml
depends_on:
  postgresql-test:
    condition: service_healthy
  ollama-test:
    condition: service_healthy
```

## 📊 Test Coverage

### Current Coverage Areas

- ✅ **Web Scraping**: URL scraping, site crawling, content extraction
- ✅ **Link Enrichment**: Batch processing, content validation, error handling
- ✅ **Structured Extraction**: Schema-based extraction, confidence scoring
- ✅ **Manufacturer Crawling**: Scheduling, job execution, page processing
- ✅ **Fallback Behavior**: Service degradation, error recovery
- ✅ **LLM Provider Switching**: Dynamic provider management
- ✅ **Integration Workflows**: End-to-end service coordination

### Coverage Goals

- **Unit Tests**: >90% line coverage for core services
- **Integration Tests**: Major workflows and service interactions
- **Error Scenarios**: Network failures, timeout, rate limiting
- **Edge Cases**: Empty data, malformed responses, concurrent access

## 🔍 Test Examples

### Basic Unit Test

```python
@pytest.mark.asyncio
async def test_scrape_url_success(web_scraping_service, mock_scraper):
    """Test successful URL scraping."""
    mock_scraper.scrape_url.return_value = {
        'success': True,
        'content': 'Test content',
        'metadata': {'status_code': 200}
    }

    result = await web_scraping_service.scrape_url('http://example.com')

    assert result['success'] is True
    assert 'content' in result
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_complete_enrichment_workflow(link_enrichment_service):
    """Test end-to-end link enrichment."""
    result = await link_enrichment_service.enrich_link(
        link_id='test-link',
        url='http://example.com/test'
    )

    assert result['success'] is True
    assert result['content_length'] > 0
```

### Fallback Behavior Test

```python
@pytest.mark.asyncio
async def test_firecrawl_fallback(web_scraping_service):
    """Test fallback from Firecrawl to BeautifulSoup."""
    # Firecrawl fails, BeautifulSoup succeeds
    result = await web_scraping_service.scrape_url('http://example.com')

    assert result['success'] is True
    assert result['backend'] == 'beautifulsoup'
```

## 🐛 Debugging Tests

### Running Tests in Debug Mode

```bash
# Run with debugger
pytest --pdb

# Stop on first failure
pytest -x

# Run with local variables in tracebacks
pytest --tb=long
```

### Mock Debugging

To debug mock interactions:

```python
# Check mock call counts
assert mock_scraper.scrape_url.call_count == 1

# Inspect mock call arguments
mock_scraper.scrape_url.assert_called_with('http://example.com')

# Get all mock calls
calls = mock_scraper.scrape_url.call_args_list
```

### Logging in Tests

Enable debug logging for tests:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use pytest fixture
@pytest.fixture(autouse=True)
def debug_logging():
    logging.basicConfig(level=logging.DEBUG)
```

## 🚦 CI/CD Integration

### GitHub Actions

Tests run automatically on:

- Pull requests
- Push to main branch
- Release creation

### Test Matrix

- **Python**: 3.9, 3.10, 3.11
- **Dependencies**: Latest and minimum supported versions
- **Database**: PostgreSQL 13, 14, 15

### Quality Gates

- ✅ All tests must pass
- ✅ Coverage >85%
- ✅ No new security vulnerabilities
- ✅ Code quality checks pass

## 📝 Writing New Tests

### Test Naming Convention

```python
# Unit test: test_{method}_{scenario}
def test_scrape_url_success(self):
    pass

def test_scrape_url_with_timeout(self):
    pass

# Integration test: test_{workflow}_e2e
def test_complete_crawl_workflow_e2e(self):
    pass
```

### Test Structure

```python
class TestServiceName:
    """Test ServiceName functionality."""

    @pytest.fixture
    def service_instance(self, mock_dependencies):
        """Create service instance for testing."""
        return ServiceName(dependencies=mock_dependencies)

    @pytest.mark.asyncio
    async def test_method_success(self, service_instance):
        """Test successful method execution."""
        # Arrange
        # Act
        # Assert
        pass
```

### Async Testing

For async methods, use the `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_method(self, async_service):
    result = await async_service.async_method()
    assert result['success'] is True
```

### Mock Best Practices

```python
# Use AsyncMock for async methods
mock_service.async_method = AsyncMock(return_value={'success': True})

# Configure side effects for error scenarios
mock_service.method.side_effect = Exception("Test error")

# Use patch for temporary modifications
with patch('module.ClassName') as mock_class:
    mock_class.return_value = mock_instance
    # Test code here
```

## 🔧 Troubleshooting

### Common Issues

1. **Database Connection Errors**

   ```bash
   # Check test database is running
   docker-compose -f archive/docker/docker-compose.test.yml ps

   # Reset test database
   docker-compose -f archive/docker/docker-compose.test.yml down -v
   docker-compose -f archive/docker/docker-compose.test.yml up -d
   ```

2. **Firecrawl API Errors**

   ```bash
   # Check API key in .env.test
   grep FIRECRAWL_API_KEY .env.test

   # Test API connectivity
   curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
        <https://api.firecrawl.dev/v1/status>
   ```

3. **Ollama Connection Issues**

   ```bash
   # Check Ollama service (test port)
   curl http://localhost:11435/api/tags

   # Restart Ollama if needed
   docker restart ollama-test
   ```

4. **Import Errors**

   ```bash
   # Install test dependencies
   pip install -r requirements-test.txt

   # Check Python path
   python -c "import sys; print(sys.path)"
   ```

### Performance Issues

For slow tests:

```bash
# Profile test execution
pytest --profile

# Run tests in parallel
pytest -n auto

# Skip slow tests during development
pytest -m "not slow"
```

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)

## 🤝 Contributing

When adding new tests:

1. Follow existing naming conventions
2. Add appropriate fixtures and mocks
3. Include both success and failure scenarios
4. Add documentation for complex test cases
5. Update this README if adding new test categories

### Test Review Checklist

- [ ] Test follows naming convention
- [ ] Appropriate fixtures are used
- [ ] Both success and failure cases tested
- [ ] Mock assertions are specific
- [ ] Test is independent (no shared state)
- [ ] Documentation is clear
- [ ] Coverage impact is considered

---

**Last Updated**: 2025-11-06

For questions or issues with tests, please open an issue in the repository or contact the development team.
