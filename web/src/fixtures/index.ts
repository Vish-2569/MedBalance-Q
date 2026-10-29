import type {
  Facility, Drug, Lot, Position, Route, Vehicle,
  TransferOrder, PlanDemo, SimClock, Scenario, Signal,
  ColdchainStatus, Benchmark, StockReport, ReviewItem,
  CustodyEvent, AuditVerify, AIHealthData, OrderDetail,
  Provenance, ResultMetrics,
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
    violations: 0,
    solver_meta: {
      solver_tier: 'greedy-descent',
      energy: -4.82,
      n_vars: 19,
      time_ms: 135.86,
      violations: 0,
      trimmed: 0,
      dropped: 0,
      attempts: [
        { tier: 'qpiai-platform', error: 'QPIAI_OPT_URL or QPIAI_OPT_TOKEN not set' },
        { tier: 'qpiai-local', error: 'QPIAI_OPT_TOKEN not set' },
        { tier: 'neal-sa', error: "No module named 'neal'" },
        { tier: 'greedy-descent', time_ms: 135.86, samples_returned: 5, energy: -4.82 },
      ],
    },
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
  { id: 'baseline', name: 'baseline', description: 'Normal consumption patterns across all facilities', active: true, params: {} },
  { id: 'dengue_outbreak', name: 'dengue_outbreak', description: 'ORS and PCM demand spike at H3 due to dengue outbreak (3x multiplier, 14 days)', active: false, params: { facility_id: 'H3', drug_code: 'ORS', demand_multiplier: 3.0, duration_days: 14 } },
  { id: 'fridge_failure', name: 'fridge_failure', description: 'ILR failure at H1 — cold chain broken, insulin at risk', active: false, params: { facility_id: 'H1', device: 'ILR-H1' } },
  { id: 'bad_data', name: 'bad_data', description: 'H4 sends corrupt report with qty=10000 and expiry=1999', active: false, params: { facility_id: 'H4' } },
  { id: 'ilr_repaired', name: 'ilr_repaired', description: 'ILR at H1 repaired — cold chain restored', active: false, params: { facility_id: 'H1', device: 'ILR-H1' } },
  { id: 'road_closure', name: 'road_closure', description: 'Road between H2 and H3 closed — route unavailable for 7 days', active: false, params: { src: 'H2', dst: 'H3', duration_days: 7 } },
  { id: 'td_campaign', name: 'td_campaign', description: 'Tetanus-diphtheria vaccination campaign at H3 — extra vaccine demand', active: false, params: { facility_id: 'H3', drug_code: 'TD', demand_multiplier: 5.0, duration_days: 7 } },
];

export const signals: Signal[] = [
  { id: 'sig_dengue_001', type: 'outbreak', params: { facility_id: 'H3', drug_code: 'ORS', demand_multiplier: 3.0, duration_days: 14 }, fired_at: '2026-11-01T08:00:00+05:30' },
  { id: 'season_dengue', type: 'dengue_season', params: { affects: ['ORS', 'PCM', 'PARA500'], factor: 1.2 }, fired_at: 'seasonal' },
];

export const coldchain: ColdchainStatus[] = [
  {
    device_id: 'sensor-01', vehicle_id: 'V1', temperature_c: 4.2, battery_pct: 87,
    last_seen: '2026-11-01T10:28:00+05:30', alert: false,
    temperature_history: [4.0, 4.1, 4.3, 4.2, 4.4, 4.1, 4.0, 3.9, 4.2, 4.3, 4.1, 4.0, 4.2, 4.3, 4.1, 4.0, 4.2, 4.1, 4.3, 4.2],
    state: 'ok',
  },
  {
    device_id: 'sensor-02', vehicle_id: 'V1', temperature_c: 5.1, battery_pct: 92,
    last_seen: '2026-11-01T10:28:00+05:30', alert: false,
    temperature_history: [5.0, 5.2, 5.1, 4.9, 5.0, 5.3, 5.1, 5.0, 4.8, 5.1, 5.2, 5.0, 4.9, 5.1, 5.3, 5.0, 5.1, 5.2, 5.0, 5.1],
    state: 'ok',
  },
  {
    device_id: 'sensor-03', vehicle_id: 'V2', temperature_c: 9.8, battery_pct: 45,
    last_seen: '2026-11-01T10:25:00+05:30', alert: true,
    temperature_history: [4.5, 4.8, 5.2, 5.5, 6.0, 6.4, 6.9, 7.2, 7.5, 7.8, 8.1, 8.4, 8.7, 9.0, 9.2, 9.4, 9.5, 9.6, 9.7, 9.8],
    state: 'excursion',
  },
];

export const benchmark: Benchmark = {
  plan_id: 'plan-demo-001',
  benchmark: [
    { solver: 'no-transfer', objective: 0, shortage_reduction: 0, expiry_avoided_inr: 0, waste_moved: 0, trips: 0, time_ms: 0 },
    { solver: 'greedy-phone-call', objective: 2.15, shortage_reduction: 0.45, expiry_avoided_inr: 850, waste_moved: 320, trips: 4, time_ms: 12 },
    { solver: 'greedy-f4', objective: 3.68, shortage_reduction: 0.62, expiry_avoided_inr: 1420, waste_moved: 498, trips: 5, time_ms: 28 },
    { solver: 'qubo (greedy-descent)', objective: 4.82, shortage_reduction: 0.72, expiry_avoided_inr: 1890, waste_moved: 618, trips: 6, time_ms: 340 },
    { solver: 'milp (OPTIMAL)', objective: 4.97, shortage_reduction: 0.74, expiry_avoided_inr: 1950, waste_moved: 625, trips: 6, time_ms: 1250 },
  ],
  gap_qubo_to_milp_pct: 3.02,
  zoning: {
    maxcut: {
      partition: { W0: 0, H1: 0, H2: 0, H3: 1, H4: 1 },
      cut_value: 2.85,
      intra_zone_cost: 1240,
      tier: 'qsv-local',
      approx_ratio: 0.95,
    },
    kmeans: {
      partition: { W0: 0, H1: 0, H2: 0, H3: 1, H4: 0 },
      cut_value: 1.92,
      intra_zone_cost: 1580,
    },
    exact: {
      partition: { W0: 0, H1: 0, H2: 0, H3: 1, H4: 1 },
      cut_value: 3.00,
      intra_zone_cost: 1200,
    },
  },
};

export const reports: StockReport[] = [
  {
    id: 'rpt-001', facility_code: 'H1', received_at: '2026-11-01T09:00:00+05:30',
    format: 'fhir', channel: 'fhir', language: 'en', status: 'processed',
    items: [
      { drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', qty: 150, unit: 'tablet', batch_no: 'B-PA-2026-002', expiry: '2026-11-20', confidence: 0.98 },
      { drug_code: 'AMOX500', drug_name: 'Amoxicillin 500mg', qty: 200, unit: 'capsule', batch_no: 'B-AX-2026-002', expiry: '2027-02-28', confidence: 0.97 },
      { drug_code: 'INSUL', drug_name: 'Insulin Human 40IU/ml', qty: 15, unit: 'vial', batch_no: 'B-IN-2026-002', expiry: '2026-11-30', confidence: 0.95 },
    ],
    anomalies: [], model: 'deterministic', prompt_id: 'fhir_adapter',
  },
  {
    id: 'rpt-002', facility_code: 'H2', received_at: '2026-11-01T09:15:00+05:30',
    format: 'csv', channel: 'csv', language: 'en', status: 'processed',
    items: [
      { drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', qty: 50, unit: 'tablet', batch_no: 'B-PA-2026-003', expiry: '2027-06-30', confidence: 0.90 },
      { drug_code: 'METF500', drug_name: 'Metformin 500mg', qty: 300, unit: 'tablet', batch_no: 'B-MF-2026-001', expiry: '2027-04-15', confidence: 0.90 },
    ],
    anomalies: [], model: 'deterministic', prompt_id: 'csv_adapter',
  },
  {
    id: 'rpt-003', facility_code: 'H3', received_at: '2026-11-01T09:30:00+05:30',
    format: 'chat', channel: 'chat', language: 'kn', status: 'processed',
    raw_text: 'ನಮಸ್ಕಾರ! ಇಂದಿನ ಸ್ಟಾಕ್ ರಿಪೋರ್ಟ್:\nಇನ್ಸುಲಿನ್ 40IU - 20 vials, batch INS-001, exp 2027-03-15\nಪ್ಯಾರಸಿಟಮಾಲ್ 500 - 100 tabs\nORS ಪೌಡರ್ - 30 sachets, batch ORS-042, exp 2026-11-25',
    items: [
      { drug_code: 'INSUL', drug_name: 'Insulin Human 40IU/ml', qty: 20, unit: 'vial', batch_no: 'INS-001', expiry: '2027-03-15', confidence: 0.82 },
      { drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', qty: 100, unit: 'tablet', batch_no: null, expiry: null, confidence: 0.78 },
      { drug_code: 'ORS', drug_name: 'ORS Sachet', qty: 30, unit: 'sachet', batch_no: 'ORS-042', expiry: '2026-11-25', confidence: 0.85 },
    ],
    anomalies: [], model: 'gemini-2.0-flash', prompt_id: 'extract_stock@v1',
  },
  {
    id: 'rpt-004', facility_code: 'H4', received_at: '2026-11-01T09:45:00+05:30',
    format: 'text', channel: 'text', language: 'en', status: 'flagged',
    raw_text: 'Stock register for today:\ninzulin 40IU - 10000 vials (batch B-IN-H4-999, exp 1999)\nparacetmol 500 - 80 tabs\namoxy 500 - some left, maybe 40 caps',
    items: [
      { drug_code: 'INSUL', drug_name: 'Insulin Human 40IU/ml', qty: 10000, unit: 'vial', batch_no: 'B-IN-H4-999', expiry: '1999-12-31', confidence: 0.72 },
      { drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', qty: 80, unit: 'tablet', batch_no: null, expiry: null, confidence: 0.75 },
      { drug_code: 'AMOX500', drug_name: 'Amoxicillin 500mg', qty: 40, unit: 'capsule', batch_no: null, expiry: null, confidence: 0.70 },
    ],
    anomalies: ['qty_spike', 'past_expiry'], model: 'gemini-2.0-flash', prompt_id: 'extract_stock@v1',
  },
];

export const custodyEvents: Record<string, CustodyEvent[]> = {
  'ORD-004': [
    { id: 1, order_id: 'ORD-004', event_type: 'dispatch', actor: 'warehouse-pharmacist', qty: 125, timestamp: '2026-11-01T11:00:00+05:30', location: 'W0', temperature_c: null, deviation: null, notes: null },
    { id: 2, order_id: 'ORD-004', event_type: 'receive', actor: 'h3-pharmacist', qty: 125, timestamp: '2026-11-01T12:15:00+05:30', location: 'H3', temperature_c: null, deviation: null, notes: null },
  ],
};

export const orderDetails: Record<string, OrderDetail> = {
  'ORD-001': {
    id: 'ORD-001', dta_number: 'DTA/BLR-U/2026/000001', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H2',
    drug_code: 'PARA500', drug_name: 'Paracetamol 500mg', batch_no: 'B-PA-2026-001', qty: 180, usable: 180, score: 0.92,
    status: 'proposed', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30',
    narration: 'Transfer 180 tablets of Paracetamol 500mg from SIM-District Warehouse to SIM-General Hospital. This addresses 69% of H2\'s current shortage of 130 units at a cost of ₹100. The lot B-PA-2026-001 expires 2026-12-15 and has 45 days residual shelf life at destination.',
    narration_grounded: true,
    qubo_terms: { shortage_reward: 0.85, trip_cost: -0.08, overfill_penalty: 0.0, batch_bonus: 0.15, total: 0.92 },
  },
  'ORD-004': {
    id: 'ORD-004', dta_number: 'DTA/BLR-U/2026/000004', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H3',
    drug_code: 'ORS', drug_name: 'ORS Sachet', batch_no: 'B-OR-2026-001', qty: 125, usable: 125, score: 0.80,
    status: 'approved', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30',
    dispatched_at: '2026-11-01T11:00:00+05:30', received_at: '2026-11-01T12:15:00+05:30',
    narration: 'Transfer 125 sachets of ORS from SIM-District Warehouse to SIM-Community Health Centre to cover 100% of the dengue-driven ORS shortage at H3.',
    narration_grounded: true,
    custody_events: [
      { id: 1, order_id: 'ORD-004', event_type: 'dispatch', actor: 'warehouse-pharmacist', qty: 125, timestamp: '2026-11-01T11:00:00+05:30', location: 'W0', temperature_c: null, deviation: null, notes: null },
      { id: 2, order_id: 'ORD-004', event_type: 'receive', actor: 'h3-pharmacist', qty: 125, timestamp: '2026-11-01T12:15:00+05:30', location: 'H3', temperature_c: null, deviation: null, notes: null },
    ],
    qubo_terms: { shortage_reward: 0.72, trip_cost: -0.10, overfill_penalty: 0.0, batch_bonus: 0.18, total: 0.80 },
  },
  'ORD-005': {
    id: 'ORD-005', dta_number: 'DTA/BLR-U/2026/000005', plan_id: 'plan-demo-001', src_facility_id: 'W0', dst_facility_id: 'H2',
    drug_code: 'INSUL', drug_name: 'Insulin Human 40IU/ml', batch_no: 'B-IN-2026-001', qty: 28, usable: 28, score: 0.95,
    status: 'proposed', temperature_req: 'cold_chain', created_at: '2026-11-01T10:30:00+05:30', vehicle_id: 'V1',
    narration: 'Transfer 28 vials of Insulin Human 40IU/ml via cold chain from SIM-District Warehouse to SIM-General Hospital. The destination has zero insulin stock and 15 units of unmet shortage.',
    narration_grounded: true,
    qubo_terms: { shortage_reward: 0.93, trip_cost: -0.12, overfill_penalty: 0.0, batch_bonus: 0.14, total: 0.95 },
  },
};

export const provenance: Provenance = {
  nodes: [
    { id: 'rpt-001', type: 'report', label: 'H1 FHIR Report', meta: { format: 'fhir', facility: 'H1' } },
    { id: 'rpt-002', type: 'report', label: 'H2 CSV Report', meta: { format: 'csv', facility: 'H2' } },
    { id: 'ext-001', type: 'extraction', label: 'Extract PARA500 × 150', meta: { confidence: 0.98 } },
    { id: 'ext-002', type: 'extraction', label: 'Extract PARA500 × 50', meta: { confidence: 0.90 } },
    { id: 'lot-001', type: 'lot', label: 'B-PA-2026-001 @ W0', meta: { qty: 2000, expiry: '2026-12-15' } },
    { id: 'cand-001', type: 'candidate', label: 'W0→H2 PARA500 180u', meta: { score: 0.92 } },
    { id: 'ORD-001', type: 'order', label: 'DTA/BLR-U/2026/000001', meta: { status: 'proposed' } },
  ],
  edges: [
    { source: 'rpt-001', target: 'ext-001' },
    { source: 'rpt-002', target: 'ext-002' },
    { source: 'ext-001', target: 'lot-001' },
    { source: 'ext-002', target: 'lot-001' },
    { source: 'lot-001', target: 'cand-001' },
    { source: 'cand-001', target: 'ORD-001' },
  ],
};

export const auditVerify: AuditVerify = { ok: true, entries: 47 };

export const aiHealth: AIHealthData = {
  status: 'healthy',
  provider: 'Gemini',
  model_fast: 'gemini-2.0-flash',
  model_smart: 'gemini-2.0-pro',
  total_calls: 156,
  cache_hit_rate: 0.72,
  p95_latency_ms: 1240,
  schema_failures: 3,
  fallbacks: 2,
  firewall_blocks: 1,
  prompts: [
    { id: 'extract_stock', version: 1, calls: 48 },
    { id: 'anomaly_explain', version: 1, calls: 32 },
    { id: 'narrate_order', version: 1, calls: 24 },
    { id: 'deviation_summary', version: 1, calls: 8 },
    { id: 'copilot_qa', version: 1, calls: 44 },
  ],
  eval_scores: { extract_stock: 0.91, anomaly_explain: 0.87, narrate_order: 0.94 },
};

export const resultMetrics: ResultMetrics = {
  stockout_days_before: 42,
  stockout_days_after: 12,
  expired_value_inr: 18500,
  expired_value_avoided_inr: 14200,
  waste_moved_units: 618,
  waste_moved_pct: 0.82,
  shortage_reduction: 0.72,
  ci_lower: 0.65,
  ci_upper: 0.79,
  ablation: [
    { variant: 'Full QUBO + Zoning', shortage_reduction: 0.72, expiry_avoided: 215, cost_inr: 1250, note: 'Production config' },
    { variant: 'QUBO no zoning', shortage_reduction: 0.68, expiry_avoided: 198, cost_inr: 1480, note: 'Without Max-Cut zone partition' },
    { variant: 'Greedy F4', shortage_reduction: 0.62, expiry_avoided: 142, cost_inr: 980, note: 'Simple feasibility-ranked greedy' },
    { variant: 'Phone-call baseline', shortage_reduction: 0.45, expiry_avoided: 85, cost_inr: 750, note: 'Manual redistribution estimate' },
    { variant: 'No transfer', shortage_reduction: 0.0, expiry_avoided: 0, cost_inr: 0, note: 'Status quo — all waste expires' },
  ],
};

export const reviews: ReviewItem[] = [
  {
    id: 'rev-001', report_id: 'rpt-004', facility_code: 'H4', item_index: 0,
    anomaly_type: 'qty_spike', anomaly_explanation: 'Reported quantity 10,000 vials is 200x the typical stock level of ~50 vials for Insulin at H4. This is likely a data entry error in the handwritten register.',
    status: 'pending', drug_code: 'INSUL', drug_name: 'Insulin Human 40IU/ml',
    extracted_qty: 10000, confidence: 0.72,
    candidates: ['INSUL', 'OXYTOCIN'],
  },
  {
    id: 'rev-002', report_id: 'rpt-004', facility_code: 'H4', item_index: 2,
    anomaly_type: 'low_confidence', anomaly_explanation: 'The text "amoxy 500 - some left, maybe 40 caps" is vague. Quantity is approximate and may not reflect actual stock.',
    status: 'accepted', drug_code: 'AMOX500', drug_name: 'Amoxicillin 500mg',
    extracted_qty: 40, confidence: 0.70,
    candidates: ['AMOX500', 'AMOX250'],
    resolved_qty: 40, resolved_drug_code: 'AMOX500', resolved_by: 'pharmacist', resolved_at: '2026-11-01T10:05:00+05:30',
  },
  {
    id: 'rev-003', report_id: 'rpt-003', facility_code: 'H3', item_index: 1,
    anomaly_type: 'unknown_drug', anomaly_explanation: 'Drug mention "ಪ್ಯಾರಸಿಟಮಾಲ್ 500" was matched to Paracetamol 500mg via Kannada alias with fuzzy score 78. No batch or expiry was provided.',
    status: 'pending', drug_code: 'PARA500', drug_name: 'Paracetamol 500mg',
    extracted_qty: 100, confidence: 0.78,
    candidates: ['PARA500', 'PARA650'],
  },
];
