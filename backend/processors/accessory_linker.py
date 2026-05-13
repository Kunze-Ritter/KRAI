"""
Accessory Linker - Automatically link accessories to products
Links accessories mentioned in documents to the main products in those documents
"""

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

from utils.accessory_detector import detect_konica_minolta_accessory

logger = logging.getLogger(__name__)


class AccessoryLinker:
    """Links accessories to products based on document co-occurrence"""

    def __init__(self, database_service: Any):
        self.database_service = database_service
        self.logger = logging.getLogger(__name__)

    def _run_db(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(coro)).result()

        return asyncio.run(coro)

    def _execute_with_retry(
        self, operation_name: str, func: Callable[[], Any], max_attempts: int = 3, base_delay: float = 0.5
    ):
        """Execute DB call with retry for transient failures."""
        last_exception = None
        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except OSError as exc:
                message = str(exc)
                if "getaddrinfo failed" in message.lower() and attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    self.logger.warning(
                        "⚠️ %s failed (attempt %d/%d): %s. Retrying in %.1fs",
                        operation_name,
                        attempt,
                        max_attempts,
                        message,
                        delay,
                    )
                    time.sleep(delay)
                    last_exception = exc
                    continue
                last_exception = exc
                break
            except Exception as exc:  # pragma: no cover - non-DNS errors propagate
                last_exception = exc
                break

        if last_exception:
            raise last_exception

        return None

    def link_accessories_for_document(self, document_id: UUID) -> dict[str, int]:
        """
        Link all accessories to main products in a document

        Strategy:
        - If accessory mentioned in document → link to document's main products
        - Main products = non-accessory products

        Args:
            document_id: Document UUID

        Returns:
            Dict with statistics: {
                'main_products': int,
                'accessories': int,
                'links_created': int,
                'links_skipped': int
            }
        """
        stats = {"main_products": 0, "accessories": 0, "links_created": 0, "links_skipped": 0, "errors": 0}

        try:
            # Get all products from this document
            products = self._get_products_from_document(document_id)

            if not products:
                self.logger.info(f"No products found in document {document_id}")
                return stats

            # Separate main products from accessories
            main_products = []
            accessories = []

            for product in products:
                if self._is_accessory(product):
                    accessories.append(product)
                else:
                    main_products.append(product)

            stats["main_products"] = len(main_products)
            stats["accessories"] = len(accessories)

            self.logger.info(
                f"📦 Document {document_id}: " f"{len(main_products)} main products, {len(accessories)} accessories"
            )

            if not main_products:
                self.logger.info("No main products to link accessories to")
                return stats

            if not accessories:
                self.logger.info("No accessories to link")
                return stats

            # Link each accessory to all main products
            for accessory in accessories:
                for main_product in main_products:
                    result = self._create_link(
                        product_id=main_product["id"],
                        accessory_id=accessory["id"],
                        is_standard=False,  # Default: optional accessory
                        compatibility_notes="Found together in document",
                    )

                    if result == "created":
                        stats["links_created"] += 1
                    elif result == "exists":
                        stats["links_skipped"] += 1
                    elif result == "error":
                        stats["errors"] += 1

            self.logger.info(
                f"✅ Linked accessories: "
                f"{stats['links_created']} created, "
                f"{stats['links_skipped']} skipped, "
                f"{stats['errors']} errors"
            )

            return stats

        except Exception as e:
            self.logger.error(f"Error linking accessories for document {document_id}: {e}")
            stats["errors"] += 1
            return stats

    def _get_products_from_document(self, document_id: UUID) -> list[dict[str, Any]]:
        """Get all products mentioned in a document"""
        try:
            rows = self._run_db(
                self.database_service.execute_query(
                    "SELECT product_id FROM krai_core.document_products WHERE document_id = $1",
                    [str(document_id)],
                )
            )

            if not rows:
                return []

            product_ids = [str(row["product_id"]) for row in rows if row.get("product_id")]
            if not product_ids:
                return []

            products = self._run_db(
                self.database_service.execute_query(
                    """
                    SELECT id, model_number, manufacturer_id, product_type
                    FROM krai_core.products
                    WHERE id = ANY($1::uuid[])
                    """.strip(),
                    [product_ids],
                )
            )

            return products or []

        except Exception as e:
            self.logger.error(f"Error getting products from document: {e}")
            return []

    def _is_accessory(self, product: dict[str, Any]) -> bool:
        """
        Determine if a product is an accessory

        Uses:
        1. Product type (if it's an accessory/consumable type)
        2. Accessory detector (model number patterns)
        """
        # Check product_type first
        product_type = product.get("product_type", "").lower()

        # Accessory types from database
        accessory_types = {
            "finisher",
            "stapler_finisher",
            "booklet_finisher",
            "punch_finisher",
            "folder",
            "trimmer",
            "stacker",
            "feeder",
            "paper_feeder",
            "envelope_feeder",
            "large_capacity_feeder",
            "document_feeder",
            "accessory",
            "cabinet",
            "work_table",
            "caster_base",
            "bridge_unit",
            "interface_kit",
            "memory_upgrade",
            "hard_drive",
            "controller",
            "fax_kit",
            "wireless_kit",
            "keyboard",
            "card_reader",
            "coin_kit",
            "option",
            "duplex_unit",
            "output_tray",
            "mailbox",
            "job_separator",
            "consumable",
            "toner_cartridge",
            "ink_cartridge",
            "drum_unit",
            "developer_unit",
            "fuser_unit",
            "transfer_belt",
            "waste_toner_box",
            "maintenance_kit",
            "staple_cartridge",
            "punch_kit",
            "print_head",
            "ink_tank",
            "paper",
        }

        if product_type in accessory_types:
            return True

        # Check model number with accessory detector
        model_number = product.get("model_number", "")
        if model_number:
            # Try Konica Minolta detector
            accessory_match = detect_konica_minolta_accessory(model_number)
            if accessory_match:
                return True

        return False

    def _create_link(
        self, product_id: str, accessory_id: str, is_standard: bool = False, compatibility_notes: str | None = None
    ) -> str:
        """
        Create a link between product and accessory

        Returns:
            'created' if new link created
            'exists' if link already exists
            'error' if error occurred
        """
        try:
            # Check if link already exists
            existing_rows = self._execute_with_retry(
                "Accessory link lookup",
                lambda: self._run_db(
                    self.database_service.execute_query(
                        """
                        SELECT id
                        FROM krai_core.product_accessories
                        WHERE product_id = $1 AND accessory_id = $2
                        LIMIT 1
                        """.strip(),
                        [str(product_id), str(accessory_id)],
                    )
                ),
            )

            if existing_rows:
                return "exists"

            # Create new link
            link_data = {
                "product_id": product_id,
                "accessory_id": accessory_id,
                "compatibility_type": "compatible",  # Default: compatible (found together in document)
                "is_standard": is_standard,
                "compatibility_notes": compatibility_notes,
            }

            self._execute_with_retry(
                "Accessory link insert",
                lambda: self._run_db(
                    self.database_service.execute_query(
                        """
                        INSERT INTO krai_core.product_accessories
                            (product_id, accessory_id, compatibility_type, is_standard, compatibility_notes)
                        VALUES
                            ($1::uuid, $2::uuid, $3, $4, $5)
                        """.strip(),
                        [
                            str(link_data["product_id"]),
                            str(link_data["accessory_id"]),
                            link_data["compatibility_type"],
                            bool(link_data["is_standard"]),
                            link_data["compatibility_notes"],
                        ],
                    )
                ),
            )

            return "created"

        except Exception as e:
            self.logger.error(f"Error creating link {product_id} -> {accessory_id}: {e}")
            return "error"

    def get_accessories_for_product(self, product_id: UUID) -> list[dict[str, Any]]:
        """Get all accessories linked to a product"""
        try:
            rows = self._run_db(
                self.database_service.execute_query(
                    """
                    SELECT accessory_id
                    FROM krai_core.product_accessories
                    WHERE product_id = $1
                    """.strip(),
                    [str(product_id)],
                )
            )

            if not rows:
                return []

            accessory_ids = [str(row["accessory_id"]) for row in rows if row.get("accessory_id")]
            if not accessory_ids:
                return []

            accessories = self._run_db(
                self.database_service.execute_query(
                    """
                    SELECT id, model_number, product_type
                    FROM krai_core.products
                    WHERE id = ANY($1::uuid[])
                    """.strip(),
                    [accessory_ids],
                )
            )

            return accessories or []

        except Exception as e:
            self.logger.error(f"Error getting accessories for product: {e}")
            return []

    def get_products_for_accessory(self, accessory_id: UUID) -> list[dict[str, Any]]:
        """Get all products that an accessory is compatible with"""
        try:
            rows = self._run_db(
                self.database_service.execute_query(
                    """
                    SELECT product_id
                    FROM krai_core.product_accessories
                    WHERE accessory_id = $1
                    """.strip(),
                    [str(accessory_id)],
                )
            )

            if not rows:
                return []

            product_ids = [str(row["product_id"]) for row in rows if row.get("product_id")]
            if not product_ids:
                return []

            products = self._run_db(
                self.database_service.execute_query(
                    """
                    SELECT id, model_number, product_type
                    FROM krai_core.products
                    WHERE id = ANY($1::uuid[])
                    """.strip(),
                    [product_ids],
                )
            )

            return products or []

        except Exception as e:
            self.logger.error(f"Error getting products for accessory: {e}")
            return []
