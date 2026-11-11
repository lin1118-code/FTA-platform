# Existing Model Registry

This file is the source of truth for model integration status. Update it only after inspecting the actual source repository and testing the adapter.

| Module | Source repository | Current platform status | Notes |
|---|---|---|---|
| Finished-product HS | https://github.com/lin1118-code/HS-complete-product | Prototype adapter | Notebook 18 candidate: SBERT_product_plus_ruling_stopword |
| Raw-material HS4 | https://github.com/davidsonny-sketch/fta-oda-hs4-model | Adapter on branch `hyunsoo/raw-material-adapter` (not merged) | Source pinned to `ac8de2f` on branch `hyunsoo/final-model-v2` (v2: HS nomenclature lexicon). Runs without Google Drive via `src/standalone.py` + `data/`. API `/api/hs/raw/predict`, `/api/hs/raw/bom`. Outputs HS4 top-1~3, status, review_required. |
| VNM analysis | To be supplied / confirm repository | Pending | Clarify whether forecasting, volatility, or risk score is the intended output |
| CTH/RVC origin evaluation | Platform rules engine | Pending | Rules-based calculation, not an ML model |

## Raw-material HS4 model findings

- Source repository default branch: `main`; inspected tree at commit `cff8564b0a3da4db4b009e57df77feb09fe13d10`.
- The repository contains a README and one Colab notebook; it does not contain the runtime Python modules or model data.
- Notebook setup authenticates Google Colab user access, reads `00_setup.py` from a Google Drive folder, then downloads `origin_check.py` and `hs4_final.py` and initializes `HS4Final('/content/rawmodel')`.
- Public notebook interface: `model.one(name)` for one ingredient and `model.bom(composition)` for a comma-separated ingredient list.
- Output fields include input name, matched Korean name, matched English INCI, name matching status, HS4 ranks 1–3, and decision status.
- Notebook reports: cross-validation 605 items accuracy 0.896 / macro-F1 0.782 / top-3 0.954; holdout A 92 accuracy 0.837 / macro-F1 0.611 / top-3 0.891; actual ingredient test B 110 accuracy 0.836 / macro-F1 0.752 / top-3 0.882. The notebook itself notes some evaluation optimism and human review for `확인 필요` cases. These are owner-reported notebook results, not independently reproduced here.
- Important runtime dependency: RDKit installation, Google Colab authentication, Google Drive API, plus the private/shared Drive data files. Do not assume this can run locally or in a server until access and deployment packaging are clarified.

## Raw-material HS4 adapter (2026-11-11, branch `hyunsoo/raw-material-adapter`)

- Integration method: thin adapter that imports the source repository from `external/fta-oda-hs4-model` (fetched by `backend/models/hs_raw/fetch_source.sh` at the pinned commit; `external/` is git-ignored). No model code or data copied into the platform.
- The source branch adds `data/` (sheet1 export with per-row label source, MFDS ingredient DB, PubChem structures, label corrections) and `src/standalone.py`, removing the Colab/Drive runtime dependency noted above.
- Owner-reported v2 metrics (source `validation/README.md`): held-out design split 291 rows accuracy 0.864 / macro-F1 0.712; test A 92 rows 0.870 / 0.658; test B 110 actual ingredients 0.900 / 0.843 (Colab).
- Tests: `tests/test_hs_raw.py` (contract tests with a fake model + real-model known cases when `external/` exists). Executed locally: 6 passed.
- Pending: merge source branch to `main` and re-pin `SOURCE_REF` to that commit; decide whether CTH evaluation consumes `hs4_candidates` directly.

## Integration checklist per model

- [ ] Confirm source repository and default branch
- [ ] Inspect README, dependencies, input schema, output schema, and license/data constraints
- [ ] Identify a stable commit or release
- [ ] Decide integration method (package, API, submodule, or copied adapter only)
- [ ] Implement adapter without changing model internals
- [ ] Add input validation and normalized output contract
- [ ] Add unit/integration tests
- [ ] Record model version and tested status here

## Repository integration policy

Do not add Git submodules automatically. First inspect repository ownership, access, dependencies, and whether the source project is intended to be consumed as a package or service. Prefer a thin adapter and pinned version. Avoid duplicating large model artifacts in the platform repository.
