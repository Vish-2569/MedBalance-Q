import type {
  Facility, Drug, Lot, Position, Route, Vehicle,
  TransferOrder, PlanDemo, SimClock, Scenario,
  ColdchainStatus, Benchmark, StockReport, ReviewItem,
  CustodyEvent, AuditVerify, AIHealthData, OrderDetail,
  Provenance, RegretEntry, PlanRunResponse,
} from '@/types/domain';

import * as fixtures from '@/fixtures';

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1';
const PLAN_CACHE_KEY = 'medbalance.latestPlan.v1';

interface RawReportItem {
  drug_code?: string | null;
  drug_name?: string;
  drug_name_raw?: string;
  qty?: number | null;
  unit?: string | null;
  batch_no: string | null;
  expiry: string | null;
  confidence?: number;
  flags?: string[];
}

interface RawReport {
  id: string;
  facility_code: string;
  reported_at: string;
  format: string;
  raw_text?: string | null;
  items: RawReportItem[];
  gate?: { flagged?: number };
}

interface RawReview {
  id: string;
  report_id: string;
  facility_code: string;
  item_index: number;
  status: string;
  extraction: {
    drug_code?: string | null;
    drug_name_raw?: string;
    qty?: number | null;
    expiry?: string | null;
    confidence?: number;
  };
  anomaly_rules: string[];
  explanation: string;
  corrected_values?: {
    drug_code?: string;
    qty?: number;
    expiry?: string;
  } | null;
  resolved_at?: string | null;
}

interface RawColdchainStatus {
  device_id: string;
  vehicle_id?: string | null;
  facility_id?: string | null;
  temperature_c: number | null;
  battery_pct?: number | null;
  last_seen: string;
  alert: boolean;
  temperature_history?: number[];
  state: string;
}

interface RawProvenanceBundle {
  order: TransferOrder;
  custody: CustodyEvent[];
  audit: {
    seq: number;
    actor: string;
    action: string;
    entity: string;
    entity_id: string;
    payload: Record<string, unknown>;
    hash: string;
    created_at: string;
  }[];
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(await responseError('GET', path, res));
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await responseError('POST', path, res));
  return res.json() as Promise<T>;
}

async function responseError(method: string, path: string, res: Response): Promise<string> {
  const detail = await res.text();
  return `${method} ${path}: ${res.status}${detail ? ` - ${detail}` : ''}`;
}

function mapReport(raw: RawReport): StockReport {
  return {
    id: raw.id,
    facility_code: raw.facility_code,
    received_at: raw.reported_at,
    format: raw.format,
    channel: raw.format,
    status: raw.gate ? (raw.gate.flagged ? 'flagged' : 'processed') : 'received',
    items: raw.items.map(item => ({
      ...item,
      drug_name: item.drug_name ?? item.drug_name_raw,
      unit: item.unit ?? undefined,
    })),
    anomalies: raw.items.flatMap(item => item.flags ?? []),
    raw_text: raw.raw_text ?? undefined,
  };
}

function mapReview(raw: RawReview): ReviewItem {
  const corrected = raw.corrected_values ?? {};
  const statuses: Record<string, ReviewItem['status']> = {
    needs_review: 'pending',
    pending: 'pending',
    accepted: 'accepted',
    corrected: 'corrected',
    rejected: 'rejected',
    auto_approved: 'auto_approved',
  };
  const status = statuses[raw.status];
  if (!status) {
    throw new Error(`Unknown review status: ${raw.status}`);
  }
  return {
    id: raw.id,
    report_id: raw.report_id,
    facility_code: raw.facility_code,
    item_index: raw.item_index,
    anomaly_type: raw.anomaly_rules.join(', '),
    anomaly_explanation: raw.explanation,
    status,
    drug_code: corrected.drug_code ?? raw.extraction.drug_code ?? undefined,
    drug_name: raw.extraction.drug_name_raw ?? undefined,
    extracted_qty: raw.extraction.qty ?? null,
    extracted_expiry: raw.extraction.expiry ?? null,
    confidence: raw.extraction.confidence,
    candidates: [],
    resolved_qty: corrected.qty,
    resolved_expiry: corrected.expiry ?? raw.extraction.expiry ?? undefined,
    resolved_drug_code: corrected.drug_code,
    resolved_at: raw.resolved_at ?? undefined,
  };
}

async function loadPlanDemo(): Promise<PlanDemo> {
  if (USE_FIXTURES) return fixtures.planDemo;

  const cached = localStorage.getItem(PLAN_CACHE_KEY);
  if (cached) {
    const planDemo = JSON.parse(cached) as PlanDemo;
    if (!planDemo.plan?.id || !Array.isArray(planDemo.orders)) {
      throw new Error('Saved optimizer plan cache is invalid; clear this site’s local storage and run the optimizer again.');
    }
    let savedOrders: TransferOrder[];
    try {
      savedOrders = await get<TransferOrder[]>(
        `/core/orders?plan_id=${encodeURIComponent(planDemo.plan.id)}`,
      );
    } catch (error) {
      return {
        ...planDemo,
        persisted: false,
        persistence_error: error instanceof Error ? error.message : String(error),
      };
    }
    const savedIds = new Set(savedOrders.map(order => order.id));
    const persisted = savedOrders.length === planDemo.orders.length
      && planDemo.orders.every(order => savedIds.has(order.id));
    return {
      ...planDemo,
      orders: persisted ? savedOrders : planDemo.orders,
      persisted,
    };
  }

  const orders = await get<TransferOrder[]>('/core/orders');
  const latest = [...orders].sort((a, b) =>
    Date.parse(b.created_at ?? '') - Date.parse(a.created_at ?? ''),
  )[0];
  const planId = latest?.plan_id;
  return {
    plan_id: planId,
    orders: planId ? orders.filter(order => order.plan_id === planId) : orders,
    candidates: [],
    regret: [],
    persisted: true,
  };
}

function mapColdchainStatus(raw: RawColdchainStatus): ColdchainStatus {
  const normalizedState = raw.state.toLowerCase();
  const state: ColdchainStatus['state'] =
    normalizedState === 'ok' || normalizedState === 'warning' || normalizedState === 'excursion'
      ? normalizedState
      : 'unknown';
  return {
    device_id: raw.device_id,
    vehicle_id: raw.vehicle_id ?? null,
    facility_id: raw.facility_id ?? null,
    temperature_c: raw.temperature_c,
    battery_pct: raw.battery_pct ?? null,
    last_seen: raw.last_seen,
    alert: raw.alert,
    temperature_history: raw.temperature_history ?? [],
    state,
  };
}

function mapProvenance(raw: RawProvenanceBundle): Provenance {
  const orderNodeId = `order:${raw.order.id}`;
  const nodes: Provenance['nodes'] = [{
    id: orderNodeId,
    type: 'order',
    label: raw.order.dta_number ?? raw.order.id,
    meta: { status: raw.order.status, qty: raw.order.qty, drug_code: raw.order.drug_code },
  }];
  const edges: Provenance['edges'] = [];

  for (const event of raw.custody) {
    const id = `custody:${event.id}`;
    nodes.push({
      id,
      type: 'custody',
      label: event.event_type,
      meta: { actor: event.actor, qty: event.qty, location: event.location },
    });
    edges.push({ source: orderNodeId, target: id });
  }

  for (const entry of raw.audit) {
    const id = `audit:${entry.seq}`;
    nodes.push({
      id,
      type: 'audit',
      label: entry.action,
      meta: { actor: entry.actor, hash: entry.hash },
    });
    edges.push({ source: orderNodeId, target: id });
  }

  return { nodes, edges };
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
      : get(`/core/orders/${encodeURIComponent(id)}`),

  getProvenance: (orderId: string): Promise<Provenance> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.provenance)
      : get<RawProvenanceBundle>(`/core/provenance/${encodeURIComponent(orderId)}`).then(mapProvenance),

  getCustody: (orderId: string): Promise<CustodyEvent[]> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.custodyEvents[orderId] ?? [])
      : get(`/core/custody/${encodeURIComponent(orderId)}`),

  getRegret: (orderId: string): Promise<RegretEntry[]> =>
    USE_FIXTURES
      ? Promise.resolve((fixtures.planDemo.regret ?? []).filter(r => r.order_id === orderId))
      : get<OrderDetail>(`/core/orders/${encodeURIComponent(orderId)}`)
        .then(order => order.plan_id
          ? get(`/optimizer/plan/${encodeURIComponent(order.plan_id)}/regret?order_id=${encodeURIComponent(orderId)}`)
          : []),

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
      : post(`/core/orders/${encodeURIComponent(id)}/approve`),

  rejectOrder: (id: string, reason: string): Promise<TransferOrder> =>
    USE_FIXTURES
      ? Promise.resolve({ ...fixtures.orders.find(o => o.id === id)!, status: 'rejected' as const })
      : post(`/core/orders/${encodeURIComponent(id)}/reject`, { reason }),

  custodyScan: (payload: { token: string; event: string; qty?: number; actor: string }): Promise<{ order_id: string; event: string; status: string; qty: number }> =>
    USE_FIXTURES
      ? Promise.resolve({ order_id: 'ORD-004', event: payload.event, status: payload.event === 'dispatch' ? 'dispatched' : payload.event === 'receive' ? 'received' : 'consumed', qty: payload.qty ?? 125 })
      : post('/core/custody/scan', payload),

  getPlanDemo: loadPlanDemo,

  runPlan: async (mode = 'live'): Promise<PlanDemo> => {
    if (USE_FIXTURES) return fixtures.planDemo;
    const result = await post<PlanRunResponse>('/optimizer/plan/run', { mode });
    let savedOrders: TransferOrder[] = [];
    let persistenceError: string | undefined;
    try {
      savedOrders = await get<TransferOrder[]>(
        `/core/orders?plan_id=${encodeURIComponent(result.plan.id)}`,
      );
    } catch (error) {
      persistenceError = error instanceof Error ? error.message : String(error);
    }
    const savedIds = new Set(savedOrders.map(order => order.id));
    const persisted = result.orders.length === 0
      || (savedOrders.length === result.orders.length && result.orders.every(order => savedIds.has(order.id)));
    const planDemo: PlanDemo = {
      plan: result.plan,
      plan_id: result.plan.id,
      orders: persisted ? savedOrders : result.orders,
      candidates: [],
      regret: [],
      persisted,
      persistence_error: persistenceError,
    };
    localStorage.setItem(PLAN_CACHE_KEY, JSON.stringify(planDemo));
    return planDemo;
  },

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
    USE_FIXTURES ? Promise.resolve({ activated: name }) : post(`/sim/scenario/${encodeURIComponent(name)}`),

  getColdchain: async (): Promise<ColdchainStatus[]> =>
    USE_FIXTURES
      ? fixtures.coldchain
      : (await get<RawColdchainStatus[]>('/coldchain/status')).map(mapColdchainStatus),

  getBenchmark: (planId?: string): Promise<Benchmark | null> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.benchmark)
      : planId ? get(`/optimizer/plan/${encodeURIComponent(planId)}/benchmark`) : Promise.resolve(null),

  getReports: (facility?: string): Promise<StockReport[]> =>
    USE_FIXTURES
      ? Promise.resolve(facility ? fixtures.reports.filter(r => r.facility_code === facility) : fixtures.reports)
      : get<RawReport[]>(`/ingest/reports${facility ? `?facility=${encodeURIComponent(facility)}` : ''}`)
        .then(reports => reports.map(mapReport)),

  getReviews: (): Promise<ReviewItem[]> =>
    USE_FIXTURES
      ? Promise.resolve(fixtures.reviews)
      : get<RawReview[]>('/ingest/reviews').then(reviews => reviews.map(mapReview)),

  resolveReview: (id: string, action: 'accept' | 'reject' | 'correct', correction?: { drug_code?: string; qty?: number; expiry?: string }): Promise<ReviewItem> =>
    USE_FIXTURES
      ? Promise.resolve({ ...fixtures.reviews.find(r => r.id === id)!, status: action === 'accept' ? 'accepted' as const : action === 'reject' ? 'rejected' as const : 'corrected' as const, resolved_by: 'pharmacist', resolved_at: new Date().toISOString(), ...(correction ?? {}) })
      : post<RawReview>(`/ingest/reviews/${encodeURIComponent(id)}/resolve`, {
        action,
        corrected_values: correction,
      }).then(mapReview),

  getSignals: (): Promise<import('@/types/domain').Signal[]> =>
    USE_FIXTURES ? Promise.resolve(fixtures.signals) : get('/sim/signals'),

  resetSim: async (seed?: number): Promise<{ seed: number; sim_date: string }> => {
    if (USE_FIXTURES) return { seed: seed ?? 42, sim_date: fixtures.clock.sim_date };
    const result = await post<{ seed: number; sim_date: string }>(
      `/sim/reset${seed != null ? `?seed=${encodeURIComponent(seed)}` : ''}`,
    );
    localStorage.removeItem(PLAN_CACHE_KEY);
    return result;
  },

  getAuditVerify: (): Promise<AuditVerify> =>
    USE_FIXTURES ? Promise.resolve(fixtures.auditVerify) : get('/core/audit/verify'),

  tamperDemo: (): Promise<{ tampered: boolean }> =>
    USE_FIXTURES ? Promise.resolve({ tampered: true }) : post('/core/admin/tamper-demo'),

  restoreDemo: (): Promise<{ restored: boolean }> =>
    USE_FIXTURES ? Promise.resolve({ restored: true }) : post('/core/admin/restore-demo'),

  getAIHealth: async (): Promise<AIHealthData> => {
    if (USE_FIXTURES) return fixtures.aiHealth;
    const raw = await get<{
      status: string;
      provider: string;
      models?: { fast?: string; smart?: string };
      prompts_loaded?: number;
      stats?: {
        calls_24h?: number;
        cache_hit_rate?: number;
        p95_ms?: number;
        fallbacks?: number;
        schema_failures?: number;
        firewall_blocks?: number;
      };
    }>('/genai/ai/health');
    const stats = raw.stats ?? {};
    return {
      status: raw.status === 'ok' ? 'healthy' : raw.status,
      provider: raw.provider,
      model_fast: raw.models?.fast ?? 'Not configured',
      model_smart: raw.models?.smart ?? 'Not configured',
      total_calls: stats.calls_24h,
      cache_hit_rate: stats.cache_hit_rate,
      p95_latency_ms: stats.p95_ms,
      schema_failures: stats.schema_failures,
      fallbacks: stats.fallbacks,
      firewall_blocks: stats.firewall_blocks,
      prompts: [],
      prompts_loaded: raw.prompts_loaded,
    };
  },
};
