import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiSyncQueue } from '../api';
import { enqueue, getQueue, saveSession } from '../auth';
import { syncQueuedProgress } from '../offlineSync';
import type { LoginResponse } from '../types';

vi.mock('../api', () => ({ apiSyncQueue: vi.fn() }));

const login: LoginResponse = {
  access_token: `header.${btoa(JSON.stringify({ sub: 'student@example.test' }))}.signature`,
  token_type: 'bearer', role: 'student', name: 'Asha', lang_pref: 'en',
  class_grade: 8, board: 'Maharashtra SSC', xp: 0, streak_days: 0,
};

beforeEach(() => {
  localStorage.clear();
  saveSession(login);
  vi.stubGlobal('navigator', { onLine: true });
  vi.mocked(apiSyncQueue).mockReset();
});

describe('syncQueuedProgress', () => {
  it('removes confirmed items and retains only failed items', async () => {
    enqueue({ kind: 'lesson_complete', lesson_id: 5, payload: { minutes: 10 } });
    enqueue({ kind: 'practice_answer', question_id: 9, payload: { answer: 1 } });
    const queued = getQueue();
    vi.mocked(apiSyncQueue).mockResolvedValue({ synced: [{ ok: true }, { ok: false }] });

    await expect(syncQueuedProgress()).resolves.toEqual({ attempted: 2, synced: 1, failed: 1, pending: 1 });
    expect(getQueue()).toHaveLength(1);
    expect(getQueue()[0]).toMatchObject({ kind: 'practice_answer', question_id: 9 });
    const sent = vi.mocked(apiSyncQueue).mock.calls[0][0] as Record<string, unknown>[];
    expect(sent).toHaveLength(2);
    expect(sent[0]).toMatchObject({ event_id: queued[0].queue_id, kind: 'lesson_complete', lesson_id: 5 });
    expect(sent[1]).toMatchObject({ event_id: queued[1].queue_id, kind: 'practice_answer', question_id: 9 });
    expect(sent[0]).not.toHaveProperty('queue_id');
  });

  it('keeps every item when the request fails', async () => {
    enqueue({ kind: 'lesson_complete', lesson_id: 5, payload: { minutes: 10 } });
    vi.mocked(apiSyncQueue).mockRejectedValue(new Error('network down'));
    await expect(syncQueuedProgress()).rejects.toThrow('network down');
    expect(getQueue()).toHaveLength(1);
  });

  it('keeps new work added after the request starts', async () => {
    enqueue({ kind: 'lesson_complete', lesson_id: 5, payload: { minutes: 10 } });
    let finish!: (value: { synced: { ok: boolean }[] }) => void;
    vi.mocked(apiSyncQueue).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const syncing = syncQueuedProgress();
    enqueue({ kind: 'lesson_complete', lesson_id: 6, payload: { minutes: 10 } });
    finish({ synced: [{ ok: true }] });

    await expect(syncing).resolves.toMatchObject({ synced: 1, pending: 1 });
    expect(getQueue().map((item) => item.lesson_id)).toEqual([6]);
  });
});
