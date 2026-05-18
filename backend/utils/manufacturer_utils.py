"""
Manufacturer Utilities
======================
Centralized manufacturer, product, and series management functions
Auto-creates entities when detected but not in database
"""

import logging
from uuid import UUID

from services.database_adapter import DatabaseAdapter
from services.database_factory import create_database_adapter

logger = logging.getLogger(__name__)

# Module-level adapter instance (lazy initialization)
_adapter: DatabaseAdapter | None = None


async def _get_adapter() -> DatabaseAdapter:
    """Get or create the module-level database adapter."""
    global _adapter
    if _adapter is None:
        _adapter = create_database_adapter()
        await _adapter.connect()
    return _adapter


async def ensure_manufacturer_exists(manufacturer_name: str, adapter: DatabaseAdapter | None = None) -> UUID | None:
    """
    Ensure manufacturer exists in database, create if needed

    This function is used across all stages to auto-create manufacturers
    when they are detected but not yet in the database.

    Args:
        manufacturer_name: Name of manufacturer (e.g., "HP", "Lexmark", "Konica Minolta")

    Returns:
        manufacturer_id (UUID) if found/created, None if failed

    Raises:
        Exception: If manufacturer cannot be created
    """
    if not manufacturer_name or manufacturer_name == "AUTO":
        return None

    try:
        # Get or use provided adapter
        if adapter is None:
            adapter = await _get_adapter()

        # 1. Try exact match first
        result = await adapter.fetch_one(
            "SELECT id, name FROM krai_core.manufacturers WHERE name = $1 LIMIT 1", [manufacturer_name]
        )

        if result:
            manufacturer_id = result["id"]
            logger.debug(f"✅ Found manufacturer: {manufacturer_name} (ID: {manufacturer_id})")
            return manufacturer_id

        # 2. Try case-insensitive match
        result = await adapter.fetch_one(
            "SELECT id, name FROM krai_core.manufacturers WHERE LOWER(name) = LOWER($1) LIMIT 1", [manufacturer_name]
        )

        if result:
            manufacturer_id = result["id"]
            logger.debug(f"✅ Found manufacturer (ilike): {result['name']} (ID: {manufacturer_id})")
            return manufacturer_id

        # 3. Try partial match
        result = await adapter.fetch_one(
            "SELECT id, name FROM krai_core.manufacturers WHERE LOWER(name) LIKE LOWER($1) LIMIT 1",
            [f"%{manufacturer_name}%"],
        )

        if result:
            manufacturer_id = result["id"]
            logger.debug(f"✅ Found manufacturer (partial): {result['name']} (ID: {manufacturer_id})")
            return manufacturer_id

        # 4. Manufacturer not found - create new entry
        logger.info(f"🔨 Creating new manufacturer: {manufacturer_name}")

        create_result = await adapter.fetch_one(
            "INSERT INTO krai_core.manufacturers (name) VALUES ($1) RETURNING id", [manufacturer_name]
        )

        if create_result:
            manufacturer_id = create_result["id"]
            logger.info(f"✅ Created manufacturer: {manufacturer_name} (ID: {manufacturer_id})")
            return manufacturer_id
        logger.error(f"❌ Failed to create manufacturer: {manufacturer_name}")
        return None

    except Exception as e:
        logger.error(f"❌ Error ensuring manufacturer exists: {e}")
        return None


async def detect_manufacturer_from_domain(domain: str, adapter: DatabaseAdapter | None = None) -> UUID | None:
    """
    Detect manufacturer from URL domain and ensure it exists

    Args:
        domain: Domain name (e.g., 'publications.lexmark.com')

    Returns:
        manufacturer_id (UUID) or None
    """
    # Domain to manufacturer mapping
    domain_mapping = {
        "lexmark.com": "Lexmark",
        "publications.lexmark.com": "Lexmark",
        "hp.com": "HP",
        "support.hp.com": "HP",
        "kyoceradocumentsolutions.com": "Kyocera",
        "kyocera.com": "Kyocera",
        "utax.com": "UTAX",
        "utax.de": "UTAX",
        "ricoh.com": "Ricoh",
        "brother.com": "Brother",
        "canon.com": "Canon",
        "epson.com": "Epson",
        "xerox.com": "Xerox",
        "konica-minolta.com": "Konica Minolta",
        "konicaminolta.com": "Konica Minolta",
        "sharp.com": "Sharp",
        "toshiba.com": "Toshiba",
        "oki.com": "OKI",
        "samsung.com": "Samsung",
        "dell.com": "Dell",
    }

    domain_lower = domain.lower()

    # Check for domain match
    for domain_key, manufacturer_name in domain_mapping.items():
        if domain_key in domain_lower:
            logger.info(f"🔍 Domain matched: {domain_key} → {manufacturer_name}")
            return await ensure_manufacturer_exists(manufacturer_name, adapter)

    logger.debug(f"ℹ️ No manufacturer detected from domain: {domain}")
    return None


async def ensure_series_exists(
    series_name: str, manufacturer_id: UUID, adapter: DatabaseAdapter | None = None
) -> UUID | None:
    """
    Ensure product series exists in database, create if needed

    Args:
        series_name: Name of series (e.g., "LaserJet Pro", "CS900")
        manufacturer_id: UUID of manufacturer

    Returns:
        series_id (UUID) or None
    """
    if not series_name or not manufacturer_id:
        return None

    try:
        # Get or use provided adapter
        if adapter is None:
            adapter = await _get_adapter()

        # 1. Try to find existing series
        result = await adapter.fetch_one(
            "SELECT id, series_name FROM krai_core.product_series WHERE manufacturer_id = $1 AND LOWER(series_name) LIKE LOWER($2) LIMIT 1",
            [str(manufacturer_id), series_name],
        )

        if result:
            series_id = result["id"]
            logger.debug(f"✅ Found series: {series_name} (ID: {series_id})")
            return series_id

        # 2. Series not found - create new entry
        logger.info(f"🔨 Creating new series: {series_name}")

        create_result = await adapter.fetch_one(
            "INSERT INTO krai_core.product_series (series_name, manufacturer_id) VALUES ($1, $2) RETURNING id",
            [series_name, str(manufacturer_id)],
        )

        if create_result:
            series_id = create_result["id"]
            logger.info(f"✅ Created series: {series_name} (ID: {series_id})")
            return series_id
        logger.error(f"❌ Failed to create series: {series_name}")
        return None

    except Exception as e:
        logger.error(f"❌ Error ensuring series exists: {e}")
        return None


async def ensure_product_exists(
    model_name: str, manufacturer_id: UUID, series_id: UUID | None = None, adapter: DatabaseAdapter | None = None
) -> UUID | None:
    """
    Ensure product exists in database, create if needed

    Args:
        model_name: Model name (e.g., "CS943", "CX94X")
        manufacturer_id: UUID of manufacturer
        series_id: Optional UUID of series

    Returns:
        product_id (UUID) or None
    """
    if not model_name or not manufacturer_id:
        return None

    try:
        # Get or use provided adapter
        if adapter is None:
            adapter = await _get_adapter()

        # 1. Try to find existing product
        result = await adapter.fetch_one(
            "SELECT id, model_number FROM krai_core.products WHERE manufacturer_id = $1 AND LOWER(model_number) LIKE LOWER($2) LIMIT 1",
            [str(manufacturer_id), model_name],
        )

        if result:
            product_id = result["id"]
            logger.debug(f"✅ Found product: {model_name} (ID: {product_id})")
            return product_id

        # 2. Product not found - create new entry
        logger.info(f"🔨 Creating new product: {model_name}")

        if series_id:
            create_result = await adapter.fetch_one(
                "INSERT INTO krai_core.products (model_number, manufacturer_id, series_id) VALUES ($1, $2, $3) RETURNING id",
                [model_name, str(manufacturer_id), str(series_id)],
            )
        else:
            create_result = await adapter.fetch_one(
                "INSERT INTO krai_core.products (model_number, manufacturer_id) VALUES ($1, $2) RETURNING id",
                [model_name, str(manufacturer_id)],
            )

        if create_result:
            product_id = create_result["id"]
            logger.info(f"✅ Created product: {model_name} (ID: {product_id})")
            return product_id
        logger.error(f"❌ Failed to create product: {model_name}")
        return None

    except Exception as e:
        logger.error(f"❌ Error ensuring product exists: {e}")
        return None


async def link_video_to_products(
    video_id: UUID, model_names: list[str], manufacturer_id: UUID, adapter: DatabaseAdapter | None = None
) -> list[UUID]:
    """
    Link video to products, auto-creating products if needed

    Args:
        video_id: UUID of video
        model_names: List of model names (e.g., ['CS943', 'CX94X'])
        manufacturer_id: UUID of manufacturer

    Returns:
        List of product IDs that were linked
    """
    if not video_id or not model_names or not manufacturer_id:
        return []

    # Get or use provided adapter
    if adapter is None:
        adapter = await _get_adapter()

    linked_products = []

    for model_name in model_names:
        try:
            # Ensure product exists
            product_id = await ensure_product_exists(model_name, manufacturer_id, None, adapter)

            if product_id:
                # Check if link already exists
                existing = await adapter.fetch_one(
                    "SELECT id FROM krai_content.video_products WHERE video_id = $1 AND product_id = $2 LIMIT 1",
                    [str(video_id), str(product_id)],
                )

                if not existing:
                    # Create link
                    await adapter.execute_query(
                        "INSERT INTO krai_content.video_products (video_id, product_id) VALUES ($1, $2)",
                        [str(video_id), str(product_id)],
                    )

                    logger.info(f"🔗 Linked video to product: {model_name}")

                linked_products.append(product_id)

        except Exception as e:
            logger.error(f"❌ Error linking video to product {model_name}: {e}")

    return linked_products
