import React from 'react';
import { render, screen } from '@testing-library/react';
import Header from '../Header';

// Mock Next.js router
jest.mock('next/link', () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => {
    return <a href={href}>{children}</a>;
  };
});

describe('Header Component', () => {
  it('renders the application title', () => {
    render(<Header />);
    expect(screen.getByText('A Fine Wine Dynasty')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    render(<Header />);
    expect(screen.getByText('Prospects')).toBeInTheDocument();
    expect(screen.getByText('Analysis')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('has correct link hrefs', () => {
    render(<Header />);
    expect(screen.getByText('A Fine Wine Dynasty').closest('a')).toHaveAttribute('href', '/');
    expect(screen.getByText('Prospects').closest('a')).toHaveAttribute('href', '/prospects');
    expect(screen.getByText('Analysis').closest('a')).toHaveAttribute('href', '/analysis');
    expect(screen.getByText('Dashboard').closest('a')).toHaveAttribute('href', '/dashboard');
  });

  it('applies correct CSS classes', () => {
    const { container } = render(<Header />);
    const header = container.querySelector('header');
    expect(header).toHaveClass('bg-blue-600', 'text-white', 'shadow-lg');
  });
});