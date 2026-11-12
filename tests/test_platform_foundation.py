import tempfile
import unittest
from unittest.mock import patch
from datetime import date
from pathlib import Path

from backend.models.registry import ModelRegistry, RawMaterialHSInput
from backend.models.adapters.base import ModelAdapter
from backend.models.hs_finished.model39 import OPERATING_CONFIG, SUPPORTED_HS4
from backend.schemas.platform import (
    AgreementRuleInput,
    BOMLineInput,
    IntegrationStatus,
    ModelMetadata,
    ProductInput,
    RunStatus,
)
from backend.services.origin import evaluate_origin
from backend.services.analysis import AnalysisService
from backend.services.repository import PlatformRepository


class PlatformFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = PlatformRepository(str(Path(self.temp_dir.name) / "test.sqlite3"))
        self.repository.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registry_distinguishes_prototype_and_unconnected_models(self):
        registry = ModelRegistry()
        modules = {item.name: item.integration_status for item in registry.list_models()}
        self.assertEqual(modules["HS4_Direct_Plus_Exclusion_Fixed36"], IntegrationStatus.PROTOTYPE)
        self.assertEqual(modules["HS4Final.one"], IntegrationStatus.PROTOTYPE)
        from backend.models.adapters.external_models import _raw_model
        _raw_model.cache_clear()
        with patch.dict("os.environ", {"FTA_RAW_HS4_SOURCE_DIR": ""}):
            result = registry.run("raw_material_hs", {"material_name": "정제수"})
            invalid = registry.run("raw_material_hs", {})
        _raw_model.cache_clear()
        self.assertEqual(result.status, RunStatus.NOT_CONNECTED)
        self.assertIsNone(result.source)
        self.assertIsNone(result.result)
        self.assertEqual(invalid.status, RunStatus.FAILED)
        self.assertIn("입력 검증 실패", invalid.warnings[0])

    def test_finished_hs39_has_frozen_operating_scope_and_contract_fields(self):
        self.assertEqual(SUPPORTED_HS4, ("3304", "3305", "3306", "3307", "3401"))
        self.assertEqual(OPERATING_CONFIG["product_aggregation"], "top3_mean")
        self.assertEqual(OPERATING_CONFIG["product_weight"], 1.0)
        self.assertEqual(OPERATING_CONFIG["ruling_aggregation"], "top3_mean")
        self.assertEqual(OPERATING_CONFIG["ruling_weight"], 1.0)
        self.assertEqual(OPERATING_CONFIG["direct_aggregation"], "top3_mean")
        self.assertEqual(OPERATING_CONFIG["exclusion_aggregation"], "max")
        self.assertEqual(OPERATING_CONFIG["direct_weight"], 0.5)
        result = ModelRegistry().run("finished_product_hs", {"product_name": "test cream"})
        self.assertEqual(result.model_name, "HS4_Direct_Plus_Exclusion_Fixed36")
        self.assertEqual(result.model_version, "experiment-39-fixed36")
        self.assertIsNotNone(result.timestamp)

    def test_products_and_bom_are_persisted(self):
        product = self.repository.create_product(ProductInput(product_name="보습 크림"))
        lines = self.repository.replace_bom(product.product_id, [
            BOMLineInput(material_name="정제수", quantity=2, unit="kg")
        ])
        self.assertEqual(len(lines), 1)
        self.assertEqual(self.repository.get_product(product.product_id).product_name, "보습 크림")
        self.assertEqual(self.repository.get_bom(product.product_id)[0].material_name, "정제수")

    def test_product_hs_recommendation_stays_unconfirmed_until_user_confirms(self):
        product = self.repository.create_product(ProductInput(product_name="Cream"))
        candidate = self.repository.update_product(
            product.product_id,
            ProductInput(product_name="Cream", hs_code="3304", hs_code_confirmed=False),
        )
        self.assertEqual(candidate.hs_code, "3304")
        self.assertFalse(candidate.hs_code_confirmed)
        confirmed = self.repository.update_product(
            product.product_id,
            ProductInput(product_name="Cream", hs_code="3304", hs_code_confirmed=True),
        )
        self.assertTrue(confirmed.hs_code_confirmed)

    def test_api_supplied_rule_cannot_be_marked_verified(self):
        product = self.repository.create_product(ProductInput(
            product_name="보습 크림", hs_code="330499", hs_code_confirmed=True
        ))
        rule = self.repository.save_rule(AgreementRuleInput(
            agreement_code="TEST", product_hs_code="330499", criterion="CTH",
            effective_from=date(2026, 1, 1), cth_digits=4,
            source_title="unverified test source",
        ))
        assessment = evaluate_origin(self.repository, product, [], "TEST", date(2026, 2, 1))
        self.assertFalse(rule["verified"])
        self.assertEqual(assessment["outcome"], "insufficient_information")

    def test_failed_model_run_does_not_claim_a_model_output_source(self):
        class FailingAdapter(ModelAdapter):
            module = "failing"
            input_schema = RawMaterialHSInput
            metadata = ModelMetadata(name="failing", integration_status=IntegrationStatus.PROTOTYPE)

            def execute(self, payload):
                raise RuntimeError("intentional test failure")

        result = FailingAdapter().run({"material_name": "test"})
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertIsNone(result.source)


    def test_unit_purchase_price_is_preserved_and_rvc_uses_line_total(self):
        product = self.repository.create_product(ProductInput(product_name="BOM price test"))
        saved = self.repository.replace_bom(product.product_id, [
            BOMLineInput(
                material_name="Glycerin", quantity=2.5, unit="kg",
                unit_price_unit="kg", unit_value=12000,
                origin_country="KR", is_originating=True, origin_confirmed=True,
            )
        ])
        self.assertEqual(saved[0].unit_value, 12000)
        self.assertEqual(saved[0].unit_price_unit, "kg")
        persisted = self.repository.get_bom(product.product_id)
        self.assertEqual(persisted[0].unit_value, 12000)
        self.assertEqual(persisted[0].unit_price_unit, "kg")
        rvc_bom = AnalysisService._to_rvc_bom(persisted)
        self.assertEqual(rvc_bom[0]["cost_krw"], 30000)

    def test_purchase_price_unit_must_match_quantity_unit(self):
        with self.assertRaises(ValueError):
            BOMLineInput(
                material_name="Glycerin", quantity=1, unit="kg",
                unit_price_unit="g", unit_value=12000,
            )


if __name__ == "__main__":
    unittest.main()
