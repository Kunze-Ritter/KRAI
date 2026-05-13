"""
Manufacturer API models for CRUD operations and related statistics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, root_validator, validator


class SortOrder(str, Enum):
    """Supported sort orders."""

    ASC = "asc"
    DESC = "desc"


class ManufacturerCreateRequest(BaseModel):
    """Payload for creating a manufacturer."""

    name: str = Field(..., min_length=1, max_length=255)
    short_name: str | None = Field(None, max_length=10)
    country: str | None = Field(None, max_length=100)
    founded_year: int | None = Field(None, ge=1800)
    website: HttpUrl | None = None
    support_email: EmailStr | None = None
    support_phone: str | None = Field(None, max_length=50)
    logo_url: HttpUrl | None = None
    is_competitor: bool = Field(default=False)
    market_share_percent: float | None = Field(None, ge=0.0, le=100.0)
    annual_revenue_usd: float | None = Field(None, ge=0.0)
    employee_count: int | None = Field(None, ge=0)
    headquarters_address: str | None = Field(None, max_length=255)
    stock_symbol: str | None = Field(None, max_length=20)
    primary_business_segment: str | None = Field(None, max_length=100)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Lexmark International",
                "short_name": "LEX",
                "country": "United States",
                "founded_year": 1991,
                "website": "https://www.lexmark.com",
                "support_email": "support@lexmark.com",
                "support_phone": "+1-800-539-6275",
                "logo_url": "https://cdn.example.com/logos/lexmark.png",
                "is_competitor": False,
                "market_share_percent": 12.5,
                "annual_revenue_usd": 3200000000.0,
                "employee_count": 9000,
                "headquarters_address": "740 W New Circle Rd, Lexington, KY 40550",
                "stock_symbol": "LEX",
                "primary_business_segment": "Printing Solutions",
            }
        }

    @validator("founded_year")
    def validate_founded_year(cls, value: int | None) -> int | None:
        if value is None:
            return value
        current_year = datetime.utcnow().year
        if value < 1800 or value > current_year:
            raise ValueError(f"founded_year must be between 1800 and {current_year}")
        return value


class ManufacturerUpdateRequest(BaseModel):
    """Payload for updating a manufacturer."""

    name: str | None = Field(None, min_length=1, max_length=255)
    short_name: str | None = Field(None, max_length=10)
    country: str | None = Field(None, max_length=100)
    founded_year: int | None = Field(None, ge=1800)
    website: HttpUrl | None = None
    support_email: EmailStr | None = None
    support_phone: str | None = Field(None, max_length=50)
    logo_url: HttpUrl | None = None
    is_competitor: bool | None = None
    market_share_percent: float | None = Field(None, ge=0.0, le=100.0)
    annual_revenue_usd: float | None = Field(None, ge=0.0)
    employee_count: int | None = Field(None, ge=0)
    headquarters_address: str | None = Field(None, max_length=255)
    stock_symbol: str | None = Field(None, max_length=20)
    primary_business_segment: str | None = Field(None, max_length=100)

    class Config:
        json_schema_extra = {
            "example": {
                "support_email": "enterprise-support@lexmark.com",
                "market_share_percent": 13.1,
                "employee_count": 9200,
                "primary_business_segment": "Enterprise Printing",
            }
        }

    @validator("founded_year")
    def validate_founded_year(cls, value: int | None) -> int | None:
        if value is None:
            return value
        current_year = datetime.utcnow().year
        if value < 1800 or value > current_year:
            raise ValueError(f"founded_year must be between 1800 and {current_year}")
        return value


class ManufacturerFilterParams(BaseModel):
    """Query parameters for filtering manufacturers."""

    country: str | None = None
    is_competitor: bool | None = None
    founded_year_from: int | None = Field(None, ge=1800)
    founded_year_to: int | None = Field(None, ge=1800)
    search: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "country": "Germany",
                "is_competitor": True,
                "founded_year_from": 1950,
                "founded_year_to": 2020,
                "search": "Konica",
            }
        }

    @root_validator(skip_on_failure=True)
    def validate_year_range(cls, values: dict[str, int | None]) -> dict[str, int | None]:
        year_from = values.get("founded_year_from")
        year_to = values.get("founded_year_to")
        if year_from and year_to and year_from > year_to:
            raise ValueError("founded_year_from must be less than or equal to founded_year_to")
        return values


class ManufacturerSortParams(BaseModel):
    """Sorting parameters for manufacturers."""

    sort_by: str = Field("name", description="Field name to sort by")
    sort_order: SortOrder = Field(SortOrder.ASC, description="Sort order: asc or desc")

    ALLOWED_SORT_FIELDS: ClassVar[set[str]] = {
        "name",
        "created_at",
        "updated_at",
        "market_share_percent",
        "employee_count",
    }

    class Config:
        json_schema_extra = {
            "example": {
                "sort_by": "market_share_percent",
                "sort_order": "desc",
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


class ManufacturerResponse(BaseModel):
    """Manufacturer representation for API responses."""

    id: UUID
    name: str
    short_name: str | None = None
    country: str | None = None
    founded_year: int | None = None
    website: HttpUrl | None = None
    support_email: EmailStr | None = None
    support_phone: str | None = None
    logo_url: HttpUrl | None = None
    is_competitor: bool
    market_share_percent: float | None = None
    annual_revenue_usd: float | None = None
    employee_count: int | None = None
    headquarters_address: str | None = None
    stock_symbol: str | None = None
    primary_business_segment: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "b686a4a8-59e3-4f7b-befe-0bbb9fa77b12",
                "name": "Lexmark International",
                "short_name": "LEX",
                "country": "United States",
                "founded_year": 1991,
                "website": "https://www.lexmark.com",
                "support_email": "support@lexmark.com",
                "support_phone": "+1-800-539-6275",
                "logo_url": "https://cdn.example.com/logos/lexmark.png",
                "is_competitor": False,
                "market_share_percent": 12.5,
                "annual_revenue_usd": 3200000000.0,
                "employee_count": 9000,
                "headquarters_address": "740 W New Circle Rd, Lexington, KY 40550",
                "stock_symbol": "LEX",
                "primary_business_segment": "Printing Solutions",
                "created_at": "2025-10-30T12:00:00Z",
                "updated_at": "2025-10-30T12:30:00Z",
            }
        }


class ManufacturerWithStatsResponse(ManufacturerResponse):
    """Manufacturer response enriched with aggregate statistics."""

    product_count: int
    document_count: int
    series_count: int

    class Config(ManufacturerResponse.Config):
        json_schema_extra = {
            "example": {
                **ManufacturerResponse.Config.json_schema_extra["example"],
                "product_count": 25,
                "document_count": 12,
                "series_count": 3,
            }
        }


class ManufacturerListResponse(BaseModel):
    """Paginated list response for manufacturers."""

    manufacturers: list[ManufacturerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "manufacturers": [ManufacturerResponse.Config.json_schema_extra["example"]],
                "total": 30,
                "page": 1,
                "page_size": 10,
                "total_pages": 3,
            }
        }


class ManufacturerStatsResponse(BaseModel):
    """Aggregate statistics for manufacturers."""

    total_manufacturers: int
    by_country: dict[str, int]
    competitors_count: int
    total_market_share: float

    class Config:
        json_schema_extra = {
            "example": {
                "total_manufacturers": 85,
                "by_country": {
                    "United States": 20,
                    "Germany": 15,
                    "Japan": 18,
                },
                "competitors_count": 42,
                "total_market_share": 87.4,
            }
        }
