from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field, root_validator

from backend.models.adapters.base import AdapterNotConnected, ModelAdapter, UnavailableAdapter
from backend.models.adapters.external_models import RawMaterialHSAdapter, RawMaterialHSBOMAdapter, VNMAdapter
from backend.schemas.platform import IntegrationStatus, ModelMetadata, ModelRunResult


class FinishedHSInput(BaseModel):
    product_name: str = ""
    ingredients_kr: str = ""
    ingredients_en: str = ""
    form_packaging: str = ""
    intended_use: str = ""
    top_k: int = Field(default=3, ge=1, le=10)

    @root_validator(pre=True)
    def require_product_description(cls, values):
        fields = ("product_name", "ingredients_kr", "ingredients_en", "form_packaging", "intended_use")
        if not any(str(values.get(field, "") or "").strip() for field in fields):
            raise ValueError("제품명, 성분, 형태·포장, 용도 중 하나 이상 입력해야 합니다.")
        return values


class RawMaterialHSInput(BaseModel):
    material_name: str = Field(min_length=1)
    description: str = ""
    composition: str = ""
    intended_use: str = ""


class RawMaterialHSBOMInput(BaseModel):
    composition: str = Field(min_length=1)


class VNMInput(BaseModel):
    product_id: str = ""
    bom: list[dict[str, Any]]
    as_of_date: str = ""
    fob: float | None = Field(default=None, gt=0)
    months: int = Field(default=3, ge=1, le=12)
    n_sim: int = Field(default=3000, ge=100, le=100000)
    seed: int = 42
    threshold: float = Field(default=40, ge=0, le=100)


class FinishedHS39Adapter(ModelAdapter):
    module = "finished_product_hs"
    input_schema = FinishedHSInput
    metadata = ModelMetadata(
        name="HS4_Direct_Plus_Exclusion_Fixed36",
        version="experiment-39-fixed36",
        repository="https://github.com/lin1118-code/HS-complete-product",
        source_commit="7cb3107d448bc6ed3324944e75d951976766e994",
        integration_status=IntegrationStatus.PROTOTYPE,
    )

    def execute(self, payload: FinishedHSInput) -> tuple[dict[str, Any], list[Any], list[str]]:
        product = {
            "Product Name": payload.product_name,
            "Main Ingredients (KR)": payload.ingredients_kr,
            "Main Ingredients (EN)": payload.ingredients_en,
            "Product Form and Packaging": payload.form_packaging,
            "Intended Use": payload.intended_use,
        }
        try:
            output = get_finished_hs39_predictor().predict(product, payload.top_k)
        except Exception as exc:
            from backend.models.hs_finished.model39 import Model39NotReady
            if isinstance(exc, Model39NotReady):
                raise AdapterNotConnected(str(exc)) from exc
            raise
        evidence = [entry for candidate in output["candidates"] for entry in candidate["direct_evidence"] + candidate["exclusion_evidence"]]
        warnings = [
            "HS4 후보 추천 결과이며 법적 HS 확정 판정이 아닙니다.",
            "운영 고정 설정의 LOPO Macro-F1은 0.713810입니다. Fold별 튜닝 결과 0.774929와 동일한 성능으로 해석할 수 없습니다.",
        ]
        return output, evidence, warnings


@lru_cache(maxsize=1)
def get_finished_hs39_predictor():
    from backend.models.hs_finished.model39 import Model39Predictor
    source_dir = __import__("os").environ.get("FTA_FINISHED_HS39_SOURCE_DIR")
    if not source_dir:
        from backend.models.hs_finished.model39 import Model39NotReady
        raise Model39NotReady("FTA_FINISHED_HS39_SOURCE_DIR에 원본 모델 39 checkout 경로를 설정해야 합니다.")
    return Model39Predictor(source_dir)


class ModelRegistry:
    def __init__(self, adapters: list[ModelAdapter] | None = None):
        self._adapters: dict[str, ModelAdapter] = {}
        for adapter in adapters or self._defaults():
            self.register(adapter)

    @staticmethod
    def _defaults() -> list[ModelAdapter]:
        return [
            FinishedHS39Adapter(),
            RawMaterialHSAdapter(RawMaterialHSInput),
            RawMaterialHSBOMAdapter(RawMaterialHSBOMInput),
            VNMAdapter(VNMInput),
        ]

    def register(self, adapter: ModelAdapter) -> None:
        if adapter.module in self._adapters:
            raise ValueError(f"이미 등록된 모듈입니다: {adapter.module}")
        self._adapters[adapter.module] = adapter

    def list_models(self) -> list[ModelMetadata]:
        return [adapter.metadata for adapter in self._adapters.values()]

    def get(self, module: str) -> ModelAdapter:
        try:
            return self._adapters[module]
        except KeyError as exc:
            raise KeyError(f"등록되지 않은 모델 모듈입니다: {module}") from exc

    def run(self, module: str, payload: dict[str, Any]) -> ModelRunResult:
        return self.get(module).run(payload)


model_registry = ModelRegistry()
