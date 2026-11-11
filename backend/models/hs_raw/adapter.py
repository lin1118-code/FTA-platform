"""원재료 HS4 모델 어댑터(플러그인) — 모델 코드는 복사하지 않고 원본 저장소를 그대로 불러옴

원본: https://github.com/davidsonny-sketch/fta-oda-hs4-model (커밋은 SOURCE_REF, fetch_source.sh로 받음)
원본 위치: 환경변수 RAW_HS4_SOURCE_DIR (기본: <플랫폼 루트>/external/fta-oda-hs4-model)
출력: docs/architecture.md 4장의 표준 봉투(module·status·source·model_name·model_version·
      input_summary·result·evidence·warnings)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = "raw_material_hs"
MODEL_NAME = "raw-material HS4 v2 (memory + HS nomenclature lexicon + RDKit structure rule + name model)"
SOURCE_REPO = "https://github.com/davidsonny-sketch/fta-oda-hs4-model"
SOURCE_REF = "8f897de6f90bbad866b834a4f82c090d1038d684"   # main (PR #2 병합, v2)
SOURCE_DIR = Path(os.environ.get("RAW_HS4_SOURCE_DIR", ROOT / "external" / "fta-oda-hs4-model"))
NOTICE = "원료명 기반 HS 4단위 추정 후보이며, '확인 필요' 원료와 최종 HS 코드는 공식 품목분류 확인이 필요합니다."


def source_available(source_dir: Path = SOURCE_DIR) -> bool:
    return (Path(source_dir) / "src" / "standalone.py").exists()


def _review_needed(state: str) -> bool:
    return not str(state).startswith("자동 확정")


def normalize(row: dict) -> dict:
    """원본 모델의 한국어 열 이름 → 플랫폼 계약(영문 키)"""
    cands = [c for c in (row.get("HS4 1순위"), row.get("HS4 2순위"), row.get("HS4 3순위")) if c]
    state = str(row.get("판정상태", ""))
    return {
        "input_name": row.get("입력", ""),
        "matched_name_kr": row.get("찾은 이름(국문)", ""),
        "matched_name_inci": row.get("찾은 이름(영문 INCI)", ""),
        "name_match": row.get("이름 찾기", ""),
        "hs4": cands[0] if cands else None,
        "hs4_candidates": cands,
        "status": state,
        "review_required": _review_needed(state),
        "semi_product_suspected": "반제품" in state,
    }


def _evidence(item: dict) -> dict:
    """판정 근거: 어떤 단계가 결정했는지(판정상태)와 이름 찾기 결과"""
    return {"input_name": item["input_name"], "decided_by": item["status"], "name_match": item["name_match"]}


def _warnings(items: list) -> list:
    w = [f"'{i['input_name']}': {i['status']}" for i in items if i["review_required"]]
    return w + [NOTICE]


def envelope(input_summary: dict, result: dict, items: list) -> dict:
    return {
        "module": MODULE,
        "status": "success",
        "source": "real_model",
        "model_name": MODEL_NAME,
        "model_version": f"{SOURCE_REPO}@{SOURCE_REF}",
        "input_summary": input_summary,
        "result": result,
        "evidence": [_evidence(i) for i in items],
        "warnings": _warnings(items),
    }


class RawMaterialHS4Adapter:
    def __init__(self, source_dir: Path = SOURCE_DIR, model=None):
        """model을 넘기면 그것을 씀(시험용). 아니면 원본 저장소의 src/standalone.py로 불러옴"""
        if model is None:
            if not source_available(source_dir):
                raise FileNotFoundError(
                    f"원재료 모델 원본이 없습니다: {Path(source_dir) / 'src'}. "
                    "backend/models/hs_raw/fetch_source.sh를 먼저 실행하세요.")
            src = str(Path(source_dir) / "src")
            if src not in sys.path:
                sys.path.insert(0, src)
            from standalone import load_model
            model = load_model()
        self.model = model

    def predict_one(self, name: str) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("원료명을 입력해야 합니다.")
        item = normalize(self.model.one(name))
        return envelope({"name": name}, item, [item])

    def predict_bom(self, ingredients: str) -> dict:
        if not (ingredients or "").strip():
            raise ValueError("성분표(쉼표로 구분한 원료명)를 입력해야 합니다.")
        items = [normalize(r) for r in self.model.bom(ingredients).to_dict("records")]
        summary = {"count": len(items),
                   "review_required": sum(i["review_required"] for i in items),
                   "semi_product_suspected": sum(i["semi_product_suspected"] for i in items)}
        return envelope({"ingredients": ingredients, "count": len(items)},
                        {"items": items, "summary": summary}, items)
