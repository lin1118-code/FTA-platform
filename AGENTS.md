# Codex project instructions

## Product goal
This repository builds an integrated FTA decision-support platform for SME exporters, initially focused on cosmetics exported to Vietnam. It is NOT an HS-code-classification-only application.

The platform must combine product/BOM inputs, HS classification, rules of origin, cost and tariff analysis, supply-chain risk, and an integrated decision report.

## Main capabilities
1. Finished-product HS classification model
2. Raw-material HS classification model
3. Rules-of-origin evaluation, including CTH and RVC where applicable
4. VNM and supply-chain volatility/risk analysis
5. Alternative raw-material scenario analysis
6. Tariff savings, evidence/documentation cost, and trade-cost analysis
7. Integrated FTA utilization recommendation and report

## Architecture principles
- Keep each existing ML/statistical model independent and reusable.
- Integrate models through adapters with explicit input/output contracts.
- Do not copy, rewrite, retrain, or modify an existing model's source without a clear reason and approval.
- Do not treat rules-based legal determinations (e.g. CTH/RVC) as ML predictions.
- Distinguish real model outputs from mock/demo outputs.
- Never invent eligibility, tariff, origin, or model-confidence results.
- Preserve source repositories and record the exact repository/commit/version used by each adapter.
- Do not commit model weights, generated embeddings, private BOMs, credentials, or secrets.
- Prefer small, testable changes. Run tests and report what was actually executed.

## Existing finished-product HS model
Source repository: https://github.com/lin1118-code/HS-complete-product
Model experiment: `18_final_model_comparison.ipynb`
Leading candidate: `SBERT_product_plus_ruling_stopword`

This is ONE component of the platform. The existing platform-side code under `backend/models/hs_finished/` is an integration prototype, not the platform's main product.

## Working procedure
1. Inspect the full repository and these docs before changing code.
2. Propose an architecture and implementation plan before broad edits.
3. Identify which parts are real, mock, or pending integration.
4. Preserve the existing model implementation and create adapters around it.
5. Implement the shared workflow and orchestration across modules.
6. Add tests for contracts, calculations, and integration boundaries.
7. Summarize changed files, commands run, test outcomes, and unresolved assumptions.

## Scope control
Do not focus exclusively on HS classification. Any work on an individual model must be situated within the end-to-end FTA workflow.
