import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Check, FileText, Plus, RefreshCw, Save, Search, Sparkles } from "lucide-react";
import { api } from "./api/client";
import { Layout, type Page } from "./components/layout";
import { Card, EmptyState, StatusBadge } from "./components/ui";
import type { Analysis, BomLine, ModelMetadata, ModelRunResult, Product, ProductInput, RunStatus } from "./types/api";

const stages: Array<{ id: Page; label: string; hint: string }> = [
  { id: "dashboard", label: "Product management", hint: "Select and review saved products." },
  { id: "product", label: "Product input", hint: "Enter finished-product details, HS4 recommendations and BOM." },
  { id: "fob", label: "FOB setup", hint: "Set costs and origin scenarios." },
  { id: "origin", label: "FTA requirements", hint: "Review CTH, RVC and origin evidence scenarios." },
  { id: "vnm", label: "VNM simulation", hint: "Run the existing ARMA and Monte Carlo engine." },
  { id: "extras", label: "Other features", hint: "Supplier email and evidence checklist." },
];
const empty: ProductInput = { product_name: "", ingredients_kr: "", ingredients_en: "", form_packaging: "", intended_use: "", description: "", hs_code_confirmed: false };
const emptyLine = (): BomLine => ({ material_name: "", description: "", quantity: 1, unit: "kg", unit_price_unit: "kg", currency: "KRW", origin_country: "UNKNOWN", origin_confirmed: false, hs_code_confirmed: false });
type CostState = { manufacturing: number; packaging: number; freight: number; freightIncluded: boolean; other: number; profit: number; actual: number | null; useActual: boolean; scenarioThreshold?: number };
const initialCosts: CostState = { manufacturing: 0, packaging: 0, freight: 0, freightIncluded: true, other: 0, profit: 0, actual: null, useActual: false, scenarioThreshold: 40 };
const USER_COSMETICS_CRITERION = { cthDigits: 4, rvcThresholdPercent: 40, relationship: "OR" as const };
type OriginScenario = Record<string, "unknown" | "domestic" | "foreign">;
const won = (n?: number | null) => n == null || !Number.isFinite(n) ? "\u2014" : `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(n)} KRW`;
const percent = (n?: number | null) => n == null || !Number.isFinite(n) ? "\u2014" : `${n.toFixed(2)}%`;
const priceDisplay = (n?: number) => n == null ? "" : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(n);
const parsePrice = (value: string) => { const normalized = value.replace(/,/g, "").replace(/[^0-9.]/g, ""); if (!normalized) return undefined; const parsed = Number(normalized); return Number.isFinite(parsed) ? Math.max(0, parsed) : undefined; };
const productInput = (p: Product): ProductInput => ({ product_name: p.product_name, ingredients_kr: p.ingredients_kr, ingredients_en: p.ingredients_en, form_packaging: p.form_packaging, intended_use: p.intended_use, description: p.description, hs_code: p.hs_code, hs_code_confirmed: p.hs_code_confirmed, fob_value: p.fob_value, fob_currency: p.fob_currency });
const lineKey = (line: BomLine, index: number) => line.line_id ?? line.rvc_material_id ?? `draft-${index}`;

export function Workflow() {
  const [page, setPage] = useState<Page>(() => {
    const saved = localStorage.getItem("fta-step") as Page | null;
    return stages.some(stage => stage.id === saved) ? saved! : "dashboard";
  });
  const [products, setProducts] = useState<Product[]>([]);
  const [product, setProduct] = useState<Product | null>(null);
  const [draft, setDraft] = useState<ProductInput>(empty);
  const [bom, setBom] = useState<BomLine[]>([]);
  const [models, setModels] = useState<ModelMetadata[]>([]);
  const [history, setHistory] = useState<Analysis[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [costs, setCosts] = useState<CostState>(() => JSON.parse(localStorage.getItem("fta-costs") || "null") ?? initialCosts);
  const [originScenario, setOriginScenario] = useState<OriginScenario>(() => JSON.parse(localStorage.getItem("fta-origin-scenario") || "{}"));
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [finishedRun, setFinishedRun] = useState<Record<string, unknown> | null>(null);
  const [rawRuns, setRawRuns] = useState<Record<string, ModelRunResult>>({});
  const [rules, setRules] = useState<Array<Record<string, unknown>>>([]);
  const [costResult, setCostResult] = useState<Record<string, any> | null>(null);
  const [costResultKey, setCostResultKey] = useState("");
  const [months, setMonths] = useState(3);
  const [repetitions, setRepetitions] = useState(3000);
  const [forecast, setForecast] = useState<ModelRunResult | null>(null);
  const [forecastKey, setForecastKey] = useState("");

  useEffect(() => {
    localStorage.setItem("fta-step", page);
    localStorage.setItem("fta-costs", JSON.stringify(costs));
    localStorage.setItem("fta-origin-scenario", JSON.stringify(originScenario));
  }, [page, costs, originScenario]);
  useEffect(() => {
    void Promise.all([api.health(), api.models(), api.products()]).then(([health, modelList, saved]) => {
      setApiOnline(health.status === "ok"); setModels(modelList); setProducts(saved);
      const remembered = localStorage.getItem("fta-product-id");
      if (remembered && saved.some(item => item.product_id === remembered)) void selectProduct(remembered, saved);
    }).catch(() => setApiOnline(false));
  // Product restoration is intentionally one-time; selectProduct is stable for this initial load.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function selectProduct(id: string, list = products) {
    setBusy(true);
    try {
      const loaded = await api.product(id);
      const picked = list.find(item => item.product_id === id) ?? loaded.product;
      setProduct(picked); setDraft(productInput(loaded.product)); setBom(loaded.bom); setAnalysis(null);
      setHistory(await api.productAnalyses(id)); localStorage.setItem("fta-product-id", id);
      setNotice("");
    } catch (error) { setNotice(error instanceof Error ? error.message : "제품 조회에 실패했습니다."); }
    finally { setBusy(false); }
  }
  function startNewProduct() {
    setProduct(null); setDraft(empty); setBom([emptyLine()]); setAnalysis(null); setHistory([]); setFinishedRun(null); setRawRuns({});
    localStorage.removeItem("fta-product-id"); setPage("product");
  }
  async function saveProduct() {
    if (!draft.product_name.trim()) { setNotice("제품명을 입력하세요."); return; }
    setBusy(true); setNotice("");
    try {
      const saved = product ? await api.updateProduct(product.product_id, draft) : await api.createProduct(draft);
      const savedBom = await api.replaceBom(saved.product_id, bom.filter(line => line.material_name.trim()));
      setProduct(saved); setDraft(productInput(saved)); setBom(savedBom.lines);
      setProducts(await api.products()); localStorage.setItem("fta-product-id", saved.product_id);
      setNotice("제품과 BOM을 저장했습니다.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "저장에 실패했습니다."); }
    finally { setBusy(false); }
  }
  const bomCost = bom.reduce((sum, line) => sum + line.quantity * (line.unit_value ?? 0), 0);
  const priceComplete = bom.length > 0 && bom.every(line => line.unit_value !== undefined && (!line.currency || line.currency.toUpperCase() === "KRW"));
  const estimatedFob = priceComplete
    ? bomCost + costs.manufacturing + costs.packaging + (costs.freightIncluded ? costs.freight : 0) + costs.other + costs.profit : undefined;
  const selectedFob = costs.useActual ? costs.actual ?? product?.fob_value : estimatedFob;
  const selectedOriginCost = bom.reduce((sum, line, index) => {
    const scenario = originScenario[lineKey(line, index)] ?? "unknown";
    const evidenceAccepted = line.origin_confirmed && line.is_originating === true && line.origin_evidence_verified;
    return sum + (evidenceAccepted || scenario === "domestic" ? 0 : line.quantity * (line.unit_value ?? 0));
  }, 0);
  const scenarioRvc = priceComplete && selectedFob && selectedFob > 0 ? (selectedFob - selectedOriginCost) / selectedFob * 100 : undefined;
  const costInputKey = JSON.stringify({ product: product?.product_id, fob: selectedFob, costs, bom: bom.map((line, index) => [lineKey(line, index), line.quantity, line.unit_value, line.currency, line.origin_country, line.is_originating, line.origin_confirmed, line.origin_evidence_verified, line.hs_code, line.hs_code_confirmed]) });
  const runCostSimulation = async () => {
    if (!product) return;
    setBusy(true);
    try {
      const response = await api.costSimulation({ product_id: product.product_id, agreement_code: "KOREA_VIETNAM", as_of_date: new Date().toISOString().slice(0, 10), manufacturing_cost: costs.manufacturing, packaging_cost: costs.packaging, freight_cost: costs.freight, freight_included_in_fob: costs.freightIncluded, other_cost: costs.other, profit: costs.profit, use_actual_fob: costs.useActual, actual_fob: costs.actual ?? product.fob_value, scenario_threshold_percent: costs.scenarioThreshold });
      setCostResult(response as unknown as Record<string, any>); setCostResultKey(costInputKey);
    } catch (error) { setNotice(error instanceof Error ? error.message : "비용 시뮬레이션 요청에 실패했습니다."); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    if (!product || selectedFob === undefined || selectedFob <= 0) { setCostResult(null); setCostResultKey(""); return; }
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const response = await api.costSimulation({ product_id: product.product_id, agreement_code: "KOREA_VIETNAM", as_of_date: new Date().toISOString().slice(0, 10), manufacturing_cost: costs.manufacturing, packaging_cost: costs.packaging, freight_cost: costs.freight, freight_included_in_fob: costs.freightIncluded, other_cost: costs.other, profit: costs.profit, use_actual_fob: costs.useActual, actual_fob: costs.actual ?? product.fob_value, scenario_threshold_percent: costs.scenarioThreshold });
        if (active) { setCostResult(response as unknown as Record<string, any>); setCostResultKey(costInputKey); }
      } catch { if (active) { setCostResult(null); setCostResultKey(""); } }
    }, 350);
    return () => { active = false; window.clearTimeout(timer); };
  }, [product?.product_id, selectedFob, costs, bom, costInputKey]);
  async function recommendFinishedHs() {
    setBusy(true);
    try { setFinishedRun(await api.predictFinishedHs({ product_name: draft.product_name, ingredients_kr: draft.ingredients_kr, ingredients_en: draft.ingredients_en, form_packaging: draft.form_packaging, intended_use: draft.intended_use })); }
    catch (error) { setNotice(error instanceof Error ? error.message : "완제품 HS 추천에 실패했습니다."); }
    finally { setBusy(false); }
  }
  async function recommendRawHs(index: number) {
    const line = bom[index]; if (!line?.material_name.trim()) return;
    setRawRuns(current => ({ ...current, [lineKey(line, index)]: { status: "running" } as ModelRunResult }));
    try { const result = await api.runModel("raw_material_hs", { material_name: line.material_name, description: line.description ?? "", composition: "", intended_use: "" }); setRawRuns(current => ({ ...current, [lineKey(line, index)]: result })); }
    catch (error) { setNotice(error instanceof Error ? error.message : "원재료 HS4 추천에 실패했습니다."); }
  }
  async function loadRules() {
    if (!draft.hs_code) { setRules([]); return; }
    try { setRules(await api.agreementRules("KOREA_VIETNAM", draft.hs_code, new Date().toISOString().slice(0, 10))); }
    catch { setRules([]); }
  }
  async function runIntegratedAnalysis() {
    if (!product) return;
    setBusy(true);
    try {
      const record = await api.runAnalysis({ product_id: product.product_id, agreement_code: "KOREA_VIETNAM", as_of_date: new Date().toISOString().slice(0, 10), ...(selectedFob && selectedFob > 0 ? { fob_override: selectedFob, fob_override_source: costs.useActual ? "actual_transaction" : "cost_estimate" } : {}) });
      setAnalysis(record); setHistory(await api.productAnalyses(product.product_id)); setNotice("통합 분석을 완료했습니다. 결과와 분석 이력을 저장했습니다.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "통합 분석 실행에 실패했습니다."); }
    finally { setBusy(false); }
  }
  const forecastSignature = useMemo(() => JSON.stringify({ fob: selectedFob, threshold: costs.scenarioThreshold, months, repetitions, bom: bom.map((line, index) => [lineKey(line, index), line.quantity, line.unit_value, line.origin_country, line.is_originating, line.origin_confirmed, line.origin_evidence_verified, line.hs_code, line.hs_code_confirmed, originScenario[lineKey(line, index)]]) }), [selectedFob, costs.scenarioThreshold, months, repetitions, bom, originScenario]);
  async function runVnm() {
    if (!product || !selectedFob || selectedFob <= 0) return setNotice("유효한 FOB 값이 필요합니다.");
    setBusy(true);
    try {
      const threshold = USER_COSMETICS_CRITERION.rvcThresholdPercent;
      const result = await api.runModel("vnm", { product_id: product.product_id, fob: selectedFob, months, n_sim: repetitions, seed: 42, threshold, bom: bom.map((line, index) => {
        const key = lineKey(line, index); const assumption = originScenario[key] ?? "unknown";
        return { material_id: line.rvc_material_id ?? line.line_id ?? key, material_name: line.material_name, cost_krw: line.quantity * (line.unit_value ?? 0), status: assumption === "domestic" || (assumption === "unknown" && line.origin_confirmed && line.is_originating === true && line.origin_evidence_verified) ? "원산지 확인" : assumption === "foreign" ? "비원산지" : "미상" };
      }) });
      setForecast(result); setForecastKey(forecastSignature);
    } catch (error) { setNotice(error instanceof Error ? error.message : "VNM 시뮬레이션 요청에 실패했습니다."); }
    finally { setBusy(false); }
  }
  const move = (delta: number) => setPage(stages[Math.max(0, Math.min(stages.length - 1, stages.findIndex(step => step.id === page) + delta))].id);
  const loadHistory = async (analysisId: string) => { setAnalysis(await api.analysis(analysisId)); };
  const shared = { products, product, draft, setDraft, bom, setBom, history, loadHistory, models, apiOnline, busy, notice, setNotice, costs, setCosts, originScenario, setOriginScenario, selectedFob, estimatedFob, bomCost, scenarioRvc, costResult: costResultKey === costInputKey ? costResult : null, setCostResult, runCostSimulation, finishedRun, setFinishedRun, recommendFinishedHs, rawRuns, recommendRawHs, rules, loadRules, forecast, forecastStale: !forecast || forecastKey !== forecastSignature, months, setMonths, repetitions, setRepetitions, runVnm, analysis, setAnalysis, selectProduct, startNewProduct, saveProduct, runIntegratedAnalysis };
  return <Layout page={page} setPage={setPage} stages={stages} selectedProductName={product?.product_name ?? "제품을 선택하세요"}>
    <div className="workflow-content">
      {notice && <div className="toast">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      <div className="workflow-step-nav">{stages.map((step, index) => <button key={step.id} className={page === step.id ? "current" : ""} onClick={() => setPage(step.id)}><span>{index}</span><b>{step.label}</b></button>)}</div>
      <div className="page-intro workflow-intro"><div><p className="eyebrow">FTA COMPASS · {String(stages.findIndex(step => step.id === page)).padStart(2, "0")}</p><h2>{stages.find(step => step.id === page)?.label}</h2><p>{stages.find(step => step.id === page)?.hint}</p></div><div className="selected-product-chip">{product?.product_name ?? "선택된 제품 없음"}</div></div>
      {page === "dashboard" && <ProductManager {...shared} />}
      {page === "product" && <ProductEditor {...shared} />}
      {page === "fob" && <FobSetup {...shared} />}
      {page === "origin" && <OriginReview {...shared} />}
      {page === "vnm" && <VnmSimulation {...shared} />}
      {page === "extras" && <Extras />}
      {page === "results" && <AnalysisResults analysis={analysis} setPage={setPage} />}
      <div className="workflow-footer"><button className="secondary" disabled={page === "dashboard"} onClick={() => move(-1)}><ArrowLeft size={16}/> 이전</button><div>선택 제품: <b>{product?.product_name ?? "제품 없음"}</b></div><button className="primary" disabled={page === "extras"} onClick={() => move(1)}>다음 <ArrowRight size={16}/></button></div>
    </div>
  </Layout>;
}
function ProductManager(props: any) {
  const { products, product, selectProduct, startNewProduct, history, loadHistory, analysis, apiOnline } = props;
  return <div className="workflow-grid"><Card>
    <div className="card-head"><div><p className="eyebrow">SAVED PRODUCTS</p><h3>저장된 제품</h3></div><button className="primary" onClick={startNewProduct}><Plus size={16}/> 새 제품</button></div>
    {products.length ? <div className="product-list">{products.map((item: Product) => <button key={item.product_id} className={`product-list-row ${product?.product_id === item.product_id ? "selected" : ""}`} onClick={() => void selectProduct(item.product_id)}><span><strong>{item.product_name}</strong><small>{item.hs_code ?? "HS4 미확정"} · {new Date(item.updated_at).toLocaleDateString("ko-KR")}</small></span><ArrowRight size={16}/></button>)}</div> : <EmptyState title="저장된 제품이 없습니다" message="새 제품을 만들어 업무를 시작하세요."/>}
  </Card><div className="stack"><Card><p className="eyebrow">CONNECTION</p><h3>연결 상태</h3><StatusBadge status={apiOnline ? "succeeded" : "not_connected"}/><p className="muted-copy">등록 모델 {props.models.length}개</p></Card>
    <Card><p className="eyebrow">ANALYSIS HISTORY</p><h3>선택 제품 분석 이력</h3>{history.length ? history.map((entry: Analysis) => <button className="history-row history-button" key={entry.analysis_id} onClick={() => void loadHistory(entry.analysis_id)}><StatusBadge status={entry.status}/><span>{new Date(entry.created_at).toLocaleString("ko-KR")}</span><ArrowRight size={14}/></button>) : <p className="muted-copy">분석 이력이 없습니다.</p>}</Card>
    {analysis && <Card><p className="eyebrow">SELECTED ANALYSIS</p><h3>{analysis.as_of_date} · {analysis.agreement_code}</h3><pre className="model-json">{JSON.stringify(analysis, null, 2)}</pre></Card>}
  </div></div>;
}
function ProductEditor(p: any) {
  const { draft, setDraft, bom, setBom, saveProduct, busy, finishedRun, recommendFinishedHs, rawRuns, recommendRawHs } = p;
  const updateBom = (index: number, update: Partial<BomLine>) => setBom(bom.map((line: BomLine, i: number) => i === index ? { ...line, ...update } : line));
  const candidates = (finishedRun?.candidates ?? []) as Array<Record<string, any>>;
  return <div className="stack">
    <Card><div className="card-head"><div><p className="eyebrow">PRODUCT PROFILE</p><h3>제품 정보</h3></div><button className="primary" disabled={busy} onClick={() => void saveProduct()}><Save size={16}/> 제품 / BOM 저장</button></div>
      <div className="form-fields"><Field label="완제품명" value={draft.product_name} onChange={v => setDraft({ ...draft, product_name: v })}/><Field label="주요 성분 (국문)" value={draft.ingredients_kr} onChange={v => setDraft({ ...draft, ingredients_kr: v })}/><Field label="주요 성분 (INCI)" value={draft.ingredients_en} onChange={v => setDraft({ ...draft, ingredients_en: v })}/><Field label="물품 형태 / 포장" value={draft.form_packaging} onChange={v => setDraft({ ...draft, form_packaging: v })}/><Field label="용도" value={draft.intended_use} onChange={v => setDraft({ ...draft, intended_use: v })}/><Field label="완제품 HS4" value={draft.hs_code ?? ""} onChange={v => setDraft({ ...draft, hs_code: v, hs_code_confirmed: false })}/></div>
      <label className="check"><input type="checkbox" checked={draft.hs_code_confirmed} onChange={e => setDraft({ ...draft, hs_code_confirmed: e.target.checked })}/> 제품 HS 코드를 확인했습니다.</label>
      <div className="inline-actions"><button className="secondary" disabled={busy || !draft.product_name.trim()} onClick={() => void recommendFinishedHs()}><Sparkles size={15}/> 완제품 HS4 Top 3 추천</button><span className="muted-copy">추천은 법적 확정이 아닙니다. 사용자가 확인 후 저장하세요.</span></div>
      {finishedRun && <div className="candidate-list">{candidates.length ? candidates.slice(0, 3).map((candidate, i) => { const code = String(candidate.hs4 ?? candidate.code ?? ""); const score = typeof candidate.rrf_score === "number" ? candidate.rrf_score : null; const examples = Array.isArray(candidate.matched_cases) ? candidate.matched_cases : []; const label = String(candidate.label ?? candidate.description ?? (examples[0]?.product_name ? `유사 제품 사례: ${examples[0].product_name}` : "품목명 데이터 없음")); return <button className={`candidate-row ${i === 0 ? "candidate-first" : ""}`} key={code || i} onClick={() => setDraft({ ...draft, hs_code: code, hs_code_confirmed: false })}><strong className="candidate-rank">{i + 1}순위</strong><b className="candidate-code">HS {code}</b><span className="candidate-label">{label}</span><span className="candidate-score">{score == null ? "점수 없음" : `RRF 순위 융합 점수 ${score.toFixed(4)}`}</span></button>; }) : <pre className="model-json">{JSON.stringify(finishedRun, null, 2)}</pre>}</div>}
    </Card>
    <Card><div className="card-head"><div><p className="eyebrow">BILL OF MATERIALS</p><h3>BOM 원재료</h3></div><button className="secondary" onClick={() => setBom([...bom, emptyLine()])}><Plus size={15}/> 원재료 추가</button></div>
      <div className="bom-table"><div className="bom-head"><span>원재료명</span><span>소요량</span><span>단위</span><span>구매단가 (KRW)</span><span>원산지</span><span/></div>
        {bom.map((line: BomLine, index: number) => { const modelRun = rawRuns[lineKey(line, index)]; const result = modelRun?.result as Record<string, any> | null; return <div className="bom-record" key={lineKey(line, index)}><div className="bom-row"><input placeholder="원재료명" value={line.material_name} onChange={e => updateBom(index, { material_name: e.target.value })}/><input type="number" min="0" step="any" value={line.quantity} onChange={e => updateBom(index, { quantity: Number(e.target.value) })}/><input value={line.unit} onChange={e => updateBom(index, { unit: e.target.value, unit_price_unit: e.target.value })}/><input type="text" inputMode="decimal" value={priceDisplay(line.unit_value)} onChange={e => updateBom(index, { unit_value: parsePrice(e.target.value) })}/><select value={line.origin_country === "KR" ? "domestic" : line.origin_country === "FOREIGN" ? "foreign" : "unknown"} onChange={e => updateBom(index, e.target.value === "domestic" ? { origin_country: "KR", is_originating: true, origin_confirmed: true, origin_evidence_verified: false } : e.target.value === "foreign" ? { origin_country: "FOREIGN", is_originating: false, origin_confirmed: true, origin_evidence_verified: false } : { origin_country: "UNKNOWN", is_originating: undefined, origin_confirmed: false, origin_evidence_verified: false })}><option value="domestic">국내산</option><option value="foreign">국외산</option><option value="unknown">미상</option></select><button className="icon-button" onClick={() => setBom(bom.filter((_: BomLine, i: number) => i !== index))}>×</button></div>
          <div className="bom-extra"><button className="text-button" disabled={!line.material_name.trim()} onClick={() => void recommendRawHs(index)}><Search size={14}/> HS4 추천</button><MaterialHsControls line={line} result={result} onChange={(update: Partial<BomLine>) => updateBom(index, update)}/>{modelRun && <><StatusBadge status={modelRun.status}/>{result && <span>Top 1: {String((result.candidates as any[])?.[0]?.hs4 ?? result.decision_status ?? "미확정")}</span>}{modelRun.warnings?.map((warning: string) => <small key={warning}>{warning}</small>)}</>}</div>
        </div>; })}
      </div><p className="muted-copy">원산지 선택과 HS4 추천 결과는 자동 확정되지 않습니다. 단위와 구매단가 기준을 맞추세요. 소요량 × 구매단가가 BOM 투입금액입니다.</p>
    </Card>
  </div>;
}
function FobSetup(p: any) {
  const { product, costs, setCosts, selectedFob, estimatedFob, bomCost, scenarioRvc } = p;
  const updateCost = (key: keyof CostState, value: number | boolean | null) => setCosts({ ...costs, [key]: value });
  return <div className="stack"><Card><div className="card-head"><div><p className="eyebrow">FOB COST BUILDER</p><h3>선택 제품 BOM 기반 비용</h3></div><button className="secondary" onClick={() => void p.runCostSimulation()}><RefreshCw size={15}/> 백엔드 계산 새로고침</button></div>
    <div className="simulator-grid"><Cost label="원재료비 (BOM 자동 합산)" value={bomCost} readOnly/><Cost label="제조비" value={costs.manufacturing} max={50000} onChange={(v: number) => updateCost("manufacturing", v)}/><Cost label="포장비" value={costs.packaging} max={20000} onChange={(v: number) => updateCost("packaging", v)}/><Cost label="운송비" value={costs.freight} max={30000} onChange={(v: number) => updateCost("freight", v)}/><Cost label="기타 비용" value={costs.other} max={20000} onChange={(v: number) => updateCost("other", v)}/><Cost label="이윤" value={costs.profit} max={50000} onChange={(v: number) => updateCost("profit", v)}/></div>
    <label className="check"><input type="checkbox" checked={costs.freightIncluded} onChange={e => updateCost("freightIncluded", e.target.checked)}/> 운송비를 FOB에 포함</label><div className="form-fields fob-actual"><Field label="실제 거래 FOB (KRW)" value={String(costs.actual ?? product?.fob_value ?? "")} onChange={v => updateCost("actual", v ? Math.max(0, Number(v)) : null)}/><label className="check"><input type="checkbox" checked={costs.useActual} onChange={e => updateCost("useActual", e.target.checked)}/> 확정 거래 FOB 사용</label></div>
    <div className="simulator-summary"><Kpi label="BOM 원재료비" value={won(bomCost)}/><Kpi label="비용 추정 FOB" value={won(estimatedFob)}/><Kpi label={costs.useActual ? "실제 거래 FOB" : "선택 예상 FOB"} value={won(selectedFob)}/><Kpi label="현재 RVC" value={percent(scenarioRvc)}/></div><p className="muted-copy">실제 FOB와 비용 추정 FOB를 구분합니다. 비용 추정값은 거래 확정값이 아닙니다.</p>
  </Card><ScenarioCard {...p}/></div>;
}
function ScenarioCard(p: any) {
  const { bom, originScenario, setOriginScenario, selectedFob, scenarioRvc } = p;
  const vnm = selectedFob && scenarioRvc !== undefined ? selectedFob * (1 - scenarioRvc / 100) : undefined;
  return <Card><p className="eyebrow">ORIGIN ASSUMPTIONS</p><h3>원산지 미상 재료 가정 시나리오</h3>{bom.length ? bom.map((line: BomLine, index: number) => { const id = lineKey(line, index); const base = line.origin_country === "KR" ? "domestic" : line.origin_country === "FOREIGN" ? "foreign" : "unknown"; const value = originScenario[id] ?? base; const isUnknown = base === "unknown"; return <div className="scenario-row" key={id}><span><b>{line.material_name || `원재료 ${index + 1}`}</b><small>{won(line.quantity * (line.unit_value ?? 0))}</small></span>{isUnknown ? <select value={value} onChange={e => setOriginScenario({ ...originScenario, [id]: e.target.value })}><option value="unknown">미상 유지</option><option value="domestic">국내 원산지 인정 가정</option><option value="foreign">국외 원산지 가정</option></select> : <span className="muted-copy">{base === "domestic" ? "저장된 국내산" : "저장된 국외산"}</span>}</div>; }) : <EmptyState title="BOM을 불러오세요" message="제품 입력 단계에서 BOM을 저장하면 여기에 표시됩니다."/>}<div className="simulator-summary"><Kpi label="가정 VNM" value={won(vnm)}/><Kpi label="가정 RVC" value={percent(scenarioRvc)}/><Kpi label="사용 FOB" value={won(selectedFob)}/></div><p className="warning-copy">시나리오 화면의 가정이며 저장된 BOM 원산지 상태를 변경하지 않습니다.</p></Card>;
}
function OriginReview(p: any) {
  const { product, draft, rules, loadRules, costResult, runCostSimulation, scenarioRvc, selectedFob, bom, analysis, runIntegratedAnalysis, busy, originScenario } = p;
  useEffect(() => { void loadRules(); }, [draft.hs_code]);
  const copy = { noPsr:"공식 PSR 데이터는 조회되지 않았습니다. 아래는 사용자가 제공한 화장품 기준을 적용한 시나리오입니다.", userRule:"사용자 제공 기준", evidence:"미상 원재료 증빙 추천", pending:"확인 보류", pass:"충족", fail:"미충족", needsHs:"완제품 및 BOM HS4 확인 필요", needsValue:"FOB/BOM 확인 필요", noTargets:"추천 가능한 미상 원재료가 없습니다.", noCombo:"입력된 HS/가격으로는 충족 조합을 계산할 수 없습니다.", already:"현재 기준 시나리오가 충족되어 추가 증빙 조합을 추천하지 않습니다.", conservative:"미상 재료는 비원산지로 계산합니다. 국내 원산지 인정은 가정 시나리오에만 반영하며 BOM은 변경하지 않습니다.", legal:"통합 API 법적 판정은 검증된 PSR 기준이며 사용자 시나리오와 구분됩니다.", minSet:"최소 증빙 조합" };
  const rows = rules as Array<Record<string, any>>;
  const officialPsr = rows.length > 0 && rows.every((rule: Record<string, any>) => rule.verified === true && (rule.source_title || rule.source_url));
  const productHs4 = String(draft.hs_code ?? "").replace(/\D/g, "").slice(0, 4);
  const hs4 = (line: BomLine) => String(line.hs_code ?? "").replace(/\D/g, "").slice(0, 4);
  const domestic = (line: BomLine, i: number) => Boolean(line.origin_confirmed && line.is_originating === true && line.origin_evidence_verified) || originScenario[lineKey(line, i)] === "domestic";
  const nonOrigin: BomLine[] = (bom as BomLine[]).filter((line, i) => !domestic(line, i));
  const cthKnown = Boolean(draft.hs_code_confirmed && productHs4.length === 4 && bom.length > 0 && nonOrigin.every(line => line.hs_code_confirmed && hs4(line).length === 4));
  const cth: boolean | undefined = cthKnown ? nonOrigin.every(line => hs4(line) !== productHs4) : undefined;
  const rvc = scenarioRvc as number | undefined; const rvcPass = rvc == null ? undefined : rvc >= 40;
  const combined: boolean | undefined = cth === true || rvcPass === true ? true : cth === false && rvcPass === false ? false : undefined;
  const fob = Number(selectedFob) > 0 ? Number(selectedFob) : undefined; const vnm = rvc != null && fob ? fob * (1 - rvc / 100) : undefined;
  type Candidate = { line: BomLine; index: number; id: string; cost: number };
  const unknown: Candidate[] = (bom as BomLine[]).map((line, index) => ({ line, index, id: String(line.line_id ?? line.rvc_material_id ?? lineKey(line, index)), cost: line.quantity * (line.unit_value ?? 0) })).filter((x: Candidate) => x.cost > 0 && (x.line.origin_country === "UNKNOWN" || x.line.is_originating == null) && (originScenario[lineKey(x.line, x.index)] ?? "unknown") === "unknown");
  const recommendation = (() => {
    if (combined === true || !fob || vnm == null || !unknown.length) return null;
    const assess = (chosen: Candidate[]) => { const ids = new Set(chosen.map((x: Candidate) => x.id)); const remaining = (bom as BomLine[]).filter((line, index) => domestic(line, index) ? false : !ids.has(String(line.line_id ?? line.rvc_material_id ?? lineKey(line, index)))); const known = draft.hs_code_confirmed && productHs4.length === 4 && remaining.every(line => line.hs_code_confirmed && hs4(line).length === 4); const cthAfter = known ? remaining.every(line => hs4(line) !== productHs4) : undefined; const recovered = chosen.reduce((sum: number, x: Candidate) => sum + x.cost, 0); const rvcAfter = (fob - Math.max(0, vnm - recovered)) / fob * 100; return { qualifies: cthAfter === true || rvcAfter >= 40, cthAfter, rvcAfter, excess: rvcAfter >= 40 ? rvcAfter - 40 : 0 }; };
    for (let size = 1; size <= unknown.length; size++) { const valid: Array<{ items: Candidate[]; outcome: ReturnType<typeof assess> }> = []; const visit = (at: number, chosen: Candidate[]) => { if (chosen.length === size) { const outcome = assess(chosen); if (outcome.qualifies) valid.push({ items: chosen, outcome }); return; } for (let i = at; i <= unknown.length - size + chosen.length; i++) visit(i + 1, [...chosen, unknown[i]]); }; visit(0, []); if (valid.length) return valid.sort((a, b) => a.outcome.excess - b.outcome.excess || a.items.map(x => x.id).join("|").localeCompare(b.items.map(x => x.id).join("|")))[0]; } return null;
  })();
  return <div className="stack">
    <Card>
      <div className="card-head"><div><p className="eyebrow">FTA PRODUCT SPECIFIC RULE</p><h3>{product?.product_name ?? draft.product_name} - HS {draft.hs_code ?? "Not confirmed"}</h3></div><button className="secondary" onClick={() => void runCostSimulation()}><RefreshCw size={15}/> Refresh</button></div>
      {officialPsr ? rows.map((rule: Record<string, any>, i: number) => <div className="rule-row" key={i}><b>{String(rule.criterion)}</b><span>{rule.criterion === "RVC" ? `RVC ${String(rule.rvc_threshold_percent)}%` : `CTH ${String(rule.cth_digits)}-digit`}</span><StatusBadge status="succeeded"/></div>) : <p className="muted-copy">{copy.noPsr}</p>}
      <div className="rule-row"><b>{copy.userRule}</b><span>CTH HS4 OR RVC 40%</span><StatusBadge status="succeeded"/></div>
      <p className="muted-copy">KOREA_VIETNAM - User-provided cosmetics criteria - Separate from official PSR database.</p>
    </Card>
    <div className="grid-2">
      <Card><p className="eyebrow">RULE ASSESSMENT</p><h3>CTH / RVC / Combined</h3>
        <div className="rule-row"><b>CTH HS4</b><strong>{cth === undefined ? copy.pending : cth ? copy.pass : copy.fail}</strong><span>{cth === undefined ? copy.needsHs : `${nonOrigin.length} non-origin or unknown materials compared`}</span></div>
        <div className="rule-row"><b>RVC 40%</b><strong>{percent(rvc)}</strong><span>{rvcPass === undefined ? copy.needsValue : rvcPass ? copy.pass : `Short by ${Math.max(0, 40 - rvc!).toFixed(2)}%p`}</span></div>
        <div className="rule-row"><b>OR</b><strong>{combined === undefined ? copy.pending : combined ? "Scenario criterion met" : "Scenario criterion not met"}</strong><span>Either CTH or RVC is sufficient</span></div>
        <p className="muted-copy">{copy.conservative}</p>
      </Card>
      <Card><p className="eyebrow">ORIGIN EVIDENCE IMPACT</p><h3>{copy.evidence}</h3>
        {unknown.length ? unknown.map((x: Candidate) => <div className="scenario-row" key={x.id}><span><b>{x.line.material_name || "Raw material"}</b><small>{won(x.cost)} - RVC +{fob ? (x.cost / fob * 100).toFixed(2) : "-"}%p{hs4(x.line) === productHs4 && productHs4 ? " - May improve CTH if domestic origin is recognized" : ""}</small></span></div>) : <p className="muted-copy">{copy.noTargets}</p>}
        {recommendation ? <div className="recommended-box"><b>{copy.minSet} - {recommendation.items.length}</b>{recommendation.items.map((x: Candidate) => <p key={x.id}>{x.line.material_name} - {won(x.cost)} - +{(x.cost / (fob || 1) * 100).toFixed(2)}%p</p>)}<p>RVC {recommendation.outcome.rvcAfter.toFixed(2)}% - {recommendation.outcome.cthAfter ? "CTH" : "RVC"} {copy.pass}</p></div> : combined === true ? <p className="muted-copy">{copy.already}</p> : unknown.length ? <p className="warning-copy">{copy.noCombo}</p> : null}
        {costResult?.rvc?.warnings?.length ? <p className="muted-copy">{costResult.rvc.warnings.join(" ")}</p> : null}
      </Card>
    </div>
    <Card><div className="card-head"><div><p className="eyebrow">INTEGRATED ANALYSIS</p><h3>Integrated analysis</h3></div><button className="primary" disabled={!product || busy} onClick={() => void runIntegratedAnalysis()}><Sparkles size={16}/> Run analysis</button></div><p className="muted-copy">{copy.legal} - FOB {won(selectedFob)} - BOM {bom.length}</p>{analysis && <StatusBadge status={analysis.status}/>}</Card>
  </div>;
}

function VnmSimulation(p: any) {
  const { forecast, forecastStale, months, setMonths, repetitions, setRepetitions, runVnm, busy, selectedFob, bom, costs } = p;
  const data = forecast?.result as Record<string, any> | null;
  const monthly = Array.isArray(data?.monthly) ? data.monthly : [];
  const displayThreshold = USER_COSMETICS_CRITERION.rvcThresholdPercent;
  const thresholdLabel = "사용자 제공 화장품 기준";
  return <div className="stack"><Card><div className="card-head"><div><p className="eyebrow">RVC-PREDICTION ENGINE</p><h3>현재 FOB 및 원산지 시나리오 기반 예측</h3></div><StatusBadge status={forecastStale ? "not_started" : forecast?.status ?? "not_started"}/></div>
    <div className="form-fields"><label className="field">예측 기간 (개월)<input type="number" min="1" max="12" value={months} onChange={e => setMonths(Math.max(1, Math.min(12, Number(e.target.value))))}/></label><label className="field">Monte Carlo 반복 횟수<input type="number" min="100" max="100000" step="100" value={repetitions} onChange={e => setRepetitions(Math.max(100, Math.min(100000, Number(e.target.value))))}/></label></div>
    <div className="simulator-summary"><Kpi label="사용 FOB" value={won(selectedFob)}/><Kpi label="시나리오 BOM" value={`${bom.length}개`}/><Kpi label="가격 데이터 기준" value="원본 가격 이력"/></div><p className="muted-copy">위험 기준: {displayThreshold}% · {thresholdLabel} (법적 기준 아님)</p><button className="primary" disabled={busy || !selectedFob || selectedFob <= 0} onClick={() => void runVnm()}><Sparkles size={16}/> 실제 ARMA / Monte Carlo 실행</button>
    {forecastStale && forecast && <p className="warning-copy">FOB, 원산지 시나리오 또는 예측 설정이 변경되어 이전 결과가 오래된 상태입니다. 다시 실행하세요.</p>}{!forecast && <p className="muted-copy">버튼을 누르면 현재 선택한 FOB와 원산지 상태로 실제 엔진을 실행합니다. 가격 이력이 없는 원재료는 예측 불가 사유가 응답에 포함됩니다.</p>}
  </Card>{!forecastStale && forecast && <><Card><div className="card-head"><div><p className="eyebrow">FORECAST SUMMARY</p><h3>예측 요약</h3></div><span className="status status-warning">통계 시뮬레이션 · 법적 판정 아님</span></div><div className="forecast-overview"><span>현재 VNM: <b>{won(data?.current_vnm)}</b></span><span>현재 RVC: <b>{percent(data?.current_rvc)}</b></span><span>위험 기준: <b>{displayThreshold}% ({thresholdLabel})</b></span>{data?.available === false && <p className="warning-copy">예측 불가 사유: {(data?.missing ?? []).join(", ")}</p>}</div></Card>
    {monthly.length > 0 && <Card><h3>월별 RVC 예측</h3><div className="forecast-chart">{monthly.map((row: any, i: number) => <div className="forecast-bar" key={i}><span>{row.month ?? i + 1}월</span><div><i style={{ width: `${Math.max(0, Math.min(100, Number(row.mean_rvc ?? row.rvc_mean ?? 0)))}%` }}/></div><b>{percent(row.mean_rvc ?? row.rvc_mean)}</b><small>90% 예측구간 {percent(row.lo)} ~ {percent(row.hi)}</small><small>예상 VNM {won(row.mean_vnm)}</small><small>기준 미달 확률 {percent(row.risk ?? row.shortfall_probability)}</small></div>)}</div></Card>}
    {Array.isArray(data?.materials) && data.materials.length > 0 && <Card><h3>원재료별 변동 기여</h3>{data.materials.map((item: any, i: number) => <div className="scenario-row" key={item.material ?? i}><span><b>{item.material}</b><small>기준 비용 {won(item.base_cost)} · 예측 비용 {won(item.forecast_cost)}</small></span><strong>{won(Number(item.forecast_cost ?? 0) - Number(item.base_cost ?? 0))}</strong></div>)}</Card>}</>}</div>;
}
function Extras() { return <div className="grid-2"><Card><FileText size={22}/><h3>공급업체 원산지확인서 요청 이메일</h3><p className="muted-copy">요청 대상 BOM 원재료를 선택하고 요청 메일을 생성하는 기능은 준비 중입니다.</p><span className="status status-muted">준비 중</span></Card><Card><FileText size={22}/><h3>BOM 원산지 증빙 상태 / 체크리스트</h3><p className="muted-copy">증빙 파일 업로드와 서류별 상태 연결은 아직 구현되지 않았습니다.</p><span className="status status-muted">준비 중</span></Card></div>; }
function AnalysisResults({ analysis, setPage }: { analysis: Analysis | null; setPage: (page: Page) => void }) { return analysis ? <Card><div className="card-head"><div><p className="eyebrow">SAVED ANALYSIS</p><h3>통합 분석 결과</h3></div><StatusBadge status={analysis.status}/></div><pre className="model-json">{JSON.stringify(analysis, null, 2)}</pre><button className="secondary" onClick={() => setPage("origin")}>요건 화면으로</button></Card> : <EmptyState title="저장된 분석 결과가 없습니다" message="요건 화면에서 통합 분석을 실행하세요."/>; }
function Cost({ label, value, onChange, readOnly, max = 20000 }: any) { const sliderValue = Math.min(Math.max(0, Number(value) || 0), max); return <div className="cost-control"><label>{label}</label>{onChange ? <><input aria-label={`${label} slider`} type="range" min="0" max={max} step="100" value={sliderValue} onChange={e => onChange(Number(e.target.value))}/><input aria-label={`${label} amount`} type="text" inputMode="numeric" value={priceDisplay(Number(value) || 0)} onChange={e => onChange(parseCost(e.target.value))}/></> : <strong>{won(value)}</strong>}</div>; }
function parseCost(value: string) { const normalized = value.replace(/,/g, "").replace(/[^0-9]/g, ""); return normalized ? Math.max(0, Number(normalized)) : 0; }
function Kpi({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) { return <label className="field"><span>{label}</span><input value={value} onChange={e => onChange(e.target.value)}/></label>; }

function MaterialHsControls({ line, result, onChange }: { line: BomLine; result: Record<string, any> | null; onChange: (update: Partial<BomLine>) => void }) {
  const candidates = Array.isArray(result?.candidates) ? result.candidates as Array<Record<string, any>> : [];
  return <div className="material-hs-controls">
    <label>HS4 <input value={line.hs_code ?? ""} onChange={event => onChange({ hs_code: event.target.value, hs_code_confirmed: false })}/></label>
    <label className="mini-check"><input type="checkbox" checked={Boolean(line.hs_code_confirmed)} disabled={!line.hs_code} onChange={event => onChange({ hs_code_confirmed: event.target.checked })}/> HS4 확인</label>
    {candidates.slice(0, 3).map((candidate, rank) => <button type="button" className="hs-candidate-chip" key={String(candidate.hs4 ?? rank)} onClick={() => onChange({ hs_code: String(candidate.hs4 ?? ""), hs_code_confirmed: false })}>Top {rank + 1}: {String(candidate.hs4 ?? "미확정")}</button>)}
  </div>;
}
