from datetime import date
from typing import Any

from backend.schemas.platform import BOMLineRecord, ProductRecord, RunStatus
from backend.services.repository import PlatformRepository


def evaluate_origin(
    repository: PlatformRepository,
    product: ProductRecord,
    bom: list[BOMLineRecord],
    agreement_code: str,
    as_of_date: date,
    fob_override: float | None = None,
    fob_override_source: str | None = None,
) -> dict[str, Any]:
    hs_code = product.hs_code
    if not hs_code or not product.hs_code_confirmed:
        return _unassessed("완제품 HS 코드가 사용자 확인 상태가 아닙니다.")
    rule = repository.find_rule(agreement_code, hs_code, as_of_date)
    if not rule:
        return _unassessed("해당 협정·품목·기준일에 적용할 규칙 데이터가 없습니다.")
    if not rule.get("verified") or not (rule.get("source_title") or rule.get("source_url")):
        return _unassessed("규칙의 공식 근거가 검증되지 않아 판정을 보류합니다.", rule)
    applicable_rules = repository.list_rules(agreement_code, hs_code, as_of_date)
    criteria = {entry.get("criterion") for entry in applicable_rules}
    if {"CTH", "RVC"}.issubset(criteria):
        # This evaluator handles one criterion at a time. Avoid presenting the
        # first matching rule as the joint legal result when both are applicable.
        return _unassessed(
            "Both CTH and RVC are registered; their relationship and joint result must be evaluated together before a legal conclusion.",
            rule,
        )
    if rule["criterion"] == "CTH":
        if not bom or any(not line.hs_code or not line.hs_code_confirmed for line in bom):
            return _unassessed("BOM의 원재료 HS 코드가 모두 확인되어야 CTH를 계산할 수 있습니다.", rule)
        digits = rule.get("cth_digits")
        if not digits:
            return _unassessed("CTH 세번 변경 단위가 규칙 데이터에 지정되지 않았습니다.", rule)
        target_prefix = hs_code.replace(".", "")[:digits]
        failures = [line.material_name for line in bom if line.hs_code.replace(".", "")[:digits] == target_prefix]
        outcome = "not_eligible" if failures else "eligible"
        return {
            "module": "cth", "status": RunStatus.SUCCEEDED.value,
            "source": "rules_engine", "outcome": outcome,
            "calculation": {"required_digits": digits, "product_hs_code": hs_code,
                            "same_prefix_materials": failures},
            "rule": rule, "evidence": [rule.get("source_title"), rule.get("source_url")],
            "warnings": ["규칙 데이터의 정확성과 입력 분류는 담당자가 확인해야 합니다."],
        }
    if rule["criterion"] == "RVC":
        if rule.get("rvc_formula") != "build_down" or rule.get("rvc_threshold_percent") is None:
            return _unassessed("지원하는 RVC 산식(build_down)과 기준 비율이 검증된 규칙에 없습니다.", rule)
        legal_fob = fob_override if fob_override_source == "actual_transaction" and fob_override is not None else product.fob_value
        if fob_override_source == "cost_estimate":
            return _unassessed("Cost-estimated FOB is a scenario input and cannot support a legal RVC determination.", rule)
        if legal_fob is None or legal_fob <= 0:
            return _unassessed("양수 완제품 FOB 기준가치가 필요합니다.", rule)
        if not bom or any(line.unit_value is None or line.is_originating is None or not line.origin_confirmed or (line.is_originating and not line.origin_evidence_verified) for line in bom):
            return _unassessed("모든 원재료 가치와 증빙 확인된 원산지 여부가 필요합니다.", rule)
        if not product.fob_currency or any(line.currency != product.fob_currency for line in bom):
            return _unassessed("완제품과 모든 BOM 가치의 통화가 명시되고 일치해야 합니다.", rule)
        fob = legal_fob
        vnm = sum(line.quantity * line.unit_value for line in bom if not line.is_originating)
        rvc = (fob - vnm) / fob * 100
        outcome = "eligible" if rvc >= rule["rvc_threshold_percent"] else "not_eligible"
        return {
            "module": "rvc", "status": RunStatus.SUCCEEDED.value,
            "source": "rules_engine", "outcome": outcome,
            "calculation": {"formula": "(FOB - VNM) / FOB * 100", "fob_proxy": fob,
                            "vnm": vnm, "rvc_percent": rvc,
                            "threshold_percent": rule["rvc_threshold_percent"]},
            "rule": rule, "evidence": [rule.get("source_title"), rule.get("source_url")],
            "warnings": ["입력 가치가 협정상 FOB 및 재료가치 정의와 일치하는지 확인해야 합니다."],
        }
    return _unassessed("지원하지 않는 원산지 기준입니다.", rule)


def _unassessed(reason: str, rule: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "module": (rule or {}).get("criterion", "origin").lower(),
        "status": RunStatus.INSUFFICIENT_INFORMATION.value,
        "source": "rules_engine", "outcome": "insufficient_information",
        "rule": rule, "evidence": [], "warnings": [reason],
    }
