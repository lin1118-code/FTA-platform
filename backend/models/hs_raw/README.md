# 원재료 HS4 모델 어댑터

- 원본 모델: https://github.com/davidsonny-sketch/fta-oda-hs4-model (코드·데이터는 원본 저장소에 있고 여기에는 복사하지 않음)
- 준비: `bash backend/models/hs_raw/fetch_source.sh` → `external/fta-oda-hs4-model`에 고정 커밋(`adapter.py`의 `SOURCE_REF`)을 받음
- 의존성: `requirements.txt`의 scikit-learn, scipy, rdkit
- API
  - `POST /api/hs/raw/predict` `{"name": "나이아신아마이드"}` → 원료 1개
  - `POST /api/hs/raw/bom` `{"ingredients": "정제수, 글리세린, ..."}` → 성분표 전체
- 출력: `docs/architecture.md` 4장 표준 봉투 — `module`(raw_material_hs), `status`, `source`(real_model), `model_name`, `model_version`(원본 저장소@커밋), `input_summary`, `result`, `evidence`(원료별 판정 단계), `warnings`(확인 필요 원료 + 안내문)
  - `result`(원료 1개): `hs4`, `hs4_candidates`(1~3순위), `status`, `review_required`, `semi_product_suspected`, 이름 찾기 결과
  - `result`(성분표): `items`(원료별 위 항목), `summary`(개수·확인 필요·반제품 의심)
- 연결 상태 확인: `GET /api/modules` → `raw_material_hs`가 `integrated`면 사용 가능, `source_missing`이면 fetch_source.sh 실행
- 성능(원본 저장소 `validation/README.md`): 숨김 검증용 291행 정확도 0.864 / Macro-F1 0.712, 시험 A 0.870 / 0.658, 시험 B 0.900 / 0.843
- 원산지(CTH·RVC) 판정은 규칙 엔진의 일이며 이 어댑터는 원료 HS 후보만 냄
