-- Migration 036: Add requires_accessory_id column to product_accessories
-- Allows tracking of accessory dependencies (e.g., FS-539 requires RU-514)

ALTER TABLE krai_core.product_accessories
  ADD COLUMN IF NOT EXISTS requires_accessory_id TEXT REFERENCES krai_core.products(model_number);

CREATE INDEX IF NOT EXISTS idx_product_accessories_requires_accessory
  ON krai_core.product_accessories(requires_accessory_id);
