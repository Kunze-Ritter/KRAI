# Processor Tests

This directory contains comprehensive test suites for the KRAI pipeline processors, covering UploadProcessor, DocumentProcessor, OptimizedTextProcessor, and the complete pipeline flow.

## 📁 Test Structure

```text
tests/processors/
├── conftest.py                    # Shared fixtures and test configuration
├── test_upload_e2e.py            # E2E tests for UploadProcessor
├── test_document_processor_e2e.py # E2E tests for DocumentProcessor
├── test_text_processor_e2e.py    # E2E tests for OptimizedTextProcessor
├── test_pipeline_flow_e2e.py     # E2E tests for complete pipeline flow
├── test_text_extractor.py        # Unit tests for TextExtractor
├── test_chunker.py               # Unit tests for SmartChunker
├── test_stage_tracker_integration.py # Integration tests for StageTracker
├── test_upload.py                # Legacy unit tests (updated)
├── test_processor.py             # Legacy unit tests (updated)
└── README.md                     # This file
```

## 🏗️ Test Categories

### 1. End-to-End (E2E) Tests
- **test_upload_e2e.py**: Complete UploadProcessor workflow testing
- **test_document_processor_e2e.py**: Complete DocumentProcessor workflow testing
- **test_text_processor_e2e.py**: Complete OptimizedTextProcessor workflow testing
- **test_pipeline_flow_e2e.py**: Full pipeline integration testing

### 2. Unit Tests
- **test_text_extractor.py**: Text extraction engine testing
- **test_chunker.py**: SmartChunker algorithm testing
- **test_stage_tracker_integration.py**: StageTracker integration testing

### 3. Legacy Tests (Updated)
- **test_upload.py**: Basic UploadProcessor functionality
- **test_processor.py**: Basic DocumentProcessor functionality

## 🧪 Test Fixtures

The `conftest.py` file provides comprehensive fixtures for consistent testing:

### Core Fixtures
- `mock_database_adapter`: Mock database adapter for testing
- `sample_pdf_files`: Pre-configured test PDF files (valid, corrupted, empty, large, OCR)
- `temp_test_pdf`: Temporary directory for dynamic test file creation
- `mock_stage_tracker`: Mock stage tracker for progress testing
- `processor_test_config`: Standardized processor configuration
- `processing_context`: Standard processing context for tests

### Utility Fixtures
- `cleanup_test_documents`: Automatic cleanup of test documents
- `sample_document_metadata`: Sample metadata for testing
- `mock_websocket_callback`: Mock WebSocket for real-time updates

## 🏷️ Test Markers

Use pytest markers to run specific test categories:

```bash
# Run all processor tests
pytest -m processor

# Run specific processor tests
pytest -m upload
pytest -m document
pytest -m text
pytest -m pipeline
pytest -m chunking
pytest -m stage_tracker

# Run E2E tests only
pytest tests/processors/test_*_e2e.py

# Run unit tests only
pytest tests/processors/test_text_extractor.py
pytest tests/processors/test_chunker.py
pytest tests/processors/test_stage_tracker_integration.py
```

## 🚀 Running Tests

### Basic Test Execution
```bash
# Run all processor tests
pytest tests/processors/

# Run with verbose output
pytest tests/processors/ -v

# Run with coverage
pytest tests/processors/ --cov=backend/processors --cov-report=html
```

### Specific Test Categories
```bash
# Run E2E tests (comprehensive)
pytest tests/processors/test_*_e2e.py -v

# Run unit tests (fast)
pytest tests/processors/test_text_extractor.py tests/processors/test_chunker.py -v

# Run integration tests
pytest tests/processors/test_stage_tracker_integration.py -v

# Run legacy tests
pytest tests/processors/test_upload.py tests/processors/test_processor.py -v
```

### Advanced Options
```bash
# Run with custom timeout
pytest tests/processors/ --timeout=1200

# Skip slow tests
pytest tests/processors/ -m "not slow"

# Run with custom PDF path
pytest tests/processors/ --pdf-path=/path/to/test/pdfs

# Run with specific markers
pytest tests/processors/ -m "processor and not slow"
```

## 📊 Test Coverage Areas

### UploadProcessor Tests
- ✅ File validation (size, type, existence)
- ✅ Duplicate detection and prevention
- ✅ Metadata extraction and preservation
- ✅ Database operations (create, read, update)
- ✅ Error handling and recovery
- ✅ Batch upload functionality
- ✅ Integration with stage tracking

### DocumentProcessor Tests
- ✅ Text extraction (PyMuPDF, pdfplumber)
- ✅ OCR fallback mechanisms
- ✅ Multi-language detection
- ✅ Manufacturer detection
- ✅ Document type classification
- ✅ Error handling for corrupted files
- ✅ Multi-page document processing
- ✅ Integration with stage tracking

### OptimizedTextProcessor Tests
- ✅ Text extraction engines
- ✅ SmartChunker functionality
- ✅ Chunk size and overlap management
- ✅ Metadata generation for chunks
- ✅ Database operations for chunks
- ✅ Configuration options
- ✅ Error handling and edge cases
- ✅ Integration with stage tracking

### Pipeline Flow Tests
- ✅ Complete Upload → Document → Text flow
- ✅ Context propagation across stages
- ✅ Stage tracking and progress updates
- ✅ Error recovery and retry mechanisms
- ✅ Data consistency validation
- ✅ Performance and concurrency testing
- ✅ Deduplication across pipeline stages

### Component Tests
- ✅ TextExtractor (engines, OCR, language detection)
- ✅ SmartChunker (size, overlap, metadata)
- ✅ StageTracker (lifecycle, progress, errors)

## 🛠️ Test Configuration

### Default Configuration
```python
processor_test_config = {
    'max_file_size_mb': 100,
    'pdf_engine': 'pymupdf',
    'chunk_size': 1000,
    'chunk_overlap': 200,
    'enable_ocr_fallback': True,
    'supported_languages': ['en', 'de', 'fr', 'es']
}
```

### Custom Configuration
Override fixtures in your test files:
```python
@pytest.fixture
def processor_test_config():
    return {
        'max_file_size_mb': 50,
        'pdf_engine': 'pdfplumber',
        'chunk_size': 500,
        'chunk_overlap': 100
    }
```

## 📝 Test Data

### Sample PDF Files
- **valid_pdf**: Standard service manual
- **corrupted_pdf**: Invalid PDF for error testing
- **empty_pdf**: Empty document for edge cases
- **large_pdf**: Large document for performance testing
- **ocr_pdf**: Image-only PDF for OCR testing
- **multi_lang_pdf**: Multi-language content

### Dynamic Test Content
Tests create dynamic content for specific scenarios:
- Error codes and technical specifications
- Multi-language documents
- Large documents for performance testing
- Corrupted files for error handling

## 🐛 Debugging Tests

### Enable Debug Logging
```bash
pytest tests/processors/ --log-cli-level=DEBUG
```

### Run Single Test
```bash
pytest tests/processors/test_upload_e2e.py::TestUploadValidation::test_file_size_validation -v -s
```

### Use Breakpoints
```python
import pytest; pytest.set_trace()
```

### Mock Debugging
Inspect mock calls during tests:
```python
# In test assertions
mock_database_adapter.create_document.assert_called_once()
mock_database_adapter.create_document.assert_called_with(expected_document)
```

## 📈 Performance Testing

### Benchmark Tests
Some tests include performance benchmarks:
- Large document processing
- Concurrent processing
- Memory usage validation
- Stage tracking overhead

### Running Performance Tests
```bash
# Run performance-focused tests
pytest tests/processors/ -m "performance" -v

# Run with memory profiling
pytest tests/processors/ --benchmark-only
```

## 🔧 Integration with CI/CD

### GitHub Actions
Tests are configured in `.github/workflows/api-tests.yml`:
- Runs on Python 3.9+
- Uses matrix testing for different configurations
- Generates coverage reports
- Uploads test artifacts

### Local Development
```bash
# Setup test environment
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Run full test suite
pytest tests/processors/ --cov=backend/processors --cov-report=html
```

## 🚨 Common Issues

### Import Errors
Ensure backend is in Python path:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### Async Test Issues
All processor tests use `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_async_functionality():
    result = await processor.process(context)
```

### Mock Configuration
Use proper async mocks:
```python
mock_database_adapter.create_document = AsyncMock(return_value="test-doc-id")
```

### File Path Issues
Use absolute paths and proper cleanup:
```python
@pytest.fixture
def temp_test_pdf(tmp_path):
    test_dir = tmp_path / "test_pdfs"
    test_dir.mkdir()
    yield test_dir
    # Cleanup handled by tmp_path fixture
```

## 📚 Best Practices

### Test Organization
- Group related tests in classes
- Use descriptive test names
- Follow Arrange-Act-Assert pattern
- Include comprehensive assertions

### Mock Usage
- Mock external dependencies
- Use realistic mock responses
- Verify mock calls when important
- Clean up mocks between tests

### Error Testing
- Test both success and failure scenarios
- Verify error messages are meaningful
- Test edge cases and boundary conditions
- Ensure graceful degradation

### Performance Considerations
- Use appropriate timeouts
- Test with realistic data sizes
- Monitor memory usage
- Profile slow tests

## 🔄 Maintenance

### Adding New Tests
1. Follow existing naming conventions
2. Use appropriate fixtures
3. Add proper markers
4. Include comprehensive coverage
5. Update documentation

### Updating Fixtures
1. Maintain backward compatibility
2. Document breaking changes
3. Update dependent tests
4. Test fixture functionality

### Test Data Management
1. Keep test data minimal but realistic
2. Use dynamic generation when possible
3. Clean up temporary files
4. Version control static test data

## 📞 Support

For questions about processor tests:
1. Check this README first
2. Review existing test patterns
3. Consult test documentation in code
4. Ask the development team

---

**Last Updated**: 2025-01-27
**Test Coverage**: Comprehensive E2E, unit, and integration testing for all pipeline processors
