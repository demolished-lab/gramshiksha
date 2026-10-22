import { expect, test } from '@playwright/test';

test('the manifest is installable and keeps the Studio share target', async ({ request }) => {
  const response = await request.get('/manifest.webmanifest');
  expect(response.status()).toBe(200);
  const manifest = await response.json();
  expect(manifest.display).toBe('standalone');
  expect(manifest.start_url).toBe('/');
  const sizes = new Set((manifest.icons ?? []).map((icon: { sizes: string }) => icon.sizes));
  expect(sizes.has('192x192')).toBe(true);
  expect(sizes.has('512x512')).toBe(true);
  expect(manifest.share_target).toMatchObject({
    action: '/studio',
    method: 'GET',
    params: { title: 'title', text: 'text', url: 'url' },
  });
});
