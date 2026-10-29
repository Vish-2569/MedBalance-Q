import type {
  Facility, Drug, Lot, Position, Route, Vehicle,
  TransferOrder, PlanRun, PlanDemo, SimClock, Scenario,
  ColdchainStatus, Benchmark, StockReport, ReviewItem,
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
    USE_FIXTURES ? Promise.resolve([]) : get(`/ingest/reports${facility ? `?facility=${facility}` : ''}`),

  getReviews: (): Promise<ReviewItem[]> =>
    USE_FIXTURES ? Promise.resolve([]) : get('/ingest/reviews'),
};
