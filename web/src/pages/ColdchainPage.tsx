import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, ReferenceLine, ReferenceArea, ResponsiveContainer, Tooltip } from 'recharts';
import { Thermometer, Battery, Loader2, AlertOctagon, Wifi, HelpCircle, Info, Snowflake, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { cn, shortDate } from '@/lib/utils';
import { api } from '@/lib/api';
import type { ColdchainStatus } from '@/types/domain';

const COLD_MIN = 2;
const COLD_MAX = 8;

export default function ColdchainPage() {
  const { data: devices = [], isLoading, error } = useQuery({ queryKey: ['coldchain'], queryFn: api.getColdchain, refetchInterval: 5000 });
  const [showGuide, setShowGuide] = useState(true);

  const hasExcursion = devices.some(d => d.state === 'excursion');

  if (isLoading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-500" /></div>;

  if (error) return (
    <div className="flex-1 flex flex-col items-center justify-center text-slate-500 gap-3 py-12">
      <Snowflake className="w-12 h-12 text-slate-300" />
      <p className="text-base font-medium text-slate-700">Cold Chain Unavailable</p>
      <p className="text-sm max-w-md text-center text-red-600">
        Failed to load cold chain data: {error.message}. Make sure the coldchain service is running.
      </p>
    </div>
  );

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

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Cold Chain Monitoring</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Monitors temperature-sensitive medicine storage and transport — ensures vaccines and biologics stay within the safe 2–8°C range.
          </p>
        </div>
        <button
          onClick={() => setShowGuide(g => !g)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          {showGuide ? 'Hide Guide' : 'Show Guide'}
        </button>
      </div>

      {/* Guide panel */}
      {showGuide && (
        <div className="bg-gradient-to-r from-sky-50 to-indigo-50 rounded-xl border border-sky-200 p-5">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-sky-100 flex items-center justify-center shrink-0 mt-0.5">
              <Info className="w-5 h-5 text-sky-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-slate-800 text-sm mb-2">Understanding Cold Chain</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-600">
                <div className="space-y-2">
                  <div className="flex items-start gap-2">
                    <Snowflake className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">What is Cold Chain?</span>
                      <p className="text-xs text-slate-500">Many medicines (vaccines, insulin, biologics) must stay between 2–8°C from source to patient. A break in this chain can ruin the medicine.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Thermometer className="w-4 h-4 text-teal-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">Device Cards</span>
                      <p className="text-xs text-slate-500">Each card shows a temperature sensor — its current reading, battery level, last contact time, and a sparkline chart of recent temperatures. The blue band on the chart marks the safe 2–8°C zone.</p>
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-start gap-2">
                    <ShieldAlert className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">Excursion Alerts</span>
                      <p className="text-xs text-slate-500">When temperature goes outside the safe range, the device enters "excursion" state. A red banner appears and affected medicine lots may be quarantined to prevent use of potentially spoiled medicines.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">Status Indicators</span>
                      <p className="text-xs text-slate-500">
                        <strong className="text-teal-600">OK</strong> = within range,{' '}
                        <strong className="text-amber-600">Warning</strong> = approaching limits,{' '}
                        <strong className="text-red-600">Excursion</strong> = out of range.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2 bg-amber-50/60 rounded-lg px-2 py-1.5 border border-amber-100">
                    <Info className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-700">
                      <strong>Note:</strong> These are simulated sensors. In production, real IoT devices would report via MQTT.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <StatCard label="Devices" value={devices.length} color="text-slate-800" tooltip="Total number of cold chain sensors reporting" />
        <StatCard label="OK" value={devices.filter(d => d.state === 'ok').length} color="text-teal-600" tooltip="Devices with temperature in the safe 2–8°C range" />
        <StatCard label="Excursions" value={devices.filter(d => d.state === 'excursion').length} color="text-red-600" tooltip="Devices with temperature outside the safe range — these need immediate attention" />
      </div>

      {/* Device cards */}
      <div>
        <p className="text-xs text-slate-400 mb-2">Each card represents a temperature sensor on a storage unit or transport vehicle. The sparkline shows recent temperature readings.</p>
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {devices.length > 0
            ? devices.map(d => <DeviceCard key={d.device_id} device={d} />)
            : (
              <div className="col-span-full flex flex-col items-center justify-center py-8 text-slate-400 gap-2">
                <Snowflake className="w-8 h-8" />
                <p className="text-sm">No cold chain devices reporting yet.</p>
                <p className="text-xs">Start the simulation on the Scenarios page to begin generating sensor data.</p>
              </div>
            )
          }
        </div>
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
        <span className="flex items-center gap-1" title="Current temperature reading">
          <Thermometer className="w-3 h-3" />
          <span className={cn(
            'font-mono font-semibold',
            device.temperature_c == null ? 'text-slate-500' : device.temperature_c > COLD_MAX ? 'text-red-600' : device.temperature_c < COLD_MIN ? 'text-blue-600' : 'text-teal-600',
          )}>
            {device.temperature_c == null ? 'Unavailable' : `${device.temperature_c.toFixed(1)}°C`}
          </span>
        </span>
        <span className="flex items-center gap-1" title="Battery level">
          <Battery className="w-3 h-3" />
          <span className={cn('font-mono', device.battery_pct != null && device.battery_pct < 20 ? 'text-red-600 font-semibold' : '')}>
            {device.battery_pct == null ? '—' : `${device.battery_pct}%`}
          </span>
        </span>
        <span className="flex items-center gap-1" title="Last time the sensor reported">
          <Wifi className="w-3 h-3" />
          {shortDate(device.last_seen)}
        </span>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, tooltip }: { label: string; value: number; color: string; tooltip?: string }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3" title={tooltip}>
      <span className="text-xs text-slate-500 font-medium">{label}</span>
      <p className={cn('text-2xl font-bold', color)}>{value}</p>
    </div>
  );
}
