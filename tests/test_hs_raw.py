"""원재료 HS4 어댑터 시험
- 계약 시험: 가짜 모델로 출력 형식·오류 처리 확인(원본 없이도 실행)
- 실제 모델 시험: external/fta-oda-hs4-model 이 있을 때만 실행"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.models.hs_raw import adapter as A
from backend.routers import hs_raw


class FakeModel:
    def one(self, name):
        return {"입력": name, "찾은 이름(국문)": name, "찾은 이름(영문 INCI)": "X", "이름 찾기": "식약처 일치",
                "HS4 1순위": "2905", "HS4 2순위": "2909", "HS4 3순위": "2906", "판정상태": "자동 확정(분자 구조 규칙)"}

    def bom(self, text):
        rows = [self.one(n.strip()) for n in text.split(",")]
        rows[-1]["판정상태"] = "확인 필요(반제품·베이스 의심)"
        return pd.DataFrame(rows)


@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    app = FastAPI(); app.include_router(hs_raw.router)   # 완제품 모델(sentence-transformers) 없이 원재료 라우터만 시험
    hs_raw.get_adapter.cache_clear()
    monkeypatch.setattr(hs_raw, "get_adapter", lambda: A.RawMaterialHS4Adapter(model=FakeModel()))
    return TestClient(app)


def test_predict_contract(client):
    r = client.post("/api/hs/raw/predict", json={"name": "글리세린"})
    assert r.status_code == 200
    j = r.json()["result"]
    assert j["hs4"] == "2905" and j["hs4_candidates"] == ["2905", "2909", "2906"]
    assert j["review_required"] is False and j["semi_product_suspected"] is False


def test_bom_summary(client):
    j = client.post("/api/hs/raw/bom", json={"ingredients": "정제수, 글리세린, 크림 베이스"}).json()
    assert j["summary"] == {"count": 3, "review_required": 1, "semi_product_suspected": 1}


@pytest.mark.parametrize("path,body", [("/api/hs/raw/predict", {"name": " "}), ("/api/hs/raw/bom", {"ingredients": ""})])
def test_empty_input_rejected(client, path, body):
    assert client.post(path, json=body).status_code == 400


def test_missing_source_message(tmp_path):
    with pytest.raises(FileNotFoundError):
        A.RawMaterialHS4Adapter(source_dir=tmp_path)


@pytest.mark.skipif(not (A.SOURCE_DIR / "src" / "standalone.py").exists(), reason="원재료 모델 원본(external/) 없음")
def test_real_model_known_cases():
    ad = A.RawMaterialHS4Adapter()
    expect = {"Ethanol": "2207", "Glycerol": "2905", "나이아신아마이드": "2936", "정제 대두 경화유": "1516", "Bees wax (밀랍)": "1521"}
    for name, hs in expect.items():
        assert ad.predict_one(name)["result"]["hs4"] == hs, name
    assert ad.predict_bom("정제수, 수분크림 베이스")["summary"]["semi_product_suspected"] == 1
