"""
Foliant PDF import and product compatibility API routes.

Handles Konica Minolta Foliant PDF uploads, extraction, and product compatibility validation.
"""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from api.middleware.auth_middleware import require_permission
from api.middleware.rate_limit_middleware import limiter, rate_limit_upload
from api.routes.response_models import SuccessResponse

LOGGER = logging.getLogger("krai.api.foliant")

router = APIRouter(prefix="/foliant", tags=["foliant"])


class FoliantUploadResponse(BaseModel):
    """Response from Foliant PDF upload and import."""

    success: bool = Field(..., description="Whether the import was successful")
    products_imported: int = Field(..., description="Number of products imported")
    accessories_imported: int = Field(..., description="Number of accessories imported")
    compatibility_links: int = Field(..., description="Number of compatibility relationships created")
    filename: str = Field(..., description="Name of the processed PDF file")


class FoliantCompatibilityCheckResponse(BaseModel):
    """Response from compatibility check validation."""

    valid: bool = Field(..., description="Whether the configuration is valid")
    conflicts: list[str] = Field(default_factory=list, description="List of compatibility conflicts if any")
    details: dict[str, Any] = Field(default_factory=dict, description="Detailed position and quantity information")


@router.post(
    "/upload",
    response_model=SuccessResponse[FoliantUploadResponse],
    status_code=status.HTTP_200_OK,
)
@limiter.limit(rate_limit_upload)
async def upload_foliant_pdf(
    request: Request,
    file: UploadFile = File(..., description="Foliant PDF file to upload and process"),
    current_user: dict[str, Any] = Depends(require_permission("products:write")),
) -> SuccessResponse[FoliantUploadResponse]:
    """
    Upload and import a Foliant PDF file.

    Extracts product data, accessories, and compatibility rules from the PDF
    and imports them into the database.

    Args:
        file: PDF file to process

    Returns:
        Import statistics: products imported, accessories imported, compatibility links created
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF",
        )

    try:
        # Import here to avoid circular imports
        # Ensure scripts directory is in path
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from scripts.import_foliant_to_db import extract_foliant_data, import_to_database

        # Create temporary file for uploaded PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        try:
            # Extract data from PDF
            LOGGER.info("Processing Foliant PDF: %s", file.filename)
            data = extract_foliant_data(tmp_path)

            # Import to database
            success = import_to_database(data)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to import PDF data to database",
                )

            LOGGER.info(
                "Successfully imported Foliant PDF: %s (products=%s, accessories=%s, compatibility_links=%s)",
                file.filename,
                len(data.get("articles", [])),
                len([a for a in data.get("articles", []) if a.get("product_type") == "accessory"]),
                len(data.get("compatibility_matrix", [])),
            )

            return SuccessResponse(
                data=FoliantUploadResponse(
                    success=True,
                    products_imported=len(
                        [a for a in data.get("articles", []) if a.get("product_type") != "accessory"]
                    ),
                    accessories_imported=len(
                        [a for a in data.get("articles", []) if a.get("product_type") == "accessory"]
                    ),
                    compatibility_links=len(data.get("compatibility_matrix", [])),
                    filename=file.filename,
                )
            )

        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.error("Failed to process Foliant PDF %s: %s", file.filename, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing PDF: {exc!s}",
        )


@router.get(
    "/check",
    response_model=SuccessResponse[FoliantCompatibilityCheckResponse],
)
async def check_configuration_compatibility(
    product_id: str,
    accessories: str = "",
    current_user: dict[str, Any] = Depends(require_permission("products:read")),
) -> SuccessResponse[FoliantCompatibilityCheckResponse]:
    """
    Validate product-accessory configuration compatibility.

    Checks if a set of accessories can be mounted on a product according to
    Foliant compatibility rules (mounting positions, max quantities, dependencies).

    Args:
        product_id: Product model number (e.g., 'C257i')
        accessories: Comma-separated list of accessory model numbers (e.g., 'FS-539,DF-633')

    Returns:
        Compatibility check result with any conflicts listed
    """
    try:
        # Import here to avoid circular imports
        from backend.services.foliant_compatibility_service import FoliantCompatibilityService

        service = FoliantCompatibilityService()

        # Parse accessories list
        accessory_list = [a.strip() for a in accessories.split(",") if a.strip()] if accessories else []

        # Perform compatibility check
        check_result = service.check_configuration_valid(product_id, accessory_list)

        LOGGER.info(
            "Compatibility check: product=%s accessories=%s valid=%s",
            product_id,
            accessory_list,
            check_result["valid"],
        )

        return SuccessResponse(
            data=FoliantCompatibilityCheckResponse(
                valid=check_result["valid"],
                conflicts=check_result.get("conflicts", []),
                details=check_result.get("details", {}),
            )
        )

    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.error("Failed to check configuration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking configuration: {exc!s}",
        )
