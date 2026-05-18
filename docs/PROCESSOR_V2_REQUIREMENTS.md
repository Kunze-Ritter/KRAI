# Document Processor V2 - Requirements & Improvements

**Version:** 2.0
**Date:** 2025-10-02
**Status:** Design Phase

---

## Lessons Learned from V1

### ❌ What Went Wrong:

1. **Products Extraction:**
   - Extracted PDF filenames instead of product models
   - Used document type as product type
   - No validation of extracted data

2. **Error Codes Extraction:**
   - Captured random words after "Error code" pattern
   - No validation that codes are numeric (XX.XX.XX format)
   - Generic useless solutions ("Refer to service manual")
   - Fake confidence scores (always 0.75)

3. **AI Vision Issues:**
   - Hallucinated or misinterpreted structured data
   - Not suitable for precise table extraction
   - Expensive and unreliable

---

## V2 Requirements

### 1. Product Extraction 📦

**Goal:** Extract REAL product model numbers, not filenames!

**Strategy:**
```
Priority Order:
1. Look for model in first page headers (e.g., "LaserJet Pro M404dn")
2. Check document metadata/properties
3. Use filename ONLY as fallback (with validation)
4. Validate against known HP/manufacturer patterns
```

**Implementation:**
- **Regex Patterns:**
  - HP LaserJet: `(LaserJet|Color LaserJet|PageWide|OfficeJet|Designjet)\s+(?:Pro|Enterprise|Managed)?\s*[A-Z]?\d{3,4}[a-z]*`
  - HP Error Code format: `[EM]?\d{3,4}[a-z]?` (e.g., E877, M455, 4015)
  - Simple numeric: `\d{3,5}`

- **Validation:**
  ```python
  def validate_model_number(model: str) -> bool:
      # Not a filename
      if '.' in model or '_' in model:
          return False
      # Has letters and numbers
      if not (any(c.isalpha() for c in model) and any(c.isdigit() for c in model)):
          return False
      # Reasonable length
      if len(model) < 3 or len(model) > 50:
          return False
      return True
  ```

- **Mapping Table:**
  ```sql
  -- Create manual mapping for common patterns
  CREATE TABLE krai_config.filename_to_model_mapping (
      filename_pattern VARCHAR(255),
      actual_model VARCHAR(100),
      manufacturer_id UUID,
      notes TEXT
  );

  -- Examples:
  INSERT INTO krai_config.filename_to_model_mapping VALUES
  ('COLORLJE47528M', 'Color LaserJet Enterprise E47528', [hp_id], 'From manual'),
  ('COLORLJM480M', 'Color LaserJet Managed M480', [hp_id], 'From manual');
  ```

**Product Type:**
- **Extract from:** Document classification, not metadata
- **Valid values:** 'printer', 'scanner', 'multifunction', 'copier', 'plotter'
- **Validation:** Must be from allowed list

---

### 2. Error Code Extraction 🔴

**Goal:** Extract ONLY real numeric error codes with proper context!

**Strategy:**
```
1. Use STRICT regex for HP error format: XX.XX.XX
2. Extract full paragraph context (before/after)
3. Parse structured solution steps
4. Real confidence based on context quality
5. Link to source chunk for traceability
```

**Implementation:**

**Regex Patterns:**
```python
# HP Error Code Patterns:
PATTERNS = {
    'hp_standard': r'\b\d{2}\.\d{2}\.\d{2}\b',           # 13.20.01
    'hp_short': r'\b\d{2}\.\d{2}\b',                     # 49.38
    'hp_events': r'\b\d{5}-\d{4}\b',                     # 12345-6789
    'hp_with_prefix': r'\b(?:Error|Code|Event)\s+\d{2}\.\d{2}\.\d{2}\b'
}

# REJECT patterns (not error codes):
REJECT_WORDS = {
    'descriptions', 'information', 'lookup', 'troubleshooting',
    'specify', 'displays', 'field', 'system', 'file', 'page',
    'section', 'chapter', 'table', 'figure'
}

def extract_error_code(text: str) -> list[dict]:
    codes = []

    for pattern_name, pattern in PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)

        for match in matches:
            code = match.group(0)

            # Extract context (500 chars before/after)
            start = max(0, match.start() - 500)
            end = min(len(text), match.end() + 500)
            context = text[start:end]

            # Extract description (next sentence)
            description = extract_description(text, match.end())

            # Extract solution steps
            solution = extract_solution_steps(context)

            # Calculate REAL confidence
            confidence = calculate_confidence(code, description, solution, context)

            # Only add if confidence > 0.6
            if confidence > 0.6:
                codes.append({
                    'error_code': code,
                    'error_description': description,
                    'solution_text': solution,
                    'context_text': context,
                    'confidence_score': confidence,
                    'extraction_method': pattern_name
                })

    return codes

def calculate_confidence(code, description, solution, context):
    """Real confidence based on quality indicators"""
    score = 0.0

    # Has proper description (not generic)
    if description and len(description) > 20:
        score += 0.3

    # Has solution steps (numbered or bulleted)
    if solution and ('1.' in solution or '•' in solution):
        score += 0.3

    # Context contains technical terms
    technical_terms = ['fuser', 'sensor', 'motor', 'cartridge', 'drum', 'replace', 'check']
    if any(term in context.lower() for term in technical_terms):
        score += 0.2

    # Code appears multiple times in context (important)
    if context.count(code) > 1:
        score += 0.1

    # Context has reasonable length
    if 200 < len(context) < 2000:
        score += 0.1

    return min(score, 1.0)
```

**Validation:**
```python
def validate_error_code(code: str) -> bool:
    # Must be numeric format
    if not re.match(r'^\d{2}\.\d{2}(\.\d{2})?$', code):
        return False

    # Not a word
    if code.lower() in REJECT_WORDS:
        return False

    return True
```

---

### 3. Chunking Strategy 📄

**Current:** Works well! Keep it.

**Improvements:**
- Add overlap between chunks (50-100 chars)
- Preserve paragraph boundaries
- Keep error code sections together
- Metadata: page_number, section_title, chunk_type

```python
def improved_chunking(text: str, max_chunk_size=1000, overlap=100):
    """
    Smart chunking that preserves context
    """
    chunks = []

    # Split by paragraphs first
    paragraphs = text.split('\n\n')

    current_chunk = ""
    current_page = 1

    for para in paragraphs:
        # Check if adding paragraph exceeds limit
        if len(current_chunk) + len(para) > max_chunk_size:
            if current_chunk:
                chunks.append({
                    'text': current_chunk,
                    'page_start': current_page,
                    'metadata': {'chunk_type': 'text'}
                })

                # Add overlap from end of previous chunk
                current_chunk = current_chunk[-overlap:] + "\n\n" + para
            else:
                # Paragraph itself is too large, split it
                current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    # Add final chunk
    if current_chunk:
        chunks.append({
            'text': current_chunk,
            'page_start': current_page,
            'metadata': {'chunk_type': 'text'}
        })

    return chunks
```

---

### 4. Processing Pipeline 🔄

**New Pipeline:**

```
1. PDF Upload → Object Storage (MinIO)
   ↓
2. Text Extraction (PyMuPDF/pdfplumber - NO AI Vision for text!)
   ↓
3. Document Classification
   - Type: service_manual, parts_catalog, user_guide
   - Manufacturer: HP, Canon, Epson, etc.
   ↓
4. Metadata Extraction (First Page Only)
   - Product model (regex + validation)
   - Document title
   - Version/date
   ↓
5. Smart Chunking (with overlap)
   ↓
6. Structured Data Extraction (per chunk)
   - Error codes (strict regex + validation)
   - Product references
   - Part numbers
   ↓
7. Embedding Generation (Ollama/OpenAI)
   ↓
8. Database Insert (with validation checks)
   ↓
9. Quality Check
   - Validate inserted data
   - Flag low-confidence entries
   - Log statistics
```

---

### 5. Technology Stack Changes 📚

**REMOVE:**
- ❌ AI Vision for structured data extraction (unreliable, expensive)
- ❌ Generic "pattern matching" without validation

**ADD:**
- ✅ PyMuPDF for text extraction (better than pdfplumber for service manuals)
- ✅ Strict regex with validation
- ✅ Manual mapping tables for edge cases
- ✅ Real confidence scoring
- ✅ Chunk-level traceability
- ✅ Quality metrics & logging

---

### 6. Validation & Quality Checks ✅

**Before Insert:**
```python
def validate_before_insert(data: dict, data_type: str):
    """Validate data before database insert"""

    if data_type == 'product':
        # Product must have valid model_number
        if not validate_model_number(data['model_number']):
            raise ValidationError(f"Invalid model: {data['model_number']}")

        # Product type must be valid
        valid_types = {'printer', 'scanner', 'multifunction', 'copier'}
        if data.get('product_type') not in valid_types:
            raise ValidationError(f"Invalid product_type: {data.get('product_type')}")

    elif data_type == 'error_code':
        # Error code must match format
        if not validate_error_code(data['error_code']):
            raise ValidationError(f"Invalid error_code: {data['error_code']}")

        # Must have real description (not generic)
        generic_phrases = ['error code', 'refer to', 'see manual']
        if any(phrase in data['error_description'].lower() for phrase in generic_phrases):
            if len(data['error_description']) < 30:
                raise ValidationError("Description too generic")

        # Confidence must be > 0.6
        if data.get('confidence_score', 0) < 0.6:
            raise ValidationError(f"Confidence too low: {data['confidence_score']}")

    return True
```

**After Processing - Statistics:**
```python
def log_processing_stats(document_id: str):
    """Log quality metrics"""
    stats = {
        'document_id': document_id,
        'total_chunks': count_chunks(document_id),
        'embeddings_created': count_embeddings(document_id),
        'products_extracted': count_products(document_id),
        'error_codes_extracted': count_error_codes(document_id),
        'avg_confidence': avg_confidence(document_id),
        'validation_failures': count_validation_failures(document_id),
        'processing_time': calculate_time(document_id)
    }

    # Save to processing_log table
    save_stats(stats)

    # Alert if quality is low
    if stats['avg_confidence'] < 0.7:
        alert_low_quality(document_id, stats)
```

---

### 7. Testing Strategy 🧪

**Unit Tests:**
- Test each regex pattern
- Test validation functions
- Test confidence scoring
- Test chunking logic

**Integration Tests:**
- Process 1 known-good PDF
- Verify extracted data matches expected
- Check all validation passes

**Quality Checks:**
```sql
-- After processing batch, check quality:

-- 1. Error codes should be numeric
SELECT error_code, COUNT(*)
FROM krai_intelligence.error_codes
WHERE error_code !~ '^\d{2}\.\d{2}(\.\d{2})?$'
GROUP BY error_code
ORDER BY COUNT(*) DESC;
-- Should return 0 rows!

-- 2. Products should not be filenames
SELECT model_number, COUNT(*)
FROM krai_core.products
WHERE model_number LIKE '%_%' OR model_number LIKE '%.%'
GROUP BY model_number;
-- Should return 0 rows!

-- 3. Confidence distribution
SELECT
    CASE
        WHEN confidence_score >= 0.9 THEN 'High (0.9+)'
        WHEN confidence_score >= 0.7 THEN 'Medium (0.7-0.9)'
        ELSE 'Low (<0.7)'
    END as confidence_range,
    COUNT(*) as count
FROM krai_intelligence.error_codes
GROUP BY confidence_range;
-- Should have mostly High/Medium!
```

---

## Implementation Checklist

### Phase 1: Prep
- [ ] Complete DB cleanup (TRUNCATE all tables)
- [ ] Object storage cleanup or new bucket
- [ ] Backup any PDFs we want to reprocess

### Phase 2: Code
- [ ] Update document processor with new regex patterns
- [ ] Add validation functions
- [ ] Implement real confidence scoring
- [ ] Add filename→model mapping table & logic
- [ ] Improve chunking with overlap
- [ ] Add quality logging

### Phase 3: Test
- [ ] Process 1 test PDF
- [ ] Verify products extracted correctly
- [ ] Verify error codes are numeric
- [ ] Check confidence scores
- [ ] Run quality SQL checks

### Phase 4: Batch Processing
- [ ] Process small batch (5 PDFs)
- [ ] Check quality metrics
- [ ] Iterate & improve
- [ ] Process larger batches
- [ ] Monitor Agent performance during processing

### Phase 5: Production
- [ ] Full document corpus processing
- [ ] Continuous quality monitoring
- [ ] Agent ready for real use

---

## Success Metrics

**Quality Targets:**
- ✅ 0 invalid error codes (all match XX.XX.XX format)
- ✅ 0 filename-based product models
- ✅ >80% error codes with confidence >0.7
- ✅ >90% products with valid model numbers
- ✅ Agent finds answers for known error codes

**Performance Targets:**
- Process 1 PDF in <30 seconds
- Generate embeddings in <2 minutes/PDF
- No processing failures due to validation

---

## Notes

- Start small: 1 PDF → verify → iterate
- Quality over quantity
- Agent can be tested in parallel during processing
- Use n8n execution logs to monitor progress
- Document any new edge cases discovered

**Created:** 2025-10-02
**Next Update:** After first test processing
