# Existing Model Registry

This file is the source of truth for model integration status. Update it only after inspecting the actual source repository and testing the adapter.

| Module | Source repository | Current platform status | Notes |
|---|---|---|---|
| Finished-product HS | https://github.com/lin1118-code/HS-complete-product | Prototype adapter | Notebook 18 candidate: SBERT_product_plus_ruling_stopword |
| Raw-material HS | To be supplied / confirm repository | Pending | Do not invent a source repository or model behavior |
| VNM analysis | To be supplied / confirm repository | Pending | Clarify whether forecasting, volatility, or risk score is the intended output |
| CTH/RVC origin evaluation | Platform rules engine | Pending | Rules-based calculation, not an ML model |

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
