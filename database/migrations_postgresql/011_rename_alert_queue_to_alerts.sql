-- Migration 011: Rename alert_queue to alerts
-- Alerts are stored in krai_system.alerts per product requirement.
-- Keep krai_system.alert_queue as a view for backward compatibility.
-- Requires migration 008 (alert_queue table) to have been applied first.
--
-- Run each block separately if using statement-by-statement execution.
-- Block 1: Rename (skip if alert_queue is already a view or missing)
-- Block 2: Ensure view exists

-- Block 1
ALTER TABLE krai_system.alert_queue RENAME TO alerts;

-- Block 2
DROP VIEW IF EXISTS krai_system.alert_queue;
CREATE VIEW krai_system.alert_queue AS SELECT * FROM krai_system.alerts;
COMMENT ON TABLE krai_system.alerts IS 'Alert queue for aggregation; recipients/webhooks metadata in alert_configurations';
