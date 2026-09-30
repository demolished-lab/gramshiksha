import { useEffect, useState } from 'react';
import { fetchGrowthConfig, inviteLink, shareLinks, type GrowthConfig, OFF_CONFIG } from '../growth';
import { apiGrowthMe } from '../api';

/** Share row: native sheet where supported + WhatsApp/Telegram/X/Facebook.
 *  Logged-in users share their own invite link (?ref=code) so signups
 *  credit them on the leaderboard; visitors share the plain page URL. */
export default function ShareButtons({ text }: { text: string }) {
  const [cfg, setCfg] = useState<GrowthConfig>(OFF_CONFIG);
  const [code, setCode] = useState('');

  useEffect(() => {
    fetchGrowthConfig().then(setCfg);
    if (localStorage.getItem('gs_token')) {
      apiGrowthMe().then((me) => setCode(me.referral_code)).catch(() => {});
    }
  }, []);

  const pageUrl =
    code && cfg.referral_enabled ? inviteLink(code, cfg.site_url) : `${location.origin}${location.pathname}#/home`;
  const targets = shareLinks(pageUrl, text);

  const native = async () => {
    try {
      await (navigator as unknown as { share: (d: { title: string; text: string; url: string }) => Promise<void> })
        .share({ title: 'GramShiksha', text, url: pageUrl });
    } catch { /* dismissed → ignore */ }
  };

  const btn: React.CSSProperties = {
    border: '1px solid #cbd5e1', borderRadius: 20, padding: '6px 12px',
    background: '#fff', cursor: 'pointer', fontSize: 13, textDecoration: 'none', color: '#0f172a',
  };
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
      <span className="muted" style={{ fontSize: 13 }}>Share:</span>
      {targets.nativeAvailable && <button style={btn} onClick={native}>📤 Share</button>}
      <a style={btn} href={targets.whatsapp} target="_blank" rel="noopener">🟢 WhatsApp</a>
      <a style={btn} href={targets.telegram} target="_blank" rel="noopener">✈️ Telegram</a>
      <a style={btn} href={targets.x} target="_blank" rel="noopener">𝕏 Post</a>
      <a style={btn} href={targets.facebook} target="_blank" rel="noopener">📘 Facebook</a>
    </div>
  );
}
