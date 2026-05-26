import { test, expect } from '@playwright/test';

/**
 * Business Registration E2E Tests
 *
 * Tests the complete business registration and approval workflow.
 */

test.describe('Business Registration', () => {
  test('should register a business account successfully', async ({ page }) => {
    await page.goto('/register');

    // Select business account type
    await page.getByLabel(/Business/i).click();

    // Fill business information
    await page.getByLabel(/Organization Name/i).fill('Acme Corporation');
    await page.getByLabel(/Business Email/i).fill('contact@acmecorp.com');
    await page.getByLabel(/Business Phone/i).fill('+1-555-0123');

    // Fill user information
    await page.getByLabel(/Full Name/i).fill('John Doe');
    await page.getByLabel(/Email/i).first().fill('john@acmecorp.com');
    await page.getByLabel(/Password/i).fill('SecurePassword123!');

    // Submit registration
    await page.getByRole('button', { name: /Register/i }).click();

    // Should redirect to pending approval page
    await expect(page).toHaveURL(/\/register\/pending/);
    await expect(page.getByText(/pending approval/i)).toBeVisible();
    await expect(page.getByText(/24 hours/i)).toBeVisible();
  });

  test('should register a personal account successfully', async ({ page }) => {
    await page.goto('/register');

    // Select personal account type (default)
    await page.getByLabel(/Personal/i).click();

    // Fill user information only
    await page.getByLabel(/Full Name/i).fill('Jane Smith');
    await page.getByLabel(/Email/i).fill('jane@example.com');
    await page.getByLabel(/Password/i).fill('SecurePassword123!');

    // Submit registration
    await page.getByRole('button', { name: /Register/i }).click();

    // Should redirect to dashboard (personal accounts auto-approved)
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('should validate business email format', async ({ page }) => {
    await page.goto('/register');

    await page.getByLabel(/Business/i).click();
    await page.getByLabel(/Business Email/i).fill('invalid-email');
    await page.getByLabel(/Full Name/i).click(); // Trigger validation

    await expect(page.getByText(/valid email/i)).toBeVisible();
  });

  test('should require all business fields', async ({ page }) => {
    await page.goto('/register');

    await page.getByLabel(/Business/i).click();

    // Try to submit without filling fields
    await page.getByRole('button', { name: /Register/i }).click();

    // Should show validation errors
    await expect(page.getByText(/Organization Name.*required/i)).toBeVisible();
  });

  test('should validate password strength', async ({ page }) => {
    await page.goto('/register');

    await page.getByLabel(/Password/i).fill('weak');
    await page.getByLabel(/Full Name/i).click();

    await expect(page.getByText(/at least 8 characters/i)).toBeVisible();
  });

  test('should show duplicate email error', async ({ page }) => {
    await page.goto('/register');

    // Try to register with existing email
    await page.getByLabel(/Email/i).fill('existing@example.com');
    await page.getByLabel(/Full Name/i).fill('Test User');
    await page.getByLabel(/Password/i).fill('SecurePassword123!');

    await page.getByRole('button', { name: /Register/i }).click();

    // Should show error toast
    await expect(page.getByText(/email already registered/i)).toBeVisible();
  });
});
