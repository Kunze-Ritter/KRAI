"""Configuration validation API routes."""

from __future__ import annotations

import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies.database import get_database_pool
from backend.api.middleware.rate_limit_middleware import rate_limit_standard
from backend.utils.configuration_validator import ConfigurationValidator

LOGGER = logging.getLogger("krai.api.configuration")

router = APIRouter(prefix="/products", tags=["configuration"])


class CompatibleAccessory(BaseModel):
    """Accessory compatible with a product."""

    id: str
    model_number: str
    product_type: str
    accessory_type: str | None = None
    is_required: bool = False


class CompatibleAccessoriesResponse(BaseModel):
    """Response containing compatible accessories for a product."""

    product_id: str
    compatible_accessories: list[CompatibleAccessory]


class ConfigurationValidationRequest(BaseModel):
    """Request to validate a product configuration."""

    accessory_ids: list[str] = Field(..., description="List of accessory UUIDs to validate")


class ConfigurationValidationResponse(BaseModel):
    """Response from configuration validation."""

    product_id: str
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []


@router.get(
    "/{product_id}/compatible-accessories",
    response_model=CompatibleAccessoriesResponse,
    dependencies=[Depends(rate_limit_standard)],
)
async def get_compatible_accessories(
    product_id: str,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> CompatibleAccessoriesResponse:
    """Get all accessories compatible with a product."""
    try:
        # Query compatible accessories from product_accessories table
        query = """
        SELECT
            p.id,
            p.model_number,
            p.product_type,
            pa.accessory_type,
            pa.is_required
        FROM krai_core.product_accessories pa
        JOIN krai_core.products p ON p.id = pa.accessory_id
        WHERE pa.product_id = $1::uuid
        ORDER BY pa.is_required DESC, p.model_number
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, UUID(product_id))

        accessories = [
            CompatibleAccessory(
                id=str(row["id"]),
                model_number=row["model_number"],
                product_type=row["product_type"],
                accessory_type=row["accessory_type"],
                is_required=row["is_required"] or False,
            )
            for row in rows
        ]

        return CompatibleAccessoriesResponse(
            product_id=product_id,
            compatible_accessories=accessories,
        )

    except ValueError as e:
        LOGGER.error("Invalid product_id format: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product_id format",
        ) from e
    except Exception as e:
        LOGGER.error("Error getting compatible accessories: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving compatible accessories",
        ) from e


@router.post(
    "/{product_id}/validate-configuration",
    response_model=ConfigurationValidationResponse,
    dependencies=[Depends(rate_limit_standard)],
)
async def validate_configuration(
    product_id: str,
    request: ConfigurationValidationRequest,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConfigurationValidationResponse:
    """Validate a product configuration against dependencies."""
    try:
        # Convert IDs to UUIDs
        product_uuid = UUID(product_id)
        accessory_uuids = [UUID(acc_id) for acc_id in request.accessory_ids]

        # Create database adapter and validator
        from backend.services.database_adapter import PostgreSQLAdapter

        adapter = PostgreSQLAdapter(pool)

        validator = ConfigurationValidator(adapter=adapter)

        # Validate configuration
        result = await validator.validate_configuration(product_uuid, accessory_uuids)

        return ConfigurationValidationResponse(
            product_id=product_id,
            valid=result.valid,
            errors=result.errors,
            warnings=result.warnings,
            recommendations=result.recommendations,
        )

    except ValueError as e:
        LOGGER.error("Invalid UUID format: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product_id or accessory_id format",
        ) from e
    except Exception as e:
        LOGGER.error("Error validating configuration: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating configuration",
        ) from e
