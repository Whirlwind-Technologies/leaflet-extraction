/**
 * Component Tests for OrganizationSwitcher
 *
 * Tests the organization switcher dropdown component.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { OrganizationSwitcher } from '@/components/dashboard/organization-switcher';
import '@testing-library/jest-dom';

describe('OrganizationSwitcher', () => {
  const mockOrganizations = [
    {
      id: 'org-1',
      name: 'Test Organization 1',
      role: 'owner',
      member_count: 5,
      status: 'active',
    },
    {
      id: 'org-2',
      name: 'Test Organization 2',
      role: 'admin',
      member_count: 3,
      status: 'active',
    },
    {
      id: 'org-3',
      name: 'Test Organization 3',
      role: 'member',
      member_count: 10,
      status: 'active',
    },
  ];

  const mockCurrentOrganization = mockOrganizations[0];
  const mockOnSwitch = jest.fn();

  beforeEach(() => {
    mockOnSwitch.mockClear();
  });

  it('should render current organization name', () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    expect(screen.getByText('Test Organization 1')).toBeInTheDocument();
  });

  it('should display dropdown when clicked', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByText('Test Organization 2')).toBeVisible();
      expect(screen.getByText('Test Organization 3')).toBeVisible();
    });
  });

  it('should display role badges for each organization', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByText('owner')).toBeInTheDocument();
      expect(screen.getByText('admin')).toBeInTheDocument();
      expect(screen.getByText('member')).toBeInTheDocument();
    });
  });

  it('should call onSwitch when organization is selected', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      const org2Option = screen.getByText('Test Organization 2');
      fireEvent.click(org2Option);
    });

    expect(mockOnSwitch).toHaveBeenCalledWith('org-2');
  });

  it('should highlight current organization', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      const org1Item = screen.getByText('Test Organization 1').closest('div');
      expect(org1Item).toHaveClass(/selected|active/i);
    });
  });

  it('should show member count in dropdown items', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByText(/5 members/i)).toBeInTheDocument();
      expect(screen.getByText(/3 members/i)).toBeInTheDocument();
      expect(screen.getByText(/10 members/i)).toBeInTheDocument();
    });
  });

  it('should have link to organization settings', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      const settingsLink = screen.getByRole('link', { name: /manage/i });
      expect(settingsLink).toHaveAttribute('href', '/settings/organization');
    });
  });

  it('should close dropdown after selection', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      const org2Option = screen.getByText('Test Organization 2');
      fireEvent.click(org2Option);
    });

    await waitFor(() => {
      expect(screen.queryByText('Test Organization 3')).not.toBeVisible();
    });
  });

  it('should render with keyboard navigation support', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');

    // Open with Enter key
    fireEvent.keyDown(trigger, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('Test Organization 2')).toBeVisible();
    });

    // Navigate with arrow keys
    fireEvent.keyDown(screen.getByText('Test Organization 2'), {
      key: 'ArrowDown',
      code: 'ArrowDown',
    });

    // Select with Enter
    fireEvent.keyDown(screen.getByText('Test Organization 3'), {
      key: 'Enter',
      code: 'Enter',
    });

    expect(mockOnSwitch).toHaveBeenCalledWith('org-3');
  });

  it('should render different badge colors for different roles', async () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    await waitFor(() => {
      const ownerBadge = screen.getByText('owner');
      const adminBadge = screen.getByText('admin');
      const memberBadge = screen.getByText('member');

      // Owner should have blue/purple badge
      expect(ownerBadge.closest('span')).toHaveClass(/blue|purple/i);

      // Admin should have green badge
      expect(adminBadge.closest('span')).toHaveClass(/green/i);

      // Member should have gray badge
      expect(memberBadge.closest('span')).toHaveClass(/gray|slate/i);
    });
  });

  it('should handle empty organizations list', () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={[mockCurrentOrganization]}
        onSwitch={mockOnSwitch}
      />
    );

    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    // Should only show current organization
    expect(screen.getAllByText('Test Organization 1')).toHaveLength(2); // In trigger and dropdown
  });

  it('should be accessible', () => {
    render(
      <OrganizationSwitcher
        currentOrganization={mockCurrentOrganization}
        organizations={mockOrganizations}
        onSwitch={mockOnSwitch}
      />
    );

    // Should have proper ARIA attributes
    const trigger = screen.getByRole('button');
    expect(trigger).toHaveAttribute('aria-expanded');
    expect(trigger).toHaveAttribute('aria-haspopup');
  });
});
