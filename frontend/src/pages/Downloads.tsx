import { useEffect, useState } from 'react';
import { getDownloads, getQueue, type DownloadEntry } from '../auth';
import { t } from '../i18n';
import { openOfflineMaterial, removeOfflineMaterial } from '../offlineMaterials';
import { syncQueuedProgress } from '../offlineSync';
import type { Lang } from '../types';

export default function Downloads({ lang, go }: { lang: Lang; go: (p: string, id?: number) => void }) {
  const [items, setItems] = useState<DownloadEntry[]>([]);
  const [queue, setQueue] = useState<ReturnType<typeof getQueue>>([]);
  const [msg, setMsg] = useState('');
  const [msgFailed, setMsgFailed] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [fileError, setFileError] = useState('');
  const [openingId, setOpeningId] = useState<number | null>(null);

  const refresh = () => { setItems(getDownloads()); setQueue(getQueue()); };
  useEffect(() => { refresh(); }, []);

  const sync = async () => {
    if (syncing) return;
    setSyncing(true);
    setMsg('');
    setMsgFailed(false);
    try {
      const result = await syncQueuedProgress();
      refresh();
      if (result.synced && result.failed) {
        setMsgFailed(true);
        setMsg(t('syncPartial', lang).replace('{done}', String(result.synced)).replace('{left}', String(result.failed)));
      } else if (result.synced) {
        setMsg(t('syncComplete', lang).replace('{n}', String(result.synced)));
      } else if (result.failed) {
        setMsgFailed(true);
        setMsg(t('syncFailed', lang).replace('{n}', String(result.failed)));
      }
    } catch (e) {
      setMsgFailed(true);
      setMsg(e instanceof Error ? e.message : String(e));
    } finally { setSyncing(false); }
  };

  const openFile = async (id: number) => {
    setOpeningId(id);
    setFileError('');
    try { await openOfflineMaterial(id); }
    catch (e) { setFileError(e instanceof Error ? e.message : String(e)); }
    finally { setOpeningId(null); }
  };

  const removeFile = async (id: number) => {
    await removeOfflineMaterial(id);
    refresh();
  };

  return (
    <div>
      <h1>📥 {t('downloads', lang)}</h1>
      {msg && <p className={msgFailed ? 'error' : 'success'} role="status">{msg}</p>}
      {queue.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <strong>⏳ {queue.length} {t('offlineChangesWaiting', lang)}</strong>
          <p className="muted">{t('offlineChangesHint', lang)}</p>
          <button className="btn small" disabled={syncing || !navigator.onLine} onClick={sync}>
            {syncing ? t('syncing', lang) : `🔄 ${t('syncNow', lang)}`}
          </button>
        </div>
      )}

      {!items.length && (
        <div className="empty-state">
          <div className="icon">📥</div>
          <p>{t('noOfflineDownloads', lang)}</p>
          <button className="btn ghost" onClick={() => go('materials')}>{t('materials', lang)}</button>
        </div>
      )}

      {fileError && <p className="error" role="alert">{fileError}</p>}
      {items.map((d) => (
        <div className="card" key={d.material_id}>
          <strong>{d.title}</strong>
          <div className="muted">
            {new Date(d.saved_at).toLocaleString(lang === 'hi' ? 'hi-IN' : lang === 'mr' ? 'mr-IN' : 'en-IN')}
            {d.size_bytes !== undefined && ` · ${(d.size_bytes / (1024 * 1024)).toFixed(1)} MB`}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <button className="btn small" disabled={openingId === d.material_id} onClick={() => openFile(d.material_id)}>
              {openingId === d.material_id ? t('openingOffline', lang) : t('openOffline', lang)}
            </button>
            <button className="btn small ghost" onClick={() => { void removeFile(d.material_id); }}>🗑 {t('remove', lang)}</button>
          </div>
        </div>
      ))}
    </div>
  );
}
