import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MapPage from './MapPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  CircleMarker: ({ children }: { children: React.ReactNode }) => <div data-testid="circle-marker">{children}</div>,
  Polyline: () => <div data-testid="polyline" />,
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/lib/api', () => ({
  api: {
    getFacilities: () => Promise.resolve(fixtures.facilities),
    getPositions: () => Promise.resolve(fixtures.positions),
    getPlanDemo: () => Promise.resolve(fixtures.planDemo),
    getClock: () => Promise.resolve(fixtures.clock),
  },
}));

describe('MapPage', () => {
  it('renders the page title', async () => {
    render(<MapPage />, { wrapper: createWrapper(['/']) });
    await waitFor(() => {
      expect(screen.getByText('District Overview')).toBeInTheDocument();
    });
  });

  it('shows facility count and transfer count', async () => {
    render(<MapPage />, { wrapper: createWrapper(['/']) });
    await waitFor(() => {
      expect(screen.getByText(/5 facilities/)).toBeInTheDocument();
      expect(screen.getByText(/6 planned transfers/)).toBeInTheDocument();
    });
  });

  it('renders the map container', async () => {
    render(<MapPage />, { wrapper: createWrapper(['/']) });
    await waitFor(() => {
      expect(screen.getByTestId('map-container')).toBeInTheDocument();
    });
  });

  it('renders circle markers for each facility', async () => {
    render(<MapPage />, { wrapper: createWrapper(['/']) });
    await waitFor(() => {
      const markers = screen.getAllByTestId('circle-marker');
      expect(markers).toHaveLength(5);
    });
  });

  it('shows facility IDs in tooltips', async () => {
    render(<MapPage />, { wrapper: createWrapper(['/']) });
    await waitFor(() => {
      expect(screen.getByText('W0')).toBeInTheDocument();
      expect(screen.getByText('H1')).toBeInTheDocument();
      expect(screen.getByText('H2')).toBeInTheDocument();
    });
  });
});
