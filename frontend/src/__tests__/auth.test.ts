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
  removeDownload, saveDownload, saveSession,
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
