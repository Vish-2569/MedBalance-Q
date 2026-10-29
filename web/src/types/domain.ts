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

export type OrderStatus = 'proposed' | 'approved' | 'rejected' | 'dispatched' | 'in_transit' | 'delivered' | 'cancelled';

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
}

export interface PlanDemo {
  plan: PlanRun;
  orders: TransferOrder[];
  candidates: Candidate[];
  regret: RegretEntry[];
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
  name: string;
  description: string;
  active: boolean;
  params: Record<string, unknown>;
}

export interface ColdchainStatus {
  device_id: string;
  vehicle_id: string;
  temperature_c: number;
  battery_pct: number;
  last_seen: string;
  alert: boolean;
}

export interface Benchmark {
  solver_tier: string;
  energy: number;
  milp_energy: number;
  gap: number;
  solve_time_ms: number;
}

export interface SSEEvent {
  id: string;
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface ReviewItem {
  id: string;
  report_id: string;
  item_index: number;
  extraction: Record<string, unknown>;
  suggested_fix?: Record<string, unknown>;
  status: 'pending' | 'accepted' | 'fixed' | 'rejected';
}

export interface StockReport {
  id: string;
  facility_code: string;
  reported_at: string;
  format: string;
  items: Record<string, unknown>[];
  raw_text?: string;
}
