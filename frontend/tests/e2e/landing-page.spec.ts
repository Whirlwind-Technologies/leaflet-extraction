import { test, expect } from '@playwright/test';

/**
 * Landing Page E2E Tests
 *
 * Tests the marketing landing page functionality.
 */

test.describe('Landing Page', () => {
  test('should display marketing content', async ({ page }) => {
    await page.goto('/');

    // Check hero section
    await expect(page.getByRole('heading', { name: /Extract Product Data/i })).toBeVisible();

    // Check CTA buttons
    await expect(page.getByRole('link', { name: /Get Started/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Sign In/i })).toBeVisible();
  });

  test('should navigate to registration page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Get Started/i }).first().click();

    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByRole('heading', { name: /Create Account/i })).toBeVisible();
  });

  test('should navigate to login page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Sign In/i }).first().click();

    await expect(page).toHaveURL(/\/login/);
  });

  test('should display features section', async ({ page }) => {
    await page.goto('/');

    // Scroll to features
    await page.getByText(/AI-Powered Extraction/i).scrollIntoViewIfNeeded();

    // Check for feature cards
    await expect(page.getByText(/AI-Powered Extraction/i)).toBeVisible();
    await expect(page.getByText(/95%\+ Accuracy/i)).toBeVisible();
  });

  test('should have working navigation links', async ({ page }) => {
    await page.goto('/');

    // Check navigation links
    const nav = page.getByRole('navigation');
    await expect(nav).toBeVisible();

    // Check footer links
    await page.getByText(/Privacy Policy/i).scrollIntoViewIfNeeded();
    await expect(page.getByRole('link', { name: /Privacy Policy/i })).toBeVisible();
  });
});
