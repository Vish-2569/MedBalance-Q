import { useQuery } from '@tanstack/react-query';
import { FileInput, AlertTriangle, Check, X, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, shortDate } from '@/lib/utils';

export default function IngestionPage() {
  const { data: reports = [] } = useQuery({ queryKey: ['reports'], queryFn: () => api.getReports() });
  const { data: reviews = [] } = useQuery({ queryKey: ['reviews'], queryFn: api.getReviews });

  const pending = reviews.filter(r => r.status === 'pending');

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">Ingestion & Review</h1>

      {pending.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
          <span className="text-sm text-amber-800 font-medium">{pending.length} items need pharmacist review</span>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Reports Received" value={reports.length} icon={FileInput} />
        <StatCard label="Pending Reviews" value={pending.length} icon={Clock} />
        <StatCard label="Resolved" value={reviews.length - pending.length} icon={Check} />
      </div>

      {reviews.length > 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                <th className="text-left px-4 py-2.5 font-medium">Report</th>
                <th className="text-left px-4 py-2.5 font-medium">Drug</th>
                <th className="text-left px-4 py-2.5 font-medium">Anomaly</th>
                <th className="text-center px-4 py-2.5 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map(r => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{r.report_id?.slice(0, 8)}</td>
                  <td className="px-4 py-2.5">{(r.extraction as Record<string, unknown>)?.drug_name_raw as string ?? '—'}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-600">Item #{r.item_index}</td>
                  <td className="px-4 py-2.5 text-center">
                    <ReviewBadge status={r.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-12">
          <FileInput className="w-10 h-10" />
          <p className="text-sm">No reports ingested yet. Run the simulation and pull reports.</p>
        </div>
      )}

      {reports.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-slate-700 mt-2">Recent Reports</h2>
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                  <th className="text-left px-4 py-2.5 font-medium">Facility</th>
                  <th className="text-left px-4 py-2.5 font-medium">Format</th>
                  <th className="text-left px-4 py-2.5 font-medium">Date</th>
                  <th className="text-right px-4 py-2.5 font-medium">Items</th>
                </tr>
              </thead>
              <tbody>
                {reports.slice(0, 20).map((r, i) => (
                  <tr key={r.id ?? i} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-medium">{r.facility_code}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">{r.format}</span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">{shortDate(r.reported_at)}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{r.items.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, icon: Icon }: { label: string; value: number; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-slate-400" />
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <p className="text-2xl font-bold text-slate-800">{value}</p>
    </div>
  );
}

function ReviewBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; icon: React.ComponentType<{ className?: string }> }> = {
    pending: { bg: 'bg-amber-100 text-amber-700', icon: Clock },
    accepted: { bg: 'bg-teal-100 text-teal-700', icon: Check },
    fixed: { bg: 'bg-blue-100 text-blue-700', icon: Check },
    rejected: { bg: 'bg-red-100 text-red-700', icon: X },
  };
  const c = config[status] ?? config.pending;
  const StatusIcon = c.icon;
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium', c.bg)}>
      <StatusIcon className="w-3 h-3" />
      {status}
    </span>
  );
}
