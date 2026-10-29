import type {
  Facility, Drug, Lot, Position, Route, Vehicle,
  TransferOrder, PlanDemo, SimClock, Scenario,
  ColdchainStatus, Benchmark,
} from '@/types/domain';

export const facilities: Facility[] = [
  { id: 'W0', name: 'SIM-District Warehouse', type: 'warehouse', lat: 12.9716, lon: 77.5946, cold_storage: true },
  { id: 'H1', name: 'SIM-City Hospital', type: 'hospital', lat: 12.9352, lon: 77.6245, cold_storage: true },
  { id: 'H2', name: 'SIM-General Hospital', type: 'hospital', lat: 12.9611, lon: 77.5683, cold_storage: true },
  { id: 'H3', name: 'SIM-Community Health Centre', type: 'hospital', lat: 13.0358, lon: 77.5970, cold_storage: false },
  { id: 'H4', name: 'SIM-Primary Health Centre', type: 'hospital', lat: 12.8990, lon: 77.6510, cold_storage: false },
];

export const drugs: Drug[] = [
  { code: 'PARA500', name: 'Paracetamol 500mg', ven: 'E', unit: 'tablet', pack_size: 10, cold_chain: false, controlled: false, min_residual_days: 30 },
  { code: 'AMOX500', name: 'Amoxicillin 500mg', ven: 'E', unit: 'capsule', pack_size: 10, cold_chain: false, controlled: false, min_residual_days: 30 },
  { code: 'INSUL', name: 'Insulin Human 40IU/ml', ven: 'V', unit: 'vial', pack_size: 1, cold_chain: true, controlled: false, min_residual_days: 60 },
  { code: 'ORS', name: 'ORS Sachet', ven: 'E', unit: 'sachet', pack_size: 25, cold_chain: false, controlled: false, min_residual_days: 30 },
  { code: 'METF500', name: 'Metformin 500mg', ven: 'N', unit: 'tablet', pack_size: 10, cold_chain: false, controlled: false, min_residual_days: 30 },
];

export const lots: Lot[] = [
  { facility_id: 'W0', drug_code: 'PARA500', batch_no: 'B-PA-2026-001', expiry: '2026-12-15', qty: 2000 },
  { facility_id: 'W0', drug_code: 'AMOX500', batch_no: 'B-AX-2026-001', expiry: '2026-12-31', qty: 800 },
  { facility_id: 'W0', drug_code: 'INSUL', batch_no: 'B-IN-2026-001', expiry: '2027-01-31', qty: 50 },
  { facility_id: 'W0', drug_code: 'ORS', batch_no: 'B-OR-2026-001', expiry: '2027-03-01', qty: 1500 },
  { facility_id: 'H1', drug_code: 'PARA500', batch_no: 'B-PA-2026-002', expiry: '2026-11-20', qty: 150 },
  { facility_id: 'H1', drug_code: 'AMOX500', batch_no: 'B-AX-2026-002', expiry: '2027-02-28', qty: 200 },
  { facility_id: 'H1', drug_code: 'INSUL', batch_no: 'B-IN-2026-002', expiry: '2026-11-30', qty: 15 },
  { facility_id: 'H2', drug_code: 'PARA500', batch_no: 'B-PA-2026-003', expiry: '2027-06-30', qty: 50 },
  { facility_id: 'H2', drug_code: 'METF500', batch_no: 'B-MF-2026-001', expiry: '2027-04-15', qty: 300 },
  { facility_id: 'H3', drug_code: 'PARA500', batch_no: 'B-PA-2026-004', expiry: '2027-05-01', qty: 400 },
  { facility_id: 'H3', drug_code: 'ORS', batch_no: 'B-OR-2026-002', expiry: '2026-11-25', qty: 30 },
  { facility_id: 'H4', drug_code: 'PARA500', batch_no: 'B-PA-2026-005', expiry: '2027-03-15', qty: 80 },
];

export const positions: Position[] = [
  { facility_id: 'W0', drug_code: 'PARA500', effective_stock: 2000, at_risk: 0, reserve: 200, shortage: 0, consumption_rate: 0.0, target_days: 0 },
  { facility_id: 'W0', drug_code: 'INSUL', effective_stock: 50, at_risk: 0, reserve: 5, shortage: 0, consumption_rate: 0.0, target_days: 0 },
  { facility_id: 'H1', drug_code: 'PARA500', effective_stock: 100, at_risk: 50, reserve: 60, shortage: 80, consumption_rate: 8.0, target_days: 30 },
  { facility_id: 'H1', drug_code: 'INSUL', effective_stock: 10, at_risk: 5, reserve: 6, shortage: 8, consumption_rate: 0.5, target_days: 30 },
  { facility_id: 'H2', drug_code: 'PARA500', effective_stock: 50, at_risk: 0, reserve: 60, shortage: 130, consumption_rate: 6.0, target_days: 30 },
  { facility_id: 'H2', drug_code: 'INSUL', effective_stock: 0, at_risk: 0, reserve: 0, shortage: 15, consumption_rate: 0.5, target_days: 30 },
  { facility_id: 'H3', drug_code: 'AMOX500', effective_stock: 0, at_risk: 0, reserve: 0, shortage: 120, consumption_rate: 4.0, target_days: 30 },
  { facility_id: 'H3', drug_code: 'ORS', effective_stock: 20, at_risk: 10, reserve: 50, shortage: 100, consumption_rate: 5.0, target_days: 30 },
  { facility_id: 'H4', drug_code: 'PARA500', effective_stock: 80, at_risk: 0, reserve: 30, shortage: 40, consumption_rate: 4.0, target_days: 30 },
];

export const routes: Route[] = [
  { src_facility_id: 'W0', dst_facility_id: 'H1', distance_km: 8.5, transit_hours: 0.5, cold_chain: true },
  { src_facility_id: 'H1', dst_facility_id: 'W0', distance_km: 8.5, transit_hours: 0.5, cold_chain: true },
  { src_facility_id: 'W0', dst_facility_id: 'H2', distance_km: 6.2, transit_hours: 0.4, cold_chain: true },
  { src_facility_id: 'H2', dst_facility_id: 'W0', distance_km: 6.2, transit_hours: 0.4, cold_chain: true },
  { src_facility_id: 'W0', dst_facility_id: 'H3', distance_km: 12.1, transit_hours: 0.8, cold_chain: false },
  { src_facility_id: 'H3', dst_facility_id: 'W0', distance_km: 12.1, transit_hours: 0.8, cold_chain: false },
  { src_facility_id: 'W0', dst_facility_id: 'H4', distance_km: 10.3, transit_hours: 0.7, cold_chain: false },
  { src_facility_id: 'H4', dst_facility_id: 'W0', distance_km: 10.3, transit_hours: 0.7, cold_chain: false },
  { src_facility_id: 'H1', dst_facility_id: 'H2', distance_km: 7.0, transit_hours: 0.5, cold_chain: false },
  { src_facility_id: 'H2', dst_facility_id: 'H1', distance_km: 7.0, transit_hours: 0.5, cold_chain: false },
  { src_facility_id: 'H1', dst_facility_id: 'H3', distance_km: 14.2, transit_hours: 1.0, cold_chain: false },
  { src_facility_id: 'H3', dst_facility_id: 'H1', distance_km: 14.2, transit_hours: 1.0, cold_chain: false },
  { src_facility_id: 'H2', dst_facility_id: 'H3', distance_km: 9.8, transit_hours: 0.7, cold_chain: false },
  { src_facility_id: 'H3', dst_facility_id: 'H2', distance_km: 9.8, transit_hours: 0.7, cold_chain: false },
];

export const vehicles: Vehicle[] = [
  { id: 'V1', name: 'Cold Van Alpha', cold_chain: true, capacity_units: 5000 },
  { id: 'V2', name: 'Utility Van Beta', cold_chain: false, capacity_units: 10000 },
];

export const orders: TransferOrder[] = [
  { id: 'ORD-001', dta_number: 'DTA/BLR-U/2026/000001', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H2', drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', batch_no: 'B-PA-2026-001', qty: 180, usable: 180, score: 0.92, status: 'proposed', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30' },
  { id: 'ORD-002', dta_number: 'DTA/BLR-U/2026/000002', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H4', drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', batch_no: 'B-PA-2026-001', qty: 120, usable: 120, score: 0.85, status: 'proposed', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30' },
  { id: 'ORD-003', dta_number: 'DTA/BLR-U/2026/000003', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H3', drug_code: 'AMOX500', drug_name: 'Amoxicillin 500mg', batch_no: 'B-AX-2026-001', qty: 120, usable: 120, score: 0.88, status: 'proposed', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30' },
  { id: 'ORD-004', dta_number: 'DTA/BLR-U/2026/000004', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H3', drug_code: 'ORS', drug_name: 'ORS Sachet', batch_no: 'B-OR-2026-001', qty: 125, usable: 125, score: 0.80, status: 'approved', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30' },
  { id: 'ORD-005', dta_number: 'DTA/BLR-U/2026/000005', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H2', drug_code: 'INSUL', drug_name: 'Insulin Human 40IU/ml', batch_no: 'B-IN-2026-001', qty: 28, usable: 28, score: 0.95, status: 'proposed', temperature_req: 'cold_chain', created_at: '2026-11-01T10:30:00+05:30' },
  { id: 'ORD-006', dta_number: 'DTA/BLR-U/2026/000006', plan_id: 'plan-demo-001', src_facility_id: 'H1', dst_facility_id: 'H2', drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', batch_no: 'B-PA-2026-002', qty: 50, usable: 45, score: 0.70, status: 'proposed', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30' },
];

export const planDemo: PlanDemo = {
  plan: {
    id: 'plan-demo-001',
    created_at: '2026-11-01T10:30:00+05:30',
    mode: 'live',
    solver_tier: 'qpiai-opt-local',
    energy: -4.82,
    gap_to_milp: 0.03,
    variables: 42,
    constraints: 18,
    transfers: 6,
    shortage_reduction: 0.72,
    expiry_avoided: 215,
    cost_inr: 1250.00,
  },
  orders,
  candidates: [],
  regret: [
    { order_id: 'ORD-005', alternative: 'Send insulin to H1 instead of H2', reason: 'H2 has higher unmet shortage.', delta_score: -0.40 },
    { order_id: 'ORD-001', alternative: 'Send PARA500 from W0 to H3 instead of H2', reason: 'H3 has no shortage. H2 scored higher.', delta_score: -0.32 },
  ],
};

export const clock: SimClock = {
  sim_date: '2026-11-01',
  sim_time: '2026-11-01T10:30:00+05:30',
  speed: 1.0,
  running: true,
  day_index: 0,
};

export const scenarios: Scenario[] = [
  { name: 'baseline', description: 'Normal consumption patterns across all facilities', active: true, params: {} },
  { name: 'outbreak-h3', description: 'ORS demand spike at H3 due to gastroenteritis outbreak', active: false, params: { facility_id: 'H3', drug_code: 'ORS', demand_multiplier: 3.0, duration_days: 14 } },
];

export const coldchain: ColdchainStatus[] = [
  { device_id: 'sensor-01', vehicle_id: 'V1', temperature_c: 4.2, battery_pct: 87, last_seen: '2026-11-01T10:28:00+05:30', alert: false },
  { device_id: 'sensor-02', vehicle_id: 'V1', temperature_c: 5.1, battery_pct: 92, last_seen: '2026-11-01T10:28:00+05:30', alert: false },
];

export const benchmark: Benchmark = {
  solver_tier: 'qpiai-opt-local',
  energy: -4.82,
  milp_energy: -4.97,
  gap: 0.03,
  solve_time_ms: 340,
};
