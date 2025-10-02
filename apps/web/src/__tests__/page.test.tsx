import React from 'react';
import { render, screen } from '@testing-library/react';
import Page from '../app/page';

// Mock Next.js Image component
jest.mock('next/image', () => ({
  __esModule: true,
  default: (props: any) => {
    // eslint-disable-next-line @next/next/no-img-element
    return <img alt="" {...props} />;
  },
}));

describe('Home Page', () => {
  it('renders without crashing', () => {
    render(<Page />);
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('contains expected content structure', () => {
    const { container } = render(<Page />);
    const main = container.querySelector('main');
    expect(main).toBeInTheDocument();
  });
});
