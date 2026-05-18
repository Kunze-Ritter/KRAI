# Benchmark Quick Reference

Quick command reference for the KRAI benchmark suite. For comprehensive documentation, see [BENCHMARK_GUIDE.md](BENCHMARK_GUIDE.md).

---

## Quick Commands

### 1. Select Benchmark Documents

```bash
python scripts/select_benchmark_documents.py \
  --snapshot-dir ./staging-snapshots/latest \
  --count 10
```

**Options:**
- `--snapshot-dir PATH`: Directory containing document snapshot (required)
- `--count N`: Number of documents to select (default: 10)
- `--min-size BYTES`: Minimum file size (default: 1024)
- `--max-size BYTES`: Maximum file size (default: 100MB)
- `--output FILE`: Output JSON file (default: benchmark_documents.json)

---

### 2. Run Baseline Benchmark

```bash
python scripts/run_benchmark.py \
  --count 10 \
  --baseline \
  --output baseline_results.json
```

**Options:**
- `--count N`: Number of documents to process (default: 10)
- `--baseline`: Store results as baseline for future comparison
- `--output FILE`: Output JSON file (default: benchmark_results.json)
- `--verbose`: Enable detailed per-document logging

---

### 3. Run Current Benchmark with Comparison

```bash
python scripts/run_benchmark.py \
  --count 10 \
  --compare \
  --output current_results.json \
  --verbose
```

**Options:**
- `--compare`: Compare current run against stored baseline
- `--verbose`: Show detailed per-document analysis

---

### 4. View Results

```bash
# View full results
cat current_results.json | jq '.'

# View comparison summary
cat current_results.json | jq '.comparison'

# View specific stage improvement
cat current_results.json | jq '.comparison.embedding.improvement.avg'

# View all stages sorted by improvement
cat current_results.json | jq '.comparison | to_entries | map({stage: .key, improvement: .value.improvement.avg}) | sort_by(.improvement)'
```

---

## Common Scenarios

### First-Time Setup

```bash
# 1. Setup staging environment
docker-compose -f docker-compose.staging.yml up -d

# 2. Select benchmark documents
python scripts/select_benchmark_documents.py \
  --snapshot-dir ./staging-snapshots/latest \
  --count 10

# 3. Run baseline
python scripts/run_benchmark.py \
  --count 10 \
  --baseline \
  --output baseline_results.json
```

---

### After Optimization

```bash
# 1. Deploy optimizations to staging
# (Update code, restart services)

# 2. Run comparison benchmark
python scripts/run_benchmark.py \
  --count 10 \
  --compare \
  --output current_results.json

# 3. Check improvement
cat current_results.json | jq '.comparison.full_pipeline.improvement.avg'
```

---

### Detailed Analysis

```bash
# Run with verbose output
python scripts/run_benchmark.py \
  --count 10 \
  --compare \
  --output detailed_results.json \
  --verbose

# Analyze per-stage bottlenecks
cat detailed_results.json | jq '.stages | to_entries | map({stage: .key, current_avg: .value.current.avg}) | sort_by(.current_avg) | reverse'

# Check P95 performance
cat detailed_results.json | jq '.comparison | to_entries | map({stage: .key, p95_improvement: .value.improvement.p95})'
```

---

### Multiple Runs for Stability

```bash
# Run 3 times and compare
for i in {1..3}; do
  python scripts/run_benchmark.py \
    --count 10 \
    --compare \
    --output run_${i}.json
  sleep 60  # Wait between runs
done

# Average results
jq -s 'map(.comparison.full_pipeline.current.avg) | add / length' run_*.json
```

---

## Database Queries

### Check Benchmark Documents

```sql
-- Count benchmark documents
SELECT COUNT(*) FROM krai_system.benchmark_documents;

-- View selected documents
SELECT
  bd.document_id,
  d.filename,
  d.manufacturer,
  bd.file_size,
  bd.selected_at
FROM krai_system.benchmark_documents bd
JOIN krai_core.documents d ON bd.document_id = d.id
ORDER BY bd.selected_at DESC
LIMIT 10;
```

---

### Check Performance Baselines

```sql
-- Latest baseline metrics
SELECT
  stage_name,
  baseline_avg_seconds,
  current_avg_seconds,
  improvement_percentage,
  measurement_date
FROM krai_system.performance_baselines
ORDER BY measurement_date DESC
LIMIT 10;

-- Full pipeline performance history
SELECT
  measurement_date,
  baseline_avg_seconds,
  current_avg_seconds,
  improvement_percentage
FROM krai_system.performance_baselines
WHERE stage_name = 'full_pipeline'
ORDER BY measurement_date DESC;
```

---

## Verification Commands

### Pre-Benchmark Checklist

```bash
# Check staging environment
docker-compose -f docker-compose.staging.yml ps

# Check database connection
psql -h staging-host -U krai_user -d krai_staging -c "SELECT 1;"

# Check benchmark documents
psql -h staging-host -U krai_user -d krai_staging -c \
  "SELECT COUNT(*) FROM krai_system.benchmark_documents;"

# Check system resources
top
df -h
```

---

### Post-Benchmark Verification

```bash
# Check baseline stored
psql -h staging-host -U krai_user -d krai_staging -c \
  "SELECT COUNT(*) FROM krai_system.performance_baselines WHERE baseline_avg_seconds IS NOT NULL;"

# Check JSON output
ls -lh baseline_results.json current_results.json

# Verify improvement calculation
cat current_results.json | jq '.comparison.full_pipeline | {baseline: .baseline.avg, current: .current.avg, improvement: .improvement.avg}'
```

---

## Interpreting Results

### Color Indicators

- **🟢 Green (30%+ improvement)**: Target achieved, optimization successful
- **🟡 Yellow (10-30% improvement)**: Moderate improvement, consider further optimization
- **🔴 Red (<10% improvement)**: Minimal improvement, review optimization strategy

### Statistical Metrics

- **Average**: Mean processing time across all documents
- **P50 (Median)**: Typical performance, less affected by outliers
- **P95**: 95th percentile, represents typical worst-case
- **P99**: 99th percentile, captures extreme cases

### Example Output

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Stage              ┃ Baseline   ┃ Current    ┃ Improvement    ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ full_pipeline      │ 45.23s     │ 31.66s     │ 🟢 30.0%       │
│ pdf_extraction     │ 12.45s     │ 10.12s     │ 🟡 18.7%       │
│ chunking           │ 8.67s      │ 7.23s      │ 🟡 16.6%       │
│ embedding          │ 18.34s     │ 11.45s     │ 🟢 37.6%       │
│ classification     │ 5.77s      │ 2.86s      │ 🟢 50.4%       │
└────────────────────┴────────────┴────────────┴────────────────┘
```

**Analysis:**
- Overall improvement: 30.0% (target achieved ✅)
- Embedding stage: Largest absolute improvement (6.89s saved)
- Classification stage: Highest percentage improvement (50.4%)
- PDF extraction: Potential for further optimization (18.7%)

---

## Troubleshooting

### "No benchmark documents found"

```bash
# Solution: Select documents first
python scripts/select_benchmark_documents.py \
  --snapshot-dir ./staging-snapshots/latest \
  --count 10
```

---

### Database Connection Error

```bash
# Check DATABASE_URL
cat .env | grep DATABASE_URL

# Test connection
psql -h staging-host -U krai_user -d krai_staging -c "SELECT 1;"
```

---

### Missing Baseline

```bash
# Solution: Store baseline first
python scripts/run_benchmark.py --count 10 --baseline
```

---

### Inconsistent Results

```bash
# Check system load
top

# Run multiple iterations
for i in {1..3}; do
  python scripts/run_benchmark.py --count 10 --compare --output run_${i}.json
  sleep 60
done
```

---

## Environment Variables

```bash
# Database connection
DATABASE_URL=postgresql://user:password@host:port/database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=krai_staging
POSTGRES_USER=krai_user
POSTGRES_PASSWORD=your_password

# Document storage
DOCUMENT_STORAGE_PATH=./staging-snapshots/latest
OBJECT_STORAGE_BUCKET=staging-documents
```

---

## Related Documentation

- **[BENCHMARK_GUIDE.md](BENCHMARK_GUIDE.md)** - Comprehensive benchmark workflow and detailed explanations
- **[PERFORMANCE_TESTING_GUIDE.md](PERFORMANCE_TESTING_GUIDE.md)** - Load testing with Locust
- **[PERFORMANCE_OPTIMIZATION.md](../architecture/PERFORMANCE_OPTIMIZATION.md)** - Optimization strategies
- **[PERFORMANCE_FEATURES.md](../PERFORMANCE_FEATURES.md)** - Performance features overview

---

## Quick Tips

1. **Use consistent document sets** for baseline and current measurements
2. **Run benchmarks during low-activity periods** to reduce noise
3. **Perform multiple runs** and average results for stability (±10% variance acceptable)
4. **Document environmental factors** (CPU load, network conditions)
5. **Store baseline before major refactoring** efforts
6. **Use `--verbose` flag** for detailed per-document analysis
7. **Review JSON output files** for detailed metrics
8. **Aim for 30%+ improvement** (green indicator) to validate optimizations

---

*For detailed explanations, staging setup, and troubleshooting, see [BENCHMARK_GUIDE.md](BENCHMARK_GUIDE.md)*
