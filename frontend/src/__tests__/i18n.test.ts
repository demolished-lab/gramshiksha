/**
 * i18n helpers that the reading list relies on: month labels come from Intl
 * (so no hand-kept month table drifts across en/hi/mr) and unknown keys fall
 * through as themselves rather than crashing the page.
 */
import { describe, expect, it } from 'vitest';
import { monthLabel, t } from '../i18n';

describe('monthLabel', () => {
  it('renders an ISO month in the reader language', () => {
    expect(monthLabel('2026-10', 'en')).toBe('October 2026');
    expect(monthLabel('2026-01', 'en')).toBe('January 2026');
    // Hindi and Marathi go through their own locales, not the English table.
    expect(monthLabel('2026-10', 'hi')).not.toBe('October 2026');
    expect(monthLabel('2026-10', 'mr')).not.toBe('October 2026');
    expect(monthLabel('2026-10', 'mr')).not.toBe('2026-10');
  });

  it('returns the input untouched when it is not a real month', () => {
    expect(monthLabel('2026-13', 'en')).toBe('2026-13');   // month out of range
    expect(monthLabel('soon', 'en')).toBe('soon');
    expect(monthLabel('', 'en')).toBe('');
  });
});

describe('t', () => {
  it('picks the requested language and falls back to the key itself', () => {
    expect(t('read', 'en')).toBe('Read');
    expect(t('read', 'mr')).toBe('वाचा');
    expect(t('no-such-key', 'en')).toBe('no-such-key');
  });
});
