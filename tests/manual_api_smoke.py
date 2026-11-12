"""Manual HTTP smoke test for raw-HS4 and RVC integration.

The server must already be listening on the supplied base URL.
"""
from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8012"


def call(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{BASE_URL}{path}", body, method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with urlopen(request, timeout=90) as response:
        return response.status, json.loads(response.read().decode())


def main() -> None:
    health_status, health = call("GET", "/health")
    raw_status, raw = call("POST", "/api/hs/raw/bom", {
        "composition": "Water, Glycerin, Niacinamide",
    })
    product_status, product = call("POST", "/api/products", {
        "product_name": "API smoke product", "fob_value": 178.5, "fob_currency": "KRW",
    })
    bom_status, _ = call("PUT", f"/api/products/{product['product_id']}/bom", {"lines": [{
        "material_name": "carboxylic acids", "quantity": 1, "unit": "kg",
        "unit_value": 59.5, "currency": "KRW", "rvc_material_id": "CLARA-05",
        "is_originating": False, "origin_confirmed": True,
    }]})
    analysis_status, analysis = call("POST", "/api/analyses", {
        "product_id": product["product_id"], "agreement_code": "TEST", "as_of_date": "2026-11-12",
    })
    summary = {
        "health_http": health_status,
        "health": health["status"],
        "raw_bom_http": raw_status,
        "raw_bom_status": raw["status"],
        "raw_bom_source": raw["source"],
        "raw_bom_items": len(raw["result"]["items"]),
        "raw_bom_results": [
            {"input": item["input"], "top1": item["candidates"][0]["hs4"],
             "decision_status": item["decision_status"]}
            for item in raw["result"]["items"]
        ],
        "product_http": product_status,
        "bom_http": bom_status,
        "analysis_http": analysis_status,
        "analysis_status": analysis["status"],
        "finished_status": analysis["steps"]["finished_product_hs"],
        "raw_status": analysis["steps"]["raw_material_hs"],
        "rvc_status": analysis["steps"]["vnm"],
        "rvc_source": analysis["results"]["vnm"]["source"],
        "rvc_available": analysis["results"]["vnm"]["result"]["available"],
        "rvc_current_rvc": analysis["results"]["vnm"]["result"]["current_rvc"],
        "rvc_monthly": analysis["results"]["vnm"]["result"].get("monthly", []),
        "origin_status": analysis["steps"]["origin"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
