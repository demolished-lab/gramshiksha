/**
 * Every literal `t('key')` in the app must exist in the dictionary.
 *
 * `t()` returns the key itself when it does not know it, so a missing string
 * ships as visible gibberish ("needLogin") instead of failing the build.
 * This scans the sources for literal keys and asserts each one resolves.
 * Dynamic calls (`t(route.page)`) are not literals and are skipped.
 */
import { describe, expect, it } from 'vitest';
import { hasString, t } from '../i18n';

const sources = import.meta.glob(
  ['../**/*.tsx', '../**/*.ts', '!../__tests__/**'],
  { query: '?raw', import: 'default', eager: true },
) as Record<string, string>;

describe('i18n dictionary covers the app', () => {
  it('has a translation for every literal key used in the UI', () => {
    const missing = new Set<string>();
    for (const [file, code] of Object.entries(sources)) {
      for (const match of code.matchAll(/\bt\(\s*'([^']+)'/g)) {
        const key = match[1];
        if (!hasString(key)) missing.add(`${key} (${file})`);
      }
    }
    expect([...missing]).toEqual([]);
  });

  it('translates the reader error states in all three languages', () => {
    expect(t('chapterUnavailable', 'en')).not.toBe('chapterUnavailable');
    expect(t('chapterUnavailable', 'hi')).not.toBe('chapterUnavailable');
    expect(t('chapterUnavailable', 'mr')).not.toBe('chapterUnavailable');
    expect(t('chapterMissing', 'en')).not.toBe('chapterMissing');
    expect(t('chapterMissing', 'hi')).not.toBe('chapterMissing');
    expect(t('chapterMissing', 'mr')).not.toBe('chapterMissing');
  });
});
