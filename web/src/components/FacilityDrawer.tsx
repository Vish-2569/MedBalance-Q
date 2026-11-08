import { useQuery } from '@tanstack/react-query';
import { X, Snowflake } from 'lucide-react';
import { api } from '@/lib/api';
import type { Facility } from '@/types/domain';
import { cn, venColor, facilityLabel, daysUntil, shortDate } from '@/lib/utils';

interface Props {
  facility: Facility;
  onClose: () => void;
  simDate?: string;
}

export default function FacilityDrawer({ facility, onClose, simDate }: Props) {
  const { data: positions } = useQuery({
    queryKey: ['positions', facility.id],
    queryFn: () => api.getPositions(facility.id),
  });
  const { data: lots } = useQuery({
    queryKey: ['lots', facility.id],
    queryFn: () => api.getLots(facility.id),
  });
  const { data: drugs } = useQuery({
    queryKey: ['drugs'],
    queryFn: api.getDrugs,
  });

  const drugMap = new Map(drugs?.map(d => [d.code, d]) ?? []);
  const refDate = simDate ?? new Date().toISOString().slice(0, 10);

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-[420px] bg-white shadow-xl border-l border-slate-200 z-50 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
        <div>
          <h2 className="text-base font-semibold text-slate-800">{facilityLabel(facility)}</h2>
          <p className="text-xs text-slate-500">{facility.id} &middot; {facility.type}{facility.cold_storage && ' ❄ cold storage'}</p>
        </div>
        <button onClick={onClose} className="p-1.5 rounded hover:bg-slate-200">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">Stock Positions</h3>
        {positions && positions.length > 0 ? (
          <div className="space-y-2">
            {positions.map(p => {
              const drug = drugMap.get(p.drug_code);
              const facLots = lots?.filter(l => l.drug_code === p.drug_code) ?? [];
              const onHand = facLots.reduce((s, l) => s + l.qty, 0);
              return (
                <div key={p.drug_code} className="rounded-lg border border-slate-100 p-3 hover:bg-slate-50">
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className={cn('text-xs font-bold', venColor(drug?.ven ?? 'N'))}>{drug?.ven}</span>
                    <span className="text-sm font-medium text-slate-800">{drug?.name ?? p.drug_code}</span>
                    {drug?.cold_chain && <Snowflake className="w-3 h-3 text-blue-500 shrink-0" />}
                  </div>
                  <div className="grid grid-cols-5 gap-1 text-center">
                    <div>
                      <p className="text-[10px] text-slate-400 leading-tight">On Hand</p>
                      <p className="text-sm font-mono font-semibold text-slate-700">{onHand}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 leading-tight">Effective</p>
                      <p className="text-sm font-mono font-semibold text-slate-700">{p.effective_stock}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 leading-tight">At Risk</p>
                      <p className={cn('text-sm font-mono font-semibold', p.at_risk > 0 ? 'text-amber-600' : 'text-slate-700')}>{p.at_risk}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 leading-tight">Shortage</p>
                      <p className={cn('text-sm font-mono font-semibold', p.shortage > 0 ? 'text-red-600' : 'text-slate-700')}>{p.shortage}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-400 leading-tight">Reserve</p>
                      <p className="text-sm font-mono font-semibold text-slate-700">{p.reserve}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-500 italic">No stock positions recorded</p>
        )}

        <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wide pt-2">Lots (FEFO)</h3>
        {lots && lots.length > 0 ? (
          <div className="space-y-2">
            {lots.sort((a, b) => a.expiry.localeCompare(b.expiry)).map(lot => {
              const days = daysUntil(lot.expiry, refDate);
              const maxDays = 180;
              const pct = Math.max(5, Math.min(100, (days / maxDays) * 100));
              const drug = drugMap.get(lot.drug_code);
              return (
                <div key={lot.batch_no} className="border border-slate-100 rounded-lg p-2.5">
                  <div className="flex justify-between items-center text-xs mb-1">
                    <span className="font-medium">{drug?.name ?? lot.drug_code}</span>
                    <span className="text-slate-500">{lot.batch_no}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          days <= 30 ? 'bg-red-500' : days <= 90 ? 'bg-amber-400' : 'bg-teal-500',
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono w-20 text-right">
                      {lot.qty} {drug?.unit ?? 'units'}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500 mt-0.5">
                    <span>Exp: {shortDate(lot.expiry)}</span>
                    <span className={cn(days <= 30 && 'text-red-500 font-medium')}>
                      {days > 0 ? `${days}d left` : 'EXPIRED'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-500 italic">No lots recorded</p>
        )}
      </div>
    </div>
  );
}
