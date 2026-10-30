import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, ReferenceLine, ReferenceArea, ResponsiveContainer, Tooltip } from 'recharts';
import { Thermometer, Battery, Loader2, AlertOctagon, Wifi } from 'lucide-react';
import { cn, shortDate } from '@/lib/utils';
import { api } from '@/lib/api';
import type { ColdchainStatus } from '@/types/domain';

const COLD_MIN = 2;
const COLD_MAX = 8;

export default function ColdchainPage() {
  const { data: devices = [], isLoading } = useQuery({ queryKey: ['coldchain'], queryFn: api.getColdchain, refetchInterval: 5000 });

  const hasExcursion = devices.some(d => d.state === 'excursion');

  if (isLoading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      {/* Excursion banner */}
      {hasExcursion && (
        <div className="excursion-banner bg-red-600 text-white rounded-lg p-3 flex items-center gap-3 shadow-lg">
          <AlertOctagon className="w-6 h-6 shrink-0" />
          <div>
            <p className="font-semibold">Cold Chain Excursion Detected</p>
            <p className="text-sm text-red-100">
              {devices.filter(d => d.state === 'excursion').map(d => d.device_id).join(', ')} — temperature outside 2-8°C range. Affected lots may be quarantined.
            </p>
          </div>
        </div>
      )}

      <h1 className="text-xl font-semibold text-slate-800">Cold Chain Monitoring</h1>

      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Devices" value={devices.length} color="text-slate-800" />
        <StatCard label="OK" value={devices.filter(d => d.state === 'ok').length} color="text-teal-600" />
        <StatCard label="Excursions" value={devices.filter(d => d.state === 'excursion').length} color="text-red-600" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {devices.map(d => <DeviceCard key={d.device_id} device={d} />)}
      </div>
    </div>
  );
}

function DeviceCard({ device }: { device: ColdchainStatus }) {
  const history = (device.temperature_history ?? []).map((t, i) => ({ i, temp: t }));
  const stateConfig = {
    ok: { bg: 'bg-teal-50 border-teal-200', badge: 'bg-teal-100 text-teal-700', label: 'OK' },
    warning: { bg: 'bg-amber-50 border-amber-200', badge: 'bg-amber-100 text-amber-700', label: 'Warning' },
    excursion: { bg: 'bg-red-50 border-red-200', badge: 'bg-red-100 text-red-700', label: 'Excursion' },
    unknown: { bg: 'bg-slate-50 border-slate-200', badge: 'bg-slate-100 text-slate-600', label: 'Unknown' },
  }[device.state];

  return (
    <div className={cn('rounded-lg border p-4', stateConfig.bg)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Thermometer className="w-4 h-4 text-slate-500" />
          <span className="font-semibold text-slate-800">{device.device_id}</span>
          <span className="text-xs text-slate-500">
            ({device.vehicle_id ?? (device.facility_id ? `Facility ${device.facility_id}` : 'Location unavailable')})
          </span>
        </div>
        <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', stateConfig.badge)}>
          {stateConfig.label}
        </span>
      </div>

      {/* Sparkline */}
      {history.length > 0 && (
        <div className="mb-3 h-24">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <ReferenceArea y1={COLD_MIN} y2={COLD_MAX} fill="rgba(59,130,246,0.08)" />
              <ReferenceLine y={COLD_MIN} stroke="#93c5fd" strokeDasharray="3 3" />
              <ReferenceLine y={COLD_MAX} stroke="#93c5fd" strokeDasharray="3 3" />
              <YAxis tick={{ fontSize: 9 }} domain={[0, 12]} tickCount={4} />
              <XAxis dataKey="i" hide />
              <Tooltip
                formatter={(v) => [`${Number(v).toFixed(1)}°C`, 'Temp']}
                contentStyle={{ fontSize: 11, borderRadius: 6, padding: '4px 8px' }}
              />
              <Line
                type="monotone" dataKey="temp" dot={false} strokeWidth={2}
                stroke={device.state === 'excursion' ? '#ef4444' : device.state === 'warning' ? '#f59e0b' : '#14b8a6'}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-slate-600">
        <span className="flex items-center gap-1">
          <Thermometer className="w-3 h-3" />
          <span className={cn(
            'font-mono font-semibold',
            device.temperature_c == null ? 'text-slate-400' : device.temperature_c > COLD_MAX ? 'text-red-600' : device.temperature_c < COLD_MIN ? 'text-blue-600' : 'text-teal-600',
          )}>
            {device.temperature_c == null ? 'Unavailable' : `${device.temperature_c.toFixed(1)}°C`}
          </span>
        </span>
        <span className="flex items-center gap-1">
          <Battery className="w-3 h-3" />
          <span className={cn('font-mono', device.battery_pct != null && device.battery_pct < 20 ? 'text-red-600 font-semibold' : '')}>
            {device.battery_pct == null ? '—' : `${device.battery_pct}%`}
          </span>
        </span>
        <span className="flex items-center gap-1">
          <Wifi className="w-3 h-3" />
          {shortDate(device.last_seen)}
        </span>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <span className="text-xs text-slate-500 font-medium">{label}</span>
      <p className={cn('text-2xl font-bold', color)}>{value}</p>
    </div>
  );
}
