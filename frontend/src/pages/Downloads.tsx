import { useEffect, useState } from 'react';
import { apiSyncQueue } from '../api';
import { clearQueue, getDownloads, getQueue, removeDownload, DownloadEntry } from '../auth';
import { t } from '../i18n';
import type { Lang } from '../types';

export default function Downloads({ lang, go }: { lang: Lang; go: (p: string, id?: number) => void }) {
  const [items, setItems] = useState<DownloadEntry[]>([]);
  const [queue, setQueue] = useState<ReturnType<typeof getQueue>>([]);
  const [msg, setMsg] = useState('');

  const refresh = () => { setItems(getDownloads()); setQueue(getQueue()); };
  useEffect(refresh, []);

  const sync = async () => {
    if (!queue.length) return;
    try {
      await apiSyncQueue(queue);
      clearQueue();
      setMsg('Progress synced ✓');
      refresh();
    } catch (e) { setMsg(String(e)); }
  };

  return (
    <div>
      <h1>📥 {t('downloads', lang)}</h1>

      {queue.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <strong>⏳ {queue.length} offline change{queue.length > 1 ? 's' : ''} waiting to sync</strong>
          <p className="muted">Completed while offline — will upload when you're back online.</p>
          <button className="btn small" onClick={sync}>🔄 Sync now</button>
          {msg && <p className="success">{msg}</p>}
        </div>
      )}

      {!items.length && (
        <div className="empty-state">
          <div className="icon">📥</div>
          <p>No downloads yet. Open any study material and tap Download — it will be available here even without internet.</p>
          <button className="btn ghost" onClick={() => go('materials')}>{t('materials', lang)}</button>
        </div>
      )}

      {items.map((d) => (
        <div className="card" key={d.material_id}>
          <strong>{d.title}</strong>
          <div className="muted">saved {new Date(d.saved_at).toLocaleString()}</div>
          {d.text && <p style={{ whiteSpace: 'pre-line', maxHeight: 120, overflow: 'hidden' }}>{d.text.slice(0, 300)}…</p>}
          <button className="btn small ghost" onClick={() => { removeDownload(d.material_id); refresh(); }}>🗑 Remove</button>
        </div>
      ))}
    </div>
  );
}
