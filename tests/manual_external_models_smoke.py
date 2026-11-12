"""Manual smoke test for externally checked-out model repositories.

Run with FTA_RAW_HS4_SOURCE_DIR and FTA_RVC_SOURCE_DIR configured.
This file is intentionally not discovered by unittest.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from backend.models.registry import ModelRegistry


def main() -> None:
    registry = ModelRegistry()

    raw = registry.run("raw_material_hs", {"material_name": "나이아신아마이드"})
    print("RAW_ONE")
    print(raw.model_dump_json(indent=2))

    raw_bom = registry.run(
        "raw_material_hs_bom",
        {"composition": "정제수, 글리세린, 나이아신아마이드"},
    )
    print("RAW_BOM")
    print(raw_bom.model_dump_json(indent=2))

    rvc_source = Path(os.environ["FTA_RVC_SOURCE_DIR"])
    history = pd.read_csv(rvc_source / "data" / "scenario_B.csv", dtype={"material_id": str})
    chosen = history.loc[history["rvc_treatment"].eq("non_originating")].drop_duplicates("material_id").iloc[0]
    payload = {
        "bom": [{
            "material_id": str(chosen.material_id),
            "material_name": str(chosen.material_name),
            "cost_krw": float(chosen.bom_base_cost_krw),
            "status": "비원산지",
        }],
        "fob": float(chosen.bom_base_cost_krw) * 3,
        "months": 2,
        "n_sim": 100,
        "seed": 7,
        "threshold": 40,
    }
    vnm = registry.run("vnm", payload)
    print("VNM_PAYLOAD", json.dumps(payload, ensure_ascii=False))
    print("VNM")
    print(vnm.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
