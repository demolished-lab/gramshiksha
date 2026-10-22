import { expect, test } from '@playwright/test';

/**
 * Mobile sign-up regression cover.
 *
 * A phone keyboard can capitalise the first letter of an email address. The
 * old flow posted that mixed-case value to /auth/register, then tried a second
 * /auth/token call that lowercased it — so the account was created but the new
 * learner stayed on the form with "Incorrect email or password". This test
 * drives the real mobile layout, asserts the payload is normalised, and proves
 * the registration session is used directly (no second credential request).
 */
test('mobile sign-up normalises the email and enters without a second login', async ({ page }) => {
  let registerBody: Record<string, unknown> | null = null;
  let tokenCalls = 0;

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith('/auth/register')) {
      registerBody = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 91,
          email: 'mobile.user@example.com',
          access_token: 'mobile-register-token',
          token_type: 'bearer',
          role: 'student',
          role_status: 'active',
          name: 'Mobile Learner',
          lang_pref: 'en',
          class_grade: 8,
          board: 'Maharashtra SSC',
          xp: 0,
          streak_days: 0,
        }),
      });
      return;
    }
    if (url.pathname.endsWith('/auth/token')) {
      tokenCalls += 1;
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"unexpected"}' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/login/student');
  await page.getByRole('button', { name: /create a free account/i }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: /sign up/i })).toBeVisible();
  await dialog.getByLabel('Name').fill('  Mobile Learner  ');
  await dialog.getByLabel('Email').fill('Mobile.User@Example.COM');
  await dialog.getByLabel('Password').fill('Passw0rd@1');

  await dialog.getByRole('button', { name: /^sign up$/i }).click();

  await expect(page).toHaveURL(/\/textbooks$/);
  expect(registerBody).toMatchObject({
    email: 'mobile.user@example.com',
    name: 'Mobile Learner',
    role: 'student',
    class_grade: 8,
  });
  expect(tokenCalls).toBe(0);
  await expect.poll(() => page.evaluate(() => localStorage.getItem('gs_token')))
    .toBe('mobile-register-token');
});

test('mobile sign-up keeps the submit disabled until the password is long enough', async ({ page }) => {
  await page.route('**/api/**', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: '[]',
  }));

  await page.goto('/login/student');
  await page.getByRole('button', { name: /create a free account/i }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Name').fill('Short Password');
  await dialog.getByLabel('Email').fill('short@example.com');
  await dialog.getByLabel('Password').fill('short');

  await expect(dialog.getByRole('button', { name: /^sign up$/i })).toBeDisabled();
  await expect(dialog.getByText(/at least 8 characters/i)).toBeVisible();

  await dialog.getByLabel('Password').fill('long-enough');
  await expect(dialog.getByRole('button', { name: /^sign up$/i })).toBeEnabled();
});
