import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Loader2, Info, HelpCircle, MousePointer, Warehouse, Building2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Facility, TransferOrder } from '@/types/domain';
import { stockHealthColor, facilityLabel } from '@/lib/utils';
import FacilityDrawer from '@/components/FacilityDrawer';
import DistrictSVG from '@/components/DistrictSVG';

const CENTER: [number, number] = [12.965, 77.605];
const EMPTY_ORDERS: TransferOrder[] = [];

export default function MapPage() {
  const [selected, setSelected] = useState<Facility | null>(null);
  const [tilesOk, setTilesOk] = useState(true);
  const [showGuide, setShowGuide] = useState(true);

  const { data: facilities = [], isLoading } = useQuery({ queryKey: ['facilities'], queryFn: api.getFacilities });
  const { data: positions = [], isLoading: positionsLoading, error: positionsError } = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.getPositions(),
  });
  const { data: planDemo, isLoading: planLoading, error: planError } = useQuery({
    queryKey: ['planDemo'],
    queryFn: api.getPlanDemo,
  });
  const { data: clock } = useQuery({ queryKey: ['clock'], queryFn: api.getClock });

  const facMap = useMemo(() => new Map(facilities.map(f => [f.id, f])), [facilities]);
  const orders = planDemo?.orders ?? EMPTY_ORDERS;

  const arcs = useMemo(() =>
    orders.map(o => {
      const src = facMap.get(o.src_facility_id);
      const dst = facMap.get(o.dst_facility_id);
      if (!src || !dst) return null;
      return { src, dst, cold: o.temperature_req === 'cold_chain' };
    }).filter(Boolean) as { src: Facility; dst: Facility; cold: boolean }[],
    [orders, facMap],
  );

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Loading district facilities and inventory data...</p>
      </div>
    );
  }

  if (facilities.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-500 p-8">
        <Building2 className="w-10 h-10" />
        <p className="text-sm font-medium">No facilities found</p>
        <p className="text-xs text-center max-w-sm">
          The system has no registered facilities yet. Make sure the backend services are running
          and the database has been seeded with facility data.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col p-4 gap-3 min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">District Overview</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Geographic view of all facilities in the district. Colors indicate stock health — click any facility to see its inventory.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm text-slate-500">
            {facilities.length} facilities &middot; {planError ? 'Transfers unavailable' : planLoading ? 'Loading transfers…' : `${orders.length} planned transfers`}
          </span>
          <button
            onClick={() => setShowGuide(g => !g)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            {showGuide ? 'Hide Guide' : 'Show Guide'}
          </button>
        </div>
      </div>

      {/* Getting Started Guide */}
      {showGuide && (
        <div className="bg-gradient-to-r from-sky-50 to-indigo-50 rounded-xl border border-sky-200 p-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-sky-100 flex items-center justify-center shrink-0 mt-0.5">
              <Info className="w-4 h-4 text-sky-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-slate-800 text-sm mb-1.5">How to Read This Map</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-slate-600">
                <div className="flex items-start gap-2">
                  <MousePointer className="w-3.5 h-3.5 text-teal-600 shrink-0 mt-0.5" />
                  <span><strong>Click any facility marker</strong> to open its inventory drawer showing stock levels, shortages, and lot details</span>
                </div>
                <div className="flex items-start gap-2">
                  <Warehouse className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
                  <span><strong>Larger markers</strong> = warehouses (supply hubs), <strong>smaller markers</strong> = hospitals (consumption points)</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-3.5 h-3.5 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-teal-500" />
                  </span>
                  <span><strong>Marker color</strong> = stock health: green (healthy), amber (some shortages), red (critical shortages or stockouts)</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-3.5 h-3.5 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="w-3 h-0.5 bg-teal-600 rounded" />
                  </span>
                  <span><strong>Lines between facilities</strong> = planned medicine transfers. Solid teal = ambient, dashed blue = cold chain</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Errors */}
      {(planError || (positionsError && !positionsLoading)) && (
        <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {planError && <p>Could not load planned transfers: {planError.message}</p>}
          {positionsError && <p>Could not load inventory positions: {positionsError.message}</p>}
        </div>
      )}

      {/* Legend Bar */}
      <div className="flex items-center gap-4 flex-wrap text-xs text-slate-600 px-1">
        <span className="text-slate-400 font-medium uppercase tracking-wide">Legend:</span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-[#10b981] opacity-80" />
          Healthy
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-[#f59e0b] opacity-80" />
          Low Stock
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-[#ef4444] opacity-80" />
          Critical
        </span>
        <span className="w-px h-4 bg-slate-300" />
        <span className="flex items-center gap-1.5">
          <span className="w-5 h-0.5 bg-teal-600 rounded" />
          Ambient Transfer
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="20" height="2" className="shrink-0">
            <line x1="0" y1="1" x2="20" y2="1" stroke="#3b82f6" strokeWidth="2" strokeDasharray="4 2" />
          </svg>
          Cold Chain Transfer
        </span>
        <span className="w-px h-4 bg-slate-300" />
        <span className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded-full border-2 border-slate-400 opacity-60" />
          Hospital
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-4.5 h-4.5 rounded-full border-2 border-slate-400 opacity-60" />
          Warehouse
        </span>
      </div>

      {/* Map */}
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
