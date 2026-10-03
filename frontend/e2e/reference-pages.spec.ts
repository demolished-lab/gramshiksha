import { test, expect, Page } from '@playwright/test';

type Role = 'student' | 'teacher' | 'platform_admin' | 'parent';

const useSession = async (page: Page, role: Role = 'student') => {
  await page.addInitScript((userRole) => {
    localStorage.setItem('gs_token', 'reference-e2e-token');
    localStorage.setItem('gs_user', JSON.stringify({
      id: 42, name: 'Pravesh Kumar', email: 'student@example.com', role: userRole,
      role_status: 'active', lang_pref: 'en', class_grade: 10, board: 'CBSE', xp: 240, streak_days: 12,
    }));
  }, role);
};

const mockApi = async (page: Page) => {
  await page.route('**/api/**', async (route) => {
    const { pathname } = new URL(route.request().url());
    let body: unknown = {};
    if (pathname.endsWith('/learn/today')) body = {
      items: [{ slot: 1, kind: 'lesson', lesson_id: 1, label: 'Linear Equations', minutes: 15 }],
      study_minutes_today: 18, streak_days: 12, xp: 240,
    };
    else if (pathname.endsWith('/my/courses')) body = [{ id: 1, title_en: 'Mathematics', progress_pct: 68 }];
    else if (pathname.endsWith('/learn/weak-topics')) body = { weak: [], message: '' };
    else if (pathname.endsWith('/progress/summary')) body = {
      lessons_completed: 4, quizzes_taken: 8, quiz_avg_pct: 82, week_minutes: 50,
      streak_days: 12, badges: [], certificates: [],
    };
    else if (pathname.endsWith('/progress/weekly')) body = [];
    else if (pathname.endsWith('/notifications')) body = [];
    else if (pathname.endsWith('/growth/config')) body = {
      site_url: 'https://example.org', referral_enabled: true, ads: null, donate: null,
      affiliates: [], sponsor: null, premium_url: null,
    };
    else if (pathname.endsWith('/growth/reading-list')) body = [];
    else if (pathname.endsWith('/notes')) body = [];
    else if (pathname.endsWith('/learn/lessons/1')) body = {
      id: 1, course_id: 1, chapter_id: 1, title: 'Linear Equations', body: 'An equation says two expressions have the same value.',
      type: 'video', duration_min: 10, estimate_mb: 24, completed: false,
      video_url: 'https://example.org/lesson.mp4', video_url_low: 'https://example.org/lesson-low.mp4',
      audio_url: null, questions: [],
    };
    else if (pathname.endsWith('/learn/practice/questions')) body = [{
      id: 10, prompt: 'Which part of the plant is mainly responsible for photosynthesis?',
      options: ['Root', 'Stem', 'Leaf', 'Flower'], type: 'choice', difficulty: 'easy',
    }];
    else if (pathname.endsWith('/learn/practice/answer')) body = {
      correct: true, correct_answer: 2, explanation: 'Leaves contain chlorophyll and capture light energy.',
    };
    else if (pathname.endsWith('/doubts')) body = route.request().method() === 'POST' ? { id: 1 } : [];
    else if (pathname.endsWith('/teacher/overview')) body = {
      my_courses: [{ id: 1, title_en: 'Mathematics', students: 20 }],
      pending_material_reviews: 0, pending_doubts: 0, total_students: 120,
    };
    else if (pathname.endsWith('/teacher/students')) body = [];
    else if (pathname.endsWith('/school/stats')) body = { students: 2450, teachers: 120, lessons_completed_total: 5100 };
    else if (pathname.endsWith('/admin/users')) body = [];
    else if (pathname.endsWith('/learn/lessons/1/complete')) body = { ok: true, xp: 10, streak_days: 12 };
    else if (pathname.endsWith('/doubts/1/reply') || pathname.endsWith('/doubts/1/resolve')) body = { ok: true };
    else if (pathname.endsWith('/catalog/availability')) body = {
      board: 'CBSE', class_grade: 10,
      mediums: [{ lang: 'en', label: 'English', books: 5 }], streams: [],
      subjects: [{ name: 'Mathematics', subject_id: 1, lessons: 2, courses: 1, course_ids: [1], books: { en: 5 }, stream: '' }],
    };
    else if (pathname.endsWith('/meta/boards')) body = [{ id: 1, name: 'CBSE' }];
    else if (pathname.endsWith('/courses')) body = { total: 0, items: [] };
    else if (pathname.endsWith('/materials') || pathname.endsWith('/textbooks')) body = [];
    else if (pathname.endsWith('/parent/children')) body = [];
    else if (pathname.endsWith('/auth/me')) body = { id: 42, name: 'Pravesh Kumar', role: 'student', role_status: 'active' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
};

test('homepage matches the reference and loads original classroom photography', async ({ page }) => {
  await mockApi(page);
  await page.goto('/#/home');
  await expect(page.getByRole('heading', { name: /Quality education/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Choose your class/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Popular classes/i })).toBeVisible();
  const hero = page.getByRole('img', { name: /Students learning together/i });
  await expect(hero).toBeVisible();
  await expect.poll(() => hero.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(1000);
  await expect(page.locator('.band-image img')).toHaveCount(4);
});

test('registration form exposes the student class, board, and language choices', async ({ page }) => {
  await mockApi(page);
  await page.goto('/#/home');
  await page.getByRole('button', { name: /log in/i }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /sign up/i }).click();
  await expect(dialog.getByRole('heading', { name: /sign up/i })).toBeVisible();
  await expect(dialog.getByText('Role')).toBeVisible();
  await expect(dialog.getByText('Board')).toBeVisible();
  await expect(dialog.getByText(/Language/)).toBeVisible();
  await expect(dialog.locator('select')).toHaveCount(4);
});

test('student dashboard shows progress, learning cards, and recommendations on desktop and mobile', async ({ page }) => {
  await useSession(page);
  await mockApi(page);
  await page.goto('/#/dashboard');
  await expect(page.getByRole('heading', { name: /Pravesh Kumar/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Overall course progress/i })).toBeVisible();
  await expect(page.getByText('Mathematics', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: /Recommended for you/i })).toBeVisible();
  await expect(page.locator('.recommendation-thumb img').first()).toBeVisible();
});

test('course lesson has the video/notes layout and marks completion', async ({ page }) => {
  await useSession(page);
  await mockApi(page);
  await page.goto('/#/lesson/1');
  await expect(page.getByRole('heading', { name: 'Linear Equations' })).toBeVisible();
  await expect(page.getByRole('img', { name: /mathematics lesson/i })).toBeVisible();
  await expect(page.getByText('Key points')).toBeVisible();
  await page.getByRole('button', { name: /mark complete/i }).click();
  await expect(page.locator('p.success')).toContainText(/XP/i);
});

test('quiz page presents the reference question, review palette, and answer feedback', async ({ page }) => {
  await useSession(page);
  await mockApi(page);
  await page.goto('/#/practice');
  await expect(page.getByRole('heading', { name: /Practice/i })).toBeVisible();
  await expect(page.getByText(/mainly responsible for photosynthesis/i)).toBeVisible();
  await page.getByText('C. Leaf').click();
  await expect(page.getByText(/Leaves contain chlorophyll/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /review/i })).toBeVisible();
});

test('doubt solving supports search, filters, and asking a question', async ({ page }) => {
  await useSession(page);
  await mockApi(page);
  await page.goto('/#/doubts');
  await expect(page.getByRole('heading', { name: /Doubts/i })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Unanswered' })).toBeVisible();
  await page.getByPlaceholder(/Type your doubt/i).fill('How do I solve a linear equation?');
  await page.getByRole('button', { name: /Send/i }).click();
  await expect(page.getByPlaceholder(/Type your doubt/i)).toHaveValue('');
});

test('teacher and admin dashboards render their operational sections', async ({ page }) => {
  await useSession(page, 'teacher');
  await mockApi(page);
  await page.goto('/#/teacher');
  await expect(page.getByRole('heading', { name: /Welcome back/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Class performance/i })).toBeVisible();
  await page.evaluate(() => {
    localStorage.setItem('gs_user', JSON.stringify({ id: 1, name: 'Admin', email: 'admin@example.com', role: 'platform_admin', role_status: 'active' }));
    location.hash = '/admin';
  });
  await expect(page.getByRole('heading', { name: /Admin/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /staff/i })).toBeVisible();
});

test('login, language switching, offline notice, progress certificates, and 404 remain reachable', async ({ page }) => {
  await page.goto('/#/login/student');
  await expect(page.getByRole('heading', { name: /Student login/i })).toBeVisible();
  await page.getByRole('link', { name: /Teacher login/i }).click();
  await expect(page.getByRole('heading', { name: /Teacher login/i })).toBeVisible();
  await page.getByRole('link', { name: /Student login/i }).click();
  await page.getByRole('button', { name: /EN/i }).click();
  await expect.poll(() => page.evaluate(() => localStorage.getItem('gs_lang'))).toBe('hi');
  await page.evaluate(() => window.dispatchEvent(new Event('offline')));
  await expect(page.getByRole('status')).toContainText(/cached lessons remain/i);
  await useSession(page);
  await mockApi(page);
  await page.reload();
  await page.goto('/#/progress');
  await expect(page.getByRole('heading', { name: /Certificates|प्रमाणपत्र/i })).toBeVisible();
  await page.goto('/#/no-such-page');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
});
