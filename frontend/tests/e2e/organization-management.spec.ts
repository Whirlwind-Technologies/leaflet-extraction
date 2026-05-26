import { test, expect } from '@playwright/test';

/**
 * Organization Management E2E Tests
 *
 * Tests organization switching, member management, and invitation workflow.
 */

test.describe('Organization Switcher', () => {
  test.beforeEach(async ({ page }) => {
    // Login as user with multiple organizations
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('multiorg@example.com');
    await page.getByLabel(/Password/i).fill('MultiOrgPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('should display current organization in header', async ({ page }) => {
    // Check organization switcher is visible
    await expect(page.locator('[data-testid="org-switcher"]')).toBeVisible();

    // Should show organization name
    await expect(page.getByText(/Test Organization/i)).toBeVisible();
  });

  test('should switch between organizations', async ({ page }) => {
    // Open organization switcher
    await page.locator('[data-testid="org-switcher"]').click();

    // Should show list of organizations
    await expect(page.getByText(/Test Organization 2/i)).toBeVisible();

    // Switch to second organization
    await page.getByText(/Test Organization 2/i).click();

    // Should reload with new organization context
    await expect(page.getByText(/Test Organization 2/i)).toBeVisible();

    // Data should be filtered to new organization
    await page.goto('/dashboard/leaflets');
    // Leaflets list should be different
  });

  test('should show role badges in organization list', async ({ page }) => {
    await page.locator('[data-testid="org-switcher"]').click();

    // Should show role badges
    await expect(page.getByText(/Admin/i)).toBeVisible();
    await expect(page.getByText(/Member/i)).toBeVisible();
  });

  test('should navigate to organization settings', async ({ page }) => {
    await page.locator('[data-testid="org-switcher"]').click();

    // Click manage organization
    await page.getByRole('link', { name: /Manage/i }).click();

    await expect(page).toHaveURL(/\/settings\/organization/);
  });
});

test.describe('Organization Settings', () => {
  test.beforeEach(async ({ page }) => {
    // Login as organization admin
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('orgadmin@example.com');
    await page.getByLabel(/Password/i).fill('AdminPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    await page.goto('/settings/organization');
  });

  test('should display organization information', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Organization Settings/i })).toBeVisible();

    // Should show organization details
    await expect(page.getByText(/Test Organization/i)).toBeVisible();
    await expect(page.getByText(/contact@testorg.com/i)).toBeVisible();
  });

  test('should update organization details', async ({ page }) => {
    // Edit organization name
    await page.getByLabel(/Organization Name/i).clear();
    await page.getByLabel(/Organization Name/i).fill('Updated Organization Name');

    // Save changes
    await page.getByRole('button', { name: /Save Changes/i }).click();

    // Should show success toast
    await expect(page.getByText(/updated successfully/i)).toBeVisible();
  });

  test('should display team members list', async ({ page }) => {
    // Scroll to members section
    await page.getByRole('heading', { name: /Team Members/i }).scrollIntoViewIfNeeded();

    // Should show member table
    await expect(page.getByText(/Full Name/i)).toBeVisible();
    await expect(page.getByText(/Email/i)).toBeVisible();
    await expect(page.getByText(/Role/i)).toBeVisible();

    // Should show role badges
    await expect(page.locator('[data-testid="role-badge"]').first()).toBeVisible();
  });

  test('should invite a new member', async ({ page }) => {
    // Click invite button
    await page.getByRole('button', { name: /Invite Member/i }).click();

    // Fill invitation form
    await page.getByLabel(/Email/i).fill('newmember@example.com');
    await page.getByLabel(/Role/i).selectOption('member');

    // Send invitation
    await page.getByRole('button', { name: /Send Invitation/i }).click();

    // Should show success
    await expect(page.getByText(/invitation sent/i)).toBeVisible();

    // Should appear in pending invitations
    await expect(page.getByText(/newmember@example.com/i)).toBeVisible();
  });

  test('should revoke pending invitation', async ({ page }) => {
    // Find pending invitation
    await page.getByRole('heading', { name: /Pending Invitations/i }).scrollIntoViewIfNeeded();

    // Click revoke button
    await page.getByRole('button', { name: /Revoke/i }).first().click();

    // Confirm revocation
    await page.getByRole('button', { name: /Confirm/i }).click();

    // Should show success
    await expect(page.getByText(/revoked/i)).toBeVisible();
  });

  test('should update member role', async ({ page }) => {
    // Find member in list
    await page.getByRole('heading', { name: /Team Members/i }).scrollIntoViewIfNeeded();

    // Click edit button
    await page.locator('[data-testid="edit-member"]').first().click();

    // Change role
    await page.getByLabel(/Role/i).selectOption('admin');

    // Save changes
    await page.getByRole('button', { name: /Save/i }).click();

    // Should show success
    await expect(page.getByText(/updated/i)).toBeVisible();
  });

  test('should remove member from organization', async ({ page }) => {
    await page.getByRole('heading', { name: /Team Members/i }).scrollIntoViewIfNeeded();

    // Click remove button
    await page.getByRole('button', { name: /Remove/i }).first().click();

    // Confirm removal
    await page.getByRole('button', { name: /Confirm/i }).click();

    // Should show success
    await expect(page.getByText(/removed/i)).toBeVisible();
  });

  test('should prevent removing last admin', async ({ page }) => {
    // Try to remove the only admin
    await page.locator('[data-testid="remove-owner"]').click();

    // Should show error
    await expect(page.getByText(/cannot remove.*last admin/i)).toBeVisible();

    // Or button should be disabled
    await expect(page.getByRole('button', { name: /Confirm/i })).toBeDisabled();
  });

  test('should request organization deletion', async ({ page }) => {
    // Scroll to danger zone
    await page.getByRole('heading', { name: /Danger Zone/i }).scrollIntoViewIfNeeded();

    // Click delete organization
    await page.getByRole('button', { name: /Delete Organization/i }).click();

    // Should show strong warning
    await expect(page.getByText(/permanently delete/i)).toBeVisible();

    // Provide reason
    await page.getByLabel(/Reason/i).fill('Business is closing down');

    // Confirm deletion request
    await page.getByRole('button', { name: /Request Deletion/i }).click();

    // Should show success
    await expect(page.getByText(/deletion request submitted/i)).toBeVisible();
  });
});

test.describe('Invitation Acceptance', () => {
  test('should accept invitation as existing user', async ({ page }) => {
    // Visit invitation link (with valid token)
    await page.goto('/invitations/valid-token-12345');

    // Should show invitation details
    await expect(page.getByText(/invited to join/i)).toBeVisible();
    await expect(page.getByText(/Test Organization/i)).toBeVisible();
    await expect(page.getByText(/Member/i)).toBeVisible();

    // Accept invitation
    await page.getByRole('button', { name: /Accept Invitation/i }).click();

    // Should redirect to dashboard
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText(/invitation accepted/i)).toBeVisible();
  });

  test('should accept invitation and create account', async ({ page }) => {
    // Visit invitation link as new user
    await page.goto('/invitations/valid-token-67890');

    // Should prompt for account creation
    await expect(page.getByText(/Create your account/i)).toBeVisible();

    // Fill user details
    await page.getByLabel(/Full Name/i).fill('New Member');
    await page.getByLabel(/Password/i).fill('SecurePassword123!');

    // Accept and create account
    await page.getByRole('button', { name: /Accept.*Create Account/i }).click();

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText(/account created/i)).toBeVisible();
  });

  test('should show error for expired invitation', async ({ page }) => {
    await page.goto('/invitations/expired-token');

    // Should show error message
    await expect(page.getByText(/expired/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /Accept/i })).toBeDisabled();
  });

  test('should show error for invalid invitation token', async ({ page }) => {
    await page.goto('/invitations/invalid-token');

    // Should show 404 or error
    await expect(page.getByText(/not found/i)).toBeVisible();
  });

  test('should show error for already accepted invitation', async ({ page }) => {
    await page.goto('/invitations/already-accepted-token');

    // Should show error
    await expect(page.getByText(/already.*accepted/i)).toBeVisible();
  });
});
