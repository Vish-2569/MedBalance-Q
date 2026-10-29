export interface Facility {
  id: string;
  name: string;
  type: 'warehouse' | 'hospital';
  lat: number;
  lon: number;
  cold_storage: boolean;
}

export interface Drug {
  code: string;
  name: string;
  ven: 'V' | 'E' | 'N';
  unit: string;
  pack_size: number;
  cold_chain: boolean;
  controlled: boolean;
  min_residual_days: number;
}

export interface Lot {
  facility_id: string;
  drug_code: string;
  batch_no: string;
  expiry: string;
  qty: number;
}

export interface Position {
  facility_id: string;
  drug_code: string;
  effective_stock: number;
  at_risk: number;
  reserve: number;
  shortage: number;
  consumption_rate: number;
  target_days: number;
}

export interface Route {
  src_facility_id: string;
  dst_facility_id: string;
  distance_km: number;
  transit_hours: number;
  cold_chain: boolean;
}

export interface Vehicle {
  id: string;
  name: string;
  cold_chain: boolean;
  capacity_units: number;
}

export type OrderStatus = 'proposed' | 'approved' | 'rejected' | 'dispatched' | 'in_transit' | 'received' | 'consumed' | 'delivered' | 'cancelled';

export interface TransferOrder {
  id: string;
  dta_number: string;
  plan_id: string;
  src_facility_id: string;
  dst_facility_id: string;
  drug_code: string;
  drug_name: string;
  batch_no: string;
  qty: number;
  usable: number;
  score: number;
  status: OrderStatus;
  temperature_req: 'ambient' | 'cold_chain';
  created_at: string;
}

export interface PlanRun {
  id: string;
  created_at: string;
  mode: 'live' | 'whatif' | 'eval';
  solver_tier: string;
  energy?: number;
  gap_to_milp?: number;
  variables: number;
  constraints: number;
  transfers: number;
  shortage_reduction: number;
  expiry_avoided: number;
  cost_inr: number;
  solver_meta?: Record<string, unknown>;
  violations?: number;
}

export interface PlanDemo {
  plan: PlanRun;
  orders: TransferOrder[];
  candidates: Candidate[];
  regret: RegretEntry[];
}

export interface PlanRunResponse {
  plan: PlanRun;
  orders: TransferOrder[];
  metrics: Record<string, unknown>;
}

export interface Candidate {
  lot: Lot;
  destination_id: string;
  usable: number;
  score: number;
  selected: boolean;
}

export interface RegretEntry {
  order_id: string;
  alternative: string;
  reason: string;
  delta_score: number;
}

export interface SimClock {
  sim_date: string;
  sim_time: string;
  speed: number;
  running: boolean;
  day_index: number;
}

export interface Scenario {
  id?: string;
  name: string;
  description: string;
  active: boolean;
  params: Record<string, unknown>;
}

export interface Signal {
  id: string;
  type: string;
  params: Record<string, unknown>;
  fired_at: string;
}

export interface ColdchainStatus {
  device_id: string;
  vehicle_id: string;
  temperature_c: number;
  battery_pct: number;
  last_seen: string;
  alert: boolean;
  temperature_history: number[];
  state: 'ok' | 'warning' | 'excursion';
}

export interface BenchmarkRow {
  solver: string;
  objective: number;
  shortage_reduction: number;
  expiry_avoided_inr: number;
  waste_moved: number;
  trips: number;
  time_ms: number;
}

export interface ZoningComparison {
  maxcut: {
    partition: Record<string, number>;
    cut_value: number;
    intra_zone_cost: number;
    tier: string;
    approx_ratio: number | null;
  };
  kmeans: {
    partition: Record<string, number>;
    cut_value: number;
    intra_zone_cost: number;
  } | null;
  exact?: {
    partition: Record<string, number>;
    cut_value: number;
    intra_zone_cost: number;
  };
}

export interface Benchmark {
  plan_id: string;
  benchmark: BenchmarkRow[];
  gap_qubo_to_milp_pct: number | null;
  zoning: ZoningComparison;
}

export interface ReportItem {
  drug_code: string;
  drug_name: string;
  qty: number;
  unit?: string;
  batch_no: string | null;
  expiry: string | null;
  confidence: number;
}

export interface StockReport {
  id: string;
  facility_code: string;
  received_at: string;
  format: string;
  channel: 'fhir' | 'csv' | 'chat' | 'text';
  language: 'en' | 'kn' | 'mixed';
  status: string;
  items: ReportItem[];
  anomalies: string[];
  raw_text?: string;
  model?: string;
  prompt_id?: string;
}

export interface ReviewItem {
  id: string;
  report_id: string;
  facility_code: string;
  item_index: number;
  anomaly_type: string;
  anomaly_explanation: string;
  status: 'pending' | 'accepted' | 'corrected' | 'rejected' | 'auto_approved';
  drug_code: string;
  drug_name: string;
  extracted_qty: number;
  confidence: number;
  candidates: string[];
  resolved_qty?: number;
  resolved_expiry?: string;
  resolved_drug_code?: string;
  resolved_by?: string;
  resolved_at?: string;
}

export interface SSEEvent {
  id: string;
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface CustodyEvent {
  id: number;
  order_id: string;
  event_type: 'dispatch' | 'receive' | 'consume';
  actor: string;
  qty: number;
  timestamp: string;
  location: string;
  temperature_c: number | null;
  deviation: string | null;
  notes: string | null;
}

export interface AuditVerify {
  ok: boolean;
  entries: number;
  broken_at?: number | null;
}

export interface AIHealthData {
  status: string;
  provider: string;
  model_fast: string;
  model_smart: string;
  total_calls: number;
  cache_hit_rate: number;
  p95_latency_ms: number;
  schema_failures: number;
  fallbacks: number;
  firewall_blocks: number;
  prompts: { id: string; version: number; calls: number }[];
  eval_scores?: Record<string, number>;
}

export interface OrderDetail extends TransferOrder {
  qr_token?: string;
  vehicle_id?: string;
  dispatched_at?: string;
  received_at?: string;
  narration?: string;
  narration_grounded?: boolean;
  custody_events?: CustodyEvent[];
  qubo_terms?: {
    shortage_reward: number;
    trip_cost: number;
    overfill_penalty: number;
    batch_bonus: number;
    total: number;
  };
}

export interface ProvenanceNode {
  id: string;
  type: 'report' | 'extraction' | 'lot' | 'candidate' | 'order' | 'custody';
  label: string;
  meta?: Record<string, unknown>;
}

export interface ProvenanceEdge {
  source: string;
  target: string;
}

export interface Provenance {
  nodes: ProvenanceNode[];
  edges: ProvenanceEdge[];
}

export interface CopilotMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: { name: string; args: Record<string, unknown>; result?: unknown }[];
  timestamp: number;
}

export interface ResultMetrics {
  stockout_days_before: number;
  stockout_days_after: number;
  expired_value_inr: number;
  expired_value_avoided_inr: number;
  waste_moved_units: number;
  waste_moved_pct: number;
  shortage_reduction: number;
  ci_lower: number;
  ci_upper: number;
  ablation: AblationRow[];
}

export interface AblationRow {
  variant: string;
  shortage_reduction: number;
  expiry_avoided: number;
  cost_inr: number;
  note: string;
}
