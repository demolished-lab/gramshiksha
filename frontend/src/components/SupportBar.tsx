import { useEffect, useState } from 'react';
import { fetchGrowthConfig, OFF_CONFIG, type GrowthConfig } from '../growth';

/** Money slots. Each section renders ONLY when its backend key is set —
 *  with everything unconfigured this component outputs nothing at all. */
export default function SupportBar() {
  const [cfg, setCfg] = useState<GrowthConfig>(OFF_CONFIG);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    fetchGrowthConfig().then((c) => { setCfg(c); setLoaded(true); });
  }, []);
  if (!loaded) return null;

  const hasDonate = !!cfg.donate;
  const hasAffiliates = cfg.affiliates.length > 0;
  const hasSponsor = !!cfg.sponsor;
  const hasPremium = !!cfg.premium_url;
  if (!hasDonate && !hasAffiliates && !hasSponsor && !hasPremium) return null;

  const card: React.CSSProperties = {
    border: '1px solid #e2e8f0', borderRadius: 12, padding: '12px 14px', marginTop: 12, background: '#fff',
  };
  return (
    <section aria-label="Support GramShiksha">
      {hasDonate && (
        <div className="card" style={card}>
          <strong>❤️ Keep GramShiksha free</strong>
          <p className="muted" style={{ margin: '6px 0' }}>
            Student donations pay the server bills so learning stays ₹0 forever.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {cfg.donate!.upi && <span className="muted">UPI: <strong>{cfg.donate!.upi}</strong></span>}
            {cfg.donate!.url && (
              <a className="btn accent" href={cfg.donate!.url} target="_blank" rel="noopener sponsored">
                Donate
              </a>
            )}
          </div>
        </div>
      )}
      {hasPremium && (
        <div className="card" style={card}>
          <strong>⭐ GramShiksha Premium</strong>
          <p className="muted" style={{ margin: '6px 0' }}>
            Support the mission and unlock premium perks. Free learning never goes away.
          </p>
          <a className="btn accent" href={cfg.premium_url!} target="_blank" rel="noopener">
            Get Premium
          </a>
        </div>
      )}
      {hasAffiliates && (
        <div className="card" style={card}>
          <strong>📚 Recommended for students</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>
            {cfg.affiliates.map((a) => (
              <li key={a.url}>
                <a href={a.url} target="_blank" rel="noopener sponsored nofollow">{a.name}</a>
              </li>
            ))}
          </ul>
        </div>
      )}
      {hasSponsor && (
        <div className="card muted" style={{ ...card, fontSize: 13 }}>
          Sponsored: <a href={cfg.sponsor!.url} target="_blank" rel="noopener sponsored nofollow">{cfg.sponsor!.text}</a>
        </div>
      )}
    </section>
  );
}
