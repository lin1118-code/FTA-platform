import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.platform import ProductInput
from backend.services.repository import PlatformRepository


class ProductHistoryApiTests(unittest.TestCase):
    def test_saved_product_and_history_are_listable_without_mutating_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = PlatformRepository(str(Path(temp_dir) / "fixture.sqlite3"))
            repository.initialize()
            product = repository.create_product(ProductInput(product_name="Test moisturizer"))
            record = {
                "analysis_id": "analysis-fixture",
                "product_id": product.product_id,
                "agreement_code": "KOREA_VIETNAM",
                "as_of_date": date(2026, 11, 13).isoformat(),
                "status": "insufficient_information",
                "steps": {},
                "results": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            repository.save_analysis(record["analysis_id"], product.product_id, record["status"], record)

            from backend.routers import platform as platform_router
            with patch.object(platform_router, "repository", repository):
                client = TestClient(app)
                products = client.get("/api/products")
                history = client.get(f"/api/products/{product.product_id}/analyses")

            self.assertEqual(products.status_code, 200)
            self.assertEqual(products.json()[0]["product_id"], product.product_id)
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json()[0]["analysis_id"], "analysis-fixture")
            self.assertEqual(repository.get_product(product.product_id).product_name, "Test moisturizer")


if __name__ == "__main__":
    unittest.main()
