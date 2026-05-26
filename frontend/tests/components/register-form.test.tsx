/**
 * Component Tests for RegisterForm
 *
 * Tests the business/personal registration form component.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RegisterForm } from '@/components/auth/register-form';
import '@testing-library/jest-dom';

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
}));

describe('RegisterForm', () => {
  it('should render personal and business account options', () => {
    render(<RegisterForm />);

    expect(screen.getByLabelText(/Personal/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Business/i)).toBeInTheDocument();
  });

  it('should default to personal account type', () => {
    render(<RegisterForm />);

    const personalRadio = screen.getByLabelText(/Personal/i);
    expect(personalRadio).toBeChecked();
  });

  it('should show business fields when business is selected', async () => {
    render(<RegisterForm />);

    const businessRadio = screen.getByLabelText(/Business/i);
    fireEvent.click(businessRadio);

    await waitFor(() => {
      expect(screen.getByLabelText(/Organization Name/i)).toBeVisible();
      expect(screen.getByLabelText(/Business Email/i)).toBeVisible();
      expect(screen.getByLabelText(/Business Phone/i)).toBeVisible();
    });
  });

  it('should hide business fields when personal is selected', async () => {
    render(<RegisterForm />);

    // Select business first
    const businessRadio = screen.getByLabelText(/Business/i);
    fireEvent.click(businessRadio);

    await waitFor(() => {
      expect(screen.getByLabelText(/Organization Name/i)).toBeVisible();
    });

    // Switch back to personal
    const personalRadio = screen.getByLabelText(/Personal/i);
    fireEvent.click(personalRadio);

    await waitFor(() => {
      expect(screen.queryByLabelText(/Organization Name/i)).not.toBeInTheDocument();
    });
  });

  it('should validate required fields', async () => {
    render(<RegisterForm />);

    // Try to submit without filling fields
    const submitButton = screen.getByRole('button', { name: /Register/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Full Name.*required/i)).toBeVisible();
      expect(screen.getByText(/Email.*required/i)).toBeVisible();
      expect(screen.getByText(/Password.*required/i)).toBeVisible();
    });
  });

  it('should validate email format', async () => {
    render(<RegisterForm />);

    const emailInput = screen.getByLabelText(/^Email/i);
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.blur(emailInput);

    await waitFor(() => {
      expect(screen.getByText(/valid email/i)).toBeVisible();
    });
  });

  it('should validate password strength', async () => {
    render(<RegisterForm />);

    const passwordInput = screen.getByLabelText(/Password/i);

    // Test weak password
    fireEvent.change(passwordInput, { target: { value: 'weak' } });
    fireEvent.blur(passwordInput);

    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeVisible();
    });
  });

  it('should show password strength indicator', async () => {
    render(<RegisterForm />);

    const passwordInput = screen.getByLabelText(/Password/i);

    // Weak password
    fireEvent.change(passwordInput, { target: { value: 'weak1' } });
    await waitFor(() => {
      expect(screen.getByText(/Weak/i)).toBeVisible();
    });

    // Medium password
    fireEvent.change(passwordInput, { target: { value: 'Medium123' } });
    await waitFor(() => {
      expect(screen.getByText(/Medium/i)).toBeVisible();
    });

    // Strong password
    fireEvent.change(passwordInput, { target: { value: 'Strong123!@#' } });
    await waitFor(() => {
      expect(screen.getByText(/Strong/i)).toBeVisible();
    });
  });

  it('should validate business email when business is selected', async () => {
    render(<RegisterForm />);

    const businessRadio = screen.getByLabelText(/Business/i);
    fireEvent.click(businessRadio);

    await waitFor(() => {
      const businessEmailInput = screen.getByLabelText(/Business Email/i);
      fireEvent.change(businessEmailInput, { target: { value: 'invalid' } });
      fireEvent.blur(businessEmailInput);
    });

    await waitFor(() => {
      expect(screen.getByText(/valid.*email/i)).toBeVisible();
    });
  });

  it('should validate phone number format', async () => {
    render(<RegisterForm />);

    const businessRadio = screen.getByLabelText(/Business/i);
    fireEvent.click(businessRadio);

    await waitFor(() => {
      const phoneInput = screen.getByLabelText(/Business Phone/i);
      fireEvent.change(phoneInput, { target: { value: 'abc' } });
      fireEvent.blur(phoneInput);
    });

    await waitFor(() => {
      expect(screen.getByText(/valid phone/i)).toBeVisible();
    });
  });

  it('should submit personal account registration', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
    global.fetch = mockFetch;

    render(<RegisterForm />);

    // Fill personal account form
    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'John Doe' },
    });
    fireEvent.change(screen.getByLabelText(/^Email/i), {
      target: { value: 'john@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'SecurePassword123!' },
    });

    // Submit form
    fireEvent.click(screen.getByRole('button', { name: /Register/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/registrations',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('john@example.com'),
        })
      );
    });
  });

  it('should submit business account registration', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ registration_id: 'reg-123', status: 'pending_approval' }),
    });
    global.fetch = mockFetch;

    render(<RegisterForm />);

    // Select business
    fireEvent.click(screen.getByLabelText(/Business/i));

    await waitFor(() => {
      // Fill business form
      fireEvent.change(screen.getByLabelText(/Organization Name/i), {
        target: { value: 'Acme Corp' },
      });
      fireEvent.change(screen.getByLabelText(/Business Email/i), {
        target: { value: 'contact@acme.com' },
      });
      fireEvent.change(screen.getByLabelText(/Business Phone/i), {
        target: { value: '+1-555-0123' },
      });
      fireEvent.change(screen.getByLabelText(/Full Name/i), {
        target: { value: 'Jane Doe' },
      });
      fireEvent.change(screen.getByLabelText(/^Email/i), {
        target: { value: 'jane@acme.com' },
      });
      fireEvent.change(screen.getByLabelText(/Password/i), {
        target: { value: 'SecurePassword123!' },
      });
    });

    // Submit form
    fireEvent.click(screen.getByRole('button', { name: /Register/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/registrations',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Acme Corp'),
        })
      );
    });
  });

  it('should show loading state during submission', async () => {
    const mockFetch = jest.fn(
      () =>
        new Promise(resolve =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => ({ success: true }),
              }),
            1000
          )
        )
    );
    global.fetch = mockFetch;

    render(<RegisterForm />);

    // Fill and submit form
    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'John Doe' },
    });
    fireEvent.change(screen.getByLabelText(/^Email/i), {
      target: { value: 'john@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'SecurePassword123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Register/i }));

    // Should show loading state
    await waitFor(() => {
      expect(screen.getByText(/Registering.../i)).toBeVisible();
    });

    // Button should be disabled
    expect(screen.getByRole('button', { name: /Registering/i })).toBeDisabled();
  });

  it('should display error message on registration failure', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'Email already registered' }),
    });
    global.fetch = mockFetch;

    render(<RegisterForm />);

    // Fill and submit form
    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'John Doe' },
    });
    fireEvent.change(screen.getByLabelText(/^Email/i), {
      target: { value: 'existing@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'SecurePassword123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Register/i }));

    await waitFor(() => {
      expect(screen.getByText(/Email already registered/i)).toBeVisible();
    });
  });

  it('should have link to login page', () => {
    render(<RegisterForm />);

    const loginLink = screen.getByRole('link', { name: /Sign In/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });

  it('should show terms and conditions checkbox', () => {
    render(<RegisterForm />);

    expect(screen.getByLabelText(/agree.*terms/i)).toBeInTheDocument();
  });

  it('should require terms acceptance before submission', async () => {
    render(<RegisterForm />);

    // Fill form but don't check terms
    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'John Doe' },
    });
    fireEvent.change(screen.getByLabelText(/^Email/i), {
      target: { value: 'john@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'SecurePassword123!' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Register/i }));

    await waitFor(() => {
      expect(screen.getByText(/must accept.*terms/i)).toBeVisible();
    });
  });

  it('should be accessible', () => {
    const { container } = render(<RegisterForm />);

    // All form fields should have labels
    const inputs = container.querySelectorAll('input');
    inputs.forEach(input => {
      const label = container.querySelector(`label[for="${input.id}"]`);
      expect(label).toBeInTheDocument();
    });

    // Form should have proper ARIA attributes
    const form = container.querySelector('form');
    expect(form).toHaveAttribute('aria-label');
  });
});
