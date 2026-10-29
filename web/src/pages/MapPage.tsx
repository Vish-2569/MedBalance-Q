import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '@/lib/api';
import type { Facility } from '@/types/domain';
import { stockHealthColor, facilityLabel } from '@/lib/utils';
import FacilityDrawer from '@/components/FacilityDrawer';
import DistrictSVG from '@/components/DistrictSVG';

const CENTER: [number, number] = [12.965, 77.605];

export default function MapPage() {
  const [selected, setSelected] = useState<Facility | null>(null);
  const [tilesOk, setTilesOk] = useState(true);

  const { data: facilities = [] } = useQuery({ queryKey: ['facilities'], queryFn: api.getFacilities });
  const { data: positions = [] } = useQuery({ queryKey: ['positions'], queryFn: () => api.getPositions() });
  const { data: planDemo } = useQuery({ queryKey: ['plan'], queryFn: api.getPlanDemo });
  const { data: clock } = useQuery({ queryKey: ['clock'], queryFn: api.getClock });

  const facMap = useMemo(() => new Map(facilities.map(f => [f.id, f])), [facilities]);
  const orders = planDemo?.orders ?? [];

  const arcs = useMemo(() =>
    orders.map(o => {
      const src = facMap.get(o.src_facility_id);
      const dst = facMap.get(o.dst_facility_id);
      if (!src || !dst) return null;
      return { src, dst, cold: o.temperature_req === 'cold_chain' };
    }).filter(Boolean) as { src: Facility; dst: Facility; cold: boolean }[],
    [orders, facMap],
  );

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 min-h-0">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">District Overview</h1>
        <span className="text-sm text-slate-500">{facilities.length} facilities &middot; {orders.length} active transfers</span>
      </div>

      <div className="flex-1 min-h-0 rounded-lg overflow-hidden border border-slate-200 shadow-sm">
        {tilesOk ? (
          <MapContainer center={CENTER} zoom={12} className="h-full w-full" scrollWheelZoom>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap'
              eventHandlers={{ tileerror: () => setTilesOk(false) }}
            />

            {arcs.map((a, i) => (
              <Polyline
                key={i}
                positions={[[a.src.lat, a.src.lon], [a.dst.lat, a.dst.lon]]}
                color={a.cold ? '#3b82f6' : '#0d9488'}
                weight={a.cold ? 3 : 2}
                dashArray={a.cold ? '8 4' : undefined}
                opacity={0.7}
              />
            ))}

            {facilities.map(f => {
              const facPos = positions.filter(p => p.facility_id === f.id);
              const color = stockHealthColor(facPos);
              return (
                <CircleMarker
                  key={f.id}
                  center={[f.lat, f.lon]}
                  radius={f.type === 'warehouse' ? 12 : 9}
                  fillColor={color}
                  color={color}
                  weight={2}
                  fillOpacity={0.35}
                  eventHandlers={{ click: () => setSelected(f) }}
                >
                  <Tooltip permanent direction="top" offset={[0, -10]}>
                    <span className="text-xs font-semibold">{f.id}</span>
                  </Tooltip>
                  <Popup>
                    <div className="text-sm">
                      <p className="font-semibold">{facilityLabel(f)}</p>
                      <p className="text-slate-500">{f.type} {f.cold_storage ? '❄' : ''}</p>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        ) : (
          <DistrictSVG
            facilities={facilities}
            positions={positions}
            orders={orders}
            onSelectFacility={setSelected}
          />
        )}
      </div>

      {selected && (
        <FacilityDrawer
          facility={selected}
          simDate={clock?.sim_date}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
