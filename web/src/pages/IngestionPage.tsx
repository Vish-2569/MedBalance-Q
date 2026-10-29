import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileInput, AlertTriangle, Check, X, Clock, ChevronDown, ChevronUp,
  Languages, Eye, Loader2, Pencil,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, shortDate } from '@/lib/utils';
import type { StockReport, ReviewItem } from '@/types/domain';

const CHANNEL_LABEL: Record<string, string> = {
  fhir: 'FHIR R5', csv: 'e-Aushadhi CSV', chat: 'Chat (Kannada)', text: 'Free Text',
};
const LANG_LABEL: Record<string, string> = {
  en: 'English', kn: 'Kannada', mixed: 'Mixed',
};

function confidenceChip(c: number) {
  if (c >= 0.85) return 'bg-teal-100 text-teal-700 border-teal-200';
  if (c >= 0.6) return 'bg-amber-100 text-amber-700 border-amber-200';
  return 'bg-red-100 text-red-700 border-red-200';
}

export default function IngestionPage() {
  const { data: reports = [], isLoading } = useQuery({ queryKey: ['reports'], queryFn: () => api.getReports() });
  const { data: reviews = [] } = useQuery({ queryKey: ['reviews'], queryFn: api.getReviews });
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [reviewTarget, setReviewTarget] = useState<ReviewItem | null>(null);

  const pending = reviews.filter(r => r.status === 'pending');
  const flagged = reports.filter(r => r.status === 'flagged').length;

  if (isLoading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">Ingestion & Review</h1>

      {pending.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
          <span className="text-sm text-amber-800 font-medium">
            {pending.length} item{pending.length > 1 ? 's' : ''} need pharmacist review
          </span>
        </div>
      )}

      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Reports Received" value={reports.length} icon={FileInput} />
        <StatCard label="Flagged" value={flagged} icon={AlertTriangle} color="text-amber-600" />
        <StatCard label="Pending Reviews" value={pending.length} icon={Clock} color="text-red-600" />
        <StatCard label="Resolved" value={reviews.length - pending.length} icon={Check} color="text-teal-600" />
      </div>

      {/* Report list */}
      <h2 className="text-lg font-semibold text-slate-700 mt-2">Reports</h2>
      {reports.length > 0 ? (
        <div className="space-y-2">
          {reports.map(r => (
            <ReportCard
              key={r.id}
              report={r}
              expanded={expandedReport === r.id}
              onToggle={() => setExpandedReport(expandedReport === r.id ? null : r.id)}
            />
          ))}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-12">
          <FileInput className="w-10 h-10" />
          <p className="text-sm">No reports ingested yet. Run the simulation and pull reports.</p>
        </div>
      )}

      {/* Review queue */}
      {reviews.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-slate-700 mt-2">Review Queue</h2>
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                  <th className="text-left px-4 py-2.5 font-medium">Facility</th>
                  <th className="text-left px-4 py-2.5 font-medium">Drug</th>
                  <th className="text-left px-4 py-2.5 font-medium">Qty</th>
                  <th className="text-left px-4 py-2.5 font-medium">Confidence</th>
                  <th className="text-left px-4 py-2.5 font-medium">Anomaly</th>
                  <th className="text-center px-4 py-2.5 font-medium">Status</th>
                  <th className="text-center px-4 py-2.5 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map(r => (
                  <tr key={r.id} className={cn(
                    'border-t border-slate-100 hover:bg-slate-50',
                    r.status === 'pending' && r.anomaly_type === 'qty_spike' && 'bg-red-50/30',
                  )}>
                    <td className="px-4 py-2.5 text-sm font-medium">{r.facility_code ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      <span className="font-medium">{r.drug_name ?? r.drug_code ?? '—'}</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-sm">{r.extracted_qty ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      {r.confidence != null && (
                        <span className={cn('text-xs px-2 py-0.5 rounded-full border font-medium', confidenceChip(r.confidence))}>
                          {(r.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {r.anomaly_type && r.anomaly_type !== 'none' ? (
                        <div>
                          <span className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200 font-medium">
                            {r.anomaly_type}
                          </span>
                          {r.anomaly_explanation && (
                            <p className="text-xs text-slate-500 mt-1 max-w-xs">{r.anomaly_explanation}</p>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">clean</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <ReviewBadge status={r.status} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {r.status === 'pending' ? (
                        <div className="flex items-center justify-center gap-1">
                          <ReviewActions review={r} onCorrect={() => setReviewTarget(r)} />
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">{r.resolved_by ?? '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Review correction modal */}
      {reviewTarget && (
        <ReviewModal
          review={reviewTarget}
          onClose={() => setReviewTarget(null)}
        />
      )}
    </div>
  );
}

function ReportCard({ report, expanded, onToggle }: {
  report: StockReport; expanded: boolean; onToggle: () => void;
}) {
  const channel = report.channel ?? report.format ?? 'unknown';
  const language = report.language ?? 'en';
  const hasKannada = language === 'kn' || language === 'mixed';

  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
      <button onClick={onToggle} className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-50 transition-colors">
        <div className="flex items-center gap-3">
          <FileInput className="w-4 h-4 text-slate-400" />
          <span className="font-medium text-slate-800">{report.facility_code}</span>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">
            {CHANNEL_LABEL[channel] ?? channel}
          </span>
          {hasKannada && (
            <span className="text-xs px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 flex items-center gap-1">
              <Languages className="w-3 h-3" />
              {LANG_LABEL[language]}
            </span>
          )}
          <span className="text-xs text-slate-500">{shortDate(report.received_at ?? '')}</span>
          <span className={cn(
            'text-xs px-2 py-0.5 rounded-full font-medium',
            report.status === 'processed' ? 'bg-teal-100 text-teal-700' : 'bg-slate-100 text-slate-600',
          )}>
            {report.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">{report.items?.length ?? 0} items</span>
          {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-100">
          <div className="flex">
            {/* Raw text panel */}
            {report.raw_text && (
              <div className="w-1/2 border-r border-slate-100 p-4">
                <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                  <Eye className="w-3 h-3" /> Raw Text
                </h4>
                <pre className={cn(
                  'text-sm whitespace-pre-wrap bg-slate-50 rounded p-3 max-h-60 overflow-auto',
                  hasKannada && 'font-kannada',
                )}>
                  {report.raw_text}
                </pre>
              </div>
            )}

            {/* Extracted items */}
            <div className={report.raw_text ? 'w-1/2 p-4' : 'w-full p-4'}>
              <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Extracted Items</h4>
              {report.items && report.items.length > 0 ? (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-400">
                      <th className="text-left py-1">Drug</th>
                      <th className="text-right py-1">Qty</th>
                      <th className="text-left py-1">Batch</th>
                      <th className="text-left py-1">Expiry</th>
                      <th className="text-center py-1">Conf.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.items.map((item: any, i: number) => (
                      <tr key={i} className="border-t border-slate-50">
                        <td className="py-1.5 font-medium">{item.drug_name ?? item.drug_code ?? '—'}</td>
                        <td className="py-1.5 text-right font-mono">{item.qty ?? '—'}</td>
                        <td className="py-1.5 text-slate-500">{item.batch_no ?? '—'}</td>
                        <td className="py-1.5 text-slate-500">{item.expiry ?? '—'}</td>
                        <td className="py-1.5 text-center">
                          {item.confidence != null && (
                            <span className={cn('px-1.5 py-0.5 rounded-full border text-xs font-medium', confidenceChip(item.confidence))}>
                              {(item.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-xs text-slate-400 italic">No items extracted</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewActions({ review, onCorrect }: { review: ReviewItem; onCorrect: () => void }) {
  const queryClient = useQueryClient();
  const acceptMut = useMutation({
    mutationFn: () => api.resolveReview(review.id, 'accept'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reviews'] }),
  });
  const rejectMut = useMutation({
    mutationFn: () => api.resolveReview(review.id, 'reject'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reviews'] }),
  });

  const loading = acceptMut.isPending || rejectMut.isPending;
  return (
    <>
      <button
        onClick={() => acceptMut.mutate()}
        disabled={loading}
        className="p-1 rounded hover:bg-teal-50 text-teal-600 transition-colors"
        title="Accept as-is"
      >
        {acceptMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
      </button>
      <button
        onClick={onCorrect}
        disabled={loading}
        className="p-1 rounded hover:bg-blue-50 text-blue-600 transition-colors"
        title="Correct values"
      >
        <Pencil className="w-4 h-4" />
      </button>
      <button
        onClick={() => rejectMut.mutate()}
        disabled={loading}
        className="p-1 rounded hover:bg-red-50 text-red-600 transition-colors"
        title="Reject"
      >
        {rejectMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
      </button>
    </>
  );
}

function ReviewModal({ review, onClose }: { review: ReviewItem; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [drugCode, setDrugCode] = useState(review.drug_code ?? '');
  const [qty, setQty] = useState(String(review.extracted_qty ?? ''));
  const [expiry, setExpiry] = useState('');

  const correctMut = useMutation({
    mutationFn: () => api.resolveReview(review.id, 'correct', {
      drug_code: drugCode, qty: Number(qty), expiry: expiry || undefined,
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['reviews'] }); onClose(); },
  });

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-lg p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-slate-800 mb-4">Correct Review Item</h3>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Drug Code</label>
            {review.candidates && review.candidates.length > 0 ? (
              <select value={drugCode} onChange={e => setDrugCode(e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm">
                <option value="">Select...</option>
                {review.candidates.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            ) : (
              <input value={drugCode} onChange={e => setDrugCode(e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
            )}
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Quantity</label>
            <input type="number" value={qty} onChange={e => setQty(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Expiry (YYYY-MM-DD)</label>
            <input type="date" value={expiry} onChange={e => setExpiry(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
          <button onClick={() => correctMut.mutate()} disabled={correctMut.isPending}
            className="px-4 py-2 text-sm bg-teal-600 text-white rounded-lg hover:bg-teal-700 flex items-center gap-1">
            {correctMut.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
            Save Correction
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: React.ComponentType<{ className?: string }>; color?: string }) {
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

function ReviewBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; icon: React.ComponentType<{ className?: string }> }> = {
    pending: { bg: 'bg-amber-100 text-amber-700', icon: Clock },
    accepted: { bg: 'bg-teal-100 text-teal-700', icon: Check },
    auto_approved: { bg: 'bg-teal-100 text-teal-700', icon: Check },
    corrected: { bg: 'bg-blue-100 text-blue-700', icon: Pencil },
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
