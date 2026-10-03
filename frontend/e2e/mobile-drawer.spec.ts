import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.beforeEach(async ({ page }) => {
  test.skip((page.viewportSize()?.width ?? 0) > 900, 'Navigation drawer is a mobile-breakpoint interaction');
  await page.addInitScript(() => {
    localStorage.setItem('gs_token', 'e2e-token');
    localStorage.setItem('gs_user', JSON.stringify({
      id: 42, name: 'Pravesh Kumar', email: 'student@example.com', role: 'student',
      role_status: 'active', lang_pref: 'en', class_grade: 10, board: 'CBSE', xp: 240, streak_days: 12,
    }));
  });
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let body: unknown = {};
    if (url.pathname.endsWith('/learn/today')) body = { items: [], study_minutes_today: 18, streak_days: 12, xp: 240 };
    else if (url.pathname.endsWith('/my/courses')) body = [];
    else if (url.pathname.endsWith('/learn/weak-topics')) body = { weak: [], message: '' };
    else if (url.pathname.endsWith('/progress/summary')) body = { lessons_completed: 4, quiz_avg_pct: 82, week_minutes: 50, badges: [], certificates: [] };
    else if (url.pathname.endsWith('/notifications')) body = [];
    else if (url.pathname.endsWith('/growth/reading-list')) body = [];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('/#/dashboard');
  await expect(page.locator('#main-content')).toBeVisible();
});

test('opens, navigates, and closes the mobile drawer', async ({ page }) => {
  const menu = page.getByRole('button', { name: 'Open navigation' });
  const drawer = page.getByRole('complementary', { name: 'Workspace navigation' });
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await menu.click();
  await expect(drawer).toHaveClass(/drawer-open/);
  await expect(page.locator('.drawer-close')).toBeVisible();
  await page.locator('.sidebar-nav').getByRole('link', { name: /Practice/ }).click();
  await expect(page).toHaveURL(/#\/practice$/);
  await expect(drawer).not.toHaveClass(/drawer-open/);
  await menu.click();
  await page.keyboard.press('Escape');
  await expect(drawer).not.toHaveClass(/drawer-open/);
});

test('locks scroll and closes the drawer through the backdrop', async ({ page }) => {
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await expect(page.locator('body')).toHaveClass(/nav-drawer-open/);
  await page.locator('.drawer-close').click();
  await expect(page.locator('body')).not.toHaveClass(/nav-drawer-open/);
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.mouse.click(380, 20);
  await expect(page.getByRole('complementary', { name: 'Workspace navigation' })).not.toHaveClass(/drawer-open/);
});

test('has no automatically detectable WCAG A/AA issues with the drawer open', async ({ page }) => {
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await expect(page.locator('.drawer-close')).toBeVisible();
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .include('.sidebar')
    .analyze();
  expect(results.violations).toEqual([]);
});
