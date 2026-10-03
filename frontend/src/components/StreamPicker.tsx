import { t } from '../i18n';
import type { AvailabilityStream, Lang } from '../types';

/** Stream chips for Classes 11-12 (Science / Commerce / Arts & Humanities /
 * Vocational). Renders nothing below class 11 — streams only exist where
 * they actually exist, so younger classes keep the flat subject list. */
const KEY: Record<string, string> = {
  science: 'streamScience',
  commerce: 'streamCommerce',
  arts: 'streamArts',
  vocational: 'streamVocational',
};

/** Translated stream name for badges and headings. */
export function streamName(code: string, lang: Lang): string {
  return KEY[code] ? t(KEY[code], lang) : code;
}

export default function StreamPicker({ lang, streams, value, onChange }: {
  lang: Lang; streams: AvailabilityStream[]; value: string;
  onChange: (code: string) => void;
}) {
  if (!streams.length) return null;
  return (
    <div className="tabs" role="tablist" aria-label={t('streamLabel', lang)}>
      <button type="button" role="tab" aria-selected={value === ''}
        className={value === '' ? 'active' : ''} onClick={() => onChange('')}>
        {t('streamAll', lang)}
      </button>
      {streams.map((s) => (
        <button key={s.code} type="button" role="tab" aria-selected={value === s.code}
          className={value === s.code ? 'active' : ''} onClick={() => onChange(s.code)}>
          {KEY[s.code] ? t(KEY[s.code], lang) : s.label_en} ({s.books})
        </button>
      ))}
    </div>
  );
}
