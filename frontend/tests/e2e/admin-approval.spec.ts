import { test, expect } from '@playwright/test';

/**
 * Admin Approval Workflow E2E Tests
 *
 * Tests the super admin approval workflow for business registrations.
 */

test.describe('Admin Approval Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Login as super admin
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('admin@example.com');
    await page.getByLabel(/Password/i).fill('AdminPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('should display pending registrations', async ({ page }) => {
    await page.goto('/admin/registrations');

    // Check page title
    await expect(page.getByRole('heading', { name: /Business Registrations/i })).toBeVisible();

    // Check table headers
    await expect(page.getByText(/Organization Name/i)).toBeVisible();
    await expect(page.getByText(/Business Email/i)).toBeVisible();
    await expect(page.getByText(/Owner Name/i)).toBeVisible();
  });

  test('should approve a registration successfully', async ({ page }) => {
    await page.goto('/admin/registrations');

    // Click approve on first registration
    await page.getByRole('button', { name: /Approve/i }).first().click();

    // Confirm in dialog
    await page.getByRole('button', { name: /Confirm/i }).click();

    // Should show success toast
    await expect(page.getByText(/approved successfully/i)).toBeVisible();

    // Registration should be removed from list
    // (or moved to approved section depending on implementation)
  });

  test('should reject a registration with reason', async ({ page }) => {
    await page.goto('/admin/registrations');

    // Click reject on first registration
    await page.getByRole('button', { name: /Reject/i }).first().click();

    // Fill rejection reason
    await page.getByLabel(/Reason/i).fill('Business does not meet requirements');

    // Confirm rejection
    await page.getByRole('button', { name: /Reject/i }).click();

    // Should show success toast
    await expect(page.getByText(/rejected/i)).toBeVisible();
  });

  test('should require rejection reason', async ({ page }) => {
    await page.goto('/admin/registrations');

    // Click reject
    await page.getByRole('button', { name: /Reject/i }).first().click();

    // Try to submit without reason
    await page.getByRole('button', { name: /Reject/i }).click();

    // Should show validation error or disabled button
    await expect(page.getByText(/reason.*required/i)).toBeVisible();
  });

  test('should view registration details', async ({ page }) => {
    await page.goto('/admin/registrations');

    // Click on first registration to view details
    await page.getByRole('row').nth(1).click();

    // Should show detailed information
    await expect(page.getByText(/Business Information/i)).toBeVisible();
    await expect(page.getByText(/Owner Information/i)).toBeVisible();
  });

  test('should filter registrations by status', async ({ page }) => {
    await page.goto('/admin/registrations');

    // Check filter options
    await page.getByLabel(/Status/i).click();

    await expect(page.getByText(/Pending/i)).toBeVisible();
    await expect(page.getByText(/Approved/i)).toBeVisible();
    await expect(page.getByText(/Rejected/i)).toBeVisible();

    // Filter by approved
    await page.getByText(/Approved/i).click();

    // Should update results
    await expect(page.getByText(/Approved Registrations/i)).toBeVisible();
  });

  test('should navigate to deletion requests', async ({ page }) => {
    await page.goto('/admin');

    // Click on deletion requests link
    await page.getByRole('link', { name: /Deletion Requests/i }).click();

    await expect(page).toHaveURL(/\/admin\/deletion-requests/);
    await expect(page.getByRole('heading', { name: /Deletion Requests/i })).toBeVisible();
  });
});

test.describe('Deletion Request Approval', () => {
  test.beforeEach(async ({ page }) => {
    // Login as super admin
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('admin@example.com');
    await page.getByLabel(/Password/i).fill('AdminPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();
  });

  test('should approve deletion request with confirmation', async ({ page }) => {
    await page.goto('/admin/deletion-requests');

    // Click approve on first request
    await page.getByRole('button', { name: /Approve/i }).first().click();

    // Should show strong warning
    await expect(page.getByText(/permanently delete/i)).toBeVisible();
    await expect(page.getByText(/cannot be undone/i)).toBeVisible();

    // List what will be deleted
    await expect(page.getByText(/All leaflets/i)).toBeVisible();
    await expect(page.getByText(/All product data/i)).toBeVisible();

    // Confirm deletion
    await page.getByRole('button', { name: /Confirm Deletion/i }).click();

    // Should show success toast
    await expect(page.getByText(/permanently deleted/i)).toBeVisible();
  });

  test('should reject deletion request with notes', async ({ page }) => {
    await page.goto('/admin/deletion-requests');

    // Click reject
    await page.getByRole('button', { name: /Reject/i }).first().click();

    // Provide rejection reason
    await page.getByLabel(/Reason/i).fill('Outstanding invoices need to be resolved first');

    // Confirm rejection
    await page.getByRole('button', { name: /Reject Request/i }).click();

    // Should show success
    await expect(page.getByText(/rejected/i)).toBeVisible();
  });

  test('should display warning for dangerous actions', async ({ page }) => {
    await page.goto('/admin/deletion-requests');

    await page.getByRole('button', { name: /Approve/i }).first().click();

    // Check for warning indicators
    await expect(page.locator('[class*="destructive"]')).toBeVisible();
    await expect(page.locator('[class*="text-red"]')).toBeVisible();
  });
});
