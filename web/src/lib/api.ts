import type {
  Facility, Drug, Lot, Position, Route, Vehicle,
  TransferOrder, PlanRun, PlanDemo, SimClock, Scenario,
  ColdchainStatus, Benchmark, StockReport, ReviewItem,
  CustodyEvent, AuditVerify, AIHealthData, OrderDetail,
  Provenance, ResultMetrics, RegretEntry,
} from '@/types/domain';

import * as fixtures from '@/fixtures';

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  getFacilities: (): Promise<Facility[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.facilities) : get('/core/facilities'),

  getDrugs: (): Promise<Drug[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.drugs) : get('/core/drugs'),

  getLots: (facility?: string): Promise<Lot[]> =>
    USE_FIXTURES
      ? Promise.resolve(facility ? fixtures.lots.filter(l => l.facility_id === facility) : fixtures.lots)
      : get(`/core/lots${facility ? `?facility=${facility}` : ''}`),

  getPositions: (facility?: string): Promise<Position[]> =>
    USE_FIXTURES
      ? Promise.resolve(facility ? fixtures.positions.filter(p => p.facility_id === facility) : fixtures.positions)
      : get(`/core/positions${facility ? `?facility=${facility}` : ''}`),

  getRoutes: (): Promise<Route[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.routes) : get('/core/routes'),

  getVehicles: (): Promise<Vehicle[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.vehicles) : get('/core/vehicles'),

  getOrders: (planId?: string): Promise<TransferOrder[]> =>
    USE_FIXTURES
      ? Promise.resolve(planId ? fixtures.orders.filter(o => o.plan_id === planId) : fixtures.orders)
      : get(`/core/orders${planId ? `?plan_id=${planId}` : ''}`),

  getOrder: (id: string): Promise<OrderDetail> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.orderDetails[id] ?? { ...fixtures.orders.find(o => o.id === id)! })
      : get(`/core/orders/${id}`),

  getProvenance: (orderId: string): Promise<Provenance> =>
    USE_FIXTURES ? Promise.resolve(fixtures.provenance) : get(`/core/orders/${orderId}/provenance`),

  getCustody: (orderId: string): Promise<CustodyEvent[]> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.custodyEvents[orderId] ?? [])
      : get(`/core/custody/${orderId}`),

  getRegret: (orderId: string): Promise<RegretEntry[]> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.planDemo.regret.filter(r => r.order_id === orderId))
      : get(`/optimizer/plan/plan-demo-001/regret?order_id=${orderId}`),

  downloadVoucher: async (orderId: string): Promise<void> => {
    if (USE_FIXTURES) {
      alert('Voucher download not available in fixture mode.');
      return;
    }
    const res = await fetch(`/api/genai/dta/${orderId}/pdf`);
    if (!res.ok) throw new Error(`Voucher download failed: ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `DTA_${orderId}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },

  approveOrder: (id: string): Promise<TransferOrder> =>
    USE_FIXTURES
      ? Promise.resolve({ ...fixtures.orders.find(o => o.id === id)!, status: 'approved' as const })
      : post(`/core/orders/${id}/approve`),

  rejectOrder: (id: string): Promise<TransferOrder> =>
    USE_FIXTURES
      ? Promise.resolve({ ...fixtures.orders.find(o => o.id === id)!, status: 'rejected' as const })
      : post(`/core/orders/${id}/reject`),

  custodyScan: (payload: { token: string; event: string; qty?: number; actor: string }): Promise<{ order_id: string; event: string; status: string; qty: number }> =>
    USE_FIXTURES
      ? Promise.resolve({ order_id: 'ORD-004', event: payload.event, status: payload.event === 'dispatch' ? 'dispatched' : payload.event === 'receive' ? 'received' : 'consumed', qty: payload.qty ?? 125 })
      : post('/core/custody/scan', payload),

  getPlanDemo: (): Promise<PlanDemo> =>
    USE_FIXTURES ? Promise.resolve(fixtures.planDemo) : get('/optimizer/plan/plan-demo-001'),

  runPlan: (mode = 'live'): Promise<PlanRun> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.planDemo.plan)
      : post('/optimizer/plan/run', { mode }),

  getClock: (): Promise<SimClock> =>
    USE_FIXTURES ? Promise.resolve(fixtures.clock) : get('/sim/clock'),

  startClock: (): Promise<SimClock> =>
    USE_FIXTURES ? Promise.resolve({ ...fixtures.clock, running: true }) : post('/sim/clock/start'),

  pauseClock: (): Promise<SimClock> =>
    USE_FIXTURES ? Promise.resolve({ ...fixtures.clock, running: false }) : post('/sim/clock/pause'),

  setSpeed: (speed: number): Promise<SimClock> =>
    USE_FIXTURES ? Promise.resolve({ ...fixtures.clock, speed }) : post('/sim/clock/speed', { speed }),

  getScenarios: (): Promise<Scenario[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.scenarios) : get('/sim/scenarios'),

  activateScenario: (name: string): Promise<{ activated: string }> =>
    USE_FIXTURES ? Promise.resolve({ activated: name }) : post(`/sim/scenario/${name}`),

  getColdchain: (): Promise<ColdchainStatus[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.coldchain) : get('/coldchain/status'),

  getBenchmark: (): Promise<Benchmark> =>
    USE_FIXTURES ? Promise.resolve(fixtures.benchmark) : get('/optimizer/plan/plan-demo-001/benchmark'),

  getReports: (facility?: string): Promise<StockReport[]> =>
    USE_FIXTURES
      ? Promise.resolve(facility ? fixtures.reports.filter(r => r.facility_code === facility) : fixtures.reports)
      : get(`/ingest/reports${facility ? `?facility=${facility}` : ''}`),

  getReviews: (): Promise<ReviewItem[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.reviews) : get('/ingest/reviews'),

  resolveReview: (id: string, action: 'accept' | 'reject' | 'correct', correction?: { drug_code?: string; qty?: number; expiry?: string }): Promise<ReviewItem> =>
    USE_FIXTURES
      ? Promise.resolve({ ...fixtures.reviews.find(r => r.id === id)!, status: action === 'accept' ? 'accepted' as const : action === 'reject' ? 'rejected' as const : 'corrected' as const, resolved_by: 'pharmacist', resolved_at: new Date().toISOString(), ...(correction ?? {}) })
      : post(`/ingest/reviews/${id}/${action}`, correction),

  getSignals: (): Promise<import('@/types/domain').Signal[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.signals) : get('/sim/signals'),

  resetSim: (seed?: number): Promise<{ ok: boolean }> =>
    USE_FIXTURES ? Promise.resolve({ ok: true }) : post('/sim/reset', seed != null ? { seed } : undefined),

  getAuditVerify: (): Promise<AuditVerify> =>
    USE_FIXTURES ? Promise.resolve(fixtures.auditVerify) : get('/core/audit/verify'),

  tamperDemo: (): Promise<{ tampered: boolean }> =>
    USE_FIXTURES ? Promise.resolve({ tampered: true }) : post('/core/admin/tamper-demo'),

  restoreDemo: (): Promise<{ restored: boolean }> =>
    USE_FIXTURES ? Promise.resolve({ restored: true }) : post('/core/admin/restore-demo'),

  getAIHealth: (): Promise<AIHealthData> =>
    USE_FIXTURES ? Promise.resolve(fixtures.aiHealth) : get('/genai/health'),

  getResultMetrics: (): Promise<ResultMetrics> =>
    USE_FIXTURES ? Promise.resolve(fixtures.resultMetrics) : get('/optimizer/results'),
};
