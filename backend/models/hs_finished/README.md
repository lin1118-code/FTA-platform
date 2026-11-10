# 완제품 HS 코드 예측 모델

18번 최종 비교 실험에서 선택한 `SBERT_product_plus_ruling_stopword` 검색 모델을 운영용 전체 사례 인덱스로 구성합니다.

## 1. 의존성 설치

```bash
pip install pandas numpy sentence-transformers kiwipiepy fastapi
```

## 2. 운영 인덱스 생성

프로젝트 루트에서 실행합니다.

```bash
python -m backend.models.hs_finished.build_index
```

처음 실행할 때 `intfloat/multilingual-e5-base` 모델을 다운로드합니다. 생성 결과는 `backend/models/hs_finished/artifacts/`에 저장됩니다.

- `metadata.csv`: 검색 대상 사례와 제품 속성
- `embeddings.npy`: 전체 사례의 정규화 임베딩
- `config.json`: 모델 및 전처리 설정

아티팩트는 재생성할 수 있으므로 Git에 올리지 않는 것을 권장합니다.

## 3. API 연결

FastAPI 앱에서 다음과 같이 라우터를 등록합니다.

```python
from backend.routers.hs_finished import router as hs_finished_router
app.include_router(hs_finished_router)
```

## 4. 요청 예시

```json
{
  "product_name": "보습 크림",
  "ingredients_kr": "정제수, 글리세린",
  "ingredients_en": "Water, Glycerin",
  "form_packaging": "크림 형태, 용기 포장",
  "intended_use": "피부 보습",
  "top_k": 3
}
```

`POST /api/hs/finished/predict`로 요청하면 Top-1 및 서로 다른 HS 코드 기준 Top-3 후보, 유사도, 근거가 된 과거 판정요지를 반환합니다.

## 주의

18번 실험의 평가는 144개 사례에 대한 4-Fold 교차검증 결과입니다. 운영 인덱스는 원본 사례 데이터 전체로 다시 생성합니다. 평가 결과와 운영 예측 성능을 동일시하지 않습니다.
