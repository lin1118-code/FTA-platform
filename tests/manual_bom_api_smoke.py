"""Manual API smoke test for BOM persistence; run against an isolated test database."""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("FTA_BOM_SMOKE_BASE_URL", "http://127.0.0.1:8014")


def request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    with urlopen(Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method), timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> None:
    _, openapi = request("GET", "/openapi.json")
    supports_price_unit = "unit_price_unit" in openapi["components"]["schemas"]["BOMLineInput"]["properties"]
    product_status, product = request("POST", "/api/products", {"product_name": "BOM API smoke product"})
    product_id = product["product_id"]
    bom_status, bom = request("PUT", f"/api/products/{product_id}/bom", {
        "lines": [{
            "material_name": "Glycerin",
            "quantity": 2.5,
            "unit": "kg",
            "unit_price_unit": "kg",
            "unit_value": 12000,
            "origin_country": "UNKNOWN",
            "origin_confirmed": False,
        }]
    })
    get_status, saved = request("GET", f"/api/products/{product_id}")
    line = saved["bom"][0]
    assert product_status == 201
    assert bom_status == 200
    assert get_status == 200
    assert line["unit_value"] == 12000
    assert line["origin_country"] == "UNKNOWN"
    assert line["origin_confirmed"] is False
    if supports_price_unit:
        assert line["unit_price_unit"] == "kg"
        try:
            request("PUT", f"/api/products/{product_id}/bom", {
                "lines": [{
                    "material_name": "Invalid unit example",
                    "quantity": 1,
                    "unit": "kg",
                    "unit_price_unit": "g",
                    "unit_value": 10,
                }]
            })
            raise AssertionError("mismatched units were accepted")
        except HTTPError as error:
            assert error.code == 422
    output = {
        "product_status": product_status,
        "bom_status": bom_status,
        "get_status": get_status,
        "saved_line": line,
        "calculated_input_amount_krw": line["quantity"] * line["unit_value"],
        "unit_price_unit_schema_supported": supports_price_unit,
        "mismatched_unit_status": 422 if supports_price_unit else "not checked: running server schema is older",
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"BOM API smoke test failed: {error}", file=sys.stderr)
        raise
