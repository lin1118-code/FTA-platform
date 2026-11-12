import type { Analysis, BomLine, CostSimulationRequest, CostSimulationResponse, ModelMetadata, ModelRunResult, Product, ProductInput } from "../types/api";

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8013";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `API 요청 실패 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  models: () => request<ModelMetadata[]>("/api/models"),
  products: () => request<Product[]>("/api/products"),
  createProduct: (product: ProductInput) => request<Product>("/api/products", { method: "POST", body: JSON.stringify(product) }),
  updateProduct: (id: string, product: ProductInput) => request<Product>(`/api/products/${id}`, { method: "PUT", body: JSON.stringify(product) }),
  product: (id: string) => request<{ product: Product; bom: BomLine[] }>(`/api/products/${id}`),
  productAnalyses: (id: string) => request<Analysis[]>(`/api/products/${id}/analyses`),
  replaceBom: (id: string, lines: BomLine[]) => request<{ product_id: string; lines: BomLine[] }>(`/api/products/${id}/bom`, { method: "PUT", body: JSON.stringify({ lines }) }),
  runModel: (module: string, payload: Record<string, unknown>) => request<ModelRunResult>(`/api/models/${module}/run`, { method: "POST", body: JSON.stringify({ payload }) }),
  runAnalysis: (payload: { product_id: string; agreement_code: string; as_of_date: string; fob_override?: number; fob_override_source?: "actual_transaction" | "cost_estimate" }) => request<Analysis>("/api/analyses", { method: "POST", body: JSON.stringify(payload) }),
  costSimulation: (payload: CostSimulationRequest) => request<CostSimulationResponse>("/api/fta/cost-simulation", { method: "POST", body: JSON.stringify(payload) }),
  analysis: (id: string) => request<Analysis>(`/api/analyses/${id}`),
  agreementRules: (agreement: string, hsCode: string, asOf: string) => request<Array<Record<string, unknown>>>(`/api/agreement-rules?agreement_code=${encodeURIComponent(agreement)}&product_hs_code=${encodeURIComponent(hsCode)}&as_of_date=${encodeURIComponent(asOf)}`),
  predictFinishedHs: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/hs/finished/predict", { method: "POST", body: JSON.stringify({ ...payload, top_k: 3 }) }),
};
