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
    if (url.pathname.endsWith('/studio/extract')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          filename: 'photosynthesis-notes.txt',
          text: 'Photosynthesis is how green plants use sunlight, water and carbon dioxide to make food. Chlorophyll absorbs the light. Oxygen is released as a by-product.',
          truncated: false,
        }),
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

test('a share from the learner’s own NotebookLM app prefills the import form', async ({ page }) => {
  const shared = 'Photosynthesis is how green plants use sunlight, water and carbon dioxide to make food. Chlorophyll absorbs the light. Oxygen is released.';
  const url = `/studio?title=${encodeURIComponent('Shared notes')}&text=${encodeURIComponent(shared)}&url=${encodeURIComponent('https://notebooklm.google.com/')}`;
  await page.goto(url);
  await expect(page.locator('#studio-title')).toHaveValue('Shared notes');
  await expect(page.locator('#studio-text')).toHaveValue(shared);
  await expect(page.locator('#studio-source')).toHaveValue('https://notebooklm.google.com/');
  await expect(page.getByText(/shared from your device/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /build study pack/i })).toBeEnabled();
});

test('a NotebookLM export file can be imported from the device', async ({ page }) => {
  await page.goto('/studio');
  await page.setInputFiles('input[type="file"]', {
    name: 'photosynthesis-notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Photosynthesis is how green plants use sunlight, water and carbon dioxide to make food.'),
  });
  await expect(page.locator('#studio-text')).toHaveValue(/Photosynthesis is how green plants/);
  await expect(page.locator('#studio-title')).toHaveValue('photosynthesis-notes');
  await expect(page.getByText(/file imported/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /build study pack/i })).toBeEnabled();
});

test('a Google Doc can be picked after a read-only Google connection', async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { google: unknown }).google = {
      accounts: {
        oauth2: {
          initTokenClient: (config: { callback: (response: { access_token: string }) => void }) => ({
            requestAccessToken: () => {
              window.setTimeout(() => config.callback({ access_token: 'drive-token' }), 0);
            },
          }),
        },
      },
    };
  });
  await page.route('https://www.googleapis.com/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/export')) {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: 'Photosynthesis is how green plants use sunlight, water and carbon dioxide to make food. Chlorophyll absorbs the light.',
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        files: [{
          id: 'doc-1',
          name: 'Photosynthesis notes',
          mimeType: 'application/vnd.google-apps.document',
          webViewLink: 'https://docs.google.com/document/d/doc-1/edit',
        }],
      }),
    });
  });

  await page.goto('/studio');
  await page.getByRole('button', { name: /connect google drive/i }).click();
  await expect(page.locator('#studio-drive-file')).toHaveValue('doc-1');
  await page.getByRole('button', { name: /import selected doc/i }).click();
  await expect(page.locator('#studio-text')).toHaveValue(/green plants use sunlight/);
  await expect(page.locator('#studio-title')).toHaveValue('Photosynthesis notes');
});

test('the install suggestion uses the browser prompt and then gets out of the way', async ({ page }) => {
  await page.goto('/studio');
  await page.getByRole('button', { name: /use a sample/i }).click();
  await page.evaluate(() => {
    const event = new Event('beforeinstallprompt') as Event & {
      prompt: () => Promise<void>;
      userChoice: Promise<{ outcome: 'accepted'; platform: string }>;
    };
    event.prompt = async () => { (window as unknown as { __installed?: boolean }).__installed = true; };
    event.userChoice = Promise.resolve({ outcome: 'accepted', platform: 'web' });
    window.dispatchEvent(event);
  });
  const install = page.getByRole('button', { name: /install app/i });
  await expect(install).toBeVisible();
  await install.click();
  expect(await page.evaluate(() => Boolean((window as unknown as { __installed?: boolean }).__installed))).toBe(true);
  await expect(install).toBeHidden();
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
