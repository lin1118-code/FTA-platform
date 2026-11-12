# FTA Platform

중소 화장품 수출기업의 FTA 활용 의사결정을 지원하는 통합 플랫폼. 초기 적용 시장은 베트남이다.

**HS 코드 판정은 여러 분석 모듈 중 하나이며, 프로젝트의 최종 목적은 HS 코드 예측 자체가 아니다.** 제품·BOM을 입력하면 HS 분류, 원산지 기준, 관세 및 비용, 공급망 리스크를 연계 분석해 FTA 활용 가능성과 경제성을 종합적으로 판단하는 것이 목표다.

## 주요 기능

- 기업·제품·BOM 입력 및 관리
- 완제품 및 원재료 HS 코드 판정 모듈
- 협정별 원산지 결정기준 조회 및 CTH/RVC 판정
- VNM 변동성 및 공급망 리스크 분석
- 대체 원재료 시나리오 비교
- 관세 절감액·증빙비용·거래비용 분석
- 통합 FTA 활용 의사결정 및 보고서

## 기술 방향

- Frontend: React
- Backend: Python FastAPI
- Data processing: Pandas / NumPy
- Database: 초기 개발 단계에서 SQLite, 이후 PostgreSQL 검토
- Model integration: 독립 모델 + adapter/service + workflow orchestration

## 개발 원칙

- 기존 모델 저장소와 학습 코드를 최대한 보존한다.
- 각 모델을 공통 adapter 계약으로 연결한다.
- 모델 출력, 규칙 기반 계산, Mock 결과를 명확히 구분한다.
- CTH/RVC는 협정별 규칙과 근거 데이터에 기반해 계산한다.
- 결과에는 입력, 데이터 버전, 계산 근거, 가정 및 누락 정보를 남긴다.
- 모델 가중치, 임베딩, 기업 기밀 BOM, 비밀키는 Git에 커밋하지 않는다.

## 프로젝트 문서

- [Codex 개발 지침](AGENTS.md)
- [전체 아키텍처](docs/architecture.md)
- [기존 모델 연결 현황](docs/model-registry.md)
- [완제품 HS 모델 어댑터 프로토타입](backend/models/hs_finished/README.md)

## 기존 모델 저장소

- 완제품 HS: https://github.com/lin1118-code/HS-complete-product
- 원재료 HS: https://github.com/davidsonny-sketch/fta-oda-hs4-model
- VNM 분석: 저장소 확인 필요

## 현재 상태

통합 아키텍처 및 개별 모델 연결 기반을 구성하는 초기 단계. 개별 모듈의 실제 연동 여부는 model registry에서 확인한다.
