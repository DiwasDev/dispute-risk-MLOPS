"""
app/schemas.py
==============
Pydantic request and response schemas for the complaint dispute prediction API.

The input schema mirrors the model's MLflow signature exactly (from MLmodel):
  Date received, Product, Sub-product, Issue, Sub-issue,
  Consumer complaint narrative, Company, State, ZIP code, Tags,
  Consumer consent provided?, Submitted via

Optional fields match the training data's observed null patterns — see
core/validation.py NULL_RATE_THRESHOLDS for the expected null rates.

No preprocessing happens here. The sklearn pipeline embedded in the loaded
MLflow model handles all imputation, encoding, and scaling identically to
training. This is the training-serving parity guarantee.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ComplaintInput(BaseModel):
    """
    Single complaint record for dispute risk prediction.

    Required fields must be present at complaint intake time.
    Optional fields may be null — the preprocessing pipeline handles them
    with sentinel imputation (same strategy as training).
    """

    # --- Required at intake (null rate < 1% in training data) ---
    Date_received: str = Field(
        ...,
        alias="Date received",
        description="Complaint intake date. Format: YYYY-MM-DD or M/D/YYYY.",
        examples=["2016-03-15"],
    )
    Product: str = Field(
        ...,
        description="Financial product category.",
        examples=["Mortgage"],
    )
    Issue: str = Field(
        ...,
        description="Nature of the complaint.",
        examples=["Loan modification,collection,foreclosure"],
    )
    Company: str = Field(
        ...,
        description="Financial institution named in the complaint.",
        examples=["Bank of America"],
    )
    State: str = Field(
        ...,
        description="Two-letter US state code.",
        examples=["CA"],
    )
    ZIP_code: str = Field(
        ...,
        alias="ZIP code",
        description="Consumer ZIP code (kept as string to preserve leading zeros).",
        examples=["90001"],
    )
    Submitted_via: str = Field(
        ...,
        alias="Submitted via",
        description="Channel through which the complaint was submitted.",
        examples=["Web"],
    )

    # --- Optional at intake (high null rate expected) ---
    Sub_product: Optional[str] = Field(
        None,
        alias="Sub-product",
        description="Product sub-category. Often null.",
        examples=["Conventional fixed mortgage"],
    )
    Sub_issue: Optional[str] = Field(
        None,
        alias="Sub-issue",
        description="Issue sub-category. Often null.",
    )
    Consumer_complaint_narrative: Optional[str] = Field(
        None,
        alias="Consumer complaint narrative",
        description="Free-text narrative. ~84% null in training data.",
    )
    Tags: Optional[str] = Field(
        None,
        description="Servicemember or Older American tag. Often null.",
        examples=["Servicemember"],
    )
    Consumer_consent_provided: Optional[str] = Field(
        None,
        alias="Consumer consent provided?",
        description="Whether consumer consented to publish narrative. Often null.",
        examples=["Consent not provided"],
    )

    model_config = {"populate_by_name": True}

    def to_dataframe(self):
        """
        Convert to a single-row pandas DataFrame with the exact column names
        the sklearn pipeline was trained on.

        Column names must match training exactly — the ColumnTransformer uses
        column names to route features to the correct transformer.
        """
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "Date received": self.Date_received,
                    "Product": self.Product,
                    "Sub-product": self.Sub_product,
                    "Issue": self.Issue,
                    "Sub-issue": self.Sub_issue,
                    "Consumer complaint narrative": self.Consumer_complaint_narrative,
                    "Company": self.Company,
                    "State": self.State,
                    "ZIP code": self.ZIP_code,
                    "Tags": self.Tags,
                    "Consumer consent provided?": self.Consumer_consent_provided,
                    "Submitted via": self.Submitted_via,
                }
            ]
        )


class PredictionResponse(BaseModel):
    """
    Dispute risk prediction response.

    dispute_probability: raw model probability (0.0–1.0).
    dispute_predicted: binary decision after threshold is applied.
    model_version: MLflow model version serving this prediction.
    model_alias: the alias currently loaded (e.g. "champion").
    threshold: the operating threshold applied to produce dispute_predicted.
    """

    dispute_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Predicted probability that the consumer will dispute the resolution.",
    )
    dispute_predicted: bool = Field(
        ...,
        description="True = route to senior dispute review queue.",
    )
    model_version: str = Field(
        ...,
        description="MLflow model version identifier.",
    )
    model_alias: str = Field(
        default="champion",
        description="Model alias currently loaded.",
    )
    threshold: float = Field(
        ...,
        description="Decision threshold applied to produce dispute_predicted.",
    )


class BatchPredictionRequest(BaseModel):
    """Request body for batch predictions (up to 1000 records)."""

    complaints: list[ComplaintInput] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of complaint records to score.",
    )


class BatchPredictionResponse(BaseModel):
    """Response for batch predictions."""

    predictions: list[PredictionResponse]
    count: int

    class HealthResponse(BaseModel):
        """Health check response including golden input parity status."""

        status: str  # "healthy" | "degraded" | "unhealthy"
        model_version: str
        model_alias: str
        golden_input_passed: bool
        message: str


class DriftRequest(BaseModel):
    """
    Request body for on-demand drift detection.

    Provide a sample of recent serving records (current_batch) and the
    endpoint will compare against the training reference distribution.
    Minimum 50 records recommended for reliable PSI estimates.
    """

    complaints: list[ComplaintInput] = Field(
        ...,
        min_length=10,
        description="Recent serving records to check for drift.",
    )


class DriftResponse(BaseModel):
    """Drift detection result summary."""

    has_drift: bool
    needs_retraining: bool
    drifted_features: list[str]
    retraining_features: list[str]
    summary: str
    current_rows: int
    reference_rows: int
