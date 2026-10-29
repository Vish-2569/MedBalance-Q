import { useQuery } from '@tanstack/react-query';
import { Thermometer, Battery, AlertTriangle, CheckCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, shortDate } from '@/lib/utils';

export default function ColdchainPage() {
  const { data: devices = [] } = useQuery({ queryKey: ['coldchain'], queryFn: api.getColdchain });
  const { data: vehicles = [] } = useQuery({ queryKey: ['vehicles'], queryFn: api.getVehicles });

  const vehicleMap = new Map(vehicles.map(v => [v.id, v]));

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">Cold Chain Monitoring</h1>

      {devices.length > 0 ? (
        <div className="grid grid-cols-2 gap-4">
          {devices.map(d => {
            const vehicle = vehicleMap.get(d.vehicle_id);
            return (
              <div key={d.device_id} className={cn(
                'bg-white rounded-lg border p-4',
                d.alert ? 'border-red-300 bg-red-50' : 'border-slate-200',
              )}>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-slate-800">{d.device_id}</h3>
                    <p className="text-xs text-slate-500">{vehicle?.name ?? d.vehicle_id}</p>
                  </div>
                  {d.alert
                    ? <AlertTriangle className="w-5 h-5 text-red-500" />
                    : <CheckCircle className="w-5 h-5 text-teal-500" />
                  }
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="flex items-center gap-2">
                    <Thermometer className={cn('w-4 h-4', d.temperature_c > 8 ? 'text-red-500' : 'text-blue-500')} />
                    <div>
                      <p className="text-lg font-bold">{d.temperature_c.toFixed(1)}°C</p>
                      <p className="text-xs text-slate-400">Temperature</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Battery className={cn('w-4 h-4', d.battery_pct < 20 ? 'text-red-500' : 'text-teal-500')} />
                    <div>
                      <p className="text-lg font-bold">{d.battery_pct}%</p>
                      <p className="text-xs text-slate-400">Battery</p>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-slate-400 mt-2">Last seen: {shortDate(d.last_seen)}</p>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-12">
          <Thermometer className="w-10 h-10" />
          <p className="text-sm">No cold chain sensors reporting yet</p>
        </div>
      )}
    </div>
  );
}
