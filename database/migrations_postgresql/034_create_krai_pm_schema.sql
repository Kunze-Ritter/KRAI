-- Migration 019: Create krai_pm Schema and Base Tables
-- Purpose: Establish the Predictive Maintenance module with harmonized service tickets,
--          part lifetimes, device lifecycle tracking, predictions, and entity mapping.
-- Created: 2026-05-19

CREATE SCHEMA IF NOT EXISTS krai_pm;

-- Harmonisierte Servicetickets aus allen Quellen
CREATE TABLE krai_pm.service_tickets (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_system         varchar(50)  NOT NULL,   -- 'radix' | 'docuform' | 'km_anfragen_of' | 'km_anfragen_pp' | 'km_anfragen_sol'
  source_ticket_id      varchar(200) NOT NULL,
  manufacturer_id       uuid REFERENCES krai_core.manufacturers(id),
  product_id            uuid REFERENCES krai_core.products(id),
  model_string_raw      text,                     -- Roh-Modellangabe wenn nicht gemappt
  created_at_source     timestamptz,              -- Erstellungsdatum im Quellsystem
  problem_short         text,
  problem_long          text,
  solution_text         text,
  error_codes           text[],                   -- extrahierte Fehlercodes
  replaced_parts        text[],                   -- erkannte Ersatzteilnummern
  replaced_part_categories text[],                -- normalisierte Kategorien: 'toner', 'drum', 'fuser', 'board', ...
  repair_time_minutes   int,
  ticket_embedding      vector(768),              -- für semantische Ähnlichkeitssuche
  metadata              jsonb,
  ingested_at           timestamptz DEFAULT now(),
  UNIQUE(source_system, source_ticket_id)
);
CREATE INDEX idx_service_tickets_embedding ON krai_pm.service_tickets USING hnsw (ticket_embedding vector_cosine_ops);
CREATE INDEX idx_service_tickets_manufacturer_date ON krai_pm.service_tickets (manufacturer_id, created_at_source DESC);
CREATE INDEX idx_service_tickets_error_codes ON krai_pm.service_tickets USING gin (error_codes);

-- Hersteller-Sollwerte für Verbrauchsmaterial/Ersatzteile
CREATE TABLE krai_pm.part_lifetimes (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  manufacturer_id       uuid NOT NULL REFERENCES krai_core.manufacturers(id),
  product_id            uuid REFERENCES krai_core.products(id),     -- nullable wenn modellübergreifend
  part_category         varchar(50)  NOT NULL,                       -- 'toner', 'drum', 'fuser', 'transfer_belt', 'pickup_roller', ...
  part_number           varchar(100),
  nominal_lifetime_pages int,                                        -- in tatsächlichen Seiten (NICHT in 1000er)
  color_channel         varchar(10),                                  -- 'K', 'C', 'M', 'Y', null
  source                varchar(50)  NOT NULL,                        -- 'km_excel_v1.18', 'oem_manual', ...
  metadata              jsonb,
  ingested_at           timestamptz DEFAULT now()
);
CREATE INDEX idx_part_lifetimes_lookup ON krai_pm.part_lifetimes (manufacturer_id, product_id, part_category);

-- Zählerstände und Geräte-Historie aus Docuform
CREATE TABLE krai_pm.device_lifecycle (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_serial_hash    varchar(64)  NOT NULL,    -- SHA-256 der Seriennummer (Pseudonymisierung)
  product_id            uuid REFERENCES krai_core.products(id),
  counter_total         bigint,
  counter_color         bigint,
  counter_bw            bigint,
  measured_at           timestamptz NOT NULL,
  toner_levels          jsonb,                     -- {"K": 75, "C": 60, ...}
  maintenance_events    jsonb,                     -- [{"date": "...", "part_category": "fuser", "action": "replace"}]
  metadata              jsonb,
  ingested_at           timestamptz DEFAULT now()
);
CREATE INDEX idx_device_lifecycle_serial_date ON krai_pm.device_lifecycle (device_serial_hash, measured_at DESC);

-- Modell-Outputs (für Monitoring, Audit, Backtest)
CREATE TABLE krai_pm.predictions (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_serial_hash    varchar(64),
  prediction_type       varchar(50)  NOT NULL,    -- 'wartungsintervall' | 'anomalie' | 'remaining_useful_life'
  target_part_category  varchar(50),
  predicted_event_date  date,
  predicted_remaining_pages int,
  risk_score            float,                     -- 0..1 für Anomaliedetektion
  confidence            float,                     -- 0..1
  model_name            varchar(100) NOT NULL,
  model_version         varchar(50)  NOT NULL,
  mlflow_run_id         varchar(100),
  created_at            timestamptz DEFAULT now(),
  ground_truth_event_date date,                    -- für Backtesting nachträglich gesetzt
  ground_truth_set_at   timestamptz
);
CREATE INDEX idx_predictions_device_type ON krai_pm.predictions (device_serial_hash, prediction_type, created_at DESC);
CREATE INDEX idx_predictions_model ON krai_pm.predictions (model_name, model_version);

-- Pseudonymisierungs-Mapping (zugriffsbeschränkt)
CREATE TABLE krai_pm.entity_mapping (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type           varchar(50)  NOT NULL,    -- 'device_serial' | 'customer' | 'technician'
  raw_value             text         NOT NULL,
  hash_value            varchar(64)  NOT NULL,
  created_at            timestamptz DEFAULT now(),
  UNIQUE(entity_type, hash_value)
);

-- Schema comment for documentation
COMMENT ON SCHEMA krai_pm IS 'Predictive Maintenance module: service tickets, part lifetimes, device tracking, and predictions.';
COMMENT ON TABLE krai_pm.service_tickets IS 'Harmonized service tickets from multiple sources (Radix, Docuform, KM Excel), with extracted error codes and part replacements.';
COMMENT ON TABLE krai_pm.part_lifetimes IS 'OEM nominal lifetimes for consumables (toner, drum, fuser, etc.) per manufacturer/product/part.';
COMMENT ON TABLE krai_pm.device_lifecycle IS 'Device counter readings and maintenance events from Docuform, pseudonymized by device serial hash.';
COMMENT ON TABLE krai_pm.predictions IS 'Model outputs for predictive maintenance: maintenance intervals and anomaly detection scores.';
COMMENT ON TABLE krai_pm.entity_mapping IS 'Pseudonymization mapping (device serial hash, customer, technician) – access restricted.';
