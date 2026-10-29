import { Routes, Route } from 'react-router-dom';
import TopBar from '@/components/TopBar';
import Sidebar from '@/components/Sidebar';
import { useSSEConnection } from '@/hooks/useSSE';
import MapPage from '@/pages/MapPage';
import IngestionPage from '@/pages/IngestionPage';
import PlanPage from '@/pages/PlanPage';
import BenchmarkPage from '@/pages/BenchmarkPage';
import ColdchainPage from '@/pages/ColdchainPage';
import ResultsPage from '@/pages/ResultsPage';
import AIHealthPage from '@/pages/AIHealthPage';
import ScenariosPage from '@/pages/ScenariosPage';

export default function App() {
  useSSEConnection();

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <TopBar />
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
          </Routes>
        </main>
      </div>
    </div>
  );
}
