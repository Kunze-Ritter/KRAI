-- Migration 009: SVG dual storage support
-- Description: Preserve original SVG assets alongside optional PNG derivatives
-- Created: 2026-02-12

ALTER TABLE krai_content.images
    ADD COLUMN IF NOT EXISTS svg_storage_url TEXT,
    ADD COLUMN IF NOT EXISTS original_svg_content TEXT,
    ADD COLUMN IF NOT EXISTS is_vector_graphic BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS has_png_derivative BOOLEAN DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_images_is_vector_graphic
    ON krai_content.images(is_vector_graphic)
    WHERE is_vector_graphic = true;

COMMENT ON COLUMN krai_content.images.svg_storage_url IS
    'MinIO URL for original SVG file';

COMMENT ON COLUMN krai_content.images.original_svg_content IS
    'Optional inline SVG content for small files (<100KB)';

COMMENT ON COLUMN krai_content.images.is_vector_graphic IS
    'Flag to identify vector graphic assets';

COMMENT ON COLUMN krai_content.images.has_png_derivative IS
    'Whether a PNG derivative exists for SVG/vector assets';
