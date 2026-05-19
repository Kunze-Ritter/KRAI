"""
Pydantic models for PM (Predictive Maintenance) domain.

Represents service ticket features, predictions, and related data structures
used throughout the ML pipeline.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceTicketFeatures(BaseModel):
    """
    Feature set extracted from a single service ticket for ML model input.

    All features are normalized or one-hot encoded for compatibility with
    XGBoost/LightGBM. Placeholders for Docuware/Radix fields marked with None defaults.
    """

    ticket_id: str = Field(..., description="Unique service ticket ID")
    repair_time_minutes: float | None = Field(None, ge=0, description="Actual repair time in minutes")
    problem_frequency: int = Field(..., ge=0, description="How many tickets have same problem_short (global count)")
    part_replacement_count: int = Field(..., ge=0, description="Number of parts replaced (len(replaced_parts))")
    error_code_count: int = Field(..., ge=0, description="Number of unique error codes extracted (len(error_codes))")
    manufacturer_encoded: int = Field(
        ..., ge=0, le=10, description="Encoded manufacturer ID (0=unknown, 1=KM, 2=HP, 3=Ricoh, ...)"
    )
    error_code_top10: list[int] = Field(
        ..., min_items=10, max_items=10, description="One-hot encoding of top-10 error codes"
    )

    # Docuware/Radix placeholders (available after Sprint 2 Category B)
    device_age_months: float | None = Field(
        None, ge=0, description="Device age in months (Docuware: from purchase date)"
    )
    page_count: int | None = Field(None, ge=0, description="Total page count (Docuware: cumulative counter)")
    service_history_count: int | None = Field(
        None, ge=0, description="Prior service calls on device (Docuware: from service history)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticket_id": "TK-2026-001",
                "repair_time_minutes": 45.5,
                "problem_frequency": 12,
                "part_replacement_count": 2,
                "error_code_count": 3,
                "manufacturer_encoded": 1,
                "error_code_top10": [1, 0, 1, 0, 0, 0, 0, 0, 0, 0],
                "device_age_months": 24.0,
                "page_count": 250000,
                "service_history_count": 5,
            }
        }
    )


class PredictionResult(BaseModel):
    """
    Single prediction output from LongTailClassifier.

    Indicates whether a ticket is Common (frequent problem) or Long-Tail (rare problem).
    """

    ticket_id: str = Field(..., description="Service ticket ID being predicted")
    is_common: bool = Field(..., description="True if problem is Common (top 20), False if Long-Tail")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence (probability of positive class)")
    model_name: str = Field(..., description="Name of the model (e.g. 'long_tail_xgb_v1')")
    model_version: str = Field(..., description="Semantic version of the model (e.g. '1.0.0')")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticket_id": "TK-2026-001",
                "is_common": True,
                "confidence": 0.87,
                "model_name": "long_tail_xgb_v1",
                "model_version": "1.0.0",
            }
        }
    )


class TicketBatchPredictionRequest(BaseModel):
    """Request to predict on a batch of tickets."""

    limit: int | None = Field(None, ge=1, le=10000, description="Max tickets to predict (None = all)")


class TicketBatchPredictionResponse(BaseModel):
    """Response from batch prediction run."""

    predicted: int = Field(..., ge=0, description="Number of tickets newly predicted")
    skipped: int = Field(..., ge=0, description="Number skipped (already have prediction)")
    errors: int = Field(..., ge=0, description="Number that failed to predict")
    timestamp: datetime = Field(..., description="When prediction run started")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "predicted": 145,
                "skipped": 35,
                "errors": 0,
                "timestamp": "2026-06-02T10:30:00Z",
            }
        }
    )
