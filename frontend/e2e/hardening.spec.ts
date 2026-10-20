import { test, expect, Page } from '@playwright/test';

/** Offline material open used a programmatic `_blank` click after an await.
 * Phone browsers treat that as a popup (blocked) or open a blank tab for a
 * blob URL. It must navigate the current tab so the file is actually shown. */
const useSession = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('gs_token', 'hardening-e2e-token');
    localStorage.setItem('gs_user', JSON.stringify({
      id: 42, name: 'Pravesh Kumar', email: 'student@example.com', role: 'student',
      role_status: 'active', lang_pref: 'en', class_grade: 8,
      board: 'Maharashtra SSC', xp: 40, streak_days: 1,
    }));
  });
};

const mockMaterialApi = async (page: Page) => {
  await page.route('**/api/**', async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname.endsWith('/materials/1/download')) {
      await route.fulfill({ status: 200, contentType: 'text/plain', body: 'offline material body' });
      return;
    }
    let body: unknown = {};
    if (pathname.endsWith('/materials')) body = [{
      id: 1, title: 'Cell notes', description: 'Short revision notes', type: 'notes',
      class_grade: 8, board: 'Maharashtra SSC', lang: 'en', stream: '',
      source_of_content: 'Teacher', downloads: 3, file_size: 2048,
    }];
    else if (pathname.endsWith('/growth/config')) body = {
      site_url: 'https://example.org', referral_enabled: true, ads: null, donate: null,
      affiliates: [], sponsor: null, premium_url: null,
    };
    else if (pathname.endsWith('/auth/me')) body = {
      id: 42, name: 'Pravesh Kumar', email: 'student@example.com', role: 'student',
      role_status: 'active', lang_pref: 'en', class_grade: 8,
      board: 'Maharashtra SSC', xp: 40, streak_days: 1,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
};

test('an offline file opens in this tab rather than through a blocked popup', async ({ page }) => {
  await useSession(page);
  await mockMaterialApi(page);
  await page.goto('/#/materials');
  await page.getByRole('button', { name: /Download$/ }).first().click();
  await expect(page.getByText(/Saved on this device for offline use/i)).toBeVisible();

  await page.goto('/#/downloads');
  await expect(page.getByText('Cell notes')).toBeVisible();
  await page.getByRole('button', { name: /Open offline/i }).click();
  await page.waitForURL(/^blob:/, { timeout: 5000 });
  await expect(page.locator('body')).toContainText('offline material body');
});
