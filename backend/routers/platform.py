from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.registry import model_registry
from backend.schemas.platform import AgreementRuleInput, AnalysisRequest, BOMInput, FobCostSimulationRequest, ProductInput
from backend.services.analysis import AnalysisService
from backend.services.fta_simulation import simulate_fob_costs
from backend.services.repository import PlatformRepository

router = APIRouter(prefix="/api", tags=["Platform"])
repository = PlatformRepository()
repository.initialize()
analysis_service = AnalysisService(repository, model_registry)


class ModelRunRequest(BaseModel):
    payload: dict[str, Any]


@router.get("/models")
def list_models():
    return [item.model_dump(mode="json") if hasattr(item, "model_dump") else item.dict()
            for item in model_registry.list_models()]


@router.get("/products")
def list_products():
    return repository.list_products()


@router.post("/products", status_code=201)
def create_product(payload: ProductInput):
    return repository.create_product(payload)


@router.put("/products/{product_id}")
def update_product(product_id: str, payload: ProductInput):
    product = repository.update_product(product_id, payload)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/{product_id}")
def get_product(product_id: str):
    product = repository.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다.")
    return {"product": product, "bom": repository.get_bom(product_id)}


@router.put("/products/{product_id}/bom")
def replace_bom(product_id: str, payload: BOMInput):
    lines = repository.replace_bom(product_id, payload.lines)
    if lines is None:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다.")
    return {"product_id": product_id, "lines": lines}


@router.post("/models/{module}/run")
def run_model(module: str, request: ModelRunRequest):
    try:
        return model_registry.run(module, request.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/hs/raw/predict")
def predict_raw_material(payload: dict[str, Any]):
    return model_registry.run("raw_material_hs", payload)


@router.post("/hs/raw/bom")
def predict_raw_material_bom(payload: dict[str, Any]):
    return model_registry.run("raw_material_hs_bom", payload)


@router.post("/rvc/simulate")
def simulate_rvc(payload: dict[str, Any]):
    return model_registry.run("vnm", payload)


@router.post("/fta/cost-simulation")
def cost_simulation(payload: FobCostSimulationRequest):
    result = simulate_fob_costs(repository, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.post("/agreement-rules", status_code=201)
def create_agreement_rule(payload: AgreementRuleInput):
    return repository.save_rule(payload)


@router.get("/agreement-rules")
def list_agreement_rules(agreement_code: str, product_hs_code: str, as_of_date: date):
    return repository.list_rules(agreement_code, product_hs_code, as_of_date)


@router.post("/analyses", status_code=201)
def run_analysis(payload: AnalysisRequest):
    record = analysis_service.run(
        product_id=payload.product_id,
        agreement_code=payload.agreement_code,
        as_of_date=payload.as_of_date,
        finished_product_top_k=payload.finished_product_top_k,
        fob_override=payload.fob_override,
        fob_override_source=payload.fob_override_source,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다.")
    return record


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    record = analysis_service.get(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")
    return record


@router.get("/products/{product_id}/analyses")
def list_product_analyses(product_id: str):
    if repository.get_product(product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return repository.list_analyses(product_id)
