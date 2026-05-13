# KRAI Benchmark Guide

## Overview

The KRAI benchmark suite provides comprehensive performance measurement and comparison capabilities for the document processing pipeline. This guide covers the complete workflow from staging environment setup through document selection, baseline measurement, optimization, current measurement, and result interpretation.

### Purpose

The benchmark suite enables:
- **Performance Measurement**: Quantify pipeline processing times with statistical rigor
- **Optimization Validation**: Verify that code changes achieve the 30%+ improvement target from resilience architecture
- **Bottleneck Identification**: Identify slow stages requiring optimization
- **Regression Detection**: Catch performance degradations before production deployment

### Key Components

- **`scripts/run_benchmark.py`**: Main benchmark execution script with baseline storage, comparison, and statistical analysis
- **`scripts/select_benchmark_documents.py`**: Document selection with stratification by type, manufacturer, page count, and file size
- **`krai_system.performance_baselines`**: Database table storing baseline and current metrics
- **`krai_system.benchmark_documents`**: Database table tracking selected benchmark documents

### Performance Target

The resilience architecture aims for **30%+ performance improvement** across pipeline stages. The benchmark suite provides statistical validation (avg, P50, P95, P99) to verify this target is achieved.

---

## Prerequisites

### Python Environment

Ensure Python 3.9+ is installed with required dependencies:

```bash
pip install rich asyncio statistics psycopg2-binary python-dotenv
```

### Database Access

The benchmark suite requires PostgreSQL access to:
- Store baseline metrics in `krai_system.performance_baselines`
- Track benchmark documents in `krai_system.benchmark_documents`
- Access document metadata from `krai_core.documents`

### Environment Variables

Configure the following in `.env`:

```env
DATABASE_URL=postgresql://user:password@host:port/database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=krai
POSTGRES_USER=krai_user
POSTGRES_PASSWORD=your_password
```

### Required Libraries

The benchmark scripts use:
- **`rich`**: Console output with tables, progress bars, and color coding
- **`asyncio`**: Asynchronous pipeline execution
- **`statistics`**: Statistical analysis (mean, median, percentiles)
- **`psycopg2`**: PostgreSQL database connectivity

### Staging Environment Access

Benchmarks should run in a staging environment or against a production snapshot to avoid impacting live services. See "Staging Environment Setup" section below.

---

## Staging Environment Setup

### Why Staging?

Running benchmarks in staging ensures:
- **Isolation**: No impact on production services or users
- **Consistency**: Controlled environment for reproducible measurements
- **Safety**: Test optimizations before production deployment
- **Realistic Data**: Use production data snapshot for accurate performance measurement

### Using docker-compose.staging.yml

The project includes `docker-compose.staging.yml` for staging deployment:

```bash
# Start staging environment
docker-compose -f docker-compose.staging.yml up -d

# Verify services are running
docker-compose -f docker-compose.staging.yml ps

# View logs
docker-compose -f docker-compose.staging.yml logs -f krai-engine
```

### Creating Production Data Snapshot

To benchmark with realistic data, create a snapshot of production documents:

#### 1. Export Production Database

```bash
# Dump production database
pg_dump -h prod-host -U krai_user -d krai \
  --schema=krai_core \
  --schema=krai_intelligence \
  --schema=krai_system \
  --file=production_snapshot.sql

# Restore to staging database
psql -h staging-host -U krai_user -d krai_staging \
  -f production_snapshot.sql
```

#### 2. Copy Document Files

```bash
# Create snapshot directory
mkdir -p ./staging-snapshots/$(date +%Y%m%d)

# Copy documents from production storage
# (Adjust paths based on your storage configuration)
rsync -av production:/path/to/documents/ \
  ./staging-snapshots/$(date +%Y%m%d)/

# Or copy from object storage (MinIO/S3)
mc mirror production-bucket/documents \
  ./staging-snapshots/$(date +%Y%m%d)/
```

#### 3. Update Staging Configuration

Update staging `.env` to point to snapshot data:

```env
DOCUMENT_STORAGE_PATH=./staging-snapshots/20250123
OBJECT_STORAGE_BUCKET=staging-documents
```

### Verification

Verify staging environment is ready:

```bash
# Check database connectivity
psql -h staging-host -U krai_user -d krai_staging -c "SELECT COUNT(*) FROM krai_core.documents;"

# Check document files are accessible
ls -lh ./staging-snapshots/latest/ | head -n 10

# Test API endpoint
curl http://localhost:8000/health
```

---

## Document Selection Process

### Overview

The `select_benchmark_documents.py` script selects a representative subset of documents for benchmarking using stratification to ensure diverse coverage across document types, manufacturers, page counts, and file sizes.

### Stratification Strategy

Documents are selected to represent:
- **Document Types**: Manuals, datasheets, troubleshooting guides, etc.
- **Manufacturers**: HP, Canon, Brother, Epson, etc.
- **Page Counts**: Short (1-10 pages), medium (11-50 pages), long (50+ pages)
- **File Sizes**: Small (<1MB), medium (1-10MB), large (>10MB)

This ensures benchmark results reflect real-world document diversity.

### Command-Line Arguments

```bash
python scripts/select_benchmark_documents.py [OPTIONS]
```

**Options:**
- `--snapshot-dir PATH`: Directory containing document snapshot (required)
- `--count N`: Number of documents to select (default: 10)
- `--min-size BYTES`: Minimum file size in bytes (default: 1024)
- `--max-size BYTES`: Maximum file size in bytes (default: 100MB)
- `--output FILE`: Output JSON file with selected document IDs (default: benchmark_documents.json)

### Example Usage

#### Select 10 Representative Documents

```bash
python scripts/select_benchmark_documents.py \
  --snapshot-dir ./staging-snapshots/latest \
  --count 10 \
  --output benchmark_documents.json
```

#### Select 20 Documents with Size Constraints

```bash
python scripts/select_benchmark_documents.py \
  --snapshot-dir ./staging-snapshots/latest \
  --count 20 \
  --min-size 10240 \
  --max-size 52428800 \
  --output benchmark_documents_20.json
```

### Document Marking

Selected documents are marked in two ways:

#### 1. Metadata Flag

Documents receive `is_benchmark: true` in their metadata JSONB column:

```sql
UPDATE krai_core.documents
SET metadata = metadata || '{"is_benchmark": true}'::jsonb
WHERE id IN (selected_document_ids);
```

#### 2. Benchmark Documents Table

Document references are stored in `krai_system.benchmark_documents`:

```sql
INSERT INTO krai_system.benchmark_documents (document_id, snapshot_id, file_size, selected_at)
VALUES (uuid, 'snapshot_20250123', 1048576, NOW());
```

### Verification

Verify document selection:

```bash
# Check benchmark_documents table
psql -h staging-host -U krai_user -d krai_staging -c \
  "SELECT COUNT(*) FROM krai_system.benchmark_documents;"

# Check metadata flags
psql -h staging-host -U krai_user -d krai_staging -c \
  "SELECT COUNT(*) FROM krai_core.documents WHERE metadata->>'is_benchmark' = 'true';"

# View selected documents
cat benchmark_documents.json | jq '.documents[] | {id, filename, size}'
```

---

## Running Baseline Benchmark

### Overview

The baseline benchmark establishes performance metrics before optimization. These metrics serve as the comparison point for measuring improvement after code changes.

### Command-Line Arguments

```bash
python scripts/run_benchmark.py [OPTIONS]
```

**Options:**
- `--count N`: Number of documents to process (default: 10)
- `--baseline`: Store results as baseline for future comparison
- `--compare`: Compare current run against stored baseline
- `--output FILE`: Output JSON file with detailed results (default: benchmark_results.json)
- `--verbose`: Enable detailed per-document logging

### Baseline Execution

#### Basic Baseline Run

```bash
python scripts/run_benchmark.py \
  --count 10 \
  --baseline \
  --output baseline_results.json
```

#### Verbose Baseline Run

```bash
python scripts/run_benchmark.py \
  --count 10 \
  --baseline \
  --output baseline_results.json \
  --verbose
```

### Pipeline vs. Stage-Specific Benchmarking

**Note**: Stage-only benchmarking mode is currently disabled. All benchmarks run the full pipeline to ensure accurate timing measurements. This provides:
- **Realistic Timings**: Includes inter-stage overhead and data transfer
- **End-to-End Metrics**: Measures complete processing time
- **Accurate Bottleneck Identification**: Shows true stage contributions to total time

### Baseline Storage

Baseline metrics are stored in `krai_system.performance_baselines`:

```sql
INSERT INTO krai_system.performance_baselines (
  stage_name,
  baseline_avg_seconds,
  baseline_p50_seconds,
  baseline_p95_seconds,
  baseline_p99_seconds,
  test_document_ids,
  measurement_date
) VALUES (
  'full_pipeline',
  45.23,
  42.10,
  58.67,
  62.34,
  ARRAY['uuid1', 'uuid2', ...],
  NOW()
);
```

### Sample Baseline Output

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Stage              ┃ Avg (s)    ┃ P50 (s)    ┃ P95 (s)    ┃ P99 (s)    ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ full_pipeline      │ 45.23      │ 42.10      │ 58.67      │ 62.34      │
│ pdf_extraction     │ 12.45      │ 11.80      │ 15.23      │ 16.12      │
│ chunking           │ 8.67       │ 8.20       │ 10.45      │ 11.23      │
│ embedding          │ 18.34      │ 17.50      │ 22.67      │ 24.01      │
│ classification     │ 5.77       │ 5.40       │ 7.32       │ 7.98       │
└────────────────────┴────────────┴────────────┴────────────┴────────────┘

✅ Baseline metrics stored successfully
📊 Processed 10 documents with 0 failures
```

### Verification

Verify baseline storage:

```bash
# Check database
psql -h staging-host -U krai_user -d krai_staging -c \
  "SELECT stage_name, baseline_avg_seconds, measurement_date
   FROM krai_system.performance_baselines
   ORDER BY measurement_date DESC LIMIT 5;"

# Check JSON output
cat baseline_results.json | jq '.baseline'
```

---

## Implementing Optimizations

### Overview

After establishing baseline metrics, implement performance optimizations in the staging environment. Test changes thoroughly before measuring improvement.

### Optimization Strategies

Refer to `docs/architecture/PERFORMANCE_OPTIMIZATION.md` for detailed strategies:

- **Concurrency**: Increase worker pools for parallel processing
- **Batch Processing**: Process multiple documents or chunks simultaneously
- **Caching**: Cache frequently accessed data (embeddings, classifications)
- **Database Optimization**: Add indexes, optimize queries, use connection pooling
- **Algorithm Improvements**: Replace slow algorithms with faster alternatives
- **Resource Management**: Optimize memory usage, reduce I/O operations

### Testing in Staging

Before benchmarking optimizations:

1. **Deploy Changes**: Update staging environment with optimized code
2. **Functional Testing**: Verify pipeline still produces correct results
3. **Smoke Testing**: Process a few documents manually to catch obvious issues
4. **Resource Monitoring**: Check CPU, memory, and database load

### Code Change Tracking

Document optimizations for reproducibility:

```bash
# Example: Increase concurrent workers
git commit -m "perf: Increase embedding workers from 4 to 8"

# Example: Add caching layer
git commit -m "perf: Add Redis cache for classification results"

# Example: Optimize database query
git commit -m "perf: Add index on chunks.document_id for faster lookups"
```

### Configuration Changes

Track configuration adjustments:

```env
# Before optimization
EMBEDDING_WORKERS=4
CHUNK_BATCH_SIZE=10

# After optimization
EMBEDDING_WORKERS=8
CHUNK_BATCH_SIZE=20
```

---

## Running Current Benchmark

### Overview

After implementing optimizations, run a current benchmark using the same document set to measure improvement against the baseline.

### Comparison Execution

#### Basic Comparison Run

```bash
python scripts/run_benchmark.py \
  --count 10 \
  --compare \
  --output current_results.json
```

#### Verbose Comparison Run

```bash
python scripts/run_benchmark.py \
  --count 10 \
  --compare \
  --output current_results.json \
  --verbose
```

### Comparison Logic

The `--compare` flag triggers:

1. **Fetch Baseline**: Retrieve stored baseline metrics from database
2. **Execute Benchmark**: Process same documents through optimized pipeline
3. **Calculate Improvement**: Compute percentage improvement for each metric
4. **Display Comparison**: Show side-by-side results with color coding

### Improvement Calculation

Improvement percentage is calculated as:

```python
improvement = (baseline - current) / baseline * 100
```

**Example:**
- Baseline: 45.23 seconds
- Current: 31.66 seconds
- Improvement: (45.23 - 31.66) / 45.23 * 100 = **30.0%**

### Sample Comparison Output

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Stage              ┃ Baseline   ┃ Current    ┃ Improvement    ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ full_pipeline      │ 45.23s     │ 31.66s     │ 🟢 30.0%       │
│ pdf_extraction     │ 12.45s     │ 10.12s     │ 🟢 18.7%       │
│ chunking           │ 8.67s      │ 7.23s      │ 🟡 16.6%       │
│ embedding          │ 18.34s     │ 11.45s     │ 🟢 37.6%       │
│ classification     │ 5.77s      │ 2.86s      │ 🟢 50.4%       │
└────────────────────┴────────────┴────────────┴────────────────┘

✅ Target achieved: 30.0% improvement
📊 Processed 10 documents with 0 failures
```

### Verification

Verify current metrics storage:

```bash
# Check database
psql -h staging-host -U krai_user -d krai_staging -c \
  "SELECT stage_name, baseline_avg_seconds, current_avg_seconds, improvement_percentage
   FROM krai_system.performance_baselines
   WHERE improvement_percentage IS NOT NULL
   ORDER BY measurement_date DESC LIMIT 5;"

# Check JSON output
cat current_results.json | jq '.comparison'
```

---

## Interpreting Results

### Statistical Metrics

The benchmark suite provides four key metrics for each stage:

#### Average (Mean)

**Definition**: Sum of all processing times divided by document count

**Use Case**: Overall performance indicator

**Interpretation**:
- Lower is better
- Affected by outliers (very slow documents)
- Good for general performance trends

**Example**: If 10 documents take [40s, 42s, 41s, 45s, 43s, 44s, 46s, 42s, 47s, 48s], average = 43.8s

#### P50 (Median)

**Definition**: Middle value when times are sorted (50th percentile)

**Use Case**: Typical performance, less affected by outliers

**Interpretation**:
- Lower is better
- More stable than average
- Represents "normal" document processing time

**Example**: From same data, P50 = 43.5s (middle of sorted list)

#### P95 (95th Percentile)

**Definition**: 95% of documents process faster than this time

**Use Case**: Typical worst-case performance

**Interpretation**:
- Lower is better
- Captures slow documents without extreme outliers
- Important for user experience (most users see this or better)

**Example**: From same data, P95 = 47.5s (95% of documents faster)

#### P99 (99th Percentile)

**Definition**: 99% of documents process faster than this time

**Use Case**: Extreme case performance

**Interpretation**:
- Lower is better
- Captures rare slow documents
- Important for SLA guarantees

**Example**: From same data, P99 = 48.0s (99% of documents faster)

### Improvement Indicators

Results are color-coded based on improvement percentage:

#### 🟢 Green (30%+ improvement)

**Meaning**: Target achieved, optimization successful

**Action**: Document changes, consider production deployment

**Example**: Baseline 45.23s → Current 31.66s = 30.0% improvement

#### 🟡 Yellow (10-30% improvement)

**Meaning**: Moderate improvement, may need further optimization

**Action**: Analyze bottlenecks, consider additional optimizations

**Example**: Baseline 8.67s → Current 7.23s = 16.6% improvement

#### 🔴 Red (<10% improvement)

**Meaning**: Minimal improvement, optimization ineffective

**Action**: Review optimization strategy, identify root causes

**Example**: Baseline 5.77s → Current 5.50s = 4.7% improvement

### Per-Stage Breakdown Interpretation

Analyze per-stage results to identify bottlenecks:

#### Example Analysis

```
Stage              Baseline   Current    Improvement
─────────────────────────────────────────────────────
full_pipeline      45.23s     31.66s     🟢 30.0%
pdf_extraction     12.45s     10.12s     🟡 18.7%
chunking           8.67s      7.23s      🟡 16.6%
embedding          18.34s     11.45s     🟢 37.6%
classification     5.77s      2.86s      🟢 50.4%
```

**Insights:**
1. **Embedding stage**: Largest absolute improvement (6.89s saved), 37.6% faster
2. **Classification stage**: Highest percentage improvement (50.4%), nearly 2x faster
3. **PDF extraction**: Moderate improvement (18.7%), potential for further optimization
4. **Chunking**: Smallest improvement (16.6%), may be bottleneck after other optimizations

**Next Steps:**
- Focus on PDF extraction optimization (still 10.12s, 32% of total time)
- Consider chunking algorithm improvements
- Validate embedding and classification optimizations in production

### Identifying Bottleneck Stages

#### Absolute Time Analysis

Look for stages with highest absolute time:

```
embedding: 11.45s (36% of total)
pdf_extraction: 10.12s (32% of total)
chunking: 7.23s (23% of total)
classification: 2.86s (9% of total)
```

**Conclusion**: Embedding and PDF extraction are bottlenecks

#### Improvement Potential Analysis

Look for stages with lowest improvement:

```
chunking: 16.6% improvement (lowest)
pdf_extraction: 18.7% improvement (second lowest)
```

**Conclusion**: These stages have most room for further optimization

### Sample Comparison Output Interpretation

```json
{
  "comparison": {
    "full_pipeline": {
      "baseline": {
        "avg": 45.23,
        "p50": 42.10,
        "p95": 58.67,
        "p99": 62.34
      },
      "current": {
        "avg": 31.66,
        "p50": 29.50,
        "p95": 41.20,
        "p99": 43.80
      },
      "improvement": {
        "avg": 30.0,
        "p50": 29.9,
        "p95": 29.8,
        "p99": 29.7
      }
    }
  }
}
```

**Analysis:**
- **Consistent improvement**: All metrics show ~30% improvement (good sign)
- **P99 improvement**: Extreme cases improved 29.7% (optimization helps slow documents)
- **Variance reduction**: P95-P50 gap reduced from 16.57s to 11.70s (more predictable performance)

---

## Best Practices

### Document Set Consistency

**Use the same document set for baseline and current measurements**

❌ **Wrong**:
```bash
# Baseline with 10 documents
python scripts/run_benchmark.py --count 10 --baseline

# Current with different 10 documents
python scripts/run_benchmark.py --count 10 --compare
```

✅ **Correct**:
```bash
# Select documents once
python scripts/select_benchmark_documents.py --count 10

# Use same documents for baseline and current
python scripts/run_benchmark.py --count 10 --baseline
python scripts/run_benchmark.py --count 10 --compare
```

### Timing Considerations

**Run benchmarks during low-activity periods to reduce noise**

- Avoid running during peak hours
- Stop other heavy processes (backups, indexing)
- Use dedicated staging environment
- Monitor system resources (CPU, RAM, disk I/O)

### Multiple Runs for Stability

**Perform multiple runs and average results**

```bash
# Run 3 times and compare
for i in {1..3}; do
  python scripts/run_benchmark.py --count 10 --compare --output run_${i}.json
done

# Average results
jq -s 'map(.comparison.full_pipeline.current.avg) | add / length' run_*.json
```

**Acceptable variance**: ±10% across runs

### Environmental Factors

**Document factors that may affect results**

Create a benchmark log:

```markdown
## Benchmark Run: 2025-01-23 10:00

**Environment:**
- CPU Load: 15% average
- RAM Usage: 8GB / 16GB
- Network Latency: 5ms to database
- Disk I/O: 50MB/s read, 20MB/s write

**Configuration:**
- EMBEDDING_WORKERS=8
- CHUNK_BATCH_SIZE=20
- DATABASE_POOL_SIZE=10

**Results:**
- Full pipeline: 31.66s avg (30.0% improvement)
- Target achieved ✅
```

### Baseline Before Refactoring

**Store baseline before major code changes**

```bash
# Before refactoring
git checkout main
python scripts/run_benchmark.py --count 10 --baseline --output baseline_pre_refactor.json

# After refactoring
git checkout feature/performance-optimization
python scripts/run_benchmark.py --count 10 --compare --output current_post_refactor.json
```

### Verbose Mode for Analysis

**Use `--verbose` flag for detailed per-document analysis**

```bash
python scripts/run_benchmark.py --count 10 --compare --verbose
```

**Verbose output includes:**
- Per-document processing times
- Stage-by-stage breakdown for each document
- Error messages and warnings
- Resource usage statistics

### JSON Output Review

**Review JSON output files for detailed metrics**

```bash
# View full results
cat current_results.json | jq '.'

# Extract specific metrics
cat current_results.json | jq '.comparison.embedding.improvement.avg'

# Compare multiple runs
jq -s '.[0].comparison.full_pipeline.current.avg, .[1].comparison.full_pipeline.current.avg' run_1.json run_2.json
```

---

## Troubleshooting

### "No benchmark documents found" Error

**Symptom:**
```
Error: No benchmark documents found in database
```

**Cause**: `select_benchmark_documents.py` has not been run

**Solution**:
```bash
# Select benchmark documents first
python scripts/select_benchmark_documents.py \
  --snapshot-dir ./staging-snapshots/latest \
  --count 10

# Verify selection
psql -h staging-host -U krai_user -d krai_staging -c \
  "SELECT COUNT(*) FROM krai_system.benchmark_documents;"
```

### Database Connection Errors

**Symptom:**
```
psycopg2.OperationalError: could not connect to server
```

**Cause**: Incorrect database credentials or unreachable database

**Solution**:
```bash
# Verify DATABASE_URL in .env
cat .env | grep DATABASE_URL

# Test connection manually
psql -h staging-host -U krai_user -d krai_staging -c "SELECT 1;"

# Check PostgreSQL is running
docker-compose -f docker-compose.staging.yml ps krai-postgres
```

### Stage-Only Benchmark Disabled

**Symptom:**
```
Warning: Stage-only benchmarking is disabled
```

**Cause**: Stage-only mode is intentionally disabled for accurate timings

**Solution**: Use full pipeline mode (default behavior)

**Explanation**: Stage-only benchmarking was disabled because:
- Inter-stage overhead is significant
- Data transfer between stages affects timing
- Full pipeline provides realistic end-to-end metrics

### Inconsistent Results

**Symptom**: Results vary significantly between runs (>20% variance)

**Possible Causes:**
- High system load (CPU, RAM, disk I/O)
- Network latency to database or object storage
- Background processes interfering
- Insufficient warm-up period

**Solutions:**

1. **Check system load:**
```bash
# Linux/Mac
top
htop

# Windows
Task Manager
```

2. **Stop background processes:**
```bash
# Stop unnecessary Docker containers
docker ps
docker stop <container_id>

# Check for CPU-intensive processes
ps aux --sort=-%cpu | head -n 10
```

3. **Run multiple iterations:**
```bash
# Run 5 times and average
for i in {1..5}; do
  python scripts/run_benchmark.py --count 10 --compare --output run_${i}.json
  sleep 60  # Wait between runs
done
```

4. **Use dedicated hardware:**
- Run on dedicated staging server
- Avoid shared development machines
- Use consistent cloud instance types

### Missing Baseline

**Symptom:**
```
Error: No baseline found for comparison
```

**Cause**: Baseline has not been stored

**Solution**:
```bash
# Store baseline first
python scripts/run_benchmark.py --count 10 --baseline

# Then run comparison
python scripts/run_benchmark.py --count 10 --compare
```

### Performance Regression

**Symptom**: Current metrics are slower than baseline (negative improvement)

**Example:**
```
full_pipeline: 45.23s → 52.10s (-15.2% regression)
```

**Investigation Steps:**

1. **Review recent code changes:**
```bash
git log --oneline --since="1 week ago"
git diff baseline_commit current_commit
```

2. **Check configuration changes:**
```bash
git diff baseline_commit:config/ current_commit:config/
```

3. **Analyze per-stage breakdown:**
```bash
cat current_results.json | jq '.comparison | to_entries | map({stage: .key, regression: .value.improvement.avg}) | sort_by(.regression)'
```

4. **Check resource constraints:**
```bash
# Database connection pool exhaustion
psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='krai_staging';"

# Memory usage
free -h

# Disk I/O
iostat -x 1 5
```

5. **Rollback and re-test:**
```bash
git checkout baseline_commit
python scripts/run_benchmark.py --count 10 --compare
```

### Document Processing Failures

**Symptom**: Benchmark reports failed documents

**Example:**
```
📊 Processed 10 documents with 3 failures
```

**Investigation:**

1. **Check verbose output:**
```bash
python scripts/run_benchmark.py --count 10 --compare --verbose
```

2. **Review error logs:**
```bash
# Check application logs
docker-compose -f docker-compose.staging.yml logs krai-engine | grep ERROR

# Check database logs
docker-compose -f docker-compose.staging.yml logs krai-postgres | grep ERROR
```

3. **Identify failing documents:**
```bash
cat current_results.json | jq '.failures[] | {document_id, error}'
```

4. **Test failing documents individually:**
```bash
# Process single document
curl -X POST http://localhost:8000/api/documents/process \
  -H "Content-Type: application/json" \
  -d '{"document_id": "failing_document_uuid"}'
```

---

## Integration with Dashboard

### Filament Dashboard Widget

Benchmark results are visualized in the Laravel Filament dashboard via `PerformanceMetricsWidget`.

**File**: `laravel-admin/app/Filament/Widgets/PerformanceMetricsWidget.php`

**Features:**
- Real-time performance metrics display
- Color-coded improvement indicators
- Per-stage breakdown charts
- Historical trend graphs

### Accessing the Dashboard

```bash
# Start Laravel admin
cd laravel-admin
php artisan serve

# Open browser
http://localhost:8001/kradmin
```

**Navigation**: Dashboard → Performance Metrics Widget

### API Endpoint

Fetch performance metrics programmatically:

```bash
# Get current metrics
curl http://localhost:8001/api/monitoring/performance

# Response format
{
  "full_pipeline": {
    "baseline_avg": 45.23,
    "current_avg": 31.66,
    "improvement_percentage": 30.0
  },
  "stages": {
    "pdf_extraction": {...},
    "chunking": {...},
    "embedding": {...},
    "classification": {...}
  }
}
```

### Improvement Visualization

The dashboard uses color coding matching the benchmark script:

- **🟢 Green**: 30%+ improvement (target achieved)
- **🟡 Yellow**: 10-30% improvement (moderate)
- **🔴 Red**: <10% improvement (minimal)

### Historical Trends

View performance trends over time:

```sql
SELECT
  measurement_date,
  stage_name,
  baseline_avg_seconds,
  current_avg_seconds,
  improvement_percentage
FROM krai_system.performance_baselines
WHERE stage_name = 'full_pipeline'
ORDER BY measurement_date DESC
LIMIT 10;
```

**Dashboard Chart**: Plots improvement percentage over time to track optimization progress

---

## Database Schema Reference

### performance_baselines Table

**Schema**: `krai_system.performance_baselines`

**Purpose**: Store baseline and current performance metrics for comparison

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `stage_name` | VARCHAR(255) | Pipeline stage identifier (e.g., 'full_pipeline', 'embedding') |
| `baseline_avg_seconds` | DECIMAL(10,3) | Baseline average processing time |
| `baseline_p50_seconds` | DECIMAL(10,3) | Baseline median (50th percentile) |
| `baseline_p95_seconds` | DECIMAL(10,3) | Baseline 95th percentile |
| `baseline_p99_seconds` | DECIMAL(10,3) | Baseline 99th percentile |
| `current_avg_seconds` | DECIMAL(10,3) | Current average processing time |
| `current_p50_seconds` | DECIMAL(10,3) | Current median (50th percentile) |
| `current_p95_seconds` | DECIMAL(10,3) | Current 95th percentile |
| `current_p99_seconds` | DECIMAL(10,3) | Current 99th percentile |
| `improvement_percentage` | DECIMAL(5,2) | Calculated improvement: (baseline - current) / baseline * 100 |
| `test_document_ids` | UUID[] | Array of document UUIDs used for measurement |
| `measurement_date` | TIMESTAMP | Timestamp of measurement |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record update timestamp |

**Indexes:**
- Primary key on `id`
- Index on `stage_name` for fast lookups
- Index on `measurement_date` for historical queries

**Example Query:**

```sql
-- Get latest baseline for full pipeline
SELECT
  stage_name,
  baseline_avg_seconds,
  current_avg_seconds,
  improvement_percentage,
  measurement_date
FROM krai_system.performance_baselines
WHERE stage_name = 'full_pipeline'
ORDER BY measurement_date DESC
LIMIT 1;
```

### benchmark_documents Table

**Schema**: `krai_system.benchmark_documents`

**Purpose**: Track documents selected for benchmarking

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `document_id` | UUID | Foreign key to `krai_core.documents.id` |
| `snapshot_id` | VARCHAR(255) | Staging snapshot identifier (e.g., 'snapshot_20250123') |
| `file_size` | BIGINT | Document file size in bytes |
| `selected_at` | TIMESTAMP | Selection timestamp |
| `created_at` | TIMESTAMP | Record creation timestamp |

**Indexes:**
- Primary key on `id`
- Foreign key on `document_id` referencing `krai_core.documents(id)`
- Index on `snapshot_id` for snapshot-specific queries

**Example Query:**

```sql
-- Get all benchmark documents with metadata
SELECT
  bd.document_id,
  d.filename,
  d.manufacturer,
  d.document_type,
  bd.file_size,
  bd.selected_at
FROM krai_system.benchmark_documents bd
JOIN krai_core.documents d ON bd.document_id = d.id
WHERE bd.snapshot_id = 'snapshot_20250123'
ORDER BY bd.selected_at DESC;
```

### Relationship to Other Tables

**Documents Table**: `krai_core.documents`

Benchmark documents reference the main documents table:

```sql
-- Find benchmark documents with full metadata
SELECT
  d.id,
  d.filename,
  d.manufacturer,
  d.document_type,
  d.page_count,
  d.metadata->>'is_benchmark' as is_benchmark,
  bd.file_size,
  bd.snapshot_id
FROM krai_core.documents d
LEFT JOIN krai_system.benchmark_documents bd ON d.id = bd.document_id
WHERE d.metadata->>'is_benchmark' = 'true';
```

---

## Example Workflow Diagram

```mermaid
sequenceDiagram
    participant User
    participant Staging as Staging Environment
    participant SelectScript as select_benchmark_documents.py
    participant BenchmarkScript as run_benchmark.py
    participant Database as PostgreSQL
    participant Dashboard as Filament Dashboard

    User->>Staging: 1. Setup staging with production snapshot
    Note over Staging: docker-compose -f docker-compose.staging.yml up -d

    User->>SelectScript: 2. Select benchmark documents
    Note over SelectScript: --snapshot-dir ./staging-snapshots/latest --count 10
    SelectScript->>Database: Store in benchmark_documents table
    SelectScript->>Database: Mark documents with is_benchmark flag
    SelectScript-->>User: benchmark_documents.json created

    User->>BenchmarkScript: 3. Run baseline benchmark (--baseline)
    Note over BenchmarkScript: --count 10 --baseline --output baseline_results.json
    BenchmarkScript->>Database: Fetch benchmark documents
    BenchmarkScript->>BenchmarkScript: Process documents through pipeline
    BenchmarkScript->>Database: Store baseline metrics
    BenchmarkScript-->>User: Display baseline results (avg, P50, P95, P99)

    User->>User: 4. Implement optimizations
    Note over User: Increase workers, add caching, optimize queries

    User->>BenchmarkScript: 5. Run current benchmark (--compare)
    Note over BenchmarkScript: --count 10 --compare --output current_results.json
    BenchmarkScript->>Database: Fetch benchmark documents
    BenchmarkScript->>BenchmarkScript: Process documents through optimized pipeline
    BenchmarkScript->>Database: Fetch baseline for comparison
    BenchmarkScript->>BenchmarkScript: Calculate improvement percentage
    BenchmarkScript->>Database: Store current metrics
    BenchmarkScript-->>User: Display comparison results (🟢 30.0% improvement)

    Dashboard->>Database: 6. Fetch performance metrics
    Note over Dashboard: GET /api/monitoring/performance
    Dashboard-->>User: Display improvement in widget
```

---

## Validation Checklist

### Pre-Benchmark Checklist

Before running benchmarks, verify:

- [ ] **Staging environment is running**
  ```bash
  docker-compose -f docker-compose.staging.yml ps
  ```

- [ ] **Benchmark documents are selected**
  ```bash
  psql -c "SELECT COUNT(*) FROM krai_system.benchmark_documents;"
  ```

- [ ] **Database connection is verified**
  ```bash
  psql -c "SELECT 1;"
  ```

- [ ] **System resources are available**
  ```bash
  # Check CPU, RAM, disk space
  top
  df -h
  ```

- [ ] **No other heavy processes running**
  ```bash
  # Check for competing processes
  ps aux --sort=-%cpu | head -n 10
  ```

### Post-Benchmark Checklist

After running benchmarks, verify:

- [ ] **Baseline metrics stored in database**
  ```bash
  psql -c "SELECT COUNT(*) FROM krai_system.performance_baselines WHERE baseline_avg_seconds IS NOT NULL;"
  ```

- [ ] **JSON report generated successfully**
  ```bash
  ls -lh baseline_results.json current_results.json
  ```

- [ ] **Statistical metrics are reasonable**
  - No extreme outliers (P99 < 3x P50)
  - Consistent metrics across runs (±10% variance)

- [ ] **Per-stage timings add up to total duration**
  ```bash
  cat current_results.json | jq '.stages | map(.current.avg) | add'
  ```

- [ ] **Improvement percentage calculated correctly**
  ```bash
  cat current_results.json | jq '.comparison.full_pipeline.improvement.avg'
  ```

- [ ] **Results visible in Filament dashboard**
  - Navigate to http://localhost:8001/kradmin
  - Check Performance Metrics Widget

### Success Criteria

Benchmark run is successful when:

- [ ] **All documents processed successfully** (0 failures)
  ```
  📊 Processed 10 documents with 0 failures
  ```

- [ ] **Baseline metrics stored with valid timestamps**
  ```sql
  SELECT measurement_date FROM krai_system.performance_baselines
  WHERE measurement_date > NOW() - INTERVAL '1 hour';
  ```

- [ ] **Improvement percentage ≥ 30%** (for optimization validation)
  ```
  🟢 30.0% improvement
  ```

- [ ] **Per-stage breakdown shows expected bottlenecks**
  - Embedding and PDF extraction typically slowest
  - Classification typically fastest

- [ ] **Results reproducible across multiple runs** (±10% variance)
  ```bash
  # Run 3 times, compare variance
  for i in {1..3}; do
    python scripts/run_benchmark.py --count 10 --compare --output run_${i}.json
  done
  ```

---

## Related Documentation

### Performance Testing

- **`docs/testing/PERFORMANCE_TESTING_GUIDE.md`**: Load testing with Locust for concurrent user simulation
- **`docs/testing/BENCHMARK_QUICK_REFERENCE.md`**: Quick command reference for benchmark suite

### Architecture & Optimization

- **`docs/architecture/PERFORMANCE_OPTIMIZATION.md`**: Detailed optimization strategies and techniques
- **`docs/PERFORMANCE_FEATURES.md`**: Overview of performance features and capabilities
- **`docs/architecture/LOGGING_SYSTEM.md`**: Logging and monitoring infrastructure

### Implementation Details

- **`backend/services/performance_service.py`**: PerformanceCollector service implementation
- **`scripts/run_benchmark.py`**: Main benchmark execution script
- **`scripts/select_benchmark_documents.py`**: Document selection script

### Database Schema

- **`database/migrations_postgresql/008_pipeline_resilience_schema.sql`**: Performance baselines table schema
- **`database/migrations_postgresql/010_benchmark_documents_table.sql`**: Benchmark documents table schema
- **`DATABASE_SCHEMA.md`**: Complete database schema reference

### Dashboard Integration

- **`laravel-admin/app/Filament/Widgets/PerformanceMetricsWidget.php`**: Dashboard widget for performance visualization
- **`docs/dashboard/USER_GUIDE.md`**: Dashboard user guide

---

## Summary

This guide covers the complete benchmark workflow:

1. **Setup**: Staging environment with production snapshot
2. **Selection**: Choose representative documents with stratification
3. **Baseline**: Measure current performance with statistical rigor
4. **Optimization**: Implement performance improvements
5. **Comparison**: Measure improvement against baseline
6. **Interpretation**: Analyze results and identify bottlenecks
7. **Validation**: Verify 30%+ improvement target achieved

**Key Takeaways:**

- Use consistent document sets for accurate comparison
- Run benchmarks in isolated staging environment
- Analyze per-stage breakdown to identify bottlenecks
- Aim for 30%+ improvement (green indicator)
- Document optimizations for reproducibility
- Verify results in Filament dashboard

**Next Steps:**

1. Review `docs/testing/BENCHMARK_QUICK_REFERENCE.md` for quick command reference
2. Explore `docs/architecture/PERFORMANCE_OPTIMIZATION.md` for optimization strategies
3. Check `docs/testing/PERFORMANCE_TESTING_GUIDE.md` for load testing guidance

For questions or issues, refer to the Troubleshooting section or contact the development team.
