"""Thin, cached adapters for externally checked-out source repositories."""
from __future__ import annotations

import importlib.util
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from backend.models.adapters.base import AdapterNotConnected, ModelAdapter
from backend.schemas.platform import IntegrationStatus, ModelMetadata


def _source_dir(env_name: str) -> Path:
    raw = os.getenv(env_name)
    if not raw:
        raise AdapterNotConnected(f"{env_name} 환경 변수가 설정되지 않았습니다.")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise AdapterNotConnected(f"원본 모델 경로가 없습니다: {path}")
    return path


@lru_cache(maxsize=1)
def _raw_model():
    source = _source_dir("FTA_RAW_HS4_SOURCE_DIR")
    src = source / "src"
    if not (src / "standalone.py").exists():
        raise AdapterNotConnected("원재료 HS4 standalone.py를 찾을 수 없습니다.")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from standalone import load_model
        return load_model(source / "data")
    except ImportError as exc:
        raise AdapterNotConnected(f"원재료 HS4 의존성이 없습니다: {exc}") from exc


def _raw_record(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "input": value.get("입력", ""),
        "matched_name_kr": value.get("찾은 이름(국문)", ""),
        "matched_inci": value.get("찾은 이름(영문 INCI)", ""),
        "name_match": value.get("이름 찾기", ""),
        "candidates": [
            {"rank": 1, "hs4": value.get("HS4 1순위", "")},
            {"rank": 2, "hs4": value.get("HS4 2순위", "")},
            {"rank": 3, "hs4": value.get("HS4 3순위", "")},
        ],
        "decision_status": value.get("판정상태", ""),
        "original_output": value,
    }


class RawMaterialHSAdapter(ModelAdapter):
    module = "raw_material_hs"

    def __init__(self, input_schema):
        self.input_schema = input_schema
        self.metadata = ModelMetadata(name="HS4Final.one", version="final-model-v2", repository="https://github.com/davidsonny-sketch/fta-oda-hs4-model", source_commit="ac8de2faeababe94af4160a22ed98a871de43cc9", integration_status=IntegrationStatus.PROTOTYPE)

    def execute(self, payload):
        raw = _raw_model().one(payload.material_name)
        record = _raw_record(raw)
        return record, [{"type": "name_match", "value": record["name_match"]}], ["원본 판정상태를 보존합니다. ‘확인 필요’는 자동 확정하지 않습니다."]


class RawMaterialHSBOMAdapter(ModelAdapter):
    module = "raw_material_hs_bom"

    def __init__(self, input_schema):
        self.input_schema = input_schema
        self.metadata = ModelMetadata(name="HS4Final.bom", version="final-model-v2", repository="https://github.com/davidsonny-sketch/fta-oda-hs4-model", source_commit="ac8de2faeababe94af4160a22ed98a871de43cc9", integration_status=IntegrationStatus.PROTOTYPE)

    def execute(self, payload):
        result = _raw_model().bom(payload.composition)
        records = [_raw_record(row) for row in result.to_dict(orient="records")]
        return {"items": records}, [], ["원본 판정상태를 보존합니다. ‘확인 필요’는 자동 확정하지 않습니다."]


@lru_cache(maxsize=1)
def _rvc_engine():
    source = _source_dir("FTA_RVC_SOURCE_DIR")
    engine_path = source / "engine.py"
    if not engine_path.exists():
        raise AdapterNotConnected("RVC engine.py를 찾을 수 없습니다.")
    spec = importlib.util.spec_from_file_location("fta_platform_rvc_engine", engine_path)
    if spec is None or spec.loader is None:
        raise AdapterNotConnected("RVC engine.py를 로드할 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as exc:
        raise AdapterNotConnected(f"RVC 의존성이 없습니다: {exc}") from exc
    return module


@lru_cache(maxsize=1)
def _rvc_history():
    source = _source_dir("FTA_RVC_SOURCE_DIR")
    path = Path(os.getenv("FTA_RVC_HISTORY_PATH", str(source / "data" / "scenario_B.csv")))
    if not path.exists():
        raise AdapterNotConnected(f"RVC 가격 이력 파일이 없습니다: {path}")
    return _rvc_engine().read_history(path)


class VNMAdapter(ModelAdapter):
    module = "vnm"

    def __init__(self, input_schema):
        self.input_schema = input_schema
        self.metadata = ModelMetadata(name="RVC-Prediction engine", version="main", repository="https://github.com/jonghwa371/RVC-Prediction", source_commit="641d7fa16994e8eedf663abea0cd7142e1e8b1af", integration_status=IntegrationStatus.PROTOTYPE)

    def execute(self, payload):
        if payload.fob is None:
            raise AdapterNotConnected("RVC 시뮬레이션에는 fob, BOM 비용, 원산지 지위가 필요합니다.")
        engine = _rvc_engine()
        bom = pd.DataFrame(payload.bom)
        required = {"material_id", "material_name", "cost_krw", "status"}
        if not required.issubset(bom.columns):
            raise ValueError(f"BOM 필수 필드가 없습니다: {sorted(required - set(bom.columns))}")
        ids = tuple(bom.loc[(bom.status.ne("원산지 확인")) & (bom.cost_krw.astype(float) > 0), "material_id"].astype(str))
        forecasts = engine.forecast_materials(_rvc_history(), list(ids), payload.months)
        output = engine.simulate(bom, forecasts, payload.fob, payload.months, payload.n_sim, payload.seed, payload.threshold)
        for key in ("monthly", "materials"):
            if isinstance(output.get(key), pd.DataFrame):
                output[key] = output[key].to_dict(orient="records")
        output["forecasts"] = [{key: value.tolist() if hasattr(value, "tolist") else value for key, value in row.items() if key != "residuals"} for row in forecasts]
        return output, [], ["RVC 위험 예측은 통계적 시뮬레이션이며 법적 원산지 충족 판정이 아닙니다.", "원본 scenario_B 데이터는 데모 이력일 수 있으므로 기업 가격 데이터 검증이 필요합니다."]
