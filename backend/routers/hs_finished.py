from functools import lru_cache
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.models.hs_finished.retriever import FinishedProductHSRetriever

router = APIRouter(prefix="/api/hs/finished", tags=["Finished Product HS"])

class FinishedProductInput(BaseModel):
    product_name: str = ""
    ingredients_kr: str = ""
    ingredients_en: str = ""
    form_packaging: str = ""
    intended_use: str = ""
    top_k: int = 3

@lru_cache(maxsize=1)
def get_retriever():
    return FinishedProductHSRetriever()

@router.post("/predict")
def predict_finished_hs(payload: FinishedProductInput):
    product = {
        "Product Name": payload.product_name,
        "Main Ingredients (KR)": payload.ingredients_kr,
        "Main Ingredients (EN)": payload.ingredients_en,
        "Product Form and Packaging": payload.form_packaging,
        "Intended Use": payload.intended_use,
    }
    try:
        return get_retriever().predict(product, payload.top_k)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
