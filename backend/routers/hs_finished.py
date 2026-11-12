from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.models.registry import model_registry
from backend.schemas.platform import RunStatus

router = APIRouter(prefix="/api/hs/finished", tags=["Finished Product HS"])

class FinishedProductInput(BaseModel):
    product_name: str = ""
    ingredients_kr: str = ""
    ingredients_en: str = ""
    form_packaging: str = ""
    intended_use: str = ""
    top_k: int = 3

@router.post("/predict")
def predict_finished_hs(payload: FinishedProductInput):
    result = model_registry.run("finished_product_hs", payload.dict())
    if result.status == RunStatus.FAILED:
        message = "; ".join(result.warnings)
        is_input_error = any(
            warning.startswith("입력 검증 실패:")
            or "제품명, 성분, 형태·포장, 용도 중 하나 이상" in warning
            for warning in result.warnings
        )
        code = 400 if is_input_error else 503
        raise HTTPException(status_code=code, detail=message)
    if result.status != RunStatus.SUCCEEDED:
        raise HTTPException(status_code=503, detail="완제품 HS 모델을 실행할 수 없습니다.")
    return result.result
