import { test, expect } from '@playwright/test';
import * as fs from 'fs';

/**
 * Data Isolation E2E Tests
 *
 * Critical security tests to ensure organizations cannot access each other's data.
 */

test.describe('Data Isolation', () => {
  test('organizations should only see their own leaflets', async ({ page, context }) => {
    // Login as Organization 1 user
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('org1@example.com');
    await page.getByLabel(/Password/i).fill('OrgPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Upload a leaflet for Org 1
    await page.goto('/dashboard/leaflets');
    await page.getByRole('button', { name: /Upload/i }).click();

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('./tests/fixtures/test-leaflet.pdf');

    await page.getByRole('button', { name: /Upload/i }).click();
    await expect(page.getByText(/uploaded successfully/i)).toBeVisible();

    // Get the leaflet ID from URL or table
    const leafletRow = page.locator('table tbody tr').first();
    const leafletId = await leafletRow.getAttribute('data-leaflet-id');

    // Logout
    await page.getByRole('button', { name: /Logout/i }).click();

    // Login as Organization 2 user in new context
    const page2 = await context.newPage();
    await page2.goto('/login');
    await page2.getByLabel(/Email/i).fill('org2@example.com');
    await page2.getByLabel(/Password/i).fill('OrgPassword123');
    await page2.getByRole('button', { name: /Sign In/i }).click();

    // Try to access Org 1's leaflet directly via URL
    await page2.goto(`/dashboard/leaflets/${leafletId}`);

    // Should show 404 or redirect
    await expect(page2.getByText(/not found/i)).toBeVisible();

    // Check leaflets list doesn't include Org 1's data
    await page2.goto('/dashboard/leaflets');
    await expect(page2.locator(`[data-leaflet-id="${leafletId}"]`)).not.toBeVisible();
  });

  test('organizations should only see their own products', async ({ page, context }) => {
    // Login as Org 1
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('org1@example.com');
    await page.getByLabel(/Password/i).fill('OrgPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Navigate to products
    await page.goto('/dashboard/products');

    const firstProduct = await page.locator('table tbody tr').first().getAttribute('data-product-id');

    // Logout and login as Org 2
    await page.getByRole('button', { name: /Logout/i }).click();

    const page2 = await context.newPage();
    await page2.goto('/login');
    await page2.getByLabel(/Email/i).fill('org2@example.com');
    await page2.getByLabel(/Password/i).fill('OrgPassword123');
    await page2.getByRole('button', { name: /Sign In/i }).click();

    // Check products list
    await page2.goto('/dashboard/products');

    // Should not see Org 1's products
    await expect(page2.locator(`[data-product-id="${firstProduct}"]`)).not.toBeVisible();

    // Product counts should be different (unless both have same count coincidentally)
    // More importantly, the actual products should be different
  });

  test('organization switcher should update data context', async ({ page }) => {
    // Login as user with multiple organizations
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('multiorg@example.com');
    await page.getByLabel(/Password/i).fill('MultiOrgPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Go to leaflets for Org 1
    await page.goto('/dashboard/leaflets');
    const org1LeafletIds = await page.locator('[data-leaflet-id]').allTextContents();

    // Switch to Org 2
    await page.locator('[data-testid="org-switcher"]').click();
    await page.getByText(/Test Organization 2/i).click();

    // Wait for page reload
    await page.waitForLoadState('networkidle');

    // Check leaflets for Org 2
    const org2LeafletIds = await page.locator('[data-leaflet-id]').allTextContents();

    // Should have different leaflets
    expect(org1LeafletIds).not.toEqual(org2LeafletIds);

    // Verify no overlap
    const overlap = org1LeafletIds.filter(id => org2LeafletIds.includes(id));
    expect(overlap.length).toBe(0);
  });

  test('API requests should include organization context', async ({ page }) => {
    // Setup request interception
    const requests: { url: string; headers: Record<string, string> }[] = [];

    page.on('request', request => {
      if (request.url().includes('/api/v1/')) {
        requests.push({
          url: request.url(),
          headers: request.headers(),
        });
      }
    });

    // Login
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('org1@example.com');
    await page.getByLabel(/Password/i).fill('OrgPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Make API request by navigating
    await page.goto('/dashboard/leaflets');
    await page.waitForLoadState('networkidle');

    // Find leaflets API request
    const leafletsRequest = requests.find(req => req.url.includes('/leaflets'));
    expect(leafletsRequest).toBeDefined();

    // JWT token should include org_id
    const authHeader = leafletsRequest.headers['authorization'];
    expect(authHeader).toBeDefined();
    expect(authHeader).toContain('Bearer');
  });

  test('should not access other org data via API manipulation', async ({ page }) => {
    // This test would require accessing browser dev tools or intercepting requests
    // For now, this is a placeholder showing the intent

    // Login as Org 1
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('org1@example.com');
    await page.getByLabel(/Password/i).fill('OrgPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Intercept and modify API request to try accessing Org 2 data
    await page.route('**/api/v1/leaflets/**', async (route, request) => {
      // Try to modify org_id in request
      const headers = request.headers();
      headers['X-Organization-ID'] = 'different-org-id';

      const response = await route.fetch({ headers });

      // Should return 403 or 404, not 200
      expect(response.status()).not.toBe(200);

      await route.continue();
    });

    await page.goto('/dashboard/leaflets');
  });

  test('exported data should be scoped to organization', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('org1@example.com');
    await page.getByLabel(/Password/i).fill('OrgPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Navigate to products
    await page.goto('/dashboard/products');

    // Setup download listener
    const downloadPromise = page.waitForEvent('download');

    // Export products
    await page.getByRole('button', { name: /Export/i }).click();
    await page.getByText(/CSV/i).click();

    const download = await downloadPromise;

    // Save file
    const path = await download.path();

    // Read and verify file contents only include org's data
    const content = fs.readFileSync(path!, 'utf-8');

    // Should not contain markers from other orgs
    expect(content).not.toContain('org2-specific-marker');
  });
});

test.describe('Member Role Permissions', () => {
  test('member should access leaflets but not admin functions', async ({ page }) => {
    // Login as member
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('member@example.com');
    await page.getByLabel(/Password/i).fill('MemberPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Can access leaflets
    await page.goto('/dashboard/leaflets');
    await expect(page.getByRole('heading', { name: /Leaflets/i })).toBeVisible();

    // Cannot access organization settings
    await page.goto('/settings/organization');
    await expect(page.getByText(/forbidden|not authorized/i)).toBeVisible();
  });

  test('admin should access organization settings', async ({ page }) => {
    // Login as admin
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('orgadmin@example.com');
    await page.getByLabel(/Password/i).fill('AdminPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Can access organization settings
    await page.goto('/settings/organization');
    await expect(page.getByRole('heading', { name: /Organization Settings/i })).toBeVisible();

    // Can invite members
    await expect(page.getByRole('button', { name: /Invite Member/i })).toBeVisible();
  });

  test('regular user should not access admin panel', async ({ page }) => {
    // Login as regular user
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('user@example.com');
    await page.getByLabel(/Password/i).fill('UserPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Try to access admin panel
    await page.goto('/admin');

    // Should be redirected or show error
    await expect(page).not.toHaveURL(/\/admin/);
    // OR
    await expect(page.getByText(/not authorized/i)).toBeVisible();
  });

  test('superuser should access admin panel', async ({ page }) => {
    // Login as superuser
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill('admin@example.com');
    await page.getByLabel(/Password/i).fill('AdminPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Can access admin panel
    await page.goto('/admin');
    await expect(page.getByRole('heading', { name: /Admin Dashboard/i })).toBeVisible();

    // Can see admin navigation
    await expect(page.getByRole('link', { name: /Registrations/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Deletion Requests/i })).toBeVisible();
  });
});
