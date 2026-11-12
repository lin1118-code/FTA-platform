import json
import sqlite3
import tempfile
from contextlib import closing
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.platform import (
    AgreementRuleInput,
    BOMLineInput,
    FobCostSimulationRequest,
    IntegrationStatus,
    ModelMetadata,
    ModelRunResult,
    ModelSource,
    ProductInput,
    RunStatus,
)
from backend.services.analysis import AnalysisService
from backend.services.fta_simulation import recommend_origin_evidence, simulate_fob_costs
from backend.services.origin import evaluate_origin
from backend.services.repository import PlatformRepository


class FobEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = PlatformRepository(str(Path(self.temp_dir.name) / "platform.sqlite3"))
        self.repository.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_verified_rvc_rule(self, agreement="TEST", hs="3304", threshold=32.5):
        saved = self.repository.save_rule(AgreementRuleInput(
            agreement_code=agreement,
            product_hs_code=hs,
            criterion="RVC",
            effective_from=date(2026, 1, 1),
            rvc_formula="build_down",
            rvc_threshold_percent=threshold,
            source_title="Verified fixture rule",
        ))
        with closing(sqlite3.connect(self.repository.db_path)) as db:
            row = db.execute("SELECT payload FROM agreement_rules WHERE rule_id=?", (saved["rule_id"],)).fetchone()
            payload = json.loads(row[0])
            payload["verified"] = True
            db.execute("UPDATE agreement_rules SET payload=? WHERE rule_id=?", (json.dumps(payload), saved["rule_id"]))
            db.commit()

    def test_fob_cost_simulation_excludes_only_included_freight(self):
        product = self.repository.create_product(ProductInput(product_name="Cream", hs_code="3304", hs_code_confirmed=True))
        self.repository.replace_bom(product.product_id, [
            BOMLineInput(material_name="Unknown", quantity=2, unit="kg", unit_price_unit="kg", unit_value=100),
        ])
        result = simulate_fob_costs(self.repository, FobCostSimulationRequest(
            product_id=product.product_id,
            agreement_code="TEST",
            manufacturing_cost=50,
            packaging_cost=20,
            freight_cost=30,
            freight_included_in_fob=False,
            other_cost=10,
            profit=40,
            scenario_threshold_percent=40,
        ))
        self.assertEqual(result["estimated_fob_krw"], 320)
        self.assertEqual(result["cost_breakdown_krw"]["freight_excluded"], 30)
        self.assertEqual(result["rvc"]["vnm_krw"], 200)
        self.assertAlmostEqual(result["rvc"]["current_rvc_percent"], 37.5)
        self.assertEqual(result["rvc"]["target_source"], "scenario_assumption")

    def test_minimum_evidence_set_tie_breaks_by_smallest_overshoot_then_id(self):
        product = self.repository.create_product(ProductInput(
            product_name="Cream", hs_code="3304", hs_code_confirmed=True,
        ))
        lines = self.repository.replace_bom(product.product_id, [
            BOMLineInput(material_name="A", quantity=1, unit="kg", unit_value=70),
            BOMLineInput(material_name="B", quantity=1, unit="kg", unit_value=65),
            BOMLineInput(material_name="C", quantity=1, unit="kg", unit_value=65),
        ])
        with closing(sqlite3.connect(self.repository.db_path)) as db:
            for line, stable_id in zip(lines, ("a", "b", "c")):
                db.execute("UPDATE bom_lines SET line_id=? WHERE line_id=?", (stable_id, line.line_id))
            db.commit()
        self.add_verified_rvc_rule()
        result = recommend_origin_evidence(
            self.repository, product, self.repository.get_bom(product.product_id),
            "TEST", date(2026, 2, 1), 200,
        )
        self.assertEqual(result["combination_status"], "recommended")
        self.assertEqual([row["material_id"] for row in result["recommended_combination"]], ["b"])
        self.assertEqual(result["target_source"], "verified_agreement_rule")

    def test_unknown_legal_target_never_defaults_to_40_percent(self):
        product = self.repository.create_product(ProductInput(product_name="Cream", hs_code="3304", hs_code_confirmed=True))
        result = recommend_origin_evidence(
            self.repository, product, [], "TEST", date(2026, 2, 1), 100,
        )
        self.assertIsNone(result["target_rvc_percent"])
        self.assertIsNone(result["target_source"])
        self.assertEqual(result["combination_status"], "scenario_threshold_required")

    def test_known_non_originating_material_is_not_a_proof_acquisition_candidate(self):
        product = self.repository.create_product(ProductInput(product_name="Cream", hs_code="3304", hs_code_confirmed=True))
        self.repository.replace_bom(product.product_id, [
            BOMLineInput(
                material_name="Imported material", quantity=1, unit="kg", unit_value=100,
                is_originating=False, origin_confirmed=True,
            ),
        ])
        result = recommend_origin_evidence(
            self.repository, product, self.repository.get_bom(product.product_id),
            "TEST", date(2026, 2, 1), 200, scenario_threshold_percent=40,
        )
        self.assertEqual(result["vnm_krw"], 100)
        self.assertEqual(result["unknown_origin_materials"], [])

    def test_cost_estimate_cannot_support_legal_rvc_determination(self):
        product = self.repository.create_product(ProductInput(product_name="Cream", hs_code="3304", hs_code_confirmed=True))
        self.repository.replace_bom(product.product_id, [
            BOMLineInput(material_name="Unknown", quantity=1, unit="kg", unit_value=100),
        ])
        self.add_verified_rvc_rule()
        result = recommend_origin_evidence(
            self.repository, product, self.repository.get_bom(product.product_id),
            "TEST", date(2026, 2, 1), 200, fob_source="cost_estimate",
        )
        self.assertIn("scenario outputs", " ".join(result["warnings"]))
        self.assertEqual(result["legal_status"], "verified")

    def test_analysis_forwards_one_selected_fob_to_vnm_and_evidence_stage(self):
        product = self.repository.create_product(ProductInput(product_name="Cream", fob_value=100))
        self.repository.replace_bom(product.product_id, [
            BOMLineInput(material_name="Unknown", quantity=1, unit="kg", unit_value=30),
        ])

        class CapturingRegistry:
            def __init__(self):
                self.inputs = {}

            def run(self, module, payload):
                self.inputs[module] = payload
                return ModelRunResult(
                    module=module,
                    status=RunStatus.SUCCEEDED,
                    source=ModelSource.REAL_MODEL,
                    model=ModelMetadata(name="test-adapter", integration_status=IntegrationStatus.PROTOTYPE),
                    result={"captured_fob": payload.get("fob")},
                )

        registry = CapturingRegistry()
        record = AnalysisService(self.repository, registry).run(
            product.product_id,
            "TEST",
            date(2026, 2, 1),
            fob_override=500,
            fob_override_source="cost_estimate",
        )
        self.assertEqual(registry.inputs["vnm"]["fob"], 500)
        self.assertEqual(record.results["origin_evidence"]["fob"], 500)
        self.assertEqual(record.results["origin_evidence"]["fob_source"], "cost_estimate")
        self.assertEqual(record.results["origin"]["outcome"], "insufficient_information")

    def test_combined_cth_rvc_rules_do_not_return_single_criterion_legal_result(self):
        product = self.repository.create_product(ProductInput(
            product_name="Cream", hs_code="3304", hs_code_confirmed=True, fob_value=200,
        ))
        self.repository.replace_bom(product.product_id, [
            BOMLineInput(
                material_name="Unknown", quantity=1, unit="kg", unit_value=100,
                currency="KRW", hs_code="2207", hs_code_confirmed=True,
                is_originating=False, origin_confirmed=True,
            ),
        ])
        self.add_verified_rvc_rule()
        cth = self.repository.save_rule(AgreementRuleInput(
            agreement_code="TEST", product_hs_code="3304", criterion="CTH",
            effective_from=date(2026, 1, 1), cth_digits=4,
            criteria_relationship="AND", source_title="Verified CTH fixture",
        ))
        with closing(sqlite3.connect(self.repository.db_path)) as db:
            row = db.execute("SELECT payload FROM agreement_rules WHERE rule_id=?", (cth["rule_id"],)).fetchone()
            payload = json.loads(row[0])
            payload["verified"] = True
            db.execute("UPDATE agreement_rules SET payload=? WHERE rule_id=?", (json.dumps(payload), cth["rule_id"]))
            db.commit()

        result = evaluate_origin(
            self.repository, product, self.repository.get_bom(product.product_id),
            "TEST", date(2026, 2, 1), 200, "actual_transaction",
        )
        self.assertEqual(result["outcome"], "insufficient_information")
        self.assertIn("Both CTH and RVC", result["warnings"][0])

    def test_cost_simulation_api_returns_live_bom_cost_and_rvc(self):
        from backend.routers import platform as platform_router

        product = self.repository.create_product(ProductInput(product_name="API cream"))
        self.repository.replace_bom(product.product_id, [
            BOMLineInput(material_name="Unknown", quantity=2, unit="kg", unit_value=100),
        ])
        previous_repository = platform_router.repository
        platform_router.repository = self.repository
        try:
            response = TestClient(app).post("/api/fta/cost-simulation", json={
                "product_id": product.product_id,
                "agreement_code": "TEST",
                "as_of_date": "2026-02-01",
                "manufacturing_cost": 50,
                "packaging_cost": 20,
                "freight_cost": 30,
                "freight_included_in_fob": False,
                "other_cost": 10,
                "profit": 40,
                "scenario_threshold_percent": 40,
            })
        finally:
            platform_router.repository = previous_repository

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["estimated_fob_krw"], 320)
        self.assertEqual(payload["rvc"]["vnm_krw"], 200)
        self.assertEqual(payload["rvc"]["target_source"], "scenario_assumption")


if __name__ == "__main__":
    unittest.main()
