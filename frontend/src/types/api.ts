export type RunStatus = "not_started" | "running" | "succeeded" | "failed" | "not_connected" | "insufficient_information";
export type ModelSource = "real_model" | "mock" | "rules_engine" | null;

export interface ModelMetadata {
  name: string;
  version: string | null;
  repository: string | null;
  source_commit: string | null;
  integration_status: "integrated" | "prototype" | "pending" | "mock";
}
export interface ModelRunResult {
  run_id: string;
  module: string;
  status: RunStatus;
  source: ModelSource;
  model: ModelMetadata;
  result: Record<string, unknown> | null;
  evidence: Array<Record<string, unknown> | string>;
  warnings: string[];
}
export interface BomLine {
  line_id?: string;
  material_name: string;
  description: string;
  quantity: number;
  unit: string;
  unit_price_unit?: string;
  unit_value?: number;
  currency?: string;
  rvc_material_id?: string;
  origin_country?: string;
  hs_code?: string;
  hs_code_confirmed?: boolean;
  is_originating?: boolean;
  origin_confirmed?: boolean;
  origin_evidence_verified?: boolean;
}
export interface ProductInput {
  product_name: string;
  ingredients_kr: string;
  ingredients_en: string;
  form_packaging: string;
  intended_use: string;
  description: string;
  hs_code?: string;
  hs_code_confirmed: boolean;
  fob_value?: number;
  fob_currency?: string;
}
export interface Product extends ProductInput { product_id: string; created_at: string; updated_at: string; }
export interface Analysis {
  analysis_id: string;
  product_id: string;
  agreement_code: string;
  as_of_date: string;
  status: RunStatus;
  steps: Record<string, RunStatus>;
  results: Record<string, unknown>;
  created_at: string;
}

export interface CostSimulationRequest {
  product_id: string;
  agreement_code: string;
  as_of_date: string;
  manufacturing_cost: number;
  packaging_cost: number;
  freight_cost: number;
  freight_included_in_fob: boolean;
  other_cost: number;
  profit: number;
  use_actual_fob: boolean;
  actual_fob?: number;
  scenario_threshold_percent?: number;
}

export interface EvidenceCandidate {
  material_id: string;
  material_name: string;
  cost_krw: number;
  rvc_improvement_percent_points: number | null;
  reason: string;
}

export interface OriginEvidenceRecommendation {
  status: RunStatus;
  legal_status: string;
  fob: number | null;
  fob_source: string;
  vnm_krw: number | null;
  current_rvc_percent: number | null;
  target_rvc_percent: number | null;
  target_source: string | null;
  shortfall_percent_points: number | null;
  unknown_origin_materials: EvidenceCandidate[];
  recommended_combination: EvidenceCandidate[];
  combination_status: string;
  predicted_rvc_after_combination_percent?: number;
  maximum_reachable_rvc_percent: number | null;
  rule_context: Record<string, unknown>;
  warnings: string[];
}

export interface CostSimulationResponse {
  status: RunStatus;
  fob_source: "actual_transaction" | "cost_estimate";
  actual_transaction_fob_krw?: number | null;
  estimated_fob_krw?: number | null;
  selected_fob_krw?: number | null;
  cost_breakdown_krw: Record<string, number>;
  missing_unit_prices: string[];
  non_krw_materials: string[];
  rvc: OriginEvidenceRecommendation;
  warnings: string[];
}
