# Database Schema Changes

## 2026-02-15: Brightcove Video Enrichment Columns (Migration 017)

### Changes Made
- Added `tags` (`text[]`) to `krai_content.videos`
- Added `enrichment_error` (`text`) to `krai_content.videos`
- Added partial index `idx_videos_enrichment_pending` for queued Brightcove enrichment records
- Removed unused `duration_seconds` column if present from duplicate migration variant
- Registered migration entry `017_video_enrichment_columns` in `krai_system.migrations`

## 2026-02-03: Alert Service Schema Fix

### Changes Made
- Recreated `krai_system.alert_configurations` table with proper schema
- Recreated `krai_system.alert_queue` table with missing columns
- Added test alert configuration

### Tables Modified

#### krai_system.alert_configurations
**Previous Issues:**
- Missing `id` column (UUID primary key)
- Missing `description` column
- Incorrect column types

**New Schema:**
```sql
CREATE TABLE krai_system.alert_configurations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name character varying(100) NOT NULL UNIQUE,
    description text,
    is_enabled boolean DEFAULT true NOT NULL,
    error_types character varying(50)[],
    stages character varying(50)[],
    severity_threshold character varying(20) DEFAULT 'medium' NOT NULL,
    error_count_threshold int4 DEFAULT 5 NOT NULL,
    time_window_minutes int4 DEFAULT 15 NOT NULL,
    aggregation_window_minutes int4 DEFAULT 5 NOT NULL,
    email_recipients text[],
    slack_webhooks text[],
    created_by uuid,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

#### krai_system.alert_queue
**Previous Issues:**
- Missing `status` column for alert tracking
- Missing `aggregation_count` column

**New Schema:**
```sql
CREATE TABLE krai_system.alert_queue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type character varying(50) NOT NULL,
    severity character varying(20) NOT NULL,
    message text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb,
    source_service character varying(100),
    correlation_id character varying(100),
    aggregation_key character varying(200),
    aggregation_count int4 DEFAULT 1 NOT NULL,
    first_occurrence timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_occurrence timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status character varying(20) DEFAULT 'pending' NOT NULL,
    sent_at timestamp,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

### Test Data Added
```sql
INSERT INTO krai_system.alert_configurations (
    rule_name,
    description,
    is_enabled,
    error_types,
    stages,
    severity_threshold,
    error_count_threshold,
    time_window_minutes,
    aggregation_window_minutes,
    email_recipients,
    slack_webhooks
) VALUES (
    'default_error_alert',
    'Default alert for any processing errors',
    true,
    ARRAY['database', 'api', 'validation'],
    ARRAY['classification', 'extraction', 'embedding'],
    'medium',
    3,
    15,
    5,
    ARRAY['admin@example.com'],
    ARRAY[]::text[]
);
```

### Impact
- Alert Service now fully functional
- Alert aggregation worker can process alerts
- Email notifications working
- No more startup errors related to missing columns

### Verification
```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'krai_system'
AND table_name IN ('alert_configurations', 'alert_queue');

-- Check test configuration
SELECT rule_name, is_enabled FROM krai_system.alert_configurations;
```
