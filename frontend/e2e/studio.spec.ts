import { expect, test } from '@playwright/test';

const USER = {
  name: 'Studio Learner',
  role: 'student',
  role_status: 'active',
  class_grade: 8,
  board: 'Maharashtra SSC',
  xp: 0,
  streak_days: 0,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript((user) => {
    localStorage.setItem('gs_token', 'studio-test-token');
    localStorage.setItem('gs_user', JSON.stringify(user));
  }, USER);
  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/auth/me')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 7, email: 'studio@example.com', ...USER }),
      });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
});

test('a learner can import notes and use the native study pack', async ({ page }) => {
  await page.goto('/studio');
  await expect(page.getByRole('heading', { name: /study studio/i }).first()).toBeVisible();

  await page.getByRole('button', { name: /use a sample/i }).click();
  await page.getByRole('button', { name: /build study pack/i }).click();

  const pack = page.locator('.studio-pack');
  await expect(pack.getByRole('heading', { name: 'Photosynthesis' })).toBeVisible();
  await expect(pack.locator('.studio-points').getByText('Chlorophyll absorbs light energy.')).toBeVisible();
  // Print/Save PDF must carry every section, not only the open tab.
  await expect(pack.locator('.studio-print-sheet')).toContainText('Revision checklist');

  await pack.getByRole('tab', { name: /flashcards/i }).click();
  const firstCard = pack.locator('.flashcard').first();
  await expect(firstCard).toBeVisible();
  await firstCard.click();
  await expect(firstCard).toContainText('Answer');

  await pack.getByRole('tab', { name: /quiz/i }).click();
  await pack.getByRole('button', { name: /show answer/i }).first().click();
  await expect(pack.locator('.studio-answer').first()).toBeVisible();

  await pack.getByRole('tab', { name: /checklist/i }).click();
  const firstCheck = pack.locator('.studio-checklist input').first();
  await firstCheck.check();
  await expect(firstCheck).toBeChecked();

  // The pack is device-local, so a reload keeps it without any server write.
  await page.reload();
  await expect(page.locator('.studio-pack').getByRole('heading', { name: 'Photosynthesis' })).toBeVisible();
  await expect(page.getByText(/1 on this device|on this device/i).first()).toBeVisible();
});

test('the study pack can be downloaded as a self-contained HTML file', async ({ page }) => {
  await page.goto('/studio');
  await page.getByRole('button', { name: /use a sample/i }).click();
  await page.getByRole('button', { name: /build study pack/i }).click();
  await expect(page.locator('.studio-pack')).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: /download html/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/photosynthesis.*\.html$/);
});

test('a signed-out visitor is asked to log in instead of seeing an empty studio', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem('gs_token');
    localStorage.removeItem('gs_user');
  });
  await page.goto('/studio');
  await expect(page.getByText(/log in to open your study studio/i)).toBeVisible();
});
