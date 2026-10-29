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
    <div className="fixed inset-y-0 right-0 w-[420px] bg-white shadow-xl border-l border-slate-200 z-50 flex flex-col overflow-hidden">
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
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 border-b border-slate-100">
                <th className="text-left py-1.5 font-medium">Drug</th>
                <th className="text-right py-1.5 font-medium">On Hand</th>
                <th className="text-right py-1.5 font-medium">Effective</th>
                <th className="text-right py-1.5 font-medium">At Risk</th>
                <th className="text-right py-1.5 font-medium">Shortage</th>
                <th className="text-right py-1.5 font-medium">Reserve</th>
              </tr>
            </thead>
            <tbody>
              {positions.map(p => {
                const drug = drugMap.get(p.drug_code);
                const facLots = lots?.filter(l => l.drug_code === p.drug_code) ?? [];
                const onHand = facLots.reduce((s, l) => s + l.qty, 0);
                return (
                  <tr key={p.drug_code} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="py-2">
                      <div className="flex items-center gap-1.5">
                        <span className={cn('text-xs font-bold', venColor(drug?.ven ?? 'N'))}>{drug?.ven}</span>
                        <span className="font-medium">{drug?.name ?? p.drug_code}</span>
                        {drug?.cold_chain && <Snowflake className="w-3 h-3 text-blue-500" />}
                      </div>
                    </td>
                    <td className="text-right font-mono">{onHand}</td>
                    <td className="text-right font-mono">{p.effective_stock}</td>
                    <td className={cn('text-right font-mono', p.at_risk > 0 && 'text-amber-600 font-semibold')}>{p.at_risk}</td>
                    <td className={cn('text-right font-mono', p.shortage > 0 && 'text-red-600 font-semibold')}>{p.shortage}</td>
                    <td className="text-right font-mono">{p.reserve}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-400 italic">No stock positions recorded</p>
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
                  <div className="flex justify-between text-xs text-slate-400 mt-0.5">
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
          <p className="text-sm text-slate-400 italic">No lots recorded</p>
        )}
      </div>
    </div>
  );
}
