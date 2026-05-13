# Performance Optimization & Instrumentation

## Goals

- Page load < 2.5s for dashboard.
- < 10 backend API calls per page load (with batching/dedup).
- Detect regressions via profiling and benchmarks.

## Components

1. **Request dedup + batching** (MonitoringService)
   - Livewire widgets share in-flight requests and reuse batch responses.

2. **Laravel Telescope** (dev/test only)
   - QueryWatcher (slow >100ms), CacheWatcher, RequestWatcher enabled.
   - Access via `/telescope` when `APP_ENV=local|testing`.

3. **PerformanceProfiler middleware**
   - Adds `X-Execution-Time`, `X-Memory-Usage`, `X-Query-Count` headers.
   - Logs slow requests >1s with query count and peak memory.

4. **krai:benchmark command**
   - `php artisan krai:benchmark --iterations=10`
   - Benchmarks key dashboard endpoints, prints min/max/avg/p50/p90 in ms.

## Setup (local/test)

```bash
composer install
php artisan telescope:install
php artisan migrate
php artisan telescope:publish
```

## How to Use

- **Browser DevTools**: inspect response headers for execution time/memory/query count.
- **Telescope**: open `/telescope` to review slow queries, cache hits/misses, requests.
- **CLI benchmark**: run `php artisan krai:benchmark --iterations=10` before/after changes; keep results in PR notes.

## Rollback

- Remove `laravel/telescope` from `require-dev`, delete TelescopeServiceProvider registration, and remove profiler middleware wiring in `bootstrap/app.php`.
- Drop Telescope tables via migration rollback if needed.

## Notes

- Telescope is restricted to local/testing environments; do not enable in production.
- Middleware is global; headers are safe for clients and useful in staging/prod.
