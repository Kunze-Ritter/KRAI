"""Pydantic models for video content management APIs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator, validator

from models.document import DocumentResponse, SortOrder
from models.manufacturer import ManufacturerResponse
from models.product import ProductResponse, ProductSeriesResponse
from models.validators import sanitize_string, validate_no_sql_injection, validate_uuid


class VideoPlatform(str, Enum):
    """Supported video distribution platforms."""

    YOUTUBE = "youtube"
    VIMEO = "vimeo"
    BRIGHTCOVE = "brightcove"
    DIRECT = "direct"


class VideoBase(BaseModel):
    """Shared video attributes."""

    link_id: str | None = Field(None, description="External link identifier if available.")
    youtube_id: str | None = Field(None, max_length=20, description="YouTube video identifier when applicable.")
    platform: VideoPlatform | None = Field(None, description="Platform hosting the video (YouTube, Vimeo, etc.).")
    video_url: HttpUrl | None = Field(None, description="Canonical accessible URL for the video resource.")
    title: str | None = Field(None, description="Human-friendly video title.")
    description: str | None = Field(None, description="Long-form description or transcript excerpt.")
    thumbnail_url: HttpUrl | None = Field(None, description="Publicly accessible thumbnail image URL.")
    duration: int | None = Field(None, ge=0, description="Video duration in seconds (if known).")
    view_count: int | None = Field(None, ge=0, description="Total number of views across the hosting platform.")
    like_count: int | None = Field(None, ge=0, description="Total number of positive reactions.")
    comment_count: int | None = Field(None, ge=0, description="Total number of comments for the video.")
    channel_id: str | None = Field(None, description="Channel identifier on the source platform.")
    channel_title: str | None = Field(None, description="Friendly name of the channel or publisher.")
    published_at: datetime | None = Field(None, description="Original publication timestamp provided by the platform.")
    manufacturer_id: str | None = Field(None, description="Associated manufacturer identifier, if applicable.")
    series_id: str | None = Field(None, description="Associated product series identifier, if available.")
    document_id: str | None = Field(None, description="Associated document identifier within the knowledge base.")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata collected during enrichment.")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_published_at(cls, values: VideoBase) -> VideoBase:
        if values.published_at and values.published_at > datetime.utcnow():
            raise ValueError("published_at cannot be in the future.")
        return values

    @validator("manufacturer_id", "series_id", "document_id")
    def validate_related_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator(
        "title",
        "description",
        "channel_title",
        "youtube_id",
        "link_id",
        pre=True,
    )
    def sanitize_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        sanitized = sanitize_string(value)
        validate_no_sql_injection(sanitized)
        return sanitized


class VideoCreateRequest(VideoBase):
    """Payload for creating a new video record."""

    platform: VideoPlatform = Field(..., description="Hosting platform for the video.")
    video_url: HttpUrl = Field(..., description="Canonical URL pointing to the video.")
    title: str = Field(..., min_length=1, description="Video title.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "How to replace the fuser unit",
                "video_url": "https://www.youtube.com/watch?v=abcd1234",
                "platform": "youtube",
                "youtube_id": "abcd1234",
                "description": "Step-by-step instructions for replacing the fuser unit.",
                "thumbnail_url": "https://img.youtube.com/vi/abcd1234/hqdefault.jpg",
                "duration": 420,
                "manufacturer_id": "mfg-001",
                "series_id": "series-01",
                "document_id": "doc-001",
            }
        }
    )


class VideoUpdateRequest(VideoBase):
    """Payload for updating video information."""

    platform: VideoPlatform | None = Field(None, description="Hosting platform for the video.")
    video_url: HttpUrl | None = Field(None)
    title: str | None = Field(None, min_length=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Updated how-to video title",
                "duration": 450,
                "view_count": 2500,
                "metadata": {"captions_available": True},
            }
        }
    )


class VideoFilterParams(BaseModel):
    """Filtering options for listing videos."""

    manufacturer_id: str | None = Field(None)
    series_id: str | None = Field(None)
    document_id: str | None = Field(None)
    platform: VideoPlatform | None = Field(None)
    youtube_id: str | None = Field(None)
    search: str | None = Field(
        None,
        description="Full-text search across title, description, and channel_title.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "manufacturer_id": "mfg-001",
                "platform": "youtube",
                "search": "installation guide",
            }
        }
    )

    @validator("manufacturer_id", "series_id", "document_id")
    def validate_filter_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator("search")
    def validate_search(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) > 150:
            raise ValueError("search must be 150 characters or less")
        validate_no_sql_injection(value)
        return value


class VideoSortParams(BaseModel):
    """Sorting configuration for video listings."""

    sort_by: str = Field(
        "created_at",
        description="Column to sort by (created_at, published_at, title, view_count, etc.).",
    )
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort direction.")


class VideoResponse(VideoBase):
    """Video record representation."""

    id: str = Field(..., description="Unique identifier for the video record.")
    platform: VideoPlatform = Field(...)
    video_url: HttpUrl = Field(...)
    title: str = Field(...)
    created_at: str | None = Field(None)
    updated_at: str | None = Field(None)
    enriched_at: str | None = Field(None, description="Timestamp when enrichment was performed, if applicable.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "vid-001",
                "title": "How to replace the fuser unit",
                "video_url": "https://www.youtube.com/watch?v=abcd1234",
                "platform": "youtube",
                "youtube_id": "abcd1234",
                "duration": 420,
                "view_count": 12345,
                "created_at": "2024-10-05T12:34:56Z",
            }
        }
    )


class VideoWithRelationsResponse(VideoResponse):
    """Video response that includes related resources."""

    manufacturer: ManufacturerResponse | None = Field(None)
    series: ProductSeriesResponse | None = Field(None)
    document: DocumentResponse | None = Field(None)
    linked_products: list[ProductResponse] = Field(
        default_factory=list, description="Products linked to this video via junction table."
    )


class VideoListResponse(BaseModel):
    """Paginated video listing."""

    videos: list[VideoResponse] = Field(...)
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "videos": [
                    {
                        "id": "vid-001",
                        "title": "How to replace the fuser unit",
                        "platform": "youtube",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 25,
                "total_pages": 1,
            }
        }
    )


class VideoProductLinkRequest(BaseModel):
    """Request payload for linking videos to products."""

    product_ids: list[str] = Field(..., min_length=1)

    model_config = ConfigDict(json_schema_extra={"example": {"product_ids": ["prod-001", "prod-002"]}})

    @validator("product_ids")
    def validate_product_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("product_ids cannot be empty")
        return [validate_uuid(product_id) for product_id in value]


class VideoEnrichmentRequest(BaseModel):
    """Payload for enrichment endpoint."""

    video_url: HttpUrl = Field(...)
    document_id: str | None = Field(None)
    manufacturer_id: str | None = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video_url": "https://www.youtube.com/watch?v=abcd1234",
                "document_id": "doc-123",
                "manufacturer_id": "mfg-001",
            }
        }
    )


class VideoEnrichmentResponse(BaseModel):
    """Response payload returned from enrichment."""

    success: bool = Field(...)
    video_id: str | None = Field(None)
    title: str | None = Field(None)
    platform: VideoPlatform | None = Field(None)
    duration: int | None = Field(None, ge=0)
    error: str | None = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "video_id": "vid-001",
                "title": "How to replace the fuser unit",
                "platform": "youtube",
                "duration": 420,
            }
        }
    )
