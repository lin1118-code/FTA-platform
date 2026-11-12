from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, root_validator


class ModelSource(str, Enum):
    REAL_MODEL = "real_model"
    MOCK = "mock"
    RULES_ENGINE = "rules_engine"


class RunStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_CONNECTED = "not_connected"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class IntegrationStatus(str, Enum):
    INTEGRATED = "integrated"
    PROTOTYPE = "prototype"
    PENDING = "pending"
    MOCK = "mock"


class ModelMetadata(BaseModel):
    name: str
    version: str | None = None
    repository: str | None = None
    source_commit: str | None = None
    integration_status: IntegrationStatus


class ModelRunResult(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    module: str
    status: RunStatus
    source: ModelSource | None = None
    model: ModelMetadata
    model_name: str | None = None
    model_version: str | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    evidence: list[dict[str, Any] | str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    timestamp: datetime | None = None


class ProductInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    ingredients_kr: str = ""
    ingredients_en: str = ""
    form_packaging: str = ""
    intended_use: str = ""
    description: str = ""
    hs_code: str | None = None
    hs_code_confirmed: bool = False
    fob_value: float | None = Field(default=None, ge=0)
    fob_currency: str | None = Field(default=None, min_length=3, max_length=3)


class ProductRecord(ProductInput):
    product_id: str
    created_at: datetime
    updated_at: datetime


class BOMLineInput(BaseModel):
    material_name: str = Field(min_length=1, max_length=300)
    description: str = ""
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)
    unit_price_unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description="Unit on which unit_value is based. When provided, it must match unit.",
    )
    unit_value: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    origin_country: str | None = None
    rvc_material_id: str | None = Field(
        default=None,
        max_length=100,
        description="Verified material identifier in the configured RVC price-history dataset.",
    )
    hs_code: str | None = None
    is_originating: bool | None = None
    origin_confirmed: bool = False
    origin_evidence_verified: bool = Field(
        default=False,
        description="Supporting origin evidence has been reviewed for the applicable agreement.",
    )
    hs_code_confirmed: bool = False

    @root_validator(skip_on_failure=True)
    def validate_unit_price_unit(cls, values: dict[str, Any]) -> dict[str, Any]:
        unit_price_unit = values.get("unit_price_unit")
        unit = values.get("unit")
        if unit_price_unit is not None and unit_price_unit != unit:
            raise ValueError("구매단가 기준 단위는 소요량 단위와 일치해야 합니다.")
        return values


class BOMLineRecord(BOMLineInput):
    line_id: str
    product_id: str


class BOMInput(BaseModel):
    lines: list[BOMLineInput]


class AgreementRuleInput(BaseModel):
    agreement_code: str = Field(min_length=1, max_length=50)
    product_hs_code: str = Field(min_length=1, max_length=20)
    criterion: str = Field(pattern="^(CTH|RVC)$")
    effective_from: date
    effective_to: date | None = None
    cth_digits: int | None = Field(default=None, ge=2, le=6)
    rvc_threshold_percent: float | None = Field(default=None, ge=0, le=100)
    rvc_formula: str | None = None
    criteria_relationship: str | None = Field(default=None, pattern="^(AND|OR)$")
    source_title: str | None = None
    source_url: str | None = None
    source_version: str | None = None


class AnalysisRequest(BaseModel):
    product_id: str
    agreement_code: str
    as_of_date: date = Field(default_factory=date.today)
    finished_product_top_k: int = Field(default=3, ge=1, le=10)
    fob_override: float | None = Field(default=None, gt=0)
    fob_override_source: str | None = Field(default=None, pattern="^(actual_transaction|cost_estimate)$")


class FobCostSimulationRequest(BaseModel):
    product_id: str
    agreement_code: str
    as_of_date: date = Field(default_factory=date.today)
    manufacturing_cost: float = Field(default=0, ge=0)
    packaging_cost: float = Field(default=0, ge=0)
    freight_cost: float = Field(default=0, ge=0)
    freight_included_in_fob: bool = True
    other_cost: float = Field(default=0, ge=0)
    profit: float = Field(default=0, ge=0)
    use_actual_fob: bool = False
    actual_fob: float | None = Field(default=None, ge=0)
    scenario_threshold_percent: float | None = Field(default=None, ge=0, le=100)


class AnalysisRecord(BaseModel):
    analysis_id: str
    product_id: str
    agreement_code: str
    as_of_date: date
    status: RunStatus
    steps: dict[str, RunStatus]
    results: dict[str, Any]
    created_at: datetime
