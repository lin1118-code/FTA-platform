"""Manual E5 and model-39 operating-inference smoke test.

Run with FTA_FINISHED_HS39_SOURCE_DIR set to the read-only model checkout.
This file is intentionally not discovered by unittest.
"""
from __future__ import annotations

from backend.models.registry import ModelRegistry


def main() -> None:
    response = ModelRegistry().run(
        "finished_product_hs",
        {
            "product_name": "보습 페이셜 크림",
            "ingredients_kr": "정제수, 글리세린, 나이아신아마이드",
            "form_packaging": "크림, 튜브",
            "intended_use": "피부 보습용 화장품",
            "top_k": 3,
        },
    )
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
