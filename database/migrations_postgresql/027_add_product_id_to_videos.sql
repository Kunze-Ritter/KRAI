-- Migration 027: Add product_id to krai_content.videos
-- Enables direct FK from a video to its primary product model

ALTER TABLE krai_content.videos
    ADD COLUMN IF NOT EXISTS product_id uuid REFERENCES krai_core.products(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_videos_product_id ON krai_content.videos(product_id);

-- Backfill: resolve existing related_products text[] → product_id via model_number match
UPDATE krai_content.videos v
SET product_id = p.id
FROM krai_core.products p
WHERE v.product_id IS NULL
  AND cardinality(v.related_products) > 0
  AND p.model_number = v.related_products[1]
  AND p.manufacturer_id = v.manufacturer_id;
