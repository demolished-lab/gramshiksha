import type { Lang, LoginResponse, Me } from './types';

const TOKEN_KEY = 'gs_token';
const USER_KEY = 'gs_user';
const LANG_KEY = 'gs_lang';
const SAVER_KEY = 'gs_data_saver';
const CACHE_KEY = 'gs_lessons_cache';

export const getLang = (): Lang => ((localStorage.getItem(LANG_KEY) as Lang) || 'en');
export const setLang = (l: Lang) => localStorage.setItem(LANG_KEY, l);

export const dataSaver = (): boolean => localStorage.getItem(SAVER_KEY) === '1';
export const setDataSaver = (on: boolean) => localStorage.setItem(SAVER_KEY, on ? '1' : '0');

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export interface SessionUser {
  name: string;
  role: string;
  class_grade: number | null;
  board: string | null;
  xp: number;
  streak_days: number;
}

export function saveSession(tok: LoginResponse): void {
  localStorage.setItem(TOKEN_KEY, tok.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify({
    name: tok.name, role: tok.role, class_grade: tok.class_grade,
    board: tok.board, xp: tok.xp, streak_days: tok.streak_days,
  } satisfies SessionUser));
  if (tok.lang_pref) setLang(tok.lang_pref);
}

export function getUser(): SessionUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  } catch {
    return null;
  }
}

export function refreshUser(me: Me): void {
  localStorage.setItem(USER_KEY, JSON.stringify({
    name: me.name, role: me.role, class_grade: me.class_grade,
    board: me.board, xp: me.xp, streak_days: me.streak_days,
  }));
}

/**
 * Drop cached `/api` responses from the service worker.
 *
 * Cache entries are keyed by request URL, not by user — so on a shared phone
 * the next account could otherwise read the previous one's cached dashboards
 * and `/auth/me` while offline. Shell assets are left alone: they contain no
 * user data.
 */
export async function clearCachedApi(): Promise<void> {
  if (typeof caches === 'undefined') return;
  try {
    const names = await caches.keys();
    for (const name of names) {
      const cache = await caches.open(name);
      const requests = await cache.keys();
      await Promise.all(
        requests
          .filter((r) => {
            try {
              return new URL(r.url).pathname.startsWith('/api/');
            } catch {
              return false;
            }
          })
          .map((r) => cache.delete(r))
      );
    }
  } catch {
    /* storage unavailable (private mode) — nothing to clear */
  }
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  void clearCachedApi();
}

/** Offline lesson cache */
export function cacheLessons(json: string): void {
  try { localStorage.setItem(CACHE_KEY, json); } catch { /* full */ }
}
export const getCachedLessons = () => localStorage.getItem(CACHE_KEY);

/** Offline sync queue for progress made while offline */
const QUEUE_KEY = 'gs_sync_queue';

export interface QueueItem {
  kind: 'lesson_complete' | 'practice_answer';
  lesson_id?: number;
  question_id?: number;
  payload: Record<string, unknown>;
}

export function enqueue(item: QueueItem): void {
  const q = getQueue();
  q.push(item);
  try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch { /* full */ }
}

export function getQueue(): QueueItem[] {
  try {
    return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]') as QueueItem[];
  } catch {
    return [];
  }
}

export function clearQueue(): void {
  localStorage.removeItem(QUEUE_KEY);
}

/** Downloaded material index (My Downloads) */
const DL_KEY = 'gs_downloads';

export interface DownloadEntry {
  material_id: number;
  title: string;
  saved_at: string;
  text?: string; // cached text content for offline reading
}

export function saveDownload(entry: DownloadEntry): void {
  const list = getDownloads().filter((d) => d.material_id !== entry.material_id);
  list.push(entry);
  try { localStorage.setItem(DL_KEY, JSON.stringify(list)); } catch { /* full */ }
}

export function getDownloads(): DownloadEntry[] {
  try {
    return JSON.parse(localStorage.getItem(DL_KEY) || '[]') as DownloadEntry[];
  } catch {
    return [];
  }
}

export function removeDownload(id: number): void {
  localStorage.setItem(DL_KEY, JSON.stringify(getDownloads().filter((d) => d.material_id !== id)));
}
