import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { api } from "../api/client";
import { Card, StatusBadge } from "./ui";
import type { BomLine, CostSimulationResponse, EvidenceCandidate, ModelRunResult, Product } from "../types/api";

export type FobCostInputs = {
  manufacturing: number;
  packaging: number;
  freight: number;
  freightIncluded: boolean;
  other: number;
  profit: number;
  useActualFob: boolean;
  actualFob: number | null;
  scenarioThreshold?: number;
};

export const initialFobCosts: FobCostInputs = {
  manufacturing: 0, packaging: 0, freight: 0, freightIncluded: true,
  other: 0, profit: 0, useActualFob: false, actualFob: null,
};

export function resolveFob(inputs: FobCostInputs, bom: BomLine[], product: Product | null) {
  const complete = bom.length > 0 && bom.every(line => line.unit_value !== undefined && (!line.currency || line.currency.toUpperCase() === "KRW"));
  const materialTotal = bom.reduce((sum, line) => sum + (line.unit_value === undefined ? 0 : line.quantity * line.unit_value), 0);
  const estimated = complete ? materialTotal + inputs.manufacturing + inputs.packaging + (inputs.freightIncluded ? inputs.freight : 0) + inputs.other + inputs.profit : undefined;
  const actual = inputs.actualFob ?? product?.fob_value ?? undefined;
  return { complete, materialTotal, estimated, value: inputs.useActualFob ? actual : estimated, source: inputs.useActualFob ? "actual_transaction" as const : "cost_estimate" as const };
}

type Props = {
  product: Product | null;
  bom: BomLine[];
  inputs: FobCostInputs;
  setInputs: (next: FobCostInputs) => void;
};

const won = (value?: number | null) => value === undefined || value === null ? "—" : `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(value)}원`;

export function FobEvidencePanel({ product, bom, inputs, setInputs }: Props) {
  const selection = resolveFob(inputs, bom, product);
  const bomComplete = selection.complete;
  const baseVnm = bom.reduce((sum, line) => {
    const cost = line.unit_value === undefined ? 0 : line.quantity * line.unit_value;
    const evidenceAccepted = line.origin_confirmed && line.is_originating === true && line.origin_evidence_verified === true;
    return sum + (evidenceAccepted ? 0 : cost);
  }, 0);
  const localRvc = selection.value !== undefined && selection.value > 0 && bomComplete ? (selection.value - baseVnm) / selection.value * 100 : undefined;
  const [serverResult, setServerResult] = useState<CostSimulationResponse>();
  const [simulationPending, setSimulationPending] = useState(false);
  const [simulationError, setSimulationError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [forecast, setForecast] = useState<ModelRunResult>();
  const [forecastSignature, setForecastSignature] = useState("");
  const [forecastPending, setForecastPending] = useState(false);
  const [forecastError, setForecastError] = useState("");

  useEffect(() => {
    if (!product || selection.value === undefined || selection.value <= 0) {
      setServerResult(undefined);
      setSimulationError(selection.value !== undefined && selection.value <= 0 ? "FOB는 0보다 커야 RVC를 계산할 수 있습니다." : "BOM 단가를 입력하면 비용 기반 FOB와 RVC를 계산합니다.");
      return;
    }
    let active = true;
    setSimulationPending(true);
    setSimulationError("");
    const timer = window.setTimeout(async () => {
      try {
        const result = await api.costSimulation({
          product_id: product.product_id,
          agreement_code: "KOREA_VIETNAM",
          as_of_date: new Date().toISOString().slice(0, 10),
          manufacturing_cost: inputs.manufacturing,
          packaging_cost: inputs.packaging,
          freight_cost: inputs.freight,
          freight_included_in_fob: inputs.freightIncluded,
          other_cost: inputs.other,
          profit: inputs.profit,
          use_actual_fob: inputs.useActualFob,
          actual_fob: inputs.actualFob ?? product.fob_value,
          scenario_threshold_percent: inputs.scenarioThreshold,
        });
        if (active) setServerResult(result);
      } catch (error) {
        if (active) {
          setServerResult(undefined);
          setSimulationError(error instanceof Error ? error.message : "비용 시뮬레이션 요청에 실패했습니다.");
        }
      } finally {
        if (active) setSimulationPending(false);
      }
    }, 450);
    return () => { active = false; window.clearTimeout(timer); };
  }, [product?.product_id, bom, inputs, selection.value]);

  const recommendation = serverResult?.rvc;
  const candidates = recommendation?.unknown_origin_materials ?? [];
  const selectedCost = candidates.filter(item => selectedIds.includes(item.material_id)).reduce((sum, item) => sum + item.cost_krw, 0);
  const simulatedRvc = selection.value !== undefined && selection.value > 0 && bomComplete
    ? (selection.value - Math.max(0, baseVnm - selectedCost)) / selection.value * 100
    : undefined;
  const legalTarget = recommendation?.target_source === "verified_agreement_rule" ? recommendation.target_rvc_percent : undefined;
  const target = legalTarget ?? inputs.scenarioThreshold;
  const thresholdLabel = legalTarget !== undefined ? "검증된 협정 기준" : inputs.scenarioThreshold !== undefined ? "사용자 가정 기준(시뮬레이션)" : "확인된 기준 없음";
  const signature = useMemo(() => JSON.stringify({ fob: selection.value, bom: bom.map((line, i) => [line.rvc_material_id ?? line.line_id ?? i, line.quantity, line.unit_value, line.is_originating, line.origin_confirmed, line.origin_evidence_verified]) }), [selection.value, bom]);
  const riskStale = !forecast || forecastSignature !== signature;
  const estimatedFob = selection.estimated;

  const update = (key: keyof FobCostInputs, value: number | boolean | undefined) => setInputs({ ...inputs, [key]: value });
  const applyRecommendedSet = () => setSelectedIds((recommendation?.recommended_combination ?? []).map(item => item.material_id));
  const toggleEvidence = (id: string, checked: boolean) => setSelectedIds(current => checked ? [...new Set([...current, id])] : current.filter(value => value !== id));

  const refreshForecast = async () => {
    if (!product || selection.value === undefined || selection.value <= 0 || !bomComplete) {
      setForecastError("양수 FOB와 모든 BOM 구매단가가 필요합니다.");
      return;
    }
    setForecastPending(true);
    setForecastError("");
    try {
      const result = await api.runModel("vnm", {
        product_id: product.product_id,
        bom: bom.map((line, index) => ({
          material_id: line.rvc_material_id ?? line.line_id ?? `bom-${index + 1}`,
          material_name: line.material_name,
          cost_krw: line.quantity * (line.unit_value ?? 0),
          status: line.origin_confirmed && line.is_originating === true && line.origin_evidence_verified === true
            ? "원산지 확인"
            : line.origin_confirmed && line.is_originating === false ? "비원산지" : "미상",
        })),
        fob: selection.value,
        months: 3,
        n_sim: 3000,
        seed: 42,
        threshold: target ?? 40,
      });
      setForecast(result);
      setForecastSignature(signature);
    } catch (error) {
      setForecastError(error instanceof Error ? error.message : "VNM 위험 예측에 실패했습니다.");
    } finally {
      setForecastPending(false);
    }
  };

  const forecastResult = forecast?.result as { current_vnm?: number; current_rvc?: number; available?: boolean; monthly?: Array<{ month?: number; mean_rvc?: number; risk?: number }> } | null;
  const cthPass = recommendation?.rule_context?.cth_pass;

  return <Card className="fob-evidence-panel">
    <div className="card-head"><div><p className="eyebrow">FOB 및 원산지 시나리오</p><h3>FOB 비용 시뮬레이터 · 원산지 증빙 확보 추천</h3></div><StatusBadge status={simulationPending ? "running" : recommendation?.status ?? "insufficient_information"}/></div>
    <p className="muted-copy">비용 변경은 가상 시뮬레이션입니다. 체크박스는 실제 BOM 원산지 상태를 바꾸지 않으며, 법적 판정에는 확인된 협정 규칙과 증빙이 필요합니다.</p>
    <div className="simulator-grid">
      <CostControl label="제조비" value={inputs.manufacturing} max={Math.max(1000000, selection.materialTotal * 2)} onChange={value => update("manufacturing", value)}/>
      <CostControl label="포장비" value={inputs.packaging} max={Math.max(1000000, selection.materialTotal * 2)} onChange={value => update("packaging", value)}/>
      <CostControl label="운송비" value={inputs.freight} max={Math.max(1000000, selection.materialTotal * 2)} onChange={value => update("freight", value)}/>
      <CostControl label="기타 비용" value={inputs.other} max={Math.max(1000000, selection.materialTotal * 2)} onChange={value => update("other", value)}/>
      <CostControl label="이윤" value={inputs.profit} max={Math.max(1000000, selection.materialTotal * 2)} onChange={value => update("profit", value)}/>
      <label className="field actual-fob"><span>실거래 FOB (원)</span><input type="number" min="0" step="1000" value={inputs.actualFob ?? product?.fob_value ?? ""} onChange={event => update("actualFob", event.target.value === "" ? undefined : Math.max(0, Number(event.target.value)))}/></label>
    </div>
    <label className="check"><input type="checkbox" checked={inputs.freightIncluded} onChange={event => update("freightIncluded", event.target.checked)}/> 운송비를 FOB에 포함</label>
    <label className="check"><input type="checkbox" checked={inputs.useActualFob} onChange={event => update("useActualFob", event.target.checked)}/> 확정된 실거래 FOB 사용 (해제 시 비용 추정 FOB 사용)</label>
    <div className="simulator-summary">
      <div><span>BOM 원재료 투입액</span><strong>{won(selection.materialTotal)}</strong></div>
      <div><span>비용 기반 예상 FOB</span><strong>{won(estimatedFob)}</strong></div>
      <div><span>{inputs.useActualFob ? "계산 기준: 실거래 FOB" : "계산 기준: 추정 FOB"}</span><strong>{won(selection.value)}</strong></div>
    </div>
    {(!bomComplete || selection.value === undefined || selection.value <= 0) && <p className="warning-copy">{!bomComplete ? "모든 원재료의 원화 구매단가가 있어야 RVC를 계산할 수 있습니다." : "FOB가 0 이하입니다. 양수 FOB를 입력해야 RVC 계산을 진행합니다."}</p>}
    <div className="rvc-live"><strong>현재 RVC</strong><b>{localRvc === undefined ? "계산 대기" : `${localRvc.toFixed(2)}%`}</b><span>RVC = (FOB − VNM) / FOB × 100</span><small>기준: {thresholdLabel}{target !== undefined && localRvc !== undefined ? ` · ${localRvc >= target ? "기준 충족" : `부족 ${Math.max(0, target - localRvc).toFixed(2)}%p`}` : ""}</small></div>

    <div className="evidence-section"><div className="card-head"><div><p className="eyebrow">5단계</p><h3>원산지 증빙 확보 추천</h3></div><button className="secondary" disabled={simulationPending || !recommendation?.recommended_combination?.length} onClick={applyRecommendedSet}><Sparkles size={15}/> 최소 조합 선택</button></div>
      <label className="field scenario-threshold"><span>가정 RVC 기준 (%) — 협정 기준 확인 전 시뮬레이션 전용</span><input type="number" min="0" max="100" step="0.1" placeholder={legalTarget !== undefined ? String(legalTarget) : "기준 미확인"} value={inputs.scenarioThreshold ?? ""} onChange={event => update("scenarioThreshold", event.target.value === "" ? undefined : Math.min(100, Math.max(0, Number(event.target.value))))}/></label>
      {simulationPending && <p className="muted-copy">비용과 적용 규칙을 다시 계산하고 있습니다…</p>}
      {simulationError && <p className="muted-copy">{simulationError}</p>}
      {recommendation && <>
        <p className="muted-copy">현재 RVC {localRvc === undefined ? "—" : `${localRvc.toFixed(2)}%`} · 목표 {target === undefined ? "미확인" : `${target.toFixed(2)}% (${thresholdLabel})`} · 부족 {target === undefined || localRvc === undefined ? "—" : `${Math.max(0, target - localRvc).toFixed(2)}%p`}</p>
        <p className="muted-copy">CTH 상태: {cthPass === true ? "충족" : cthPass === false ? "미충족" : "확인 보류"} · 기준 관계: {String(recommendation.rule_context.relationship ?? "미확인")}</p>
        {candidates.map(item => <EvidenceCheck key={item.material_id} item={item} checked={selectedIds.includes(item.material_id)} onChange={checked => toggleEvidence(item.material_id, checked)}/>)}
        {candidates.length === 0 && <p className="muted-copy">추가 증빙 검토 대상이 없습니다.</p>}
        <p className="muted-copy">선택 조합의 예상 RVC: {simulatedRvc === undefined ? "계산 불가" : `${simulatedRvc.toFixed(2)}%`} · 증빙 확보 전 {localRvc === undefined ? "—" : `${localRvc.toFixed(2)}%`} → 가정 후 {simulatedRvc === undefined ? "—" : `${simulatedRvc.toFixed(2)}%`}</p>
        {recommendation.recommended_combination.map(item => <p className="recommendation-reason" key={`why-${item.material_id}`}>{item.material_name}: {item.reason}</p>)}
        {recommendation.combination_status === "unreachable" && <p className="warning-copy">모든 미확인 원재료를 인정한다고 가정해도 목표 RVC에 도달하지 못합니다. 최대 예상 RVC {recommendation.maximum_reachable_rvc_percent?.toFixed(2)}%.</p>}
        {recommendation.warnings.map((warning, index) => <p className="muted-copy" key={`warning-${index}`}>{warning}</p>)}
      </>}
    </div>

    <div className="risk-refresh"><div><strong>VNM 변동성 / RVC 위험 예측</strong><p className="muted-copy">사용 FOB: {won(selection.value)} · 위험 기준 {target ?? 40}%{target === undefined ? " (40% 시뮬레이션 가정, 법적 기준 아님)" : ""}</p>{riskStale && <span className="status status-warning">입력 변경으로 재계산 필요</span>}</div><button className="secondary" disabled={forecastPending || selection.value === undefined || selection.value <= 0 || !bomComplete} onClick={() => void refreshForecast()}><RefreshCw size={15}/>{forecastPending ? "예측 중" : "동일 FOB로 예측 갱신"}</button></div>
    {forecastError && <p className="warning-copy">{forecastError}</p>}
    {!riskStale && forecastResult && <p className="muted-copy">{forecast?.status === "succeeded" ? `현재 VNM ${won(forecastResult.current_vnm)} · 현재 RVC ${forecastResult.current_rvc?.toFixed(2)}% · 3개월 예측 ${forecastResult.monthly?.map(row => `${row.mean_rvc?.toFixed(1)}% (위험 ${row.risk?.toFixed(1)}%)`).join(" / ") ?? "자료 부족"}` : `모델 상태: ${forecast?.status}. ${forecast?.warnings?.join(" ") ?? ""}`}</p>}
  </Card>;
}

function CostControl({ label, value, max, onChange }: { label: string; value: number; max: number; onChange: (value: number) => void }) {
  return <div className="cost-control"><label>{label} (원)</label><input type="range" min="0" max={max} step="1000" value={Math.min(value, max)} onChange={event => onChange(Number(event.target.value))}/><input type="number" min="0" step="1000" value={value} onChange={event => onChange(Math.max(0, Number(event.target.value)))}/></div>;
}

function EvidenceCheck({ item, checked, onChange }: { item: EvidenceCandidate; checked: boolean; onChange: (checked: boolean) => void }) {
  return <label className="evidence-candidate"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)}/><div><strong>{item.material_name}</strong><small>{won(item.cost_krw)} · 예상 RVC 개선 {item.rvc_improvement_percent_points?.toFixed(2) ?? "—"}%p</small><small>{item.reason}</small></div></label>;
}
