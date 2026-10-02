import type { Availability, AvailabilitySubject, Lang } from './types';

/** Subjects worth showing for one medium: has a book in that medium (or in
 * any medium when `lang` is '' = all), or has actual lessons. A subject with
 * nothing is never offered — the catalog stops pretending. */
export const visibleSubjects = (a: Availability, lang: string): AvailabilitySubject[] =>
  a.subjects.filter((s) => (
    lang
      ? (s.books_by_lang[lang] ?? 0) > 0
      : Object.keys(s.books_by_lang).length > 0
  ) || s.courses > 0);

/** Localized subject name with fallback to English when no translation
 * row exists for this (board, class). */
export const subjectLabel = (s: AvailabilitySubject, lang: Lang): string => {
  if (lang === 'hi' && s.name_hi) return s.name_hi;
  if (lang === 'mr' && s.name_mr) return s.name_mr;
  return s.name;
};

/** Book count for one medium ('' = every medium). */
export const booksIn = (s: AvailabilitySubject, lang: string): number =>
  lang
    ? (s.books_by_lang[lang] ?? 0)
    : Object.values(s.books_by_lang).reduce((n, c) => n + c, 0);
