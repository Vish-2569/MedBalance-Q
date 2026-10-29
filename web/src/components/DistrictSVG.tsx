import type { Facility, Position } from '@/types/domain';
import { stockHealthColor, facilityLabel } from '@/lib/utils';

interface Props {
  facilities: Facility[];
  positions: Position[];
  orders?: { src_facility_id: string; dst_facility_id: string; temperature_req: string }[];
  onSelectFacility?: (f: Facility) => void;
}

const MIN_LAT = 12.88;
const MAX_LAT = 13.05;
const MIN_LON = 77.55;
const MAX_LON = 77.67;
const W = 600;
const H = 500;
const PAD = 40;

function project(lat: number, lon: number): [number, number] {
  const x = PAD + ((lon - MIN_LON) / (MAX_LON - MIN_LON)) * (W - 2 * PAD);
  const y = PAD + ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * (H - 2 * PAD);
  return [x, y];
}

export default function DistrictSVG({ facilities, positions, orders = [], onSelectFacility }: Props) {
  const facMap = new Map(facilities.map(f => [f.id, f]));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full bg-slate-50 rounded-lg border border-slate-200">
      <defs>
        <marker id="arrow-teal" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#0d9488" />
        </marker>
        <marker id="arrow-blue" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#3b82f6" />
        </marker>
      </defs>

      <rect x={PAD - 10} y={PAD - 10} width={W - 2 * PAD + 20} height={H - 2 * PAD + 20}
        fill="none" stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 4" rx="8" />

      {orders.map((o, i) => {
        const src = facMap.get(o.src_facility_id);
        const dst = facMap.get(o.dst_facility_id);
        if (!src || !dst) return null;
        const [x1, y1] = project(src.lat, src.lon);
        const [x2, y2] = project(dst.lat, dst.lon);
        const cold = o.temperature_req === 'cold_chain';
        return (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke={cold ? '#3b82f6' : '#0d9488'}
            strokeWidth={cold ? 2.5 : 1.5}
            strokeDasharray={cold ? '6 3' : 'none'}
            markerEnd={cold ? 'url(#arrow-blue)' : 'url(#arrow-teal)'}
            opacity={0.7}
          />
        );
      })}

      {facilities.map(f => {
        const [x, y] = project(f.lat, f.lon);
        const facPos = positions.filter(p => p.facility_id === f.id);
        const color = stockHealthColor(facPos);
        const r = f.type === 'warehouse' ? 18 : 14;

        return (
          <g key={f.id} className="cursor-pointer" onClick={() => onSelectFacility?.(f)}>
            <circle cx={x} cy={y} r={r + 4} fill={color} opacity={0.15} />
            <circle cx={x} cy={y} r={r} fill="white" stroke={color} strokeWidth={3} />
            <text x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle"
              className="text-[10px] font-bold fill-slate-700">{f.id}</text>
            <text x={x} y={y + r + 14} textAnchor="middle"
              className="text-[10px] fill-slate-500 font-medium">{facilityLabel(f)}</text>
          </g>
        );
      })}

      <g transform={`translate(${W - 160}, ${H - 80})`}>
        <rect width="140" height="70" fill="white" stroke="#e2e8f0" rx="6" />
        <circle cx={16} cy={16} r={6} fill="#14b8a6" />
        <text x={28} y={20} className="text-[10px] fill-slate-600">Healthy</text>
        <circle cx={16} cy={34} r={6} fill="#f59e0b" />
        <text x={28} y={38} className="text-[10px] fill-slate-600">Low stock</text>
        <circle cx={16} cy={52} r={6} fill="#ef4444" />
        <text x={28} y={56} className="text-[10px] fill-slate-600">Stockout</text>
        <line x1={85} y1={16} x2={110} y2={16} stroke="#0d9488" strokeWidth={1.5} />
        <text x={115} y={20} className="text-[10px] fill-slate-600">Transfer</text>
        <line x1={85} y1={34} x2={110} y2={34} stroke="#3b82f6" strokeWidth={2} strokeDasharray="4 2" />
        <text x={115} y={38} className="text-[10px] fill-slate-600">Cold</text>
      </g>
    </svg>
  );
}
