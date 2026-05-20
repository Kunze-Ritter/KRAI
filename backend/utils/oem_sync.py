"""
OEM Relationships Sync Utility
===============================

Syncs OEM mappings from oem_mappings.py to the PostgreSQL database.
Also updates products table with OEM information.

Usage:
    from backend.utils.oem_sync import sync_oem_relationships_to_db

    await sync_oem_relationships_to_db()
"""

import json
import logging
from uuid import UUID

from backend.config.oem_mappings import OEM_MAPPINGS, get_oem_info, get_oem_manufacturer
from backend.services.database_adapter import DatabaseAdapter
from backend.services.database_factory import create_database_adapter

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


async def sync_oem_relationships_to_db(adapter: DatabaseAdapter | None = None) -> dict[str, int]:
    """
    Sync OEM mappings from oem_mappings.py to database

    Returns:
        Dictionary with sync statistics
    """
    stats = {"total_mappings": len(OEM_MAPPINGS), "inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

    logger.info(f"Syncing {stats['total_mappings']} OEM mappings to database...")

    # Get or use provided adapter
    if adapter is None:
        adapter = await _get_adapter()

    for (brand, pattern), mapping in OEM_MAPPINGS.items():
        try:
            # Check if mapping already exists
            existing = await adapter.fetch_one(
                "SELECT id FROM krai_core.oem_relationships WHERE brand_manufacturer = $1 AND brand_series_pattern = $2 AND oem_manufacturer = $3",
                [brand, pattern, mapping["oem_manufacturer"]],
            )

            applies_to = json.dumps(mapping.get("applies_to", ["error_codes", "parts"]))
            notes = mapping.get("notes", "")

            if existing:
                # Update existing
                await adapter.execute_query(
                    """UPDATE krai_core.oem_relationships
                       SET relationship_type = $1, applies_to = $2::jsonb, notes = $3, confidence = $4, source = $5, verified = $6
                       WHERE id = $7""",
                    ["engine", applies_to, notes, 1.0, "oem_mappings.py", True, existing["id"]],
                )
                stats["updated"] += 1
                logger.debug(f"Updated: {brand} {pattern} → {mapping['oem_manufacturer']}")
            else:
                # Insert new
                await adapter.execute_query(
                    """INSERT INTO krai_core.oem_relationships
                       (brand_manufacturer, brand_series_pattern, oem_manufacturer, relationship_type, applies_to, notes, confidence, source, verified)
                       VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9)""",
                    [
                        brand,
                        pattern,
                        mapping["oem_manufacturer"],
                        "engine",
                        applies_to,
                        notes,
                        1.0,
                        "oem_mappings.py",
                        True,
                    ],
                )
                stats["inserted"] += 1
                logger.debug(f"Inserted: {brand} {pattern} → {mapping['oem_manufacturer']}")

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error syncing {brand} {pattern}: {e}")

    logger.info(f"Sync complete: {stats['inserted']} inserted, {stats['updated']} updated, {stats['errors']} errors")
    return stats


async def update_product_oem_info(
    product_id: UUID, manufacturer: str, model_or_series: str, adapter: DatabaseAdapter | None = None
) -> bool:
    """
    Update a product with OEM information

    Args:
        product_id: UUID of product to update
        manufacturer: Brand manufacturer name
        model_or_series: Model or series name

    Returns:
        True if updated, False otherwise
    """
    try:
        # Get OEM info
        oem_info = get_oem_info(manufacturer, model_or_series)

        if not oem_info:
            # No OEM relationship
            return False

        # Get or use provided adapter
        if adapter is None:
            adapter = await _get_adapter()

        # Update product with OEM info
        await adapter.execute_query(
            "UPDATE krai_core.products SET oem_manufacturer = $1, oem_relationship_type = $2, oem_notes = $3 WHERE id = $4",
            [oem_info["oem_manufacturer"], "engine", oem_info["notes"], str(product_id)],
        )

        logger.info(f"✅ Updated product {product_id} with OEM: {oem_info['oem_manufacturer']}")
        return True

    except Exception as e:
        logger.error(f"Error updating product {product_id} OEM info: {e}")
        return False


async def batch_update_products_oem_info(limit: int = 1000, adapter: DatabaseAdapter | None = None) -> dict[str, int]:
    """
    Batch update all products with OEM information

    Args:
        limit: Maximum number of products to process

    Returns:
        Dictionary with update statistics
    """
    stats = {"total_products": 0, "updated": 0, "no_oem": 0, "errors": 0}

    logger.info("Batch updating products with OEM information...")

    try:
        # Get or use provided adapter
        if adapter is None:
            adapter = await _get_adapter()

        # Get all products
        products = await adapter.fetch_all(
            "SELECT p.id, p.manufacturer_id, p.model_number, s.series_name FROM krai_core.products p LEFT JOIN krai_core.product_series s ON p.series_id = s.id LIMIT $1",
            [limit],
        )

        if not products:
            logger.info("No products found")
            return stats

        stats["total_products"] = len(products)

        # Get manufacturer names
        manufacturer_ids = list(set(p["manufacturer_id"] for p in products if p.get("manufacturer_id")))
        manufacturers = {}

        for mfr_id in manufacturer_ids:
            mfr = await adapter.fetch_one("SELECT id, name FROM krai_core.manufacturers WHERE id = $1", [mfr_id])
            if mfr:
                manufacturers[mfr_id] = mfr["name"]

        # Update each product
        for product in products:
            try:
                manufacturer_name = manufacturers.get(product.get("manufacturer_id"))
                if not manufacturer_name:
                    stats["no_oem"] += 1
                    continue

                model_or_series = product.get("series_name") or product.get("model_number")
                if not model_or_series:
                    stats["no_oem"] += 1
                    continue

                # Update OEM info
                if await update_product_oem_info(product["id"], manufacturer_name, model_or_series, adapter):
                    stats["updated"] += 1
                else:
                    stats["no_oem"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error processing product {product.get('id')}: {e}")

        logger.info(f"Batch update complete: {stats['updated']}/{stats['total_products']} products updated")

    except Exception as e:
        logger.error(f"Error in batch update: {e}")
        stats["errors"] += 1

    return stats


def get_oem_equivalent_manufacturers(manufacturer: str, model_or_series: str) -> list[str]:
    """
    Get list of equivalent manufacturers for cross-OEM search

    Args:
        manufacturer: Brand manufacturer name
        model_or_series: Model or series name

    Returns:
        List of manufacturer names to search (includes original + OEM)

    Example:
        >>> get_oem_equivalent_manufacturers("Konica Minolta", "5000i")
        ["Konica Minolta", "Brother"]
    """
    manufacturers = [manufacturer]  # Always include original

    # Get OEM manufacturer
    oem = get_oem_manufacturer(manufacturer, model_or_series, for_purpose="error_codes")
    if oem and oem != manufacturer:
        manufacturers.append(oem)

    return manufacturers


def expand_search_query_with_oem(manufacturer: str, model_or_series: str, search_query: str) -> list[str]:
    """
    Expand search query to include OEM equivalents

    Args:
        manufacturer: Brand manufacturer name
        model_or_series: Model or series name
        search_query: Original search query

    Returns:
        List of expanded search queries

    Example:
        >>> expand_search_query_with_oem("Konica Minolta", "5000i", "error C4080")
        [
            "Konica Minolta 5000i error C4080",
            "Brother 5000i error C4080",
            "Brother error C4080"
        ]
    """
    queries = [search_query]  # Original query

    # Get OEM manufacturer
    oem = get_oem_manufacturer(manufacturer, model_or_series, for_purpose="error_codes")

    if oem and oem != manufacturer:
        # Add OEM-specific queries
        queries.append(search_query.replace(manufacturer, oem))

        # Add query without model (just OEM + search terms)
        if model_or_series in search_query:
            oem_query = search_query.replace(manufacturer, oem).replace(model_or_series, "").strip()
            queries.append(oem_query)

    return queries


if __name__ == "__main__":
    # Test/demo mode
    print("=" * 80)
    print("OEM Relationships Sync Utility")
    print("=" * 80)

    # Test get_oem_equivalent_manufacturers
    test_cases = [
        ("Konica Minolta", "5000i"),
        ("Lexmark", "CS943"),
        ("UTAX", "P-4020"),
        ("Xerox", "Versant 280"),
    ]

    print("\nTest: get_oem_equivalent_manufacturers()")
    print("-" * 80)
    for brand, model in test_cases:
        manufacturers = get_oem_equivalent_manufacturers(brand, model)
        print(f"{brand} {model}:")
        print(f"  → Search manufacturers: {manufacturers}")

    # Test expand_search_query_with_oem
    print("\nTest: expand_search_query_with_oem()")
    print("-" * 80)
    query = "error code C4080 solution"
    for brand, model in test_cases:
        queries = expand_search_query_with_oem(brand, model, f"{brand} {model} {query}")
        print(f"\n{brand} {model} {query}:")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")
