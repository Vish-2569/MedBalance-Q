import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Cpu, Package, TrendingDown, Timer, ShieldCheck, AlertTriangle,
  ChevronDown, ChevronUp, Snowflake, Truck, Loader2, ExternalLink,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatINR, formatPct } from '@/lib/utils';
import type { PlanDemo, TransferOrder, Facility } from '@/types/domain';

const STAGE_LABELS = ['Snapshot', 'Feasibility', 'Zoning', 'QUBO Build', 'Solve', 'Validate', 'Persist'];

function solverBadge(tier: string) {
  if (tier.includes('platform')) return { label: 'QpiAI Platform', bg: 'bg-purple-100 text-purple-700' };
  if (tier.includes('local') || tier.includes('qsv')) return { label: 'QpiAI Local', bg: 'bg-blue-100 text-blue-700' };
  if (tier.includes('neal') || tier.includes('sa')) return { label: 'SA (neal)', bg: 'bg-amber-100 text-amber-700' };
  if (tier.includes('greedy')) return { label: 'Greedy Descent', bg: 'bg-slate-100 text-slate-700' };
  return { label: tier, bg: 'bg-slate-100 text-slate-600' };
}

const ZONE_COLORS = ['#3b82f6', '#f59e0b', '#8b5cf6'];

export default function PlanPage() {
  const queryClient = useQueryClient();
  const { data: demo, isLoading } = useQuery<PlanDemo>({ queryKey: ['planDemo'], queryFn: api.getPlanDemo });
  const { data: facilities = [] } = useQuery({ queryKey: ['facilities'], queryFn: api.getFacilities });
  const { data: benchmark } = useQuery({ queryKey: ['benchmark'], queryFn: api.getBenchmark });
  const [expandedDst, setExpandedDst] = useState<string | null>(null);

  const runMut = useMutation({
    mutationFn: () => api.runPlan('live'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['planDemo'] }),
  });
  const runOptimizerButton = (
    <button onClick={() => runMut.mutate()} disabled={runMut.isPending}
      className="flex items-center gap-2 px-4 py-2 text-sm bg-teal-600 text-white rounded-lg hover:bg-teal-700">
      {runMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Cpu className="w-4 h-4" />}
      Run Optimizer
    </button>
  );

  if (isLoading) return <div className="flex-1 flex items-center justify-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin" /></div>;
  if (!demo?.plan) {
    return (
      <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-800">Redistribution Plan</h1>
          {runOptimizerButton}
        </div>
        <div role="status" className="flex-1 flex items-center justify-center text-slate-500 p-8">
          No saved plan data. Run the optimizer to generate a redistribution plan.
        </div>
      </div>
    );
  }

  const { plan, orders } = demo;
  const sb = solverBadge(plan.solver_tier);

  const grouped = orders.reduce<Record<string, TransferOrder[]>>((acc, o) => {
    (acc[o.dst_facility_id] ??= []).push(o);
    return acc;
  }, {});

  const attempts = (plan.solver_meta as any)?.attempts as { tier: string; error?: string; time_ms?: number; energy?: number }[] | undefined;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Redistribution Plan</h1>
        {runOptimizerButton}
      </div>

      {/* Solver tier + violations */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className={cn('text-xs px-3 py-1 rounded-full font-medium', sb.bg)}>{sb.label}</span>
        {plan.gap_to_milp != null && (
          <span className="text-xs px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 font-medium">
            Gap to MILP: {formatPct(plan.gap_to_milp)}
          </span>
        )}
        <span className={cn(
          'text-xs px-3 py-1 rounded-full font-medium flex items-center gap-1',
          (plan.violations ?? 0) === 0 ? 'bg-teal-50 text-teal-700' : 'bg-red-100 text-red-700',
        )}>
          <ShieldCheck className="w-3 h-3" />
          Violations: {plan.violations ?? 0}
        </span>
      </div>

      {/* Solver attempts */}
      {attempts && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">Solver Attempts</h3>
          <div className="flex gap-2 flex-wrap">
            {attempts.map((a, i) => (
              <div key={i} className={cn(
                'text-xs px-3 py-1.5 rounded-lg border',
                a.error ? 'bg-slate-50 border-slate-200 text-slate-500' : 'bg-teal-50 border-teal-200 text-teal-700',
              )}>
                <span className="font-medium">{a.tier}</span>
                {a.error && <span className="ml-1 text-slate-400">- skipped</span>}
                {a.time_ms != null && <span className="ml-1">({a.time_ms.toFixed(0)}ms)</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard icon={Package} label="Transfers" value={String(plan.transfers)} />
        <KpiCard icon={TrendingDown} label="Shortage Reduction" value={formatPct(plan.shortage_reduction)} color="text-teal-600" />
        <KpiCard icon={AlertTriangle} label="Expiry Avoided" value={`${plan.expiry_avoided} units`} color="text-amber-600" />
        <KpiCard icon={Timer} label="Cost" value={formatINR(plan.cost_inr)} />
      </div>

      {/* Stage pipeline */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">Pipeline Stages</h3>
        <div className="flex items-center gap-1">
          {STAGE_LABELS.map((s, i) => (
            <div key={s} className="flex items-center gap-1">
              <div className="text-xs px-3 py-1.5 rounded bg-teal-100 text-teal-700 font-medium">{s}</div>
              {i < STAGE_LABELS.length - 1 && <div className="w-4 h-0.5 bg-teal-300" />}
            </div>
          ))}
        </div>
      </div>

      {/* Zone mini-map */}
      {benchmark?.zoning?.maxcut && facilities.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">Zone Partition (Max-Cut)</h3>
          <div className="flex items-center gap-6">
            <ZoneMiniMap facilities={facilities} partition={benchmark.zoning.maxcut.partition} orders={orders} />
            <div className="flex flex-col gap-2">
              {Object.entries(
                Object.entries(benchmark.zoning.maxcut.partition).reduce<Record<number, string[]>>((acc, [f, z]) => {
                  (acc[z] ??= []).push(f); return acc;
                }, {})
              ).map(([z, facs]) => (
                <div key={z} className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ background: ZONE_COLORS[Number(z)] }} />
                  <span className="text-xs font-medium text-slate-600">Zone {z}:</span>
                  <span className="text-xs text-slate-500">{(facs as string[]).join(', ')}</span>
                </div>
              ))}
              <span className="text-xs text-slate-400 mt-1">
                Tier: {benchmark.zoning.maxcut.tier} | Cut: {benchmark.zoning.maxcut.cut_value.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Orders grouped by destination */}
      <h2 className="text-lg font-semibold text-slate-700 mt-2">Transfer Orders by Destination</h2>
      <div className="space-y-2">
        {Object.entries(grouped).map(([dst, dstOrders]) => {
          const expanded = expandedDst === dst;
          const hasCold = dstOrders.some(o => o.temperature_req === 'cold_chain');
          return (
            <div key={dst} className="bg-white rounded-lg border border-slate-200 shadow-sm">
              <button onClick={() => setExpandedDst(expanded ? null : dst)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-3">
                  <Truck className="w-4 h-4 text-slate-400" />
                  <span className="font-semibold text-slate-800">{dst}</span>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                    {dstOrders.length} order{dstOrders.length > 1 ? 's' : ''}
                  </span>
                  {hasCold && <Snowflake className="w-3.5 h-3.5 text-blue-500" />}
                </div>
                {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {expanded && (
                <div className="border-t border-slate-100 overflow-x-auto">
                  <table className="w-full text-sm min-w-[640px]">
                    <thead>
                      <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                        <th className="text-left px-4 py-2 font-medium">DTA</th>
                        <th className="text-left px-4 py-2 font-medium">Drug</th>
                        <th className="text-left px-4 py-2 font-medium">Source</th>
                        <th className="text-right px-4 py-2 font-medium">Qty</th>
                        <th className="text-right px-4 py-2 font-medium">Score</th>
                        <th className="text-center px-4 py-2 font-medium">Status</th>
                        <th className="text-center px-4 py-2 font-medium"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {dstOrders.map(o => (
                        <tr key={o.id} className="border-t border-slate-50 hover:bg-slate-50">
                          <td className="px-4 py-2 text-xs font-mono text-slate-600">{o.dta_number}</td>
                          <td className="px-4 py-2">
                            <span className="font-medium">{o.drug_name}</span>
                            {o.temperature_req === 'cold_chain' && <Snowflake className="w-3 h-3 text-blue-500 inline ml-1" />}
                          </td>
                          <td className="px-4 py-2 text-slate-600">{o.src_facility_id}</td>
                          <td className="px-4 py-2 text-right font-mono">{o.qty}</td>
                          <td className="px-4 py-2 text-right font-mono">{o.score.toFixed(2)}</td>
                          <td className="px-4 py-2 text-center">
                            <span className={cn(
                              'text-xs px-2 py-0.5 rounded-full font-medium',
                              o.status === 'approved' ? 'bg-teal-100 text-teal-700' :
                              o.status === 'proposed' ? 'bg-amber-100 text-amber-700' :
                              'bg-slate-100 text-slate-600',
                            )}>{o.status}</span>
                          </td>
                          <td className="px-4 py-2 text-center">
                            <Link to={`/orders/${o.id}`} className="inline-flex items-center gap-1 text-xs text-teal-600 hover:text-teal-800 font-medium">
                              View <ExternalLink className="w-3 h-3" />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Regret analysis */}
      {demo.regret.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-slate-700 mt-2">Regret Analysis</h2>
          <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
            {demo.regret.map((r, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                <div>
                  <span className="font-medium text-slate-700">{r.order_id}</span>
                  <span className="text-slate-500 mx-2">|</span>
                  <span className="text-slate-600">{r.alternative}</span>
                  <span className="text-xs text-slate-400 ml-2">({r.reason}, delta {r.delta_score.toFixed(2)})</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ZoneMiniMap({ facilities, partition, orders }: {
  facilities: Facility[]; partition: Record<string, number>; orders: TransferOrder[];
}) {
  const lats = facilities.map(f => f.lat);
  const lons = facilities.map(f => f.lon);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const pad = 0.02;
  const w = 200, h = 160;

  function project(lat: number, lon: number): [number, number] {
    const x = ((lon - minLon + pad) / (maxLon - minLon + 2 * pad)) * w;
    const y = h - ((lat - minLat + pad) / (maxLat - minLat + 2 * pad)) * h;
    return [x, y];
  }

  const facMap = new Map(facilities.map(f => [f.id, f]));

  return (
    <svg width={w} height={h} className="rounded border border-slate-200 bg-slate-50">
      {orders.map((o, i) => {
        const src = facMap.get(o.src_facility_id);
        const dst = facMap.get(o.dst_facility_id);
        if (!src || !dst) return null;
        const [x1, y1] = project(src.lat, src.lon);
        const [x2, y2] = project(dst.lat, dst.lon);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={o.temperature_req === 'cold_chain' ? '#3b82f6' : '#94a3b8'} strokeWidth={1}
          strokeDasharray={o.temperature_req === 'cold_chain' ? '4 2' : undefined} opacity={0.4} />;
      })}
      {facilities.map(f => {
        const [x, y] = project(f.lat, f.lon);
        const zone = partition[f.id] ?? 0;
        return (
          <g key={f.id}>
            <circle cx={x} cy={y} r={f.type === 'warehouse' ? 10 : 7}
              fill={ZONE_COLORS[zone]} opacity={0.8} stroke="white" strokeWidth={1.5} />
            <text x={x} y={y + 16} textAnchor="middle" fontSize={8} fill="#475569" fontWeight={500}>
              {f.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function KpiCard({ icon: Icon, label, value, color }: {
  icon: React.ComponentType<{ className?: string }>; label: string; value: string; color?: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-slate-400" />
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <p className={cn('text-2xl font-bold', color ?? 'text-slate-800')}>{value}</p>
    </div>
  );
}
