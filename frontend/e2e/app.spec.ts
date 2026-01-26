import { test, expect } from '@playwright/test';

test.describe('Timetable Generator', () => {
  test('should display landing page', async ({ page }) => {
    await page.goto('/');
    
    // Check for main heading
    await expect(page.getByRole('heading', { name: /timetable generator/i })).toBeVisible();
    
    // Check for Get Started button
    await expect(page.getByRole('button', { name: /get started/i })).toBeVisible();
  });

  test('should navigate to upload page', async ({ page }) => {
    await page.goto('/');
    
    // Click Get Started
    await page.getByRole('button', { name: /get started/i }).click();
    
    // Should be on upload page
    await expect(page).toHaveURL('/upload');
    await expect(page.getByText(/upload your school data/i)).toBeVisible();
  });

  test('should navigate through sidebar', async ({ page }) => {
    await page.goto('/');
    
    // Click on Upload in sidebar
    await page.getByRole('link', { name: /upload data/i }).click();
    await expect(page).toHaveURL('/upload');
    
    // Click on Constraints in sidebar
    await page.getByRole('link', { name: /constraints/i }).click();
    await expect(page).toHaveURL('/constraints');
    
    // Click on Generate in sidebar
    await page.getByRole('link', { name: /generate/i }).click();
    await expect(page).toHaveURL('/generate');
    
    // Click on Recent Jobs in sidebar
    await page.getByRole('link', { name: /recent jobs/i }).click();
    await expect(page).toHaveURL('/jobs');
  });
});

test.describe('Upload Flow', () => {
  test('should show file upload dropzone', async ({ page }) => {
    await page.goto('/upload');
    
    // Check for dropzone
    await expect(page.getByText(/drag and drop/i)).toBeVisible();
    
    // Check for supported formats
    await expect(page.getByText(/xlsx/i)).toBeVisible();
  });
});

test.describe('Constraints Page', () => {
  test('should display constraint toggles', async ({ page }) => {
    await page.goto('/constraints');
    
    // Check for hard constraints section
    await expect(page.getByText(/hard constraints/i)).toBeVisible();
    
    // Check for soft constraints section
    await expect(page.getByText(/soft constraints/i)).toBeVisible();
  });
});
