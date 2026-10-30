import { Routes, Route } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import TopBar from '@/components/TopBar';
import Sidebar from '@/components/Sidebar';
import CopilotPanel from '@/components/CopilotPanel';
import { useSSEConnection, useLiveEvents } from '@/hooks/useSSE';
import MapPage from '@/pages/MapPage';
import IngestionPage from '@/pages/IngestionPage';
import PlanPage from '@/pages/PlanPage';
import BenchmarkPage from '@/pages/BenchmarkPage';
import ColdchainPage from '@/pages/ColdchainPage';
import ResultsPage from '@/pages/ResultsPage';
import AIHealthPage from '@/pages/AIHealthPage';
import ScenariosPage from '@/pages/ScenariosPage';
import OrderDetailPage from '@/pages/OrderDetailPage';
import ScanPage from '@/pages/ScanPage';

function ExcursionBanner() {
  const events = useLiveEvents(50);
  const excursions = events.filter(e => e.type === 'coldchain.alert' && (e.data as Record<string, unknown>).severity === 'excursion');
  if (excursions.length === 0) return null;

  return (
    <div className="excursion-banner bg-red-600 text-white px-4 py-2 flex items-center gap-2 text-sm font-medium">
      <AlertTriangle className="w-4 h-4" />
      COLD CHAIN EXCURSION — {excursions.length} active alert{excursions.length > 1 ? 's' : ''}. Affected lots may be quarantined.
    </div>
  );
}

export default function App() {
  useSSEConnection();

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Routes>
        {/* Standalone scan page — no sidebar/navbar */}
        <Route path="/scan" element={<ScanPage />} />
        <Route path="/scan/:token" element={<ScanPage />} />

        {/* Main layout with sidebar */}
        <Route path="*" element={
          <>
            <TopBar />
            <ExcursionBanner />
            <div className="flex flex-1 min-h-0">
              <Sidebar />
              <main className="flex-1 flex flex-col min-h-0 overflow-hidden bg-slate-50">
                <Routes>
                  <Route path="/" element={<MapPage />} />
                  <Route path="/ingestion" element={<IngestionPage />} />
                  <Route path="/plan" element={<PlanPage />} />
                  <Route path="/benchmark" element={<BenchmarkPage />} />
                  <Route path="/coldchain" element={<ColdchainPage />} />
                  <Route path="/results" element={<ResultsPage />} />
                  <Route path="/ai-health" element={<AIHealthPage />} />
                  <Route path="/scenarios" element={<ScenariosPage />} />
                  <Route path="/orders/:id" element={<OrderDetailPage />} />
                </Routes>
              </main>
            </div>
            <CopilotPanel />
          </>
        } />
      </Routes>
    </div>
  );
}
