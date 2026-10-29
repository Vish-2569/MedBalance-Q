import { useState, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Pause, Zap, Clock, Activity, ShieldCheck, ShieldAlert } from 'lucide-react';
import { api } from '@/lib/api';
import { useLiveEvents } from '@/hooks/useSSE';
import { cn } from '@/lib/utils';

const SPEEDS = [1, 2, 5, 10];

export default function TopBar() {
  const queryClient = useQueryClient();
  const { data: clock } = useQuery({ queryKey: ['clock'], queryFn: api.getClock, refetchInterval: 5000 });
  const { data: auditStatus } = useQuery({ queryKey: ['audit-verify'], queryFn: api.getAuditVerify, refetchInterval: 10_000 });
  const events = useLiveEvents(5);

  const startMut = useMutation({ mutationFn: api.startClock, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clock'] }) });
  const pauseMut = useMutation({ mutationFn: api.pauseClock, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clock'] }) });
  const speedMut = useMutation({ mutationFn: api.setSpeed, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clock'] }) });

  return (
    <header className="bg-white border-b border-slate-200 px-4 py-2 flex items-center gap-4 shrink-0">
      <div className="flex items-center gap-2 font-semibold text-teal-700 text-lg">
        <Activity className="w-5 h-5" />
        <span>MedBalance-Q</span>
      </div>

      <div className="flex items-center gap-2 ml-4 px-3 py-1 rounded-lg bg-slate-50 border border-slate-200">
        <Clock className="w-4 h-4 text-slate-500" />
        <span className="text-sm font-mono font-medium text-slate-700">
          {clock?.sim_date ?? '—'}
        </span>
        <span className={cn(
          'text-xs px-1.5 py-0.5 rounded font-medium',
          clock?.running ? 'bg-teal-100 text-teal-700' : 'bg-slate-200 text-slate-500',
        )}>
          {clock?.running ? 'LIVE' : 'PAUSED'}
        </span>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => clock?.running ? pauseMut.mutate() : startMut.mutate()}
          className="p-1.5 rounded hover:bg-slate-100 transition-colors"
          title={clock?.running ? 'Pause' : 'Play'}
        >
          {clock?.running
            ? <Pause className="w-4 h-4 text-slate-600" />
            : <Play className="w-4 h-4 text-teal-600" />
          }
        </button>
        {SPEEDS.map(s => (
          <button
            key={s}
            onClick={() => speedMut.mutate(s)}
            className={cn(
              'text-xs px-2 py-1 rounded font-medium transition-colors',
              clock?.speed === s ? 'bg-teal-600 text-white' : 'text-slate-500 hover:bg-slate-100',
            )}
          >
            {s}x
          </button>
        ))}
      </div>

      <div className="flex-1" />

      <div className="flex items-center gap-2 max-w-md overflow-hidden">
        <Zap className="w-4 h-4 text-amber-500 shrink-0" />
        <div className="flex gap-1.5 overflow-x-auto text-xs">
          {events.length === 0 && (
            <span className="text-slate-400 italic">No events yet</span>
          )}
          {events.map(e => (
            <span
              key={e.id}
              className={cn(
                'px-2 py-0.5 rounded-full whitespace-nowrap border',
                e.type.includes('alert') || e.type.includes('anomaly')
                  ? 'bg-red-50 border-red-200 text-red-700'
                  : e.type.includes('plan')
                    ? 'bg-teal-50 border-teal-200 text-teal-700'
                    : 'bg-slate-50 border-slate-200 text-slate-600',
              )}
            >
              {e.type.split('.').pop()}
            </span>
          ))}
        </div>
      </div>

      <AuditBadge auditStatus={auditStatus} />
    </header>
  );
}

function AuditBadge({ auditStatus }: { auditStatus?: { ok: boolean; entries: number; broken_at?: number | null } }) {
  const queryClient = useQueryClient();
  const [adminOpen, setAdminOpen] = useState(false);
  const [confirmTamper, setConfirmTamper] = useState(false);
  const clickCountRef = useRef(0);
  const clickTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const tamperMut = useMutation({
    mutationFn: api.tamperDemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit-verify'] });
      setAdminOpen(false);
      setConfirmTamper(false);
    },
  });
  const restoreMut = useMutation({
    mutationFn: api.restoreDemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit-verify'] });
      setAdminOpen(false);
    },
  });

  const handleBadgeClick = useCallback(() => {
    clickCountRef.current += 1;
    if (clickTimerRef.current) clearTimeout(clickTimerRef.current);

    if (clickCountRef.current >= 5) {
      clickCountRef.current = 0;
      setAdminOpen(prev => !prev);
      setConfirmTamper(false);
    } else {
      clickTimerRef.current = setTimeout(() => {
        clickCountRef.current = 0;
      }, 1500);
    }
  }, []);

  return (
    <div className="relative">
      <button
        onClick={handleBadgeClick}
        className={cn(
          'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors select-none',
          auditStatus?.ok
            ? 'bg-teal-50 border-teal-200 text-teal-700'
            : 'bg-red-50 border-red-300 text-red-700 animate-pulse',
        )}
        title={`Audit: ${auditStatus?.ok ? 'OK' : 'TAMPERED'} (${auditStatus?.entries ?? 0} entries)`}
      >
        {auditStatus?.ok
          ? <ShieldCheck className="w-4 h-4" />
          : <ShieldAlert className="w-4 h-4" />
        }
        <span>
          {auditStatus?.ok
            ? `Ledger verified ✓ ${auditStatus.entries}`
            : `Tampered at #${auditStatus?.broken_at ?? '?'}`
          }
        </span>
      </button>

      {adminOpen && (
        <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-lg border border-slate-200 shadow-lg py-1 z-50">
          <div className="px-3 py-1.5 text-xs text-slate-400 font-medium">Admin Demo</div>

          {!confirmTamper ? (
            <button
              onClick={() => setConfirmTamper(true)}
              className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              Tamper audit row
            </button>
          ) : (
            <div className="px-3 py-2 space-y-2">
              <p className="text-xs text-red-600 font-medium">Are you sure? This will break the hash chain.</p>
              <div className="flex gap-2">
                <button
                  onClick={() => tamperMut.mutate()}
                  disabled={tamperMut.isPending}
                  className="px-3 py-1 text-xs bg-red-600 text-white rounded font-medium hover:bg-red-700 disabled:opacity-50"
                >
                  {tamperMut.isPending ? 'Tampering...' : 'Confirm'}
                </button>
                <button
                  onClick={() => setConfirmTamper(false)}
                  className="px-3 py-1 text-xs bg-slate-100 text-slate-600 rounded font-medium hover:bg-slate-200"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <button
            onClick={() => restoreMut.mutate()}
            disabled={restoreMut.isPending}
            className="w-full text-left px-3 py-2 text-sm text-teal-600 hover:bg-teal-50 transition-colors"
          >
            {restoreMut.isPending ? 'Restoring...' : 'Restore audit row'}
          </button>

          <div className="border-t border-slate-100 mt-1 pt-1">
            <button
              onClick={() => { setAdminOpen(false); setConfirmTamper(false); }}
              className="w-full text-left px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-50"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
