import type { Availability, AvailabilitySubject, Lang } from './types';

/** Older API responses and cached fixtures used `books`; tolerate both so a
 * stale offline payload can never crash the Explore page. */
const booksByLang = (s: AvailabilitySubject): Record<string, number> =>
  s.books_by_lang ?? (s as AvailabilitySubject & { books?: Record<string, number> }).books ?? {};

/** Subjects worth showing for one medium: has a book in that medium (or in
 * any medium when `lang` is '' = all), or has actual lessons. A subject with
 * nothing is never offered — the catalog stops pretending. */
export const visibleSubjects = (a: Availability, lang: string): AvailabilitySubject[] =>
  a.subjects.filter((s) => {
    const books = booksByLang(s);
    return (lang ? (books[lang] ?? 0) > 0 : Object.keys(books).length > 0)
      || s.courses > 0;
  });

/** Localized subject name with fallback to English when no translation
 * row exists for this (board, class). */
export const subjectLabel = (s: AvailabilitySubject, lang: Lang): string => {
  if (lang === 'hi' && s.name_hi) return s.name_hi;
  if (lang === 'mr' && s.name_mr) return s.name_mr;
  return s.name;
};

/** Book count for one medium ('' = every medium). */
export const booksIn = (s: AvailabilitySubject, lang: string): number => {
  const books = booksByLang(s);
  return lang
    ? (books[lang] ?? 0)
    : Object.values(books).reduce((n, c) => n + c, 0);
};
