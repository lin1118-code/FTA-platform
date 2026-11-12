# FTA Platform Architecture

## 1. Product definition

FTA Platform is an integrated decision-support system for small and medium-sized exporters. The initial use case is Korean cosmetics exporters evaluating exports to Vietnam and the use of an applicable FTA.

The product's central outcome is not an HS code by itself. It is a defensible, evidence-backed assessment of whether and how an exporter can use an FTA, what economic benefit may result, and what origin, sourcing, cost, or documentation risks must be addressed.

## 2. End-to-end user journey

1. Company and export-market setup
2. Finished product and BOM entry (manual or spreadsheet upload)
3. Finished-product and raw-material HS classification suggestions
4. Agreement/product-specific rules-of-origin lookup
5. CTH/RVC and other applicable origin-rule evaluation
6. Tariff savings and cost-benefit analysis
7. VNM, sourcing, and supply-chain risk analysis
8. Alternative material/scenario comparison
9. Integrated recommendation, evidence checklist, and downloadable report

## 3. Logical architecture

```text
Frontend (React)
  ├── Company / Product / BOM workspace
  ├── HS classification results
  ├── Origin-rule assessment
  ├── Cost & tariff analysis
  ├── Risk & scenario analysis
  └── Integrated report
          |
          v
Backend API (FastAPI)
  ├── Workflow / orchestration service
  ├── Product & BOM service
  ├── Model registry and adapters
  │     ├── Finished-product HS adapter
  │     ├── Raw-material HS adapter
  │     └── VNM model adapter
  ├── Rules engine
  │     ├── Agreement and product-specific rule lookup
  │     ├── CTH evaluator
  │     └── RVC evaluator
  ├── Tariff and cost analysis service
  ├── Risk and scenario service
  └── Report service
          |
          v
Data layer
  ├── Company / product / BOM records
  ├── HS and origin-rule reference data
  ├── Model metadata and run history
  └── Analysis results and evidence trace
```

## 4. Model integration contract

Each model is wrapped by a platform adapter. The adapter must:
- validate required inputs;
- map platform field names to the model's original input schema;
- invoke the model without changing its core implementation;
- normalize output into a documented response schema;
- expose model name, version/source commit, execution status, and evidence;
- label demo/mock output explicitly.

Suggested normalized envelope:

```json
{
  "module": "finished_product_hs",
  "status": "success",
  "source": "real_model",
  "model_name": "SBERT_product_plus_ruling_stopword",
  "model_version": "record exact commit or release",
  "input_summary": {},
  "result": {},
  "evidence": [],
  "warnings": []
}
```

Use `source` values such as `real_model`, `mock`, and `rules_engine`. Do not label similarity scores as calibrated probabilities.

## 5. Rules versus models

HS classification and VNM analysis may use ML/statistical models where appropriate. CTH, RVC, and agreement-specific origin requirements must be evaluated using explicit rules and traceable source data. A model can assist with extraction or recommendations but must not silently replace the legal/rules evaluation.

Every origin result should retain:
- agreement and effective date;
- product HS code and rule version;
- required origin criterion;
- input BOM and material classifications;
- calculation details;
- missing evidence and assumptions;
- outcome: eligible / not eligible / insufficient information.

## 6. Data and auditability

Keep raw user inputs, normalized inputs, model outputs, rules version, calculation details, and report generation metadata traceable. Avoid storing sensitive business data unnecessarily. Never commit real company BOMs or credentials.

## 7. Implementation sequence

Phase 1: inspect existing code and repositories; settle data contracts and project structure.
Phase 2: implement product/BOM workflow and module registry/adapters.
Phase 3: connect existing finished-product HS, raw-material HS, and VNM models independently.
Phase 4: implement origin-rule data and CTH/RVC rule engine.
Phase 5: add tariff/cost/risk/scenario orchestration.
Phase 6: frontend workflow, integrated report, and end-to-end tests.

Do not assume that every module is already available. Maintain a registry showing integrated, prototype, pending, or mock status.

## 8. Initial backend foundation

The initial backend now separates:

- `backend/schemas/`: shared product, BOM, rule, analysis, and model-run contracts.
- `backend/models/registry.py` and `backend/models/adapters/`: model metadata, input validation, normalized run status, and adapter invocation. The existing finished-product retriever remains in place and is called through a thin adapter.
- `backend/services/`: SQLite persistence, analysis orchestration, and conservative origin-rule evaluation.
- `backend/routers/`: API endpoints; the legacy finished-HS route remains available.

SQLite stores product/BOM records, agreement rules, and analysis snapshots. Configure `FTA_PLATFORM_DB` to choose another database file. The default local data directory is ignored by Git.

Current API routes are `GET /api/models`, `POST /api/products`, `GET /api/products/{product_id}`, `PUT /api/products/{product_id}/bom`, `POST /api/models/{module}/run`, `POST /api/agreement-rules`, `GET /api/agreement-rules`, `POST /api/analyses`, and `GET /api/analyses/{analysis_id}`. Rules submitted through the initial API are always stored as unverified; there is no trusted rule-authoring workflow yet. Thus CTH/RVC outcomes remain `insufficient_information` until verified source data and required inputs are available.

Tariff/cost, supply-chain risk, and alternative-material scenario stages are included in analysis status and explicitly return `not_connected`; this backend foundation does not invent those results. Analysis execution is synchronous in this first version.
