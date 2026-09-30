import { useEffect, useRef, useState } from 'react';
import { fetchGrowthConfig } from '../growth';

/** AdSense slot. Renders nothing until ADSENSE_CLIENT + ADSENSE_SLOT are
 *  set on the backend AND AdSense has approved the site — before that the
 *  layout is exactly as if ads never existed (no empty boxes, no CLS). */
export default function AdSlot({ format = 'auto' }: { format?: string }) {
  const [unit, setUnit] = useState<{ client: string; slot: string } | null>(null);
  const pushed = useRef(false);

  useEffect(() => {
    fetchGrowthConfig().then((c) => setUnit(c.ads));
  }, []);

  useEffect(() => {
    if (!unit || pushed.current) return;
    pushed.current = true;
    const scriptId = 'gs-adsense';
    const push = () => {
      try {
        ((window as unknown as { adsbygoogle?: unknown[] }).adsbygoogle ??= []).push({});
      } catch { /* ad blocker → stay invisible */ }
    };
    if (!document.getElementById(scriptId)) {
      const s = document.createElement('script');
      s.id = scriptId;
      s.async = true;
      s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${unit.client}`;
      s.crossOrigin = 'anonymous';
      s.onload = push;
      s.onerror = push;
      document.head.appendChild(s);
    } else {
      push();
    }
  }, [unit]);

  if (!unit) return null;
  return (
    <ins
      className="adsbygoogle"
      style={{ display: 'block', textAlign: 'center' }}
      data-ad-client={unit.client}
      data-ad-slot={unit.slot}
      data-ad-format={format}
      data-full-width-responsive="true"
    />
  );
}
