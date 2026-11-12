# Existing Model Registry

This file is the source of truth for model integration status. Update it only after inspecting the actual source repository and testing the adapter.

| Module | Source repository | Current platform status | Notes |
|---|---|---|---|
| Finished-product HS4 | https://github.com/lin1118-code/HS-complete-product | Prototype adapter | Experiment 39 fixed operating setting: `top3_mean`, `max`, `0.5`, `0.5`; source commit `7cb3107d448bc6ed3324944e75d951976766e994`. It needs an external source checkout through `FTA_FINISHED_HS39_SOURCE_DIR`; no source data or embeddings are committed here. Fixed36 LOPO Macro-F1 is 0.713810; Fold-tuned LOPO Macro-F1 is 0.774929 and is not the operating score. |
| Raw-material HS | To be supplied / confirm repository | Pending / disconnected | Registered contract placeholder only. No model output is generated. |
| VNM analysis | To be supplied / confirm repository | Pending / disconnected | Registered contract placeholder only. No model output is generated. Clarify expected output semantics before integration. |
| CTH/RVC origin evaluation | Platform rules engine | Scaffold / unverified | Rules are stored as unverified by the API. Results remain insufficient-information until the rule and inputs are verified. |

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
