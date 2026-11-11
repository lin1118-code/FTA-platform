from functools import lru_cache
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/hs/raw", tags=["Raw Material HS4"])


class RawMaterialInput(BaseModel):
    name: str = ""


class BomInput(BaseModel):
    ingredients: str = ""


@lru_cache(maxsize=1)
def get_adapter():
    from backend.models.hs_raw.adapter import RawMaterialHS4Adapter   # 원본 모델(rdkit 등)은 처음 호출할 때만 불러옴
    return RawMaterialHS4Adapter()


@router.post("/predict")
def predict_raw_hs(payload: RawMaterialInput):
    try:
        return get_adapter().predict_one(payload.name)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/bom")
def predict_raw_bom(payload: BomInput):
    try:
        return get_adapter().predict_bom(payload.ingredients)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
