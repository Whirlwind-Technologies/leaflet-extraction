/**
 * Test Helper Utilities
 *
 * Common functions and utilities for E2E tests.
 */

import { Page } from '@playwright/test';

/**
 * Login helper function
 */
export async function login(
  page: Page,
  email: string,
  password: string
): Promise<void> {
  await page.goto('/login');
  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel(/Password/i).fill(password);
  await page.getByRole('button', { name: /Sign In/i }).click();
  await page.waitForURL(/\/dashboard/);
}

/**
 * Logout helper function
 */
export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: /Logout/i }).click();
  await page.waitForURL(/\/login/);
}

/**
 * Login as different user types
 */
export const loginAs = {
  superadmin: async (page: Page) => {
    await login(page, 'admin@example.com', 'AdminPassword123');
  },

  orgAdmin: async (page: Page) => {
    await login(page, 'orgadmin@example.com', 'AdminPassword123');
  },

  member: async (page: Page) => {
    await login(page, 'member@example.com', 'MemberPassword123');
  },

  user: async (page: Page) => {
    await login(page, 'user@example.com', 'UserPassword123');
  },

  multiOrg: async (page: Page) => {
    await login(page, 'multiorg@example.com', 'MultiOrgPassword123');
  },

  org1: async (page: Page) => {
    await login(page, 'org1@example.com', 'OrgPassword123');
  },

  org2: async (page: Page) => {
    await login(page, 'org2@example.com', 'OrgPassword123');
  },
};

/**
 * Switch organization helper
 */
export async function switchOrganization(
  page: Page,
  organizationName: string
): Promise<void> {
  await page.locator('[data-testid="org-switcher"]').click();
  await page.getByText(organizationName).click();
  await page.waitForLoadState('networkidle');
}

/**
 * Upload leaflet helper
 */
export async function uploadLeaflet(
  page: Page,
  filePath: string = './tests/fixtures/test-leaflet.pdf'
): Promise<string> {
  await page.goto('/dashboard/leaflets');
  await page.getByRole('button', { name: /Upload/i }).click();

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(filePath);

  await page.getByRole('button', { name: /Upload/i }).click();
  await page.waitForSelector('text=/uploaded successfully/i');

  // Get the leaflet ID from the first row
  const leafletRow = page.locator('table tbody tr').first();
  const leafletId = await leafletRow.getAttribute('data-leaflet-id');

  return leafletId || '';
}

/**
 * Invite user helper
 */
export async function inviteUser(
  page: Page,
  email: string,
  role: 'member' | 'admin' = 'member'
): Promise<void> {
  await page.goto('/settings/organization');

  await page.getByRole('button', { name: /Invite Member/i }).click();

  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel(/Role/i).selectOption(role);

  await page.getByRole('button', { name: /Send Invitation/i }).click();

  await page.waitForSelector('text=/invitation sent/i');
}

/**
 * Wait for toast notification
 */
export async function waitForToast(
  page: Page,
  message: string | RegExp
): Promise<void> {
  await page.waitForSelector(`text=${message}`);
}

/**
 * Create test organization via API
 */
export async function createTestOrganization(
  page: Page,
  name: string,
  email: string
): Promise<string> {
  const response = await page.request.post('/api/v1/registrations', {
    data: {
      organization_name: name,
      business_email: email,
      user_full_name: 'Test Owner',
      user_email: email,
      user_password: 'TestPassword123!',
    },
  });

  const data = await response.json();
  return data.registration_id;
}

/**
 * Approve registration via API (as superadmin)
 */
export async function approveRegistration(
  page: Page,
  registrationId: string
): Promise<void> {
  await loginAs.superadmin(page);

  await page.request.post(
    `/api/v1/admin/registrations/${registrationId}/approve`,
    {
      headers: {
        Authorization: `Bearer ${await getAuthToken(page)}`,
      },
    }
  );
}

/**
 * Get authentication token from page
 */
export async function getAuthToken(page: Page): Promise<string> {
  const cookies = await page.context().cookies();
  const authCookie = cookies.find(c => c.name === 'access_token');
  return authCookie?.value || '';
}

/**
 * Check if element is visible with timeout
 */
export async function isVisible(
  page: Page,
  selector: string,
  timeout: number = 5000
): Promise<boolean> {
  try {
    await page.waitForSelector(selector, { timeout, state: 'visible' });
    return true;
  } catch {
    return false;
  }
}

/**
 * Intercept and log API requests
 */
interface LoggedRequest {
  method: string;
  url: string;
  headers: Record<string, string>;
  timestamp: string;
}

export function setupRequestLogging(page: Page): LoggedRequest[] {
  const requests: LoggedRequest[] = [];

  page.on('request', request => {
    if (request.url().includes('/api/')) {
      requests.push({
        method: request.method(),
        url: request.url(),
        headers: request.headers(),
        timestamp: new Date().toISOString(),
      });
    }
  });

  return requests;
}

/**
 * Mock API response
 */
export async function mockApiResponse(
  page: Page,
  url: string | RegExp,
  response: unknown,
  status: number = 200
): Promise<void> {
  await page.route(url, async route => {
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });
}

/**
 * Clear all mocks
 */
export async function clearMocks(page: Page): Promise<void> {
  await page.unrouteAll();
}

/**
 * Take screenshot with timestamp
 */
export async function takeScreenshot(
  page: Page,
  name: string
): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  await page.screenshot({
    path: `./test-results/screenshots/${name}-${timestamp}.png`,
    fullPage: true,
  });
}
