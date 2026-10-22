import { useEffect, useRef, useState } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

const DISMISS_KEY = 'gs_install_prompt_dismissed_v1';
const DISMISS_MS = 30 * 24 * 60 * 60 * 1000;

const standalone = (): boolean => {
  try {
    return window.matchMedia('(display-mode: standalone)').matches
      || Boolean((navigator as unknown as { standalone?: boolean }).standalone);
  } catch {
    return false;
  }
};

const iosDevice = (): boolean =>
  /iphone|ipad|ipod/i.test(navigator.userAgent) && !standalone();

const dismissedRecently = (): boolean => {
  try {
    const raw = localStorage.getItem(DISMISS_KEY);
    const at = raw ? Number(raw) : 0;
    return Number.isFinite(at) && at > 0 && Date.now() - at < DISMISS_MS;
  } catch {
    return false;
  }
};

/**
 * PWA install suggestion for Study Studio.
 *
 * Browsers only fire `beforeinstallprompt` when the app is installable, and
 * only the event's own `prompt()` may open the install dialog. A site can
 * never install an extension or an app silently. On iOS the event does not
 * exist, so we show the one manual step Safari requires.
 */
export default function InstallPrompt() {
  const [event, setEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [hidden, setHidden] = useState(true);
  const [ios, setIos] = useState(false);
  const dismissed = useRef(true);

  useEffect(() => {
    const isStandalone = standalone();
    dismissed.current = dismissedRecently();
    setIos(iosDevice());
    setHidden(isStandalone || dismissed.current);

    const onPrompt = (raw: Event) => {
      raw.preventDefault();
      if (standalone() || dismissed.current) return;
      setEvent(raw as BeforeInstallPromptEvent);
      setHidden(false);
    };
    const onInstalled = () => {
      setHidden(true);
      setEvent(null);
    };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  const dismiss = () => {
    dismissed.current = true;
    setHidden(true);
    setEvent(null);
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      // Private mode: the suggestion can reappear on the next visit.
    }
  };

  const install = async () => {
    if (!event) return;
    try {
      await event.prompt();
      const choice = await event.userChoice;
      if (choice.outcome === 'accepted') {
        setHidden(true);
        setEvent(null);
      }
    } catch {
      // The browser may withdraw a stale prompt. Keep the card so the learner
      // can use the browser menu instead.
    }
  };

  if (hidden || (!event && !ios)) return null;

  return (
    <aside className="install-card no-print" aria-label="Install GramShiksha">
      <div className="install-copy">
        <strong>Install GramShiksha</strong>
        <p>
          Faster opens, offline study packs, and one-tap sharing from
          NotebookLM on Android.
        </p>
        {!event && (
          <p className="install-ios">
            On iPhone or iPad: tap <strong>Share</strong> → <strong>Add to Home Screen</strong>.
          </p>
        )}
      </div>
      <div className="install-actions">
        {event && <button className="btn small" type="button" onClick={install}>Install app</button>}
        <button className="install-dismiss" type="button" onClick={dismiss} aria-label="Dismiss install suggestion">×</button>
      </div>
    </aside>
  );
}
