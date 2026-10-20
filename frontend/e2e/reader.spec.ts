import { test, expect, Page } from '@playwright/test';

/** A phone cannot rely on an inline PDF frame: Android Chrome has no PDF
 * plugin for iframes, and a never-firing onLoad used to leave the white
 * "Opening" overlay over a blank panel. The mobile reader must offer the
 * same-origin PDF as a direct action, while desktop keeps the frame. */
const useSession = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('gs_token', 'reader-e2e-token');
    localStorage.setItem('gs_user', JSON.stringify({
      id: 42, name: 'Pravesh Kumar', email: 'student@example.com', role: 'student',
      role_status: 'active', lang_pref: 'en', class_grade: 8,
      board: 'Maharashtra SSC', xp: 40, streak_days: 1,
    }));
  });
};

const mockReaderApi = async (page: Page) => {
  await page.route('**/api/**', async (route) => {
    const { pathname } = new URL(route.request().url());
    let body: unknown = {};
    if (pathname.endsWith('/auth/me')) body = {
      id: 42, name: 'Pravesh Kumar', email: 'student@example.com', role: 'student',
      role_status: 'active', lang_pref: 'en', class_grade: 8,
      board: 'Maharashtra SSC', xp: 40, streak_days: 1,
    };
    else if (pathname.endsWith('/textbooks')) body = [{
      id: 140, title: 'English — Class 8 (Balbharati)', class_grade: 8,
      board: 'Maharashtra SSC', subject_name: 'English', lang: 'en',
      has_deep_link: true, has_chapters: false, cover_url: null,
      stream: '', part_label: null,
    }];
    else if (pathname.endsWith('/catalog/availability')) body = {
      board: 'Maharashtra SSC', class_grade: 8,
      mediums: [{ lang: 'en', label: 'English', books: 1, subjects: 1 }],
      streams: [],
      subjects: [{
        name: 'English', name_hi: null, name_mr: null, subject_id: null,
        books_by_lang: { en: 1 }, courses: 0, lessons: 0, course_ids: [], stream: '',
      }],
    };
    else if (pathname.endsWith('/library/reading')) body = [];
    else if (pathname.endsWith('/library/requests')) body = [];
    else if (pathname.endsWith('/open')) {
      await route.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF\n' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
};

test('desktop keeps the frame and phones get a direct PDF action', async ({ page }) => {
  await useSession(page);
  await mockReaderApi(page);
  await page.goto('/textbooks');
  await page.getByRole('button', { name: /Read$/ }).first().click();
  await expect(page.locator('.viewer')).toBeVisible();

  const width = page.viewportSize()?.width ?? 1280;
  if (width <= 768) {
    await expect(page.locator('.viewer-phone')).toBeVisible();
    await expect(page.locator('.viewer-phone')).toContainText(/opens PDFs in its own reader/i);
    await expect(page.locator('.viewer-frame')).toHaveCount(0);
    const open = page.getByRole('link', { name: /Open PDF/i });
    await expect(open).toBeVisible();
    await expect(open).toHaveAttribute('href', '/api/textbooks/140/open');
    await expect(open).toHaveAttribute('target', '_blank');
  } else {
    await expect(page.locator('.viewer-frame')).toHaveAttribute('src', '/api/textbooks/140/open');
    await expect(page.getByRole('link', { name: /Open PDF/i })).toBeVisible();
  }
});
