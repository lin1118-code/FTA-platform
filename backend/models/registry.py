"""플랫폼 모듈(플러그인) 목록 — 각 모델이 지금 연결돼 있는지 한 곳에서 확인

모델을 실제로 불러오지 않고(무거운 패키지 import 없음) 파일 존재만 보고 상태를 판단한다.
상태 값: integrated(원본·데이터 준비됨) / source_missing(원본 받기 필요) / prototype / pending
"""
from pathlib import Path

from backend.models.hs_raw import adapter as raw

ROOT = Path(__file__).resolve().parents[2]


def modules() -> list:
    finished_art = ROOT / "backend" / "models" / "hs_finished" / "artifacts" / "config.json"
    return [
        {
            "module": "finished_product_hs",
            "kind": "real_model",
            "status": "prototype" if finished_art.exists() else "prototype (index not built)",
            "endpoints": ["POST /api/hs/finished/predict"],
            "source": "https://github.com/lin1118-code/HS-complete-product",
        },
        {
            "module": raw.MODULE,
            "kind": "real_model",
            "status": "integrated" if raw.source_available() else "source_missing",
            "endpoints": ["POST /api/hs/raw/predict", "POST /api/hs/raw/bom"],
            "source": f"{raw.SOURCE_REPO}@{raw.SOURCE_REF}",
            "setup": "bash backend/models/hs_raw/fetch_source.sh",
        },
        {"module": "origin_cth_rvc", "kind": "rules_engine", "status": "pending", "endpoints": []},
        {"module": "vnm_analysis", "kind": "real_model", "status": "pending", "endpoints": []},
    ]
