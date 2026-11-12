# Existing Model Registry

This file is the source of truth for model integration status. Update it only after inspecting the actual source repository and testing the adapter.

| Module | Source repository | Current platform status | Notes |
|---|---|---|---|
| Finished-product HS4 | https://github.com/lin1118-code/HS-complete-product | Prototype adapter | Experiment 39 fixed operating setting: `top3_mean`, `max`, `0.5`, `0.5`; source commit `7cb3107d448bc6ed3324944e75d951976766e994`. It needs an external source checkout through `FTA_FINISHED_HS39_SOURCE_DIR`; no source data or embeddings are committed here. Fixed36 LOPO Macro-F1 is 0.713810; Fold-tuned LOPO Macro-F1 is 0.774929 and is not the operating score. |
| Raw-material HS4 | https://github.com/davidsonny-sketch/fta-oda-hs4-model | Source inspected; integration pending | Notebook: `원재료 HS4 판정 모델 (최종).ipynb`; uses `HS4Final.one()` and `HS4Final.bom()`; pulls `00_setup.py`, `hs4_final.py`, `origin_check.py` and data from Google Drive at runtime. HS4 top-1~3 plus decision status; human review required for low-confidence/uncertain cases. Need resolve Drive/runtime data access before production adapter. |
| VNM analysis | https://github.com/jonghwa371/RVC-Prediction | Pending / disconnected | Registered contract placeholder only. No model output is generated until the source and required price history are available. |
| CTH/RVC origin evaluation | Platform rules engine | Scaffold / unverified | Rules are stored as unverified by the API. Results remain insufficient-information until the rule and inputs are verified. |

## Raw-material HS4 model findings

- Source repository default branch: `main`; inspected tree at commit `cff8564b0a3da4db4b009e57df77feb09fe13d10`.
- The repository contains a README and one Colab notebook; it does not contain the runtime Python modules or model data.
- Notebook setup authenticates Google Colab user access, reads `00_setup.py` from a Google Drive folder, then downloads `origin_check.py` and `hs4_final.py` and initializes `HS4Final('/content/rawmodel')`.
- Public notebook interface: `model.one(name)` for one ingredient and `model.bom(composition)` for a comma-separated ingredient list.
- Output fields include input name, matched Korean name, matched English INCI, name matching status, HS4 ranks 1–3, and decision status.
- Notebook reports: cross-validation 605 items accuracy 0.896 / macro-F1 0.782 / top-3 0.954; holdout A 92 accuracy 0.837 / macro-F1 0.611 / top-3 0.891; actual ingredient test B 110 accuracy 0.836 / macro-F1 0.752 / top-3 0.882. The notebook itself notes some evaluation optimism and human review for `확인 필요` cases. These are owner-reported notebook results, not independently reproduced here.
- Important runtime dependency: RDKit installation, Google Colab authentication, Google Drive API, plus the private/shared Drive data files. Do not assume this can run locally or in a server until access and deployment packaging are clarified.

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

## Runtime status

The platform registry currently exposes `finished_product_hs`, `raw_material_hs`, and `vnm`. The finished-product module is a prototype with its experiment-39 source commit pinned in platform metadata. It returns `not_connected` until an external source checkout and the required runtime dependency are supplied; it never returns fabricated candidates. The other two modules also return `not_connected` without fabricated outputs. Registry metadata and each run envelope expose integration state, source type, timestamps, warnings, and model version fields.
