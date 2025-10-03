import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InAppFAQ } from '../InAppFAQ';

describe('InAppFAQ Component', () => {
  it('should render the help button initially', () => {
    render(<InAppFAQ />);

    const helpButton = screen.getByRole('button', { name: /open faq/i });
    expect(helpButton).toBeInTheDocument();
    expect(screen.getByText('Help')).toBeInTheDocument();
  });

  it('should open FAQ panel when help button is clicked', () => {
    render(<InAppFAQ />);

    const helpButton = screen.getByRole('button', { name: /open faq/i });
    fireEvent.click(helpButton);

    expect(screen.getByText('Frequently Asked Questions')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search FAQ...')).toBeInTheDocument();
  });

  it('should close FAQ panel when close button is clicked', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    const helpButton = screen.getByRole('button', { name: /open faq/i });
    fireEvent.click(helpButton);

    // Close the FAQ
    const closeButton = screen.getByRole('button', { name: /close faq/i });
    fireEvent.click(closeButton);

    // Should show the help button again
    expect(
      screen.getByRole('button', { name: /open faq/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByText('Frequently Asked Questions')
    ).not.toBeInTheDocument();
  });

  it('should display all FAQ items by default', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    // Check for some FAQ questions
    expect(
      screen.getByText('How do I upgrade my subscription?')
    ).toBeInTheDocument();
    expect(
      screen.getByText('What data sources do you use for prospect information?')
    ).toBeInTheDocument();
    expect(
      screen.getByText('How often are rankings updated?')
    ).toBeInTheDocument();
  });

  it('should filter FAQ items by search query', async () => {
    const user = userEvent.setup();
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    const searchInput = screen.getByPlaceholderText('Search FAQ...');

    // Search for "subscription"
    await user.type(searchInput, 'subscription');

    // Should show subscription-related questions
    expect(
      screen.getByText('How do I upgrade my subscription?')
    ).toBeInTheDocument();

    // Should not show unrelated questions
    expect(
      screen.queryByText('How often are rankings updated?')
    ).not.toBeInTheDocument();
  });

  it('should filter FAQ items by category', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    // Click on "Billing" category
    const billingButton = screen.getByRole('button', { name: 'Billing' });
    fireEvent.click(billingButton);

    // Should show billing questions
    expect(
      screen.getByText('How do I upgrade my subscription?')
    ).toBeInTheDocument();

    // Should not show non-billing questions
    expect(
      screen.queryByText('How often are rankings updated?')
    ).not.toBeInTheDocument();
  });

  it('should reset category filter when "All" is clicked', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    // Filter by category
    fireEvent.click(screen.getByRole('button', { name: 'Billing' }));
    expect(
      screen.queryByText('How often are rankings updated?')
    ).not.toBeInTheDocument();

    // Click "All"
    fireEvent.click(screen.getByRole('button', { name: 'All' }));

    // Should show all questions again
    expect(
      screen.getByText('How do I upgrade my subscription?')
    ).toBeInTheDocument();
    expect(
      screen.getByText('How often are rankings updated?')
    ).toBeInTheDocument();
  });

  it('should expand and collapse FAQ items', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    const firstQuestion = screen.getByText('How do I upgrade my subscription?');

    // Answer should not be visible initially
    expect(
      screen.queryByText(/Navigate to Account Settings/)
    ).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(firstQuestion);

    // Answer should now be visible
    expect(
      screen.getByText(/Navigate to Account Settings/)
    ).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(firstQuestion);

    // Answer should be hidden again
    expect(
      screen.queryByText(/Navigate to Account Settings/)
    ).not.toBeInTheDocument();
  });

  it('should display tags for expanded items', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    const firstQuestion = screen.getByText('How do I upgrade my subscription?');

    // Expand the question
    fireEvent.click(firstQuestion);

    // Should show tags
    expect(screen.getByText('subscription')).toBeInTheDocument();
    expect(screen.getByText('upgrade')).toBeInTheDocument();
    expect(screen.getByText('payment')).toBeInTheDocument();
  });

  it('should show no results message when search yields no results', async () => {
    const user = userEvent.setup();
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    const searchInput = screen.getByPlaceholderText('Search FAQ...');

    // Search for something that doesn't exist
    await user.type(searchInput, 'xyz123nonexistent');

    expect(
      screen.getByText('No questions found. Try adjusting your search.')
    ).toBeInTheDocument();
  });

  it('should display contact support link', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    const supportLink = screen.getByRole('link', { name: /contact support/i });
    expect(supportLink).toBeInTheDocument();
    expect(supportLink).toHaveAttribute(
      'href',
      'mailto:support@afinewinedynasty.com'
    );
  });

  it('should highlight selected category', () => {
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    const billingButton = screen.getByRole('button', { name: 'Billing' });
    const allButton = screen.getByRole('button', { name: 'All' });

    // Initially "All" should be selected (blue background)
    expect(allButton).toHaveClass('bg-blue-600', 'text-white');
    expect(billingButton).toHaveClass('bg-gray-100', 'text-gray-700');

    // Click Billing
    fireEvent.click(billingButton);

    // Now Billing should be selected
    expect(billingButton).toHaveClass('bg-blue-600', 'text-white');
    expect(allButton).toHaveClass('bg-gray-100', 'text-gray-700');
  });

  it('should maintain expanded state when filtering', async () => {
    const user = userEvent.setup();
    render(<InAppFAQ />);

    // Open the FAQ
    fireEvent.click(screen.getByRole('button', { name: /open faq/i }));

    // Expand a question
    const question = screen.getByText('How do I upgrade my subscription?');
    fireEvent.click(question);
    expect(
      screen.getByText(/Navigate to Account Settings/)
    ).toBeInTheDocument();

    // Search for something that still includes this question
    const searchInput = screen.getByPlaceholderText('Search FAQ...');
    await user.type(searchInput, 'upgrade');

    // The question should still be expanded
    expect(
      screen.getByText(/Navigate to Account Settings/)
    ).toBeInTheDocument();
  });
});
