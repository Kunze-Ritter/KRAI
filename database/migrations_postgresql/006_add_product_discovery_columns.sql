-- Migration 006: Add Product Discovery Columns
-- Adds specifications, urls, metadata, and OEM columns to products table
-- Required for ManufacturerVerificationService.save_to_db functionality

-- Add JSONB columns for product discovery data
ALTER TABLE krai_core.products
ADD COLUMN IF NOT EXISTS specifications JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS pricing JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS lifecycle JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS urls JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Add OEM relationship columns
ALTER TABLE krai_core.products
ADD COLUMN IF NOT EXISTS oem_manufacturer VARCHAR(100),
ADD COLUMN IF NOT EXISTS oem_relationship_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS oem_notes TEXT;

-- Add product codes for catalog integration
ALTER TABLE krai_core.products
ADD COLUMN IF NOT EXISTS article_code VARCHAR(50);

-- Update product_type default to match current usage
ALTER TABLE krai_core.products
ALTER COLUMN product_type SET DEFAULT 'laser_printer';

-- Create index on model_number for faster product discovery lookups
CREATE INDEX IF NOT EXISTS idx_products_model_number ON krai_core.products(model_number);

-- Create index on JSONB columns for faster queries
CREATE INDEX IF NOT EXISTS idx_products_specifications ON krai_core.products USING GIN (specifications);
CREATE INDEX IF NOT EXISTS idx_products_urls ON krai_core.products USING GIN (urls);
CREATE INDEX IF NOT EXISTS idx_products_metadata ON krai_core.products USING GIN (metadata);

-- Comment
COMMENT ON COLUMN krai_core.products.specifications IS 'Product specifications extracted from web or documents (JSONB)';
COMMENT ON COLUMN krai_core.products.urls IS 'Product page URLs and related links (JSONB)';
COMMENT ON COLUMN krai_core.products.metadata IS 'Additional product metadata from discovery process (JSONB)';
COMMENT ON COLUMN krai_core.products.oem_manufacturer IS 'OEM manufacturer name if product is rebadged';
COMMENT ON COLUMN krai_core.products.oem_relationship_type IS 'Type of OEM relationship (rebadge, white_label, etc.)';
