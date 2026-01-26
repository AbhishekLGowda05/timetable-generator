import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LandingPage } from '../pages/LandingPage';

// Create a wrapper with necessary providers
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('LandingPage', () => {
  it('renders the welcome heading', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    
    expect(screen.getByText(/Timetable Generator/i)).toBeInTheDocument();
  });

  it('renders feature cards', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    
    // Use getAllByText since these texts may appear in multiple places (headings and descriptions)
    expect(screen.getAllByText(/Upload Your Data/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Configure Constraints/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Generate Timetable/i).length).toBeGreaterThan(0);
  });

  it('renders the get started button', () => {
    render(<LandingPage />, { wrapper: createWrapper() });
    
    // The "Get Started" button is rendered as a link (using asChild with Link)
    const link = screen.getByRole('link', { name: /Get Started/i });
    expect(link).toBeInTheDocument();
  });
});
