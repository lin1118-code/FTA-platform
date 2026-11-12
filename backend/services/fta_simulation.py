"""Cost-based FOB/RVC scenario calculations and origin-evidence recommendations."""
from __future__ import annotations

from datetime import date
from itertools import combinations
from typing import Any

from backend.schemas.platform import FobCostSimulationRequest
from backend.services.repository import PlatformRepository


def _line_cost(line: Any) -> float | None:
    if line.unit_value is None:
        return None
    return float(line.quantity) * float(line.unit_value)


def _has_origin_evidence(line: Any) -> bool:
    return bool(
        line.origin_confirmed
        and line.is_originating is True
        and getattr(line, "origin_evidence_verified", False)
    )


def _rvc(vnm: float, fob: float) -> float | None:
    if fob <= 0:
        return None
    return (fob - vnm) / fob * 100


def _rules_context(
    repository: PlatformRepository,
    product: Any,
    bom: list[Any],
    agreement_code: str,
    as_of_date: date,
) -> dict[str, Any]:
    if not product.hs_code or not product.hs_code_confirmed:
        return {"status": "insufficient_information", "reason": "Finished-product HS code is not user-confirmed."}
    rules = repository.list_rules(agreement_code, product.hs_code, as_of_date)
    if not rules:
        return {"status": "insufficient_information", "reason": "No applicable product-specific origin rule is registered."}
    if any(not rule.get("verified") or not (rule.get("source_title") or rule.get("source_url")) for rule in rules):
        return {"status": "insufficient_information", "reason": "At least one applicable rule lacks verified official evidence."}

    by_criterion: dict[str, list[dict[str, Any]]] = {"CTH": [], "RVC": []}
    for rule in rules:
        criterion = rule.get("criterion")
        if criterion not in by_criterion:
            return {"status": "insufficient_information", "reason": "An unsupported origin criterion is registered."}
        by_criterion[criterion].append(rule)
    if any(len(entries) > 1 for entries in by_criterion.values()):
        return {"status": "insufficient_information", "reason": "Multiple effective rules make the applicable criterion ambiguous."}

    criteria = [key for key, entries in by_criterion.items() if entries]
    relationship = "SINGLE"
    if len(criteria) > 1:
        relationships = {by_criterion[key][0].get("criteria_relationship") for key in criteria}
        if len(relationships) != 1 or None in relationships:
            return {"status": "insufficient_information", "reason": "The rule does not say whether CTH and RVC are alternatives or cumulative requirements."}
        relationship = relationships.pop()

    rvc_rule = by_criterion["RVC"][0] if by_criterion["RVC"] else None
    threshold = None
    if rvc_rule:
        if rvc_rule.get("rvc_formula") != "build_down" or rvc_rule.get("rvc_threshold_percent") is None:
            return {"status": "insufficient_information", "reason": "The verified RVC rule lacks a supported build-down formula or threshold."}
        threshold = float(rvc_rule["rvc_threshold_percent"])

    cth_pass: bool | None = None
    if by_criterion["CTH"]:
        cth_rule = by_criterion["CTH"][0]
        digits = cth_rule.get("cth_digits")
        product_hs = str(product.hs_code).replace(".", "")
        if not digits or len(product_hs) < digits or not bom or any(not line.hs_code or not line.hs_code_confirmed for line in bom):
            return {"status": "insufficient_information", "reason": "CTH requires confirmed product and BOM HS codes and a verified digit-change rule."}
        cth_pass = all(str(line.hs_code).replace(".", "")[:digits] != product_hs[:digits] for line in bom)
    return {
        "status": "verified",
        "criteria": criteria,
        "relationship": relationship,
        "rvc_threshold_percent": threshold,
        "cth_pass": cth_pass,
        "rules": rules,
    }


def _best_minimum_combination(candidates: list[dict[str, Any]], needed_cost: float) -> list[dict[str, Any]] | None:
    """Find fewest evidence items; then smallest passing excess; then ID order."""
    ordered = sorted(candidates, key=lambda item: item["material_id"])
    for count in range(1, len(ordered) + 1):
        passing: list[tuple[float, tuple[str, ...], tuple[int, ...]]] = []
        for indexes in combinations(range(len(ordered)), count):
            total = sum(ordered[index]["cost_krw"] for index in indexes)
            if total + 1e-9 >= needed_cost:
                ids = tuple(ordered[index]["material_id"] for index in indexes)
                passing.append((total, ids, indexes))
        if passing:
            _, _, indexes = min(passing, key=lambda item: (item[0], item[1]))
            return [ordered[index] for index in indexes]
    return None


def recommend_origin_evidence(
    repository: PlatformRepository,
    product: Any,
    bom: list[Any],
    agreement_code: str,
    as_of_date: date,
    fob: float | None,
    scenario_threshold_percent: float | None = None,
    fob_source: str = "actual_transaction",
) -> dict[str, Any]:
    costs = [_line_cost(line) for line in bom]
    missing_costs = [line.material_name for line, cost in zip(bom, costs) if cost is None]
    foreign_currency = [line.material_name for line in bom if line.currency and line.currency.upper() != "KRW"]
    input_errors = []
    if fob is None or fob <= 0:
        input_errors.append("FOB must be greater than zero.")
    if missing_costs:
        input_errors.append("Unit purchase price is missing for: " + ", ".join(missing_costs))
    if foreign_currency:
        input_errors.append("Convert BOM values to KRW before comparison: " + ", ".join(foreign_currency))

    safe_costs = [cost or 0.0 for cost in costs]
    vnm = sum(
        cost for line, cost in zip(bom, safe_costs)
        if not _has_origin_evidence(line)
    )
    current_rvc = _rvc(vnm, fob or 0)
    rule_context = _rules_context(repository, product, bom, agreement_code, as_of_date)
    legal_threshold = rule_context.get("rvc_threshold_percent") if rule_context.get("status") == "verified" else None
    target = legal_threshold if legal_threshold is not None else scenario_threshold_percent
    target_source = "verified_agreement_rule" if legal_threshold is not None else ("scenario_assumption" if scenario_threshold_percent is not None else None)

    unknown = []
    for line, cost in zip(bom, safe_costs):
        unknown_origin = (
            line.is_originating is None
            or (line.is_originating is True and not _has_origin_evidence(line))
        )
        if unknown_origin and cost > 0:
            unknown.append({
                "material_id": line.line_id,
                "material_name": line.material_name,
                "cost_krw": cost,
                "rvc_improvement_percent_points": cost / fob * 100 if fob and fob > 0 else None,
                "reason": "Origin evidence is not verified; this cost remains in VNM until supporting evidence is accepted.",
            })

    result: dict[str, Any] = {
        "module": "origin_evidence",
        "status": "insufficient_information" if input_errors or (current_rvc is None) else "succeeded",
        "legal_status": rule_context.get("status", "insufficient_information"),
        "source": "rules_engine",
        "fob": fob,
        "fob_source": fob_source,
        "vnm_krw": vnm if not input_errors else None,
        "current_rvc_percent": current_rvc if not input_errors else None,
        "target_rvc_percent": target,
        "target_source": target_source,
        "shortfall_percent_points": max(0.0, target - current_rvc) if target is not None and current_rvc is not None else None,
        "unknown_origin_materials": unknown,
        "individual_impacts": unknown,
        "recommended_combination": [],
        "combination_status": "withheld",
        "maximum_reachable_rvc_percent": None,
        "rule_context": rule_context,
        "warnings": input_errors.copy(),
    }
    if fob_source == "cost_estimate":
        result["warnings"].append("RVC values use a cost-estimated FOB and are scenario outputs, not a legal origin determination.")
    if input_errors or current_rvc is None:
        return result

    if rule_context.get("status") == "verified" and rule_context.get("criteria") == ["CTH"]:
        if rule_context.get("cth_pass") is True:
            result["combination_status"] = "already_satisfied"
            result["warnings"].append("The verified CTH criterion is already met; origin evidence is not needed to satisfy it.")
        else:
            result["combination_status"] = "no_evidence_combination_can_fix_cth"
            result["warnings"].append("Origin evidence assumptions do not change HS classification and cannot cure a failed CTH rule.")
        return result

    if target is None:
        result["warnings"].append("No verified RVC target is available. Enter a scenario-only threshold to compare hypothetical combinations; no legal pass/fail is inferred.")
        result["combination_status"] = "scenario_threshold_required"
        return result

    max_reachable = _rvc(max(0.0, vnm - sum(item["cost_krw"] for item in unknown)), fob)
    result["maximum_reachable_rvc_percent"] = max_reachable
    threshold_is_legal = target_source == "verified_agreement_rule"

    criteria = rule_context.get("criteria", []) if rule_context.get("status") == "verified" else []
    relationship = rule_context.get("relationship")
    cth_pass = rule_context.get("cth_pass")
    if not threshold_is_legal:
        result["warnings"].append("This combination is a scenario only; it does not establish compliance with an agreement rule.")
    elif "CTH" in criteria and relationship is None:
        result["warnings"].append("The relationship between CTH and RVC is unverified; a legal recommendation is withheld.")
        return result

    rvc_already_passes = current_rvc >= target
    current_qualifies = rvc_already_passes
    if "CTH" in criteria:
        if relationship == "AND":
            current_qualifies = current_qualifies and cth_pass is True
        elif relationship == "OR":
            current_qualifies = current_qualifies or cth_pass is True
        else:
            current_qualifies = cth_pass is True if "RVC" not in criteria else current_qualifies
    if current_qualifies:
        result["combination_status"] = "already_satisfied"
        result["warnings"].append("Current values already meet the applicable criterion; no additional evidence is recommended.")
        return result

    if "CTH" in criteria and relationship == "AND" and cth_pass is False:
        result["combination_status"] = "no_evidence_combination_can_fix_cth"
        result["warnings"].append("Evidence assumptions do not change HS classification. CTH fails; HS classification or production facts need review separately.")
        return result
    if "CTH" in criteria and "RVC" not in criteria:
        result["combination_status"] = "no_evidence_combination_can_fix_cth"
        result["warnings"].append("Evidence assumptions do not change HS classification and cannot cure a failed CTH rule.")
        return result
    if "CTH" in criteria and relationship == "OR" and cth_pass is True:
        result["combination_status"] = "already_satisfied"
        return result

    if max_reachable is not None and max_reachable + 1e-9 < target:
        result["combination_status"] = "unreachable"
        result["warnings"].append("Even if all currently unknown-origin materials qualified, the RVC target would remain out of reach.")
        return result

    needed_cost = max(0.0, (target - current_rvc) * fob / 100)
    combination = _best_minimum_combination(unknown, needed_cost)
    if combination is None:
        result["combination_status"] = "no_combination"
        result["warnings"].append("No set of currently unknown-origin materials reaches the requested RVC target.")
        return result
    improvement = sum(item["rvc_improvement_percent_points"] or 0 for item in combination)
    result["recommended_combination"] = [
        {**item, "reason": "Assuming acceptable origin evidence is obtained, this material reduces VNM and improves RVC."}
        for item in combination
    ]
    result["predicted_rvc_after_combination_percent"] = min(100.0, current_rvc + improvement)
    result["combination_status"] = "scenario_recommendation" if not threshold_is_legal else "recommended"
    return result


def simulate_fob_costs(
    repository: PlatformRepository,
    request: FobCostSimulationRequest,
) -> dict[str, Any] | None:
    product = repository.get_product(request.product_id)
    if product is None:
        return None
    bom = repository.get_bom(request.product_id)
    line_costs = [_line_cost(line) for line in bom]
    missing = [line.material_name for line, cost in zip(bom, line_costs) if cost is None]
    foreign = [line.material_name for line in bom if line.currency and line.currency.upper() != "KRW"]
    materials = sum(cost or 0.0 for cost in line_costs)
    freight_added = request.freight_cost if request.freight_included_in_fob else 0.0
    estimated_fob = None if missing or foreign else materials + request.manufacturing_cost + request.packaging_cost + freight_added + request.other_cost + request.profit
    actual_fob = request.actual_fob if request.actual_fob is not None else product.fob_value
    selected_fob = actual_fob if request.use_actual_fob else estimated_fob
    fob_source = "actual_transaction" if request.use_actual_fob else "cost_estimate"
    recommendation = recommend_origin_evidence(
        repository, product, bom, request.agreement_code, request.as_of_date,
        selected_fob, request.scenario_threshold_percent, fob_source,
    )
    return {
        "module": "fob_rvc_simulation",
        "status": "succeeded" if selected_fob is not None and selected_fob > 0 and not missing and not foreign else "insufficient_information",
        "source": "rules_engine",
        "fob_source": fob_source,
        "actual_transaction_fob_krw": actual_fob,
        "estimated_fob_krw": estimated_fob,
        "selected_fob_krw": selected_fob,
        "cost_breakdown_krw": {
            "materials": materials,
            "manufacturing": request.manufacturing_cost,
            "packaging": request.packaging_cost,
            "freight_included": freight_added,
            "freight_excluded": 0.0 if request.freight_included_in_fob else request.freight_cost,
            "other": request.other_cost,
            "profit": request.profit,
        },
        "missing_unit_prices": missing,
        "non_krw_materials": foreign,
        "rvc": recommendation,
        "warnings": (["FOB must be greater than zero before RVC can be calculated."] if selected_fob is None or selected_fob <= 0 else [])
        + (["Estimated FOB is incomplete because one or more BOM unit prices are missing."] if missing else [])
        + (["Convert non-KRW BOM amounts before computing FOB or RVC."] if foreign else []),
    }
