from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from backend.models.registry import ModelRegistry
from backend.schemas.platform import AnalysisRecord, RunStatus
from backend.services.origin import evaluate_origin
from backend.services.fta_simulation import recommend_origin_evidence
from backend.services.repository import PlatformRepository


class AnalysisService:
    def __init__(self, repository: PlatformRepository, registry: ModelRegistry):
        self.repository = repository
        self.registry = registry

    def run(self, product_id: str, agreement_code: str, as_of_date: date,
            finished_product_top_k: int = 3, fob_override: float | None = None,
            fob_override_source: str | None = None) -> AnalysisRecord | None:
        product = self.repository.get_product(product_id)
        if product is None:
            return None
        bom = self.repository.get_bom(product_id)
        steps: dict[str, RunStatus] = {}
        results: dict[str, Any] = {}

        finished = self.registry.run("finished_product_hs", {
            "product_name": product.product_name,
            "ingredients_kr": product.ingredients_kr,
            "ingredients_en": product.ingredients_en,
            "form_packaging": product.form_packaging,
            "intended_use": product.intended_use,
            "top_k": finished_product_top_k,
        })
        results["finished_product_hs"] = finished.model_dump(mode="json") if hasattr(finished, "model_dump") else finished.dict()
        steps["finished_product_hs"] = finished.status

        raw_results = []
        for line in bom:
            run = self.registry.run("raw_material_hs", {
                "material_name": line.material_name,
                "description": line.description,
                "composition": "",
                "intended_use": "",
            })
            raw_results.append({"line_id": line.line_id, "run": run.model_dump(mode="json") if hasattr(run, "model_dump") else run.dict()})
        results["raw_material_hs"] = raw_results
        raw_statuses = [item["run"]["status"] for item in raw_results]
        if not raw_statuses:
            steps["raw_material_hs"] = RunStatus.INSUFFICIENT_INFORMATION
        elif all(status == RunStatus.SUCCEEDED.value for status in raw_statuses):
            steps["raw_material_hs"] = RunStatus.SUCCEEDED
        elif all(status == RunStatus.NOT_CONNECTED.value for status in raw_statuses):
            steps["raw_material_hs"] = RunStatus.NOT_CONNECTED
        else:
            steps["raw_material_hs"] = RunStatus.INSUFFICIENT_INFORMATION

        selected_fob = fob_override if fob_override is not None else product.fob_value
        selected_fob_source = fob_override_source or "actual_transaction"
        vnm = self.registry.run("vnm", {
            "product_id": product_id,
            "bom": self._to_rvc_bom(bom),
            "as_of_date": as_of_date.isoformat(),
            "fob": selected_fob,
        })
        results["vnm"] = vnm.model_dump(mode="json") if hasattr(vnm, "model_dump") else vnm.dict()
        steps["vnm"] = vnm.status

        origin = evaluate_origin(self.repository, product, bom, agreement_code, as_of_date, selected_fob, selected_fob_source)
        results["origin"] = origin
        steps[origin["module"]] = RunStatus(origin["status"])

        evidence = recommend_origin_evidence(
            self.repository, product, bom, agreement_code, as_of_date,
            selected_fob, fob_source=selected_fob_source,
        )
        results["origin_evidence"] = evidence
        steps["origin_evidence"] = RunStatus(evidence["status"])

        overall = RunStatus.SUCCEEDED
        if any(status in (RunStatus.FAILED, RunStatus.NOT_CONNECTED,
                          RunStatus.INSUFFICIENT_INFORMATION) for status in steps.values()):
            overall = RunStatus.INSUFFICIENT_INFORMATION
        record = AnalysisRecord(
            analysis_id=str(uuid4()), product_id=product_id,
            agreement_code=agreement_code, as_of_date=as_of_date,
            status=overall, steps=steps, results=results,
            created_at=datetime.now(timezone.utc),
        )
        serialized = record.model_dump(mode="json") if hasattr(record, "model_dump") else record.dict()
        self.repository.save_analysis(record.analysis_id, product_id, overall.value, serialized)
        return record

    @staticmethod
    def _to_rvc_bom(bom: list[Any]) -> list[dict[str, Any]]:
        """Map persisted BOM records to the unmodified RVC engine's input contract."""
        records = []
        for line in bom:
            unit_value = line.unit_value or 0
            if line.origin_confirmed and line.is_originating and line.origin_evidence_verified:
                status = "원산지 확인"
            elif line.origin_confirmed and line.is_originating is False:
                status = "비원산지"
            else:
                status = "미확인"
            records.append({
                "material_id": line.rvc_material_id or line.line_id,
                "material_name": line.material_name,
                "cost_krw": line.quantity * unit_value,
                "status": status,
            })
        return records

    def get(self, analysis_id: str) -> AnalysisRecord | None:
        data = self.repository.get_analysis(analysis_id)
        if data is None:
            return None
        if hasattr(AnalysisRecord, "model_validate"):
            return AnalysisRecord.model_validate(data)
        return AnalysisRecord.parse_obj(data)

