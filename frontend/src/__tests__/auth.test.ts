/**
 * Session and offline-storage behaviour. The interesting contract here is
 * logout: cached `/api` responses live in the Cache Storage API and are keyed
 * by URL, not by user, so on a shared phone they must be dropped or the next
 * account can read the previous one's dashboards offline.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LoginResponse } from '../types';
import {
  clearCachedApi, clearQueue, enqueue, getDownloads, getQueue, getUser, logout,
  refreshUser, removeDownload, saveDownload, saveSession,
} from '../auth';

const login: LoginResponse = {
  access_token: 'tok',
  token_type: 'bearer',
  role: 'student',
  name: 'Asha',
  lang_pref: 'hi',
  class_grade: 8,
  board: 'Maharashtra SSC',
  xp: 120,
  streak_days: 3,
};

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('session', () => {
  it('round-trips the signed-in user and drops it on logout', () => {
    saveSession(login);

    expect(getUser()).toMatchObject({ name: 'Asha', role: 'student', xp: 120, streak_days: 3 });
    expect(localStorage.getItem('gs_token')).toBe('tok');
    expect(localStorage.getItem('gs_lang')).toBe('hi'); // lang_pref is honoured

    logout();

    expect(getUser()).toBeNull();
    expect(localStorage.getItem('gs_token')).toBeNull();
  });

  it('persists role_status so the UI can show the approval notice right away', () => {
    saveSession({ ...login, role: 'teacher', role_status: 'pending' });
    expect(getUser()?.role_status).toBe('pending');
  });

  it('treats a session stored before the approval workflow as approved', () => {
    // Old sessions have no role_status at all. Reading it as `pending` would
    // suddenly lock every existing teacher out of their own dashboard, so an
    // absent status must mean approved.
    localStorage.setItem('gs_user', JSON.stringify({ name: 'Asha', role: 'teacher' }));
    expect(getUser()?.role_status).toBeUndefined();
  });

  it('refreshUser keeps role_status — the approval re-check depends on it', () => {
    saveSession(login);
    // What ApprovalNotice's "Check approval status" button writes back after
    // /auth/me reports the admin approved the account.
    refreshUser({
      id: 1, email: 'teacher@x.in', name: 'Asha', role: 'teacher', role_status: 'active',
      lang_pref: 'en', class_grade: 8, board: null, school_id: null, xp: 130,
      streak_days: 4, profile_pic: null,
    });

    expect(getUser()).toMatchObject({ role: 'teacher', role_status: 'active', xp: 130 });
  });

  it('returns null instead of throwing on corrupt stored user json', () => {
    localStorage.setItem('gs_user', '{not json');
    expect(getUser()).toBeNull();
  });
});

describe('offline queue', () => {
  it('persists and clears progress recorded while offline', () => {
    expect(getQueue()).toEqual([]);

    enqueue({ kind: 'lesson_complete', lesson_id: 5, payload: { xp: 10 } });
    enqueue({ kind: 'practice_answer', question_id: 9, payload: { answer: 2 } });

    expect(getQueue()).toHaveLength(2);
    expect(getQueue()[0]).toMatchObject({ lesson_id: 5 });

    clearQueue();
    expect(getQueue()).toEqual([]);
  });
});

describe('downloads', () => {
  it('saves and removes offline copies by material id', () => {
    saveDownload({ material_id: 1, title: 'Notes', saved_at: '2026-01-01T00:00:00Z' });
    saveDownload({ material_id: 2, title: 'Slides', saved_at: '2026-01-02T00:00:00Z' });
    expect(getDownloads()).toHaveLength(2);

    removeDownload(1);
    expect(getDownloads().map((d) => d.material_id)).toEqual([2]);
  });
});

describe('clearCachedApi', () => {
  it('removes cached API responses but keeps the app shell', async () => {
    const deleted: string[] = [];
    const entries: Record<string, string[]> = {
      'gramshiksha-v3': [
        'https://app.example/api/progress/summary',
        'https://app.example/api/auth/me',
        'https://app.example/learn/3',
        'https://app.example/index.html',
      ],
    };
    vi.stubGlobal('caches', {
      keys: async () => Object.keys(entries),
      open: async (name: string) => ({
        keys: async () => (entries[name] ?? []).map((url) => ({ url })),
        delete: async (req: { url: string }) => {
          deleted.push(req.url);
          return true;
        },
      }),
    });

    await clearCachedApi();

    expect(deleted).toEqual([
      'https://app.example/api/progress/summary',
      'https://app.example/api/auth/me',
    ]);
  });

  it('resolves quietly when the Cache API is unavailable', async () => {
    await expect(clearCachedApi()).resolves.toBeUndefined();
  });
});
