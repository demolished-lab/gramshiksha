/**
 * Explore-hub helpers: the filters must only ever offer what exists.
 * - visibleSubjects: a medium chip's subject list contains subjects with a
 *   book in that medium (or any book under 'all') or real lessons — never a
 *   dead card.
 * - subjectLabel: falls back to English when a (board, class) has no
 *   translation row for the subject.
 * - prefs: take-once semantics, so a later unrelated visit isn't haunted by
 *   an old filter choice.
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { booksIn, subjectLabel, visibleSubjects } from '../catalog';
import {
  peekExplorePref, setCoursesPref, setExplorePref, setTextbookPref,
  takeCoursesPref, takeTextbookPref,
} from '../prefs';
import type { Availability } from '../types';

const avail: Availability = {
  board: 'Maharashtra SSC',
  class_grade: 7,
  mediums: [
    { lang: 'en', label: 'English', books: 2, subjects: 1 },
    { lang: 'mr', label: 'मराठी', books: 3, subjects: 2 },
  ],
  subjects: [
    { name: 'Mathematics', name_hi: 'गणित', name_mr: 'गणित', subject_id: 1,
      books_by_lang: { en: 1, mr: 2 }, courses: 1, lessons: 4, course_ids: [10] },
    { name: 'Marathi', name_hi: 'मराठी', name_mr: 'मराठी', subject_id: null,
      books_by_lang: { mr: 1 }, courses: 0, lessons: 0, course_ids: [] },
    { name: 'Craft', name_hi: null, name_mr: null, subject_id: 2,
      books_by_lang: {}, courses: 2, lessons: 6, course_ids: [11, 12] },
  ],
};

beforeEach(() => {
  sessionStorage.clear();
});

describe('visibleSubjects', () => {
  it('keeps only subjects with a book in the selected medium', () => {
    const mr = visibleSubjects(avail, 'mr').map((s) => s.name);
    expect(mr).toEqual(['Mathematics', 'Marathi', 'Craft']);
    const en = visibleSubjects(avail, 'en').map((s) => s.name);
    // Marathi has no English book; Craft still qualifies via lessons.
    expect(en).toEqual(['Mathematics', 'Craft']);
  });

  it("under 'all mediums' keeps any book or lessons", () => {
    const all = visibleSubjects(avail, '').map((s) => s.name);
    expect(all).toEqual(['Mathematics', 'Marathi', 'Craft']);
  });

  it('drops subjects with neither books nor lessons', () => {
    const empty: Availability = {
      ...avail,
      subjects: [...avail.subjects,
        { name: 'Ghost', name_hi: null, name_mr: null, subject_id: null,
          books_by_lang: {}, courses: 0, lessons: 0, course_ids: [] }],
    };
    expect(visibleSubjects(empty, 'en').map((s) => s.name)).not.toContain('Ghost');
  });
});

describe('subjectLabel and booksIn', () => {
  it('uses the translation when present, English otherwise', () => {
    expect(subjectLabel(avail.subjects[0], 'hi')).toBe('गणित');
    expect(subjectLabel(avail.subjects[0], 'mr')).toBe('गणित');
    expect(subjectLabel(avail.subjects[0], 'en')).toBe('Mathematics');
    expect(subjectLabel(avail.subjects[2], 'mr')).toBe('Craft'); // null translation
  });

  it('counts one medium or every medium', () => {
    expect(booksIn(avail.subjects[0], 'mr')).toBe(2);
    expect(booksIn(avail.subjects[0], 'ur')).toBe(0); // medium not published here
    expect(booksIn(avail.subjects[0], '')).toBe(3);
    expect(booksIn(avail.subjects[2], '')).toBe(0);
  });
});

describe('filter prefs', () => {
  it('textbook pref is taken once and then gone', () => {
    setTextbookPref({ grade: 7, board: 'Maharashtra SSC', subject: 'Mathematics', lang: 'mr' });
    expect(takeTextbookPref()).toEqual(
      { grade: 7, board: 'Maharashtra SSC', subject: 'Mathematics', lang: 'mr' });
    expect(takeTextbookPref()).toBeNull();
  });

  it('courses pref round-trips, explore pref can be peeked repeatedly', () => {
    setCoursesPref({ grade: 10, board: 'CBSE', subjectId: 5 });
    expect(takeCoursesPref()).toEqual({ grade: 10, board: 'CBSE', subjectId: 5 });
    expect(takeCoursesPref()).toBeNull();

    setExplorePref({ grade: 4, board: 'Maharashtra HSC' });
    expect(peekExplorePref()).toEqual({ grade: 4, board: 'Maharashtra HSC' });
    expect(peekExplorePref()).toEqual({ grade: 4, board: 'Maharashtra HSC' });
  });
});
