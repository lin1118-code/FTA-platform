"""원재료 HS4 모델 어댑터 — 모델 코드는 복사하지 않고 원본 저장소를 그대로 불러옴

원본: https://github.com/davidsonny-sketch/fta-oda-hs4-model (브랜치·커밋은 SOURCE_REF, fetch_source.sh로 받음)
원본 위치: 환경변수 RAW_HS4_SOURCE_DIR (기본: <플랫폼 루트>/external/fta-oda-hs4-model)
출력 계약: 원료마다 HS4 1~3순위, 판정상태, 사람 확인 필요 여부, 이름 찾기 결과
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_REPO = "https://github.com/davidsonny-sketch/fta-oda-hs4-model"
SOURCE_REF = "ac8de2faeababe94af4160a22ed98a871de43cc9"   # 브랜치 hyunsoo/final-model-v2 (main 병합 전)
SOURCE_DIR = Path(os.environ.get("RAW_HS4_SOURCE_DIR", ROOT / "external" / "fta-oda-hs4-model"))
NOTICE = "원료명 기반 HS 4단위 추정 후보이며, '확인 필요' 원료와 최종 HS 코드는 공식 품목분류 확인이 필요합니다."


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


class RawMaterialHS4Adapter:
    def __init__(self, source_dir: Path = SOURCE_DIR, model=None):
        """model을 넘기면 그것을 씀(시험용). 아니면 원본 저장소의 src/standalone.py로 불러옴"""
        if model is None:
            src = Path(source_dir) / "src"
            if not (src / "standalone.py").exists():
                raise FileNotFoundError(
                    f"원재료 모델 원본이 없습니다: {src}. backend/models/hs_raw/fetch_source.sh를 먼저 실행하세요.")
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            from standalone import load_model
            model = load_model()
        self.model = model

    def predict_one(self, name: str) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("원료명을 입력해야 합니다.")
        return {"source": {"repository": SOURCE_REPO, "ref": SOURCE_REF}, "result": normalize(self.model.one(name)), "notice": NOTICE}

    def predict_bom(self, ingredients: str) -> dict:
        if not (ingredients or "").strip():
            raise ValueError("성분표(쉼표로 구분한 원료명)를 입력해야 합니다.")
        df = self.model.bom(ingredients)
        rows = [normalize(r) for r in df.to_dict("records")]
        return {
            "source": {"repository": SOURCE_REPO, "ref": SOURCE_REF},
            "items": rows,
            "summary": {"count": len(rows), "review_required": sum(r["review_required"] for r in rows),
                        "semi_product_suspected": sum(r["semi_product_suspected"] for r in rows)},
            "notice": NOTICE,
        }
