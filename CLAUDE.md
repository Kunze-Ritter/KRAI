# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KRAI (Knowledge Retrieval and Intelligence) is a multimodal AI document processing pipeline with local-first architecture. It extracts, analyzes, and indexes technical documents through a 16-stage modular pipeline. Built with FastAPI (Python), PostgreSQL+pgvector, MinIO, Ollama, and Laravel/Filament dashboard.

## Common Commands

### Running the Application
```bash
# Start infrastructure services
docker-compose -f docker-compose.simple.yml up -d

# Run backend locally (with --reload for dev)
python -m uvicorn backend.api.app:app --reload --host 0.0.0.0 --port 8000

# Full production stack
docker-compose -f docker-compose.production.yml up --build -d
```

### Running Tests
```bash
# All tests
python -m pytest backend/tests/ -v

# Single test file
python -m pytest backend/tests/integration/test_link_enrichment_e2e.py -v

# By marker (see pytest.ini for full list)
python -m pytest backend/tests/ -v -m "processor and not slow"

# With coverage
python -m pytest backend/tests/ --cov=backend --cov-report=html
```

Test paths configured in `pytest.ini`: `backend/tests`, `tests/processors`, `tests/verification`.

### Environment Setup
```bash
# Windows
.\setup.ps1

# Linux/macOS
./setup.sh
```

Generates secrets, RSA keys, and creates `.env` from `.env.example`.

### Validation
```bash
python scripts/validate_env.py --verbose
```

## Architecture

### 16-Stage Processing Pipeline

Orchestrated by `KRMasterPipeline` (`backend/pipeline/master_pipeline.py`):

UPLOAD → TEXT_EXTRACTION → TABLE_EXTRACTION → SVG_PROCESSING → IMAGE_PROCESSING → VISUAL_EMBEDDING → LINK_EXTRACTION → VIDEO_ENRICHMENT → CHUNK_PREPROCESSING → CLASSIFICATION → METADATA_EXTRACTION → PARTS_EXTRACTION → SERIES_DETECTION → STORAGE → EMBEDDING → SEARCH_INDEXING

Each processor lives in `backend/processors/` and inherits from `BaseProcessor` (`backend/core/base_processor.py`). Processing is invoked via `safe_process()` which provides error handling, retry logic, idempotency checks, and correlation ID tracking.

**Important:** All processors must be registered unconditionally in `master_pipeline.py`'s `self.processors` dict. Processors handle their own enabled/disabled state internally (e.g., `VideoEnrichmentProcessor` checks `ENABLE_BRIGHTCOVE_ENRICHMENT`, `SVGProcessor` always runs). Never conditionally set a processor to `None` — this causes "Processor not available for stage" errors.

### Key Directories
- `backend/api/` - FastAPI app (`app.py`), routes, middleware (auth, rate limiting)
- `backend/processors/` - One file per pipeline stage
- `backend/services/` - DatabaseAdapter, StorageService, AIService, AlertService
- `backend/core/` - BaseProcessor, ProcessingContext/ProcessingResult data models, ErrorClassifier, IdempotencyChecker
- `backend/pipeline/` - Master pipeline orchestrator
- `database/migrations_postgresql/` - 018 SQL migration files applied in order
- `laravel-admin/` - Laravel 12 + Filament 4 dashboard (sole UI)
- `scripts/` - CLI tools, health checks, benchmarks

### Database

PostgreSQL 15+ with pgvector. Multiple `krai_*` schemas (see `DB_QUICK_REFERENCE.md` for current list from live DB).

Core schemas: `krai_core`, `krai_intelligence`, `krai_content`, `krai_parts`, `krai_system`, `krai_users` — plus others (e.g. `krai_pm`, `krai_config`) as introspected from Docker.

All views use `vw_` prefix in `public` schema. Embeddings are in `krai_intelligence.chunks`, not a separate schema.

**Agent rules:** See `AGENTS.md` and `agent.md` (root) — especially schema sync and parallel documentation agent.

**Schema docs (live DB as source of truth):**
- **Semantic/architecture** (what each schema is for, canonical sources, lifecycle): `DATABASE_ARCHITECTURE.md` (hand-maintained) — read this first to understand the DB
- Regenerate after **every** schema change: `python scripts/generate_schema_docs.py`
- Verify before done: `python scripts/generate_schema_docs.py --check`
- Migrations: `python scripts/run_migrations.py --status|--baseline` (tracked in `krai_system.migrations`; `public.migrations` is Laravel's)
- Full reference: `DATABASE_SCHEMA.md` (auto-generated — do not edit by hand)
- Quick + traps: `DB_QUICK_REFERENCE.md` (auto-generated)
- Visual ERD: `schema/krai.dbml` (auto-generated → dbdiagram.io)
- Manual traps only: `schema/column-traps.yaml`
- **Never** use `docs/database/DATABASE_SCHEMA.md` (deprecated redirect)

**Always consult `DATABASE_SCHEMA.md` or `schema/krai.dbml` before writing any DB queries.** Never guess column names or schema locations.

#### Schema documentation sync (MANDATORY)

Whenever you add/change migrations, tables, columns, FKs, or views:

1. Apply migration to local Docker PostgreSQL (`krai-postgres-prod`, DB `krai`)
2. Run `python scripts/generate_schema_docs.py`
3. Update `schema/column-traps.yaml` if new naming traps or JSONB-only fields
4. Run `python scripts/generate_schema_docs.py --check` — must pass before completing the task
5. Commit generated files **together** with migration/code changes

Do **not** hand-edit `schema/krai.dbml`, `DATABASE_SCHEMA.md`, or `DB_QUICK_REFERENCE.md`.

#### Parallel Schema Documentation Agent

For migration or schema work, **start a parallel agent** (Cursor Task / second session) using the prompt in `AGENTS.md` § Parallel Schema Documentation Agent. That agent regenerates docs and runs `--check` while the primary agent implements code.

If parallel agents are unavailable, the **same agent** must run steps 1–4 above — no exceptions.

**Known column name traps** (historically caused bugs — use the correct name on the right):

| Wrong | Correct | Table |
|-------|---------|-------|
| `chunk_text` | `text_chunk` | `krai_intelligence.chunks` |
| `enrichment_error` | `metadata->>'enrichment_error'` | `krai_content.videos` (no column, stored in JSONB) |
| `tags` (on videos) | `metadata->>'tags'` | `krai_content.videos` (no column, stored in JSONB) |

### Error Code Hierarchy

Error codes in `krai_intelligence.error_codes` support hierarchical grouping via two columns (migration 018):
- `parent_code` — references the parent category's `error_code` value (e.g., `13.B9` for `13.B9.Az`)
- `is_category` — `true` for category entries that group child codes (e.g., `13.B9` = "Fuser Area Jams")

**Extraction flow:** `ErrorCodeExtractor` (`backend/processors/error_code_extractor.py`) extracts codes using manufacturer-specific regex patterns from `backend/config/error_code_patterns.json`, derives `parent_code` via `_derive_parent_code()`, and creates category entries via `_create_category_entries()`.

**Hierarchy strategies** (configured per manufacturer in `error_code_patterns.json` → `hierarchy_rules`):
- `first_n_segments` — split by separator, take first N segments (HP: `13.B9.Az` → `13.B9`, Xerox: `541-011` → `541`)
- `prefix_digits` — take first N characters (Konica Minolta: `C-2801` → `C-28`, Ricoh: `SC542` → `SC5`)

**Manufacturers with hierarchy:** HP, Konica Minolta, Ricoh, Xerox, Lexmark, Kyocera, Sharp, Fujifilm.
**Manufacturers without hierarchy** (codes too flat): Canon, Brother, Riso, Toshiba, OKI, Epson.

**HP-specific:** Patterns support alphanumeric segments (`13.B9.Az`, `50.FF.02`). Other manufacturers use numeric codes with optional letter prefixes.

**Key queries:**
```sql
-- All children of a category
SELECT error_code, error_description FROM krai_intelligence.error_codes
WHERE parent_code = '13.B9' ORDER BY error_code;

-- All category entries
SELECT error_code, error_description FROM krai_intelligence.error_codes
WHERE is_category = true;

-- Video linked to error code family (via chunks)
SELECT v.title, v.video_url FROM krai_content.videos v
JOIN krai_intelligence.chunks c ON c.id = ANY(v.related_chunks)
JOIN krai_intelligence.error_codes ec ON ec.chunk_id = c.id
WHERE ec.parent_code = '13.B9' OR ec.error_code = '13.B9';
```

**Data models:**
- `ExtractedErrorCode` (`backend/processors/models.py`) — extraction-time model with `parent_code` and `is_category` fields
- `ErrorCodeModel` (`backend/core/data_models.py`) — DB persistence model, mapped in `metadata_processor_ai.py`

### Services
- **Ollama** (local LLM): `nomic-embed-text` for embeddings, `llava` for vision
- **MinIO**: S3-compatible object storage (buckets: documents, images)
- **Laravel Dashboard**: http://localhost:80 — document management, pipeline monitoring, error handling

## Critical Development Rules

These rules come from `.windsurf/rules/project-rules.md` and must be followed:

### Processing & Error Handling
- Always use `BaseProcessor.safe_process()` — never implement custom retry loops
- Classify errors as transient (5xx, 429, ConnectionError, TimeoutError → retry) or permanent (4xx, ValidationError → no retry) using `ErrorClassifier`
- Check `stage_completion_markers` before processing (idempotency). Compute SHA-256 data hash for duplicate detection
- Use PostgreSQL advisory locks in **try-finally** blocks to prevent concurrent retries
- Queue alerts via `AlertService.queue_alert()` — never send notifications directly
- Include correlation IDs in all log entries: format `req_{uuid}.stage_{name}.retry_{n}`
- Never use `time.sleep()` for retry delays; `safe_process()` handles hybrid sync/async retries

### Database
- Live PostgreSQL is the source of truth; **always** run `generate_schema_docs.py` + `--check` after schema changes (see `AGENTS.md`)
- For migrations: spawn parallel **Schema Documentation Agent** per `AGENTS.md`, or run doc sync yourself before done
- Never hand-edit `krai.dbml` / `DATABASE_SCHEMA.md` / `DB_QUICK_REFERENCE.md`
- Always read `DATABASE_SCHEMA.md` / `schema/krai.dbml` before making assumptions about tables/columns
- Manufacturer names must go through mapping (e.g., `HP Inc.` → `Hewlett Packard`). See `ManufacturerVerificationService`
- Migrations go in `database/migrations_postgresql/` as sequential SQL files (applied to DB, then regenerate docs)

### Code Style
- Raise `ProcessingError` (from `backend/processors/exceptions.py`) with descriptive messages, processor name, and original exception
- Catch specific exception types, not generic `Exception`
- Never run benchmarks in production — use staging (`docker-compose.staging.yml`)

### External Systems & Data Access
- **READ-ONLY MODE ONLY**: Never write to external systems (Radix, Docuware, etc.). Only GET requests allowed.
- No INSERT, UPDATE, DELETE, PATCH, or POST mutations to external APIs — data flows inbound only
- All external data imports must be idempotent (duplicate detection via ID or hash)
- Validate external data before inserting into KRAI database (schema conformance, manufacturer mapping, etc.)
- Log all external data source, import count, and skip count for audit trail

### Commit Messages
Format: `[Component] What was changed`
Example: `[Pipeline] Add idempotency checks to ChunkPreprocessor`

---

## Coding Standards

This project uses automated code quality tools. All tools are configured in `pyproject.toml`:

### Running Locally
```bash
# Install pre-commit hooks (run once)
pre-commit install

# Run all linters manually
pre-commit run --all-files

# Or individually:
ruff check backend/
ruff format backend/
black backend/
mypy backend/
bandit -r backend/
```

### Tools Configured
- **ruff**: Fast linting + import sorting
- **black**: Code formatting
- **mypy**: Static type checking
- **bandit**: Security checks
- **pre-commit**: Git hooks (auto-run on commit)

---

## Recent Refactorings (2026-03)

### Import Optimization
- Lazy loading of `PostgreSQLAdapter` in `database_factory.py`
- Import time reduced: 34.8s → 0.2s (167x faster!)

### Module Splitting
Large processor files have been split for better maintainability:

| File | Modules |
|------|---------|
| `error_code_extractor.py` | `error_code_patterns.py`, `error_code_hierarchy.py` |
| `embedding_processor.py` | `embedding_config.py` |
| `image_processor.py` | `image_config.py` |

### New Files
- `backend/pipeline/service_locator.py` - Lazy service loading
- `AGENTS.md` / `agent.md` - Agent rules (schema sync, parallel doc agent)
- `DB_QUICK_REFERENCE.md` - Compact database reference (auto-generated)
- `schema/krai.dbml` - Visual ERD (auto-generated from live DB)
- `schema/column-traps.yaml` - Known column/query traps (manual)
- `scripts/generate_schema_docs.py` - Regenerate schema docs from live Docker DB
- `MASTER-TODO.md` - Project task overview
