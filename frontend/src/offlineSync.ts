import { apiSyncQueue } from './api';
import { getQueue, getToken, getUser, offlineStorageScope, settleQueue } from './auth';

export interface SyncSummary {
  attempted: number;
  synced: number;
  failed: number;
  pending: number;
}

let activeSync: { scope: string; promise: Promise<SyncSummary> } | null = null;

/**
 * Send only the current student's pending events. The API returns a result for
 * every event, so a failed/unsupported item remains queued for a later retry.
 */
export function syncQueuedProgress(): Promise<SyncSummary> {
  const scope = offlineStorageScope();
  const pending = getQueue();
  if (!scope || !getToken() || getUser()?.role !== 'student'
      || (typeof navigator !== 'undefined' && !navigator.onLine) || !pending.length) {
    return Promise.resolve({ attempted: 0, synced: 0, failed: 0, pending: pending.length });
  }
  if (activeSync?.scope === scope) return activeSync.promise;

  const batch = pending.map((item) => {
    const payload = { ...item } as Record<string, unknown>;
    payload.event_id = item.queue_id;
    delete payload.queue_id;
    return payload;
  });
  const batchIds = pending.map((item) => item.queue_id);
  const promise = apiSyncQueue(batch).then((response) => {
    // A login switch while the request was in flight must never settle another
    // account's queue. apiSyncQueue captures its Authorization header at call.
    if (offlineStorageScope() !== scope) {
      return { attempted: batch.length, synced: 0, failed: batch.length, pending: getQueue().length };
    }
    const failedIds = batchIds.filter((_, index) => response.synced?.[index]?.ok !== true);
    settleQueue(batchIds, failedIds);
    return {
      attempted: batch.length,
      synced: batch.length - failedIds.length,
      failed: failedIds.length,
      pending: getQueue().length,
    };
  }).finally(() => {
    if (activeSync?.promise === promise) activeSync = null;
  });
  activeSync = { scope, promise };
  return promise;
}
