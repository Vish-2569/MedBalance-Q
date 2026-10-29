import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  TrendingDown, Package, Truck, AlertTriangle, Snowflake, Play, Loader2,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, statusColor, formatINR, formatPct } from '@/lib/utils';
import { useLiveEvents } from '@/hooks/useSSE';

export default function PlanPage() {
  const queryClient = useQueryClient();
  const { data: planDemo, isLoading } = useQuery({ queryKey: ['plan'], queryFn: api.getPlanDemo });
  const [progress, setProgress] = useState<number | null>(null);

  const events = useLiveEvents(10);
  const planEvents = events.filter(e => e.type.startsWith('plan.'));

  const runMut = useMutation({
    mutationFn: () => api.runPlan('live'),
    onMutate: () => setProgress(0),
    onSuccess: () => {
      setProgress(null);
      void queryClient.invalidateQueries({ queryKey: ['plan'] });
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
    onError: () => setProgress(null),
  });

  const progressEvent = planEvents.find(e => e.type === 'plan.progress');
  const pct = progressEvent?.data?.progress_pct as number | undefined;
  const displayProgress = pct ?? progress;

  const plan = planDemo?.plan;
  const orders = planDemo?.orders ?? [];

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Redistribution Plan</h1>
        <button
          onClick={() => runMut.mutate()}
          disabled={runMut.isPending}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            runMut.isPending
              ? 'bg-slate-200 text-slate-400 cursor-wait'
              : 'bg-teal-600 text-white hover:bg-teal-700',
          )}
        >
          {runMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Run Plan
        </button>
      </div>

      {displayProgress !== null && (
        <div className="bg-teal-50 border border-teal-200 rounded-lg p-3">
          <div className="flex items-center justify-between text-sm text-teal-700 mb-1">
            <span>Optimizing...</span>
            <span>{displayProgress}%</span>
          </div>
          <div className="h-2 bg-teal-100 rounded-full overflow-hidden">
            <div className="h-full bg-teal-500 rounded-full transition-all" style={{ width: `${displayProgress}%` }} />
          </div>
        </div>
      )}

      {plan && (
        <>
          <div className="grid grid-cols-4 gap-3">
            <KpiCard icon={TrendingDown} label="Shortage Reduced" value={formatPct(plan.shortage_reduction)} color="teal" />
            <KpiCard icon={Package} label="Expiry Avoided" value={`${plan.expiry_avoided} units`} color="amber" />
            <KpiCard icon={Truck} label="Transfers" value={String(plan.transfers)} sub={formatINR(plan.cost_inr)} color="slate" />
            <KpiCard icon={AlertTriangle} label="Gap to MILP" value={plan.gap_to_milp !== undefined ? `${(plan.gap_to_milp * 100).toFixed(1)}%` : '—'} sub={plan.solver_tier} color="slate" />
          </div>

          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                  <th className="text-left px-4 py-2.5 font-medium">DTA No.</th>
                  <th className="text-left px-4 py-2.5 font-medium">Drug</th>
                  <th className="text-left px-4 py-2.5 font-medium">Lot</th>
                  <th className="text-left px-4 py-2.5 font-medium">Route</th>
                  <th className="text-right px-4 py-2.5 font-medium">Qty</th>
                  <th className="text-right px-4 py-2.5 font-medium">Usable</th>
                  <th className="text-center px-4 py-2.5 font-medium">Temp</th>
                  <th className="text-center px-4 py-2.5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(o => (
                  <tr key={o.id} className="border-t border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-xs">{o.dta_number}</td>
                    <td className="px-4 py-2.5 font-medium">{o.drug_name}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">{o.batch_no}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-slate-700">{o.src_facility_id}</span>
                      <span className="text-slate-400 mx-1">&rarr;</span>
                      <span className="text-slate-700">{o.dst_facility_id}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono">{o.qty}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{o.usable}</td>
                    <td className="px-4 py-2.5 text-center">
                      {o.temperature_req === 'cold_chain'
                        ? <Snowflake className="w-4 h-4 text-blue-500 mx-auto" />
                        : <span className="text-xs text-slate-400">ambient</span>
                      }
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', statusColor(o.status))}>
                        {o.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {isLoading && (
        <div className="flex-1 flex items-center justify-center text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          Loading plan data...
        </div>
      )}
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    teal: 'bg-teal-50 border-teal-200 text-teal-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    slate: 'bg-white border-slate-200 text-slate-700',
    red: 'bg-red-50 border-red-200 text-red-700',
  };
  return (
    <div className={cn('rounded-lg border p-3', colorMap[color] ?? colorMap.slate)}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 opacity-60" />
        <span className="text-xs font-medium opacity-70">{label}</span>
      </div>
      <p className="text-xl font-bold">{value}</p>
      {sub && <p className="text-xs opacity-60 mt-0.5">{sub}</p>}
    </div>
  );
}
