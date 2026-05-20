-- Migration 040: Drop unused empty schemas and the dead duplicate chunks table
-- Purpose: Structure consolidation. These 5 schemas are entirely empty (0 rows,
-- no incoming FKs, no backend code references — only stale docs) and were never
-- used in production. krai_content.chunks is an empty duplicate of the real
-- krai_intelligence.chunks (20k+ rows); code that queried the dead table has been
-- repointed to krai_intelligence.chunks.
-- Created: 2026-05-20
--
-- Preserved (NOT touched): krai_core (manufacturers/products/series),
-- krai_content (videos/images/links), krai_intelligence, krai_system, krai_pm,
-- krai_parts, krai_users, and Laravel's public.migrations.

DROP SCHEMA IF EXISTS krai_analytics CASCADE;
DROP SCHEMA IF EXISTS krai_config CASCADE;
DROP SCHEMA IF EXISTS krai_integrations CASCADE;
DROP SCHEMA IF EXISTS krai_ml CASCADE;
DROP SCHEMA IF EXISTS krai_service CASCADE;

-- Dead duplicate of krai_intelligence.chunks (the canonical chunk store)
DROP TABLE IF EXISTS krai_content.chunks CASCADE;
