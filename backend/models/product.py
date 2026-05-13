"""
Product API models for CRUD operations and batch processing.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field, HttpUrl, root_validator, validator

from models.validators import sanitize_string, validate_no_sql_injection, validate_uuid


class SortOrder(str, Enum):
    """Supported sort orders."""

    ASC = "asc"
    DESC = "desc"


class ProductCreateRequest(BaseModel):
    """Payload used to create a new product record."""

    manufacturer_id: str = Field(..., min_length=1)
    series_id: str = Field(..., min_length=1)
    model_number: str = Field(..., min_length=1, max_length=100)
    model_name: str = Field(..., min_length=1, max_length=255)
    product_type: str = Field(..., min_length=1, max_length=100)
    launch_date: date | None = None
    end_of_life_date: date | None = None
    msrp_usd: float | None = Field(None, ge=0)
    weight_kg: float | None = Field(None, ge=0)
    dimensions_mm: dict[str, int | float] | None = None
    color_options: list[str] | None = None
    connectivity_options: list[str] | None = None
    print_technology: str | None = Field(None, max_length=100)
    max_print_speed_ppm: int | None = Field(None, ge=0)
    max_resolution_dpi: int | None = Field(None, ge=0)
    max_paper_size: str | None = Field(None, max_length=50)
    duplex_capable: bool | None = None
    network_capable: bool | None = None
    mobile_print_support: bool | None = None
    supported_languages: list[str] | None = None
    energy_star_certified: bool | None = None
    warranty_months: int | None = Field(None, ge=0)
    service_manual_url: HttpUrl | None = None
    parts_catalog_url: HttpUrl | None = None
    driver_download_url: HttpUrl | None = None
    firmware_version: str | None = Field(None, max_length=100)
    option_dependencies: dict[str, list[str]] | None = None
    replacement_parts: dict[str, list[str]] | None = None
    common_issues: dict[str, str] | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "manufacturer_id": "8dc1d2a5-8ef3-4dc1-90f9-1d4b7c6c1234",
                "series_id": "2b6450f2-58f3-41f6-a03b-84b324adf943",
                "model_number": "CS920",
                "model_name": "Lexmark CS920",
                "product_type": "printer",
                "launch_date": "2023-04-01",
                "msrp_usd": 3299.99,
                "print_technology": "laser",
                "network_capable": True,
                "supported_languages": ["en", "de", "fr"],
                "warranty_months": 24,
                "service_manual_url": "https://example.com/manuals/cs920",
                "driver_download_url": "https://example.com/drivers/cs920",
                "option_dependencies": {"finisher": ["duplex_module"]},
                "replacement_parts": {"fuser": ["40X7702"]},
                "common_issues": {"900.01": "Controller board reset"},
            }
        }

    @validator("manufacturer_id", "series_id")
    def validate_required_ids(cls, value: str) -> str:
        return validate_uuid(value)

    @validator(
        "model_number", "model_name", "product_type", "print_technology", "max_paper_size", "firmware_version", pre=True
    )
    def sanitize_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return sanitize_string(value)

    @validator("color_options", "connectivity_options", "supported_languages")
    def validate_non_empty_lists(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("List cannot be empty when provided")
        if any(not item for item in value):
            raise ValueError("List items cannot be empty strings")
        return value

    @validator("dimensions_mm")
    def validate_dimensions(cls, value: dict[str, int | float] | None):
        if value is None:
            return value
        if not value:
            raise ValueError("dimensions_mm cannot be empty when provided")
        for key, number in value.items():
            if number is None or float(number) <= 0:
                raise ValueError("dimensions_mm values must be positive numbers")
            if key not in {"width", "height", "depth"}:
                raise ValueError("dimensions_mm keys must be one of: width, height, depth")
        return value

    @root_validator(skip_on_failure=True)
    def validate_dates(cls, values: dict[str, object]) -> dict[str, object]:
        launch_date = values.get("launch_date")
        end_of_life = values.get("end_of_life_date")
        if launch_date and end_of_life and launch_date > end_of_life:
            raise ValueError("launch_date must be before end_of_life_date")
        return values


class ProductUpdateRequest(BaseModel):
    """Payload used to update an existing product."""

    manufacturer_id: str | None = None
    series_id: str | None = None
    model_number: str | None = Field(None, min_length=1, max_length=100)
    model_name: str | None = Field(None, min_length=1, max_length=255)
    product_type: str | None = Field(None, min_length=1, max_length=100)
    launch_date: date | None = None
    end_of_life_date: date | None = None
    msrp_usd: float | None = Field(None, ge=0)
    weight_kg: float | None = Field(None, ge=0)
    dimensions_mm: dict[str, int | float] | None = None
    color_options: list[str] | None = None
    connectivity_options: list[str] | None = None
    print_technology: str | None = Field(None, max_length=100)
    max_print_speed_ppm: int | None = Field(None, ge=0)
    max_resolution_dpi: int | None = Field(None, ge=0)
    max_paper_size: str | None = Field(None, max_length=50)
    duplex_capable: bool | None = None
    network_capable: bool | None = None
    mobile_print_support: bool | None = None
    supported_languages: list[str] | None = None
    energy_star_certified: bool | None = None
    warranty_months: int | None = Field(None, ge=0)
    service_manual_url: HttpUrl | None = None
    parts_catalog_url: HttpUrl | None = None
    driver_download_url: HttpUrl | None = None
    firmware_version: str | None = Field(None, max_length=100)
    option_dependencies: dict[str, list[str]] | None = None
    replacement_parts: dict[str, list[str]] | None = None
    common_issues: dict[str, str] | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "Lexmark CS920 Pro",
                "network_capable": True,
                "launch_date": "2024-01-15",
                "max_print_speed_ppm": 50,
                "supported_languages": ["en", "es"],
            }
        }

    @validator("manufacturer_id", "series_id", pre=True)
    def validate_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator(
        "model_number",
        "model_name",
        "product_type",
        "print_technology",
        "max_paper_size",
        "firmware_version",
        pre=True,
    )
    def sanitize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return sanitize_string(value)

    @validator("color_options", "connectivity_options", "supported_languages")
    def validate_non_empty_lists(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("List cannot be empty when provided")
        if any(not item for item in value):
            raise ValueError("List items cannot be empty strings")
        return value

    @validator("dimensions_mm")
    def validate_dimensions(cls, value: dict[str, int | float] | None):
        if value is None:
            return value
        if not value:
            raise ValueError("dimensions_mm cannot be empty when provided")
        for key, number in value.items():
            if number is None or float(number) <= 0:
                raise ValueError("dimensions_mm values must be positive numbers")
            if key not in {"width", "height", "depth"}:
                raise ValueError("dimensions_mm keys must be one of: width, height, depth")
        return value

    @root_validator(skip_on_failure=True)
    def validate_dates(cls, values: dict[str, object]) -> dict[str, object]:
        launch_date = values.get("launch_date")
        end_of_life = values.get("end_of_life_date")
        if launch_date and end_of_life and launch_date > end_of_life:
            raise ValueError("launch_date must be before end_of_life_date")
        return values


class ProductFilterParams(BaseModel):
    """Query parameters used to filter products in list view."""

    manufacturer_id: str | None = None
    series_id: str | None = None
    product_type: str | None = None
    launch_date_from: date | None = None
    launch_date_to: date | None = None
    end_of_life_date_from: date | None = None
    end_of_life_date_to: date | None = None
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)
    print_technology: str | None = None
    network_capable: bool | None = None
    search: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "manufacturer_id": "8dc1d2a5-8ef3-4dc1-90f9-1d4b7c6c1234",
                "product_type": "printer",
                "launch_date_from": "2022-01-01",
                "launch_date_to": "2024-12-31",
                "min_price": 1000,
                "max_price": 5000,
                "network_capable": True,
                "search": "Lexmark CS",
            }
        }

    @validator("manufacturer_id", "series_id")
    def validate_filter_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator("product_type", pre=True)
    def sanitize_filter_product_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return sanitize_string(value)

    @validator("search")
    def validate_search(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) > 100:
            raise ValueError("search must be 100 characters or less")
        validate_no_sql_injection(value)
        return value

    @root_validator(skip_on_failure=True)
    def validate_ranges(cls, values: dict[str, object]) -> dict[str, object]:
        launch_from = values.get("launch_date_from")
        launch_to = values.get("launch_date_to")
        if launch_from and launch_to and launch_from > launch_to:
            raise ValueError("launch_date_from must be before launch_date_to")

        eol_from = values.get("end_of_life_date_from")
        eol_to = values.get("end_of_life_date_to")
        if eol_from and eol_to and eol_from > eol_to:
            raise ValueError("end_of_life_date_from must be before end_of_life_date_to")

        min_price = values.get("min_price")
        max_price = values.get("max_price")
        if (min_price is not None and max_price is not None) and (min_price > max_price):
            raise ValueError("min_price cannot exceed max_price")

        return values


class ProductSortParams(BaseModel):
    """Sorting parameters for product listings."""

    sort_by: str = Field("created_at", description="Field name to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order: asc or desc")

    ALLOWED_SORT_FIELDS: ClassVar[set[str]] = {
        "created_at",
        "updated_at",
        "model_number",
        "model_name",
        "product_type",
        "launch_date",
        "msrp_usd",
    }

    class Config:
        json_schema_extra = {
            "example": {
                "sort_by": "launch_date",
                "sort_order": "asc",
            }
        }

    @validator("sort_by")
    def validate_sort_by(cls, value: str) -> str:
        if value not in cls.ALLOWED_SORT_FIELDS:
            allowed = ", ".join(sorted(cls.ALLOWED_SORT_FIELDS))
            raise ValueError(f"sort_by must be one of: {allowed}")
        return value

    @validator("sort_order", pre=True)
    def validate_sort_order(cls, value: str | SortOrder) -> SortOrder:
        try:
            return SortOrder(value)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in SortOrder)
            raise ValueError(f"sort_order must be one of: {allowed}") from exc


class ProductResponse(BaseModel):
    """Product representation used in API responses."""

    id: str
    parent_id: str | None = None
    manufacturer_id: str
    series_id: str
    model_number: str
    model_name: str
    product_type: str
    launch_date: date | None = None
    end_of_life_date: date | None = None
    msrp_usd: float | None = None
    weight_kg: float | None = None
    dimensions_mm: dict[str, int | float] | None = None
    color_options: list[str] | None = None
    connectivity_options: list[str] | None = None
    print_technology: str | None = None
    max_print_speed_ppm: int | None = None
    max_resolution_dpi: int | None = None
    max_paper_size: str | None = None
    duplex_capable: bool | None = None
    network_capable: bool | None = None
    mobile_print_support: bool | None = None
    supported_languages: list[str] | None = None
    energy_star_certified: bool | None = None
    warranty_months: int | None = None
    service_manual_url: HttpUrl | None = None
    parts_catalog_url: HttpUrl | None = None
    driver_download_url: HttpUrl | None = None
    firmware_version: str | None = None
    option_dependencies: dict[str, list[str]] | None = None
    replacement_parts: dict[str, list[str]] | None = None
    common_issues: dict[str, str] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "f214ab9d-6727-406d-bf4e-8e1f0346a123",
                "manufacturer_id": "8dc1d2a5-8ef3-4dc1-90f9-1d4b7c6c1234",
                "series_id": "2b6450f2-58f3-41f6-a03b-84b324adf943",
                "model_number": "CS920",
                "model_name": "Lexmark CS920",
                "product_type": "printer",
                "launch_date": "2023-04-01",
                "network_capable": True,
                "supported_languages": ["en", "de", "fr"],
                "created_at": "2025-10-30T12:00:00Z",
                "updated_at": "2025-10-30T12:30:00Z",
            }
        }


class ProductSeriesResponse(BaseModel):
    """Related product series information."""

    id: str
    manufacturer_id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "2b6450f2-58f3-41f6-a03b-84b324adf943",
                "manufacturer_id": "8dc1d2a5-8ef3-4dc1-90f9-1d4b7c6c1234",
                "name": "CS900 Series",
                "description": "High-performance color laser printers",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-06-15T12:00:00Z",
            }
        }


class ProductWithRelationsResponse(ProductResponse):
    """Product response enriched with related entities."""

    manufacturer: ManufacturerResponse | None = None
    series: ProductSeriesResponse | None = None
    parent_product: ProductResponse | None = None

    class Config(ProductResponse.Config):
        json_schema_extra = {
            "example": {
                **ProductResponse.Config.json_schema_extra["example"],
                "manufacturer": {
                    "id": "b686a4a8-59e3-4f7b-befe-0bbb9fa77b12",
                    "name": "Lexmark",
                    "country": "United States",
                    "created_at": "2020-01-01T00:00:00Z",
                    "updated_at": "2025-09-01T12:00:00Z",
                },
                "series": ProductSeriesResponse.Config.json_schema_extra["example"],
                "parent_product": None,
            }
        }


class ProductListResponse(BaseModel):
    """Paginated list response for products."""

    products: list[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "products": [ProductResponse.Config.json_schema_extra["example"]],
                "total": 42,
                "page": 1,
                "page_size": 10,
                "total_pages": 5,
            }
        }


class ProductStatsResponse(BaseModel):
    """Aggregated statistics about products."""

    total_products: int
    by_type: dict[str, int]
    by_manufacturer: dict[str, int]
    active_products: int
    discontinued_products: int

    class Config:
        json_schema_extra = {
            "example": {
                "total_products": 1200,
                "by_type": {"printer": 800, "multifunction": 400},
                "by_manufacturer": {"Lexmark": 300, "Canon": 250},
                "active_products": 950,
                "discontinued_products": 250,
            }
        }


class ProductBatchCreateRequest(BaseModel):
    """Batch creation payload for products."""

    products: list[ProductCreateRequest] = Field(..., max_items=100)

    @validator("products")
    def validate_batch_size(cls, value: list[ProductCreateRequest]) -> list[ProductCreateRequest]:
        if len(value) > 100:
            raise ValueError("Maximum 100 products per batch")
        return value

    class Config:
        json_schema_extra = {
            "example": {
                "products": [
                    ProductCreateRequest.Config.json_schema_extra["example"],
                ]
            }
        }


class ProductBatchUpdateItem(BaseModel):
    """Individual update entry used in batch updates."""

    id: str = Field(..., min_length=1)
    update_data: ProductUpdateRequest

    class Config:
        json_schema_extra = {
            "example": {
                "id": "f214ab9d-6727-406d-bf4e-8e1f0346a123",
                "update_data": ProductUpdateRequest.Config.json_schema_extra["example"],
            }
        }

    @validator("id")
    def validate_id(cls, value: str) -> str:
        return validate_uuid(value)


class ProductBatchUpdateRequest(BaseModel):
    """Batch update payload for products."""

    updates: list[ProductBatchUpdateItem] = Field(..., max_items=100)

    @validator("updates")
    def validate_batch_size(cls, value: list[ProductBatchUpdateItem]) -> list[ProductBatchUpdateItem]:
        if len(value) > 100:
            raise ValueError("Maximum 100 updates per batch")
        return value

    class Config:
        json_schema_extra = {"example": {"updates": [ProductBatchUpdateItem.Config.json_schema_extra["example"]]}}


class ProductBatchDeleteRequest(BaseModel):
    """Batch delete payload for products."""

    product_ids: list[str] = Field(..., max_items=100)

    @validator("product_ids")
    def validate_ids(cls, value: list[str]) -> list[str]:
        if len(value) > 100:
            raise ValueError("Maximum 100 products per batch")
        cleaned = []
        for item in value:
            if not item:
                raise ValueError("product_ids cannot contain empty strings")
            cleaned.append(validate_uuid(item))
        return cleaned

    class Config:
        json_schema_extra = {
            "example": {
                "product_ids": [
                    "f214ab9d-6727-406d-bf4e-8e1f0346a123",
                    "c0b0c10f-5e94-4b29-8d9f-8cbb8fbd8d02",
                ]
            }
        }


class ProductBatchResult(BaseModel):
    """Individual result entry for batch responses."""

    id: str | None
    status: str
    error: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "f214ab9d-6727-406d-bf4e-8e1f0346a123",
                "status": "success",
                "error": None,
            }
        }


class ProductBatchResponse(BaseModel):
    """Response summarising batch operation outcomes."""

    success: bool
    total: int
    successful: int
    failed: int
    results: list[ProductBatchResult]

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total": 3,
                "successful": 2,
                "failed": 1,
                "results": [
                    {
                        "id": "f214ab9d-6727-406d-bf4e-8e1f0346a123",
                        "status": "success",
                        "error": None,
                    },
                    {
                        "id": None,
                        "status": "failed",
                        "error": "Duplicate model_number for manufacturer",
                    },
                ],
            }
        }
