import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PlanPage from './PlanPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('@/lib/api', () => ({
  api: {
    getPlanDemo: () => Promise.resolve(fixtures.planDemo),
    getFacilities: () => Promise.resolve(fixtures.facilities),
    getBenchmark: () => Promise.resolve(fixtures.benchmark),
    runPlan: () => Promise.resolve(fixtures.planDemo),
  },
}));

describe('PlanPage', () => {
  it('renders the page title', async () => {
    render(<PlanPage />, { wrapper: createWrapper(['/plan']) });
    await waitFor(() => {
      expect(screen.getByText('Redistribution Plan')).toBeInTheDocument();
    });
  });

  it('shows solver tier badge', async () => {
    render(<PlanPage />, { wrapper: createWrapper(['/plan']) });
    await waitFor(() => {
      expect(screen.getByText('QpiAI Local')).toBeInTheDocument();
    });
  });

  it('shows violations badge with repaired count', async () => {
    render(<PlanPage />, { wrapper: createWrapper(['/plan']) });
    await waitFor(() => {
      expect(screen.getByText(/Violations: 0/)).toBeInTheDocument();
      expect(screen.getByText(/2 repaired/)).toBeInTheDocument();
    });
  });

  it('shows KPI cards with plan data', async () => {
    render(<PlanPage />, { wrapper: createWrapper(['/plan']) });
    await waitFor(() => {
      expect(screen.getByText('Transfers')).toBeInTheDocument();
      expect(screen.getByText('6')).toBeInTheDocument();
      expect(screen.getByText('Shortage Reduction')).toBeInTheDocument();
    });
  });

  it('shows pipeline stages', async () => {
    render(<PlanPage />, { wrapper: createWrapper(['/plan']) });
    await waitFor(() => {
      expect(screen.getByText('Snapshot')).toBeInTheDocument();
      expect(screen.getByText('Feasibility')).toBeInTheDocument();
      expect(screen.getByText('Validate')).toBeInTheDocument();
    });
  });

  it('renders benchmark table with 5 rows', async () => {
    render(<PlanPage />, { wrapper: createWrapper(['/plan']) });
    await waitFor(() => {
      expect(screen.getByText('Solver Benchmark')).toBeInTheDocument();
      expect(screen.getByText('no-transfer')).toBeInTheDocument();
      expect(screen.getByText('greedy-phone-call')).toBeInTheDocument();
      expect(screen.getByText('greedy-f4')).toBeInTheDocument();
      expect(screen.getByText('qubo (qpiai-local)')).toBeInTheDocument();
      expect(screen.getByText('milp (OPTIMAL)')).toBeInTheDocument();
    });
  });

  it('renders Run Optimizer button', async () => {
    render(<PlanPage />, { wrapper: createWrapper(['/plan']) });
    await waitFor(() => {
      expect(screen.getByText('Run Optimizer')).toBeInTheDocument();
    });
  });
});
