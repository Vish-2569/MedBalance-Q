import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import BenchmarkPage from './BenchmarkPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  Cell: () => <div />,
}));

vi.mock('@/lib/api', () => ({
  api: {
    getPlanDemo: () => Promise.resolve(fixtures.planDemo),
    getBenchmark: () => Promise.resolve(fixtures.benchmark),
  },
}));

describe('BenchmarkPage', () => {
  it('renders the page title', async () => {
    render(<BenchmarkPage />, { wrapper: createWrapper(['/benchmark']) });
    await waitFor(() => {
      expect(screen.getByText('Benchmark Comparison')).toBeInTheDocument();
    });
  });

  it('shows zoning comparison section', async () => {
    render(<BenchmarkPage />, { wrapper: createWrapper(['/benchmark']) });
    await waitFor(() => {
      expect(screen.getByText('Zoning Comparison')).toBeInTheDocument();
    });
  });

  it('renders benchmark table with all solver rows', async () => {
    render(<BenchmarkPage />, { wrapper: createWrapper(['/benchmark']) });
    await waitFor(() => {
      expect(screen.getByText('no-transfer')).toBeInTheDocument();
      expect(screen.getByText('greedy-phone-call')).toBeInTheDocument();
      expect(screen.getByText('greedy-f4')).toBeInTheDocument();
      expect(screen.getByText('qubo (qpiai-local)')).toBeInTheDocument();
      expect(screen.getByText('milp (OPTIMAL)')).toBeInTheDocument();
    });
  });

  it('shows maxcut zoning card with tier', async () => {
    render(<BenchmarkPage />, { wrapper: createWrapper(['/benchmark']) });
    await waitFor(() => {
      expect(screen.getByText('QAOA Max-Cut')).toBeInTheDocument();
      expect(screen.getByText('exact-brute-force')).toBeInTheDocument();
    });
  });

  it('shows k-means and exact brute-force zoning cards', async () => {
    render(<BenchmarkPage />, { wrapper: createWrapper(['/benchmark']) });
    await waitFor(() => {
      expect(screen.getByText('k-means')).toBeInTheDocument();
      expect(screen.getByText('Exact Brute-Force')).toBeInTheDocument();
    });
  });

  it('renders bar charts', async () => {
    render(<BenchmarkPage />, { wrapper: createWrapper(['/benchmark']) });
    await waitFor(() => {
      const charts = screen.getAllByTestId('bar-chart');
      expect(charts).toHaveLength(2);
    });
  });
});
