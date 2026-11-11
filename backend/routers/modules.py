from fastapi import APIRouter

from backend.models.registry import modules

router = APIRouter(prefix="/api/modules", tags=["Modules"])


@router.get("")
def list_modules():
    """연결된 모델(플러그인)과 상태 목록"""
    return {"modules": modules()}
