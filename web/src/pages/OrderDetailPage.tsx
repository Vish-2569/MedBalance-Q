import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, ArrowRight, CheckCircle, XCircle, Snowflake, FileText,
  Package, MapPin, User, Download, Loader2, AlertTriangle, Truck,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, statusColor, shortDate } from '@/lib/utils';
import type { OrderDetail, CustodyEvent, ProvenanceNode, Facility, RegretEntry } from '@/types/domain';

const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  report:     { bg: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  extraction: { bg: '#dcfce7', border: '#22c55e', text: '#166534' },
  lot:        { bg: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  candidate:  { bg: '#dcfce7', border: '#22c55e', text: '#166534' },
  order:      { bg: '#fef3c7', border: '#f59e0b', text: '#854d0e' },
  custody:    { bg: '#fef3c7', border: '#f59e0b', text: '#854d0e' },
  audit:      { bg: '#f1f5f9', border: '#64748b', text: '#334155' },
};

const QUBO_COLORS: Record<string, string> = {
  shortage_reward: '#14b8a6',
  trip_cost: '#ef4444',
  overfill_penalty: '#f59e0b',
  batch_bonus: '#3b82f6',
};

const QUBO_LABELS: Record<string, string> = {
  shortage_reward: 'Shortage Reward',
  trip_cost: 'Trip Cost',
  overfill_penalty: 'Overfill Penalty',
  batch_bonus: 'Batch Bonus',
};

const STATUS_ORDER = ['proposed', 'approved', 'dispatched', 'in_transit', 'received', 'consumed', 'delivered'];

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: order, isLoading, error } = useQuery({
    queryKey: ['order', id],
    queryFn: () => api.getOrder(id!),
    enabled: !!id,
  });

  const { data: provenance, isLoading: provLoading, error: provError } = useQuery({
    queryKey: ['provenance', id],
    queryFn: () => api.getProvenance(id!),
    enabled: !!id,
  });

  const { data: custody = [], isLoading: custodyLoading, error: custodyError } = useQuery({
    queryKey: ['custody', id],
    queryFn: () => api.getCustody(id!),
    enabled: !!id,
  });

  const { data: regret = [], isLoading: regretLoading } = useQuery<RegretEntry[]>({
    queryKey: ['regret', id],
    queryFn: () => api.getRegret(id!),
    enabled: !!id,
  });

  const { data: facilities = [] } = useQuery<Facility[]>({
    queryKey: ['facilities'],
    queryFn: api.getFacilities,
  });

  const approveMut = useMutation({
    mutationFn: () => api.approveOrder(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['order', id] });
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
      void queryClient.invalidateQueries({ queryKey: ['planDemo'] });
    },
  });

  const rejectMut = useMutation({
    mutationFn: (reason: string) => api.rejectOrder(id!, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['order', id] });
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
      void queryClient.invalidateQueries({ queryKey: ['planDemo'] });
    },
  });

  const rejectOrder = () => {
    const reason = window.prompt('Enter a reason for rejecting this transfer order:');
    if (reason?.trim()) rejectMut.mutate(reason.trim());
  };

  const allCustody = order?.custody_events ?? custody;

  const facName = (fid: string) => {
    const f = facilities.find(x => x.id === fid);
    return f ? f.name.replace('SIM-', '') : fid;
  };

  const isApprovedOrBeyond = order
    ? STATUS_ORDER.indexOf(order.status) >= STATUS_ORDER.indexOf('approved')
    : false;

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading order...
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-3">
        <AlertTriangle className="w-8 h-8" />
        <p>Failed to load order {id}.</p>
        <Link to="/plan" className="text-teal-600 hover:underline text-sm">Back to Plan</Link>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      {/* Back link */}
      <Link to="/plan" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-teal-600 w-fit">
        <ArrowLeft className="w-4 h-4" /> Back to Plan
      </Link>

      {/* Header */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        {(approveMut.error || rejectMut.error) && (
          <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {(approveMut.error ?? rejectMut.error)?.message}
          </div>
        )}
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-xl font-bold text-slate-800 font-mono">{order.dta_number}</h1>
              <span className={cn('px-2.5 py-1 rounded-full text-xs font-semibold', statusColor(order.status))}>
                {order.status.toUpperCase()}
              </span>
              {order.temperature_req === 'cold_chain' && (
                <span className="flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200">
                  <Snowflake className="w-3 h-3" /> Cold Chain
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <span className="font-medium">{facName(order.src_facility_id)}</span>
              <ArrowRight className="w-4 h-4 text-slate-400" />
              <span className="font-medium">{facName(order.dst_facility_id)}</span>
            </div>
          </div>
          <div className="text-right text-sm text-slate-500">
            <p className="font-medium text-slate-700">{order.drug_name}</p>
            <p>{order.qty} units &middot; Batch {order.batch_no}</p>
            <p className="text-xs mt-1">Created {shortDate(order.created_at ?? '')}</p>
            <p className="text-xs text-slate-400">Score: {order.score.toFixed(2)}</p>
          </div>
        </div>

        {order.status === 'proposed' && (
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => approveMut.mutate()}
              disabled={approveMut.isPending}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50"
            >
              <CheckCircle className="w-4 h-4" />
              {approveMut.isPending ? 'Approving...' : 'Approve'}
            </button>
            <button
              onClick={rejectOrder}
              disabled={rejectMut.isPending}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-red-50 text-red-700 border border-red-200 rounded-lg text-sm font-medium hover:bg-red-100 disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              {rejectMut.isPending ? 'Rejecting...' : 'Reject'}
            </button>
          </div>
        )}
      </div>

      {/* Narration */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="w-4 h-4 text-teal-600" />
          <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">AI Narration</h3>
          {order.narration_grounded != null && (
            <span className={cn(
              'text-xs px-2 py-0.5 rounded-full font-medium',
              order.narration_grounded
                ? 'bg-teal-50 text-teal-700 border border-teal-200'
                : 'bg-amber-50 text-amber-700 border border-amber-200',
            )}>
              {order.narration_grounded ? 'grounded ✓' : 'template'}
            </span>
          )}
        </div>
        {order.narration ? (
          <p className="text-sm text-slate-600 leading-relaxed">{order.narration}</p>
        ) : (
          <p className="text-sm text-slate-400 italic">No narration available.</p>
        )}
      </div>

      {/* QUBO Term Breakdown */}
      {order.qubo_terms && (
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">QUBO Term Breakdown</h3>
          <QuboBar terms={order.qubo_terms} />
        </div>
      )}

      {/* Regret Alternatives Table */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">Regret Alternatives</h3>
        {regretLoading ? (
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading...
          </div>
        ) : regret.length === 0 ? (
          <p className="text-sm text-slate-400 italic">No alternatives evaluated.</p>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[500px]">
            <thead>
              <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                <th className="text-left px-3 py-2 font-medium">Alternative Facility</th>
                <th className="text-right px-3 py-2 font-medium">Regret Score</th>
                <th className="text-left px-3 py-2 font-medium">Reason Skipped</th>
              </tr>
            </thead>
            <tbody>
              {regret.map((r, i) => (
                <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2.5 text-slate-700">{r.alternative}</td>
                  <td className="px-3 py-2.5 text-right">
                    <span className={cn(
                      'font-mono text-xs px-2 py-0.5 rounded',
                      r.delta_score < 0 ? 'bg-red-50 text-red-600' : 'bg-teal-50 text-teal-600',
                    )}>
                      {r.delta_score > 0 ? '+' : ''}{r.delta_score.toFixed(2)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-slate-500">{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* Voucher Download */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">DTA Voucher</h3>
            <p className="text-xs text-slate-400 mt-1">
              {isApprovedOrBeyond
                ? 'Download the Drug Transfer Advice voucher as PDF.'
                : 'Voucher available after approval.'}
            </p>
          </div>
          <button
            disabled={!isApprovedOrBeyond}
            onClick={() => api.downloadVoucher(id!)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium',
              isApprovedOrBeyond
                ? 'bg-teal-600 text-white hover:bg-teal-700'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed',
            )}
          >
            <Download className="w-4 h-4" />
            Download DTA Voucher
          </button>
        </div>
      </div>

      {/* Custody Timeline */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-4">
          <Truck className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Custody Timeline</h3>
        </div>
        {custodyLoading ? (
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading...
          </div>
        ) : custodyError ? (
          <p role="alert" className="text-sm text-red-600">
            Could not load custody events: {custodyError.message}
          </p>
        ) : allCustody.length > 0 ? (
          <CustodyTimeline events={allCustody} />
        ) : (
          <p className="text-sm text-slate-400 italic">No custody events recorded yet.</p>
        )}
      </div>

      {/* Provenance Graph */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-4">
          <Package className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Provenance Graph</h3>
        </div>
        {provLoading ? (
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading...
          </div>
        ) : provError ? (
          <p role="alert" className="text-sm text-red-600">
            Could not load provenance: {provError.message}
          </p>
        ) : provenance && provenance.nodes.length > 0 ? (
          <ProvenanceSVG nodes={provenance.nodes} edges={provenance.edges} />
        ) : (
          <p className="text-sm text-slate-400 italic">No provenance data available.</p>
        )}
      </div>
    </div>
  );
}

/* -- Custody Timeline --------------------------------------------------- */

function CustodyTimeline({ events }: { events: CustodyEvent[] }) {
  return (
    <div className="relative pl-6">
      <div className="absolute left-2.5 top-1 bottom-1 w-0.5 bg-slate-200" />
      {events.map((evt, i) => {
        const deviationData = typeof evt.deviation === 'string' && evt.deviation
          ? (() => { try { return JSON.parse(evt.deviation); } catch { return evt.deviation; } })()
          : evt.deviation;
        const deviations = Array.isArray(deviationData) ? deviationData : deviationData ? [deviationData] : [];
        return (
          <div key={evt.id ?? i} className="relative mb-4 last:mb-0">
            <div className={cn(
              'absolute -left-3.5 top-1 w-3 h-3 rounded-full border-2',
              evt.event_type === 'dispatch' ? 'bg-blue-500 border-blue-300' :
              evt.event_type === 'receive' ? 'bg-teal-500 border-teal-300' :
              'bg-green-500 border-green-300',
            )} />
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="flex items-center gap-2 text-sm">
                <span className={cn(
                  'px-2 py-0.5 rounded text-xs font-semibold uppercase',
                  evt.event_type === 'dispatch' ? 'bg-blue-100 text-blue-700' :
                  evt.event_type === 'receive' ? 'bg-teal-100 text-teal-700' :
                  'bg-green-100 text-green-700',
                )}>
                  {evt.event_type}
                </span>
                <span className="text-slate-400 text-xs">
                  {new Date(evt.timestamp).toLocaleString('en-IN')}
                </span>
                {deviations.length > 0 && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
                    Deviation
                  </span>
                )}
              </div>
              <div className="mt-1.5 flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                <span className="flex items-center gap-1"><User className="w-3 h-3" />{evt.actor}</span>
                <span className="flex items-center gap-1"><Package className="w-3 h-3" />{evt.qty} units</span>
                <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{evt.location}</span>
                {evt.temperature_c != null && <span>{evt.temperature_c}&deg;C</span>}
              </div>
              {deviations.length > 0 && (
                <div className="mt-2 flex gap-1.5 flex-wrap">
                  {deviations.map((d: { type?: string } | string, j: number) => (
                    <span key={j} className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200">
                      {typeof d === 'string' ? d : (d.type ?? 'deviation').replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
              {evt.notes && <p className="text-xs text-slate-500 mt-1.5 italic">{evt.notes}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* -- Provenance SVG (left-to-right flow) -------------------------------- */

function ProvenanceSVG({ nodes, edges }: { nodes: ProvenanceNode[]; edges: { source: string; target: string }[] }) {
  const typeOrder: ProvenanceNode['type'][] = ['report', 'extraction', 'lot', 'candidate', 'order', 'audit', 'custody'];
  const grouped = new Map<string, ProvenanceNode[]>();
  for (const n of nodes) {
    const list = grouped.get(n.type) ?? [];
    list.push(n);
    grouped.set(n.type, list);
  }

  const cols = typeOrder.filter(t => grouped.has(t));
  const nodeW = 140, nodeH = 46, gapX = 36, gapY = 16, padX = 16, padY = 16;

  const maxPerCol = Math.max(1, ...cols.map(t => (grouped.get(t) ?? []).length));
  const svgW = cols.length * (nodeW + gapX) - gapX + padX * 2;
  const svgH = maxPerCol * (nodeH + gapY) - gapY + padY * 2;

  const nodePos = new Map<string, { x: number; y: number }>();
  cols.forEach((t, ci) => {
    const items = grouped.get(t)!;
    const totalH = items.length * (nodeH + gapY) - gapY;
    const startY = (svgH - totalH) / 2;
    items.forEach((n, ni) => {
      nodePos.set(n.id, {
        x: padX + ci * (nodeW + gapX),
        y: startY + ni * (nodeH + gapY),
      });
    });
  });

  const metaLine = (n: ProvenanceNode): string => {
    if (!n.meta) return '';
    if (n.type === 'extraction' && n.meta.confidence != null)
      return `conf ${((n.meta.confidence as number) * 100).toFixed(0)}%`;
    if (n.type === 'candidate' && n.meta.score != null)
      return `score ${(n.meta.score as number).toFixed(2)}`;
    if (n.type === 'lot' && n.meta.qty != null)
      return `qty ${n.meta.qty}`;
    if (n.type === 'order' && n.meta.status)
      return String(n.meta.status);
    if (n.type === 'audit' && n.meta.actor)
      return String(n.meta.actor);
    if (n.type === 'custody' && n.meta.qty != null)
      return `qty ${n.meta.qty}`;
    if (n.type === 'report' && n.meta.format)
      return String(n.meta.format).toUpperCase();
    return '';
  };

  return (
    <div className="overflow-x-auto">
      <svg width={svgW} height={svgH} className="block">
        <defs>
          <marker id="prov-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6" fill="#94a3b8" />
          </marker>
        </defs>

        {edges.map((e, i) => {
          const from = nodePos.get(e.source);
          const to = nodePos.get(e.target);
          if (!from || !to) return null;
          return (
            <line
              key={i}
              x1={from.x + nodeW} y1={from.y + nodeH / 2}
              x2={to.x} y2={to.y + nodeH / 2}
              stroke="#cbd5e1" strokeWidth={1.5}
              markerEnd="url(#prov-arrow)"
            />
          );
        })}

        {nodes.map(n => {
          const pos = nodePos.get(n.id);
          if (!pos) return null;
          const colors = NODE_COLORS[n.type] ?? NODE_COLORS.order;
          const meta = metaLine(n);
          return (
            <g key={n.id}>
              <rect
                x={pos.x} y={pos.y}
                width={nodeW} height={nodeH}
                rx={8} ry={8}
                fill={colors.bg} stroke={colors.border} strokeWidth={1.5}
              />
              <text
                x={pos.x + nodeW / 2} y={pos.y + (meta ? 18 : 26)}
                textAnchor="middle" fontSize={10} fontWeight={600} fill={colors.text}
              >
                {n.label.length > 20 ? n.label.slice(0, 18) + '…' : n.label}
              </text>
              {meta && (
                <text
                  x={pos.x + nodeW / 2} y={pos.y + 34}
                  textAnchor="middle" fontSize={9} fill="#64748b"
                >
                  {meta}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* -- QUBO Breakdown Bar ------------------------------------------------- */

function QuboBar({ terms }: { terms: NonNullable<OrderDetail['qubo_terms']> }) {
  const entries = [
    { key: 'shortage_reward', value: terms.shortage_reward },
    { key: 'batch_bonus', value: terms.batch_bonus },
    { key: 'trip_cost', value: Math.abs(terms.trip_cost) },
    { key: 'overfill_penalty', value: Math.abs(terms.overfill_penalty) },
  ].filter(e => e.value > 0);

  const sum = entries.reduce((s, e) => s + e.value, 0);

  return (
    <div>
      <div className="flex h-8 rounded-lg overflow-hidden">
        {entries.map(e => {
          const pct = sum > 0 ? (e.value / sum) * 100 : 0;
          return (
            <div
              key={e.key}
              style={{ width: `${pct}%`, backgroundColor: QUBO_COLORS[e.key] }}
              className="flex items-center justify-center text-white text-xs font-bold min-w-[36px]"
              title={`${QUBO_LABELS[e.key]}: ${e.key === 'trip_cost' || e.key === 'overfill_penalty' ? '-' : ''}${e.value.toFixed(2)}`}
            >
              {pct > 12 ? e.value.toFixed(2) : ''}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-4 mt-3">
        {entries.map(e => {
          const negative = e.key === 'trip_cost' || e.key === 'overfill_penalty';
          return (
            <span key={e.key} className="flex items-center gap-1.5 text-xs text-slate-600">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: QUBO_COLORS[e.key] }} />
              {QUBO_LABELS[e.key]}: <span className="font-mono">{negative ? '-' : ''}{e.value.toFixed(2)}</span>
            </span>
          );
        })}
      </div>
      <div className="mt-2 text-right text-sm font-semibold text-slate-700">
        Total Score: {terms.total.toFixed(2)}
      </div>
    </div>
  );
}
