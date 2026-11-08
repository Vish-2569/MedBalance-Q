import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ScenariosPage from './ScenariosPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('@/lib/api', () => ({
  api: {
    getScenarios: () => Promise.resolve(fixtures.scenarios),
    getSignals: () => Promise.resolve(fixtures.signals),
    getClock: () => Promise.resolve(fixtures.clock),
    startClock: () => Promise.resolve({ ...fixtures.clock, running: true }),
    pauseClock: () => Promise.resolve({ ...fixtures.clock, running: false }),
    setSpeed: (s: number) => Promise.resolve({ ...fixtures.clock, speed: s }),
    activateScenario: (name: string) => Promise.resolve({ activated: name }),
    resetSim: () => Promise.resolve({ seed: 42, sim_date: fixtures.clock.sim_date }),
  },
}));

describe('ScenariosPage', () => {
  it('renders the page title', async () => {
    render(<ScenariosPage />, { wrapper: createWrapper(['/scenarios']) });
    await waitFor(() => {
      expect(screen.getByText('Scenario Console')).toBeInTheDocument();
    });
  });

  it('shows simulation clock with date and speed', async () => {
    render(<ScenariosPage />, { wrapper: createWrapper(['/scenarios']) });
    await waitFor(() => {
      expect(screen.getByText('2026-11-01')).toBeInTheDocument();
      expect(screen.getByText('Day 0')).toBeInTheDocument();
    });
  });

  it('shows active scenario with Active badge', async () => {
    render(<ScenariosPage />, { wrapper: createWrapper(['/scenarios']) });
    await waitFor(() => {
      expect(screen.getByText('Active Scenarios')).toBeInTheDocument();
      expect(screen.getByText('baseline')).toBeInTheDocument();
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });

  it('shows available scenarios with Activate buttons', async () => {
    render(<ScenariosPage />, { wrapper: createWrapper(['/scenarios']) });
    await waitFor(() => {
      expect(screen.getByText('Available Scenarios')).toBeInTheDocument();
      expect(screen.getByText('dengue outbreak')).toBeInTheDocument();
      const activateButtons = screen.getAllByText('Activate');
      expect(activateButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows recent signals section', async () => {
    render(<ScenariosPage />, { wrapper: createWrapper(['/scenarios']) });
    await waitFor(() => {
      const headings = screen.getAllByText('Recent Signals');
      expect(headings.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Disease Outbreak')).toBeInTheDocument();
    });
  });

  it('shows Reset button and seed input', async () => {
    render(<ScenariosPage />, { wrapper: createWrapper(['/scenarios']) });
    await waitFor(() => {
      expect(screen.getByText('Reset All')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('seed')).toBeInTheDocument();
    });
  });
});
