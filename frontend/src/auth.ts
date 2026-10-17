import type { Lang, LoginResponse, Me, RoleStatus } from './types';

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
  /** Absent in sessions stored before the approval workflow shipped — an
   * account of unknown age is treated as approved, never as pending. */
  role_status?: RoleStatus;
  class_grade: number | null;
  board: string | null;
  xp: number;
  streak_days: number;
}

export function saveSession(tok: LoginResponse): void {
  localStorage.setItem(TOKEN_KEY, tok.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify({
    name: tok.name, role: tok.role, role_status: tok.role_status,
    class_grade: tok.class_grade, board: tok.board, xp: tok.xp,
    streak_days: tok.streak_days,
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
    name: me.name, role: me.role, role_status: me.role_status,
    class_grade: me.class_grade, board: me.board, xp: me.xp,
    streak_days: me.streak_days,
  }));
}

/**
 * Where a fresh authentication should drop the user (null = don't move).
 *
 * Students open straight into the e-book library — cover grid, orange
 * Download buttons, pre-filtered to their class/board on the page — because
 * "log in and see the books" is the product requirement. Only a login that
 * started from the landing/login screens redirects: a student who signs in
 * mid-browse (say, from #/courses) stays exactly where they were. Every
 * other role keeps the historical behaviour of no redirect.
 */
export function landingAfterAuth(
  role: string | null | undefined,
  routePage: string,
): string | null {
  return role === 'student' && (routePage === 'home' || routePage === 'login')
    ? 'textbooks'
    : null;
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

/** Stable, opaque account scope for offline records on shared devices. */
export function offlineStorageScope(): string | null {
  const token = getToken();
  if (!token) return null;
  let identity = token;
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const claims = JSON.parse(atob(payload.padEnd(Math.ceil(payload.length / 4) * 4, '='))) as { sub?: unknown };
    if (typeof claims.sub === 'string' && claims.sub) identity = claims.sub.toLowerCase();
  } catch { /* opaque fallback token still isolates this session */ }
  let a = 2166136261;
  let b = 5381;
  for (let i = 0; i < identity.length; i += 1) {
    const code = identity.charCodeAt(i);
    a = Math.imul(a ^ code, 16777619);
    b = Math.imul(b, 33) ^ code;
  }
  return `acct-${(a >>> 0).toString(36)}${(b >>> 0).toString(36)}`;
}

function scopedStorageKey(base: string): string | null {
  // Older releases wrote these stores without an owner. They cannot safely be
  // attributed on a shared phone, so discard them rather than expose them.
  try {
    localStorage.removeItem('gs_sync_queue');
    localStorage.removeItem('gs_downloads');
  } catch { /* storage unavailable */ }
  const scope = offlineStorageScope();
  return scope ? `${base}:${scope}` : null;
}

/** Offline sync queue for progress made while offline */
const QUEUE_KEY = 'gs_sync_queue';

export interface QueueItem {
  queue_id: string;
  kind: 'lesson_complete' | 'practice_answer';
  lesson_id?: number;
  question_id?: number;
  payload: Record<string, unknown>;
}

function queueId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function writeQueue(key: string, items: QueueItem[]): void {
  try {
    if (items.length) localStorage.setItem(key, JSON.stringify(items));
    else localStorage.removeItem(key);
  } catch { /* storage full or unavailable */ }
}

export function enqueue(item: Omit<QueueItem, 'queue_id'>): boolean {
  const key = scopedStorageKey(QUEUE_KEY);
  if (!key) return false;
  const q = getQueue();
  q.push({ ...item, queue_id: queueId() });
  writeQueue(key, q);
  return true;
}

export function getQueue(): QueueItem[] {
  const key = scopedStorageKey(QUEUE_KEY);
  if (!key) return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '[]') as Partial<QueueItem>[];
    if (!Array.isArray(parsed)) return [];
    const normalized = parsed.map((item) => ({ ...item, queue_id: item.queue_id || queueId() })) as QueueItem[];
    if (normalized.some((item, i) => item.queue_id !== parsed[i]?.queue_id)) writeQueue(key, normalized);
    return normalized;
  } catch {
    return [];
  }
}

export function clearQueue(): void {
  const key = scopedStorageKey(QUEUE_KEY);
  if (key) localStorage.removeItem(key);
}

/** Remove confirmed queue records while retaining failed and newly-added work. */
export function settleQueue(batchIds: string[], failedIds: string[]): void {
  const key = scopedStorageKey(QUEUE_KEY);
  if (!key) return;
  const batch = new Set(batchIds);
  const failed = new Set(failedIds);
  writeQueue(key, getQueue().filter((item) => !batch.has(item.queue_id) || failed.has(item.queue_id)));
}

/** Downloaded material index (My Downloads) */
const DL_KEY = 'gs_downloads';

export interface DownloadEntry {
  material_id: number;
  title: string;
  saved_at: string;
  mime_type?: string;
  size_bytes?: number;
}

export function saveDownload(entry: DownloadEntry): boolean {
  const key = scopedStorageKey(DL_KEY);
  if (!key) return false;
  const list = getDownloads().filter((d) => d.material_id !== entry.material_id);
  list.push(entry);
  try { localStorage.setItem(key, JSON.stringify(list)); return true; } catch { return false; }
}

export function getDownloads(): DownloadEntry[] {
  const key = scopedStorageKey(DL_KEY);
  if (!key) return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(parsed) ? parsed as DownloadEntry[] : [];
  } catch {
    return [];
  }
}

export function removeDownload(id: number): void {
  const key = scopedStorageKey(DL_KEY);
  if (key) localStorage.setItem(key, JSON.stringify(getDownloads().filter((d) => d.material_id !== id)));
}
