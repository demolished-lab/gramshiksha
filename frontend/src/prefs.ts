/** Cross-page filter memory: a student picks class/board/medium once on the
 * explore hub, and every page they jump into opens pre-filtered to that
 * choice instead of starting back at "all of everything". Session-scoped —
 * a new tab starts fresh, nothing sticks after logout-equivalent reloads. */

const TB_KEY = 'gs_tb_pref';
const COURSES_KEY = 'gs_courses_pref';

export interface TextbookPref {
  grade: number;
  board: string;
  subject?: string;
  lang?: string;
  /** A title to hand straight to the Smart Book Finder — set by "Find this
   * book" on a Monthly Reading List pick so the student lands on the page
   * with the search already filled and running. */
  q?: string;
  /** A reading-list pick whose catalog row is readable: land on the library
   * with that book already open in the in-app reader. */
  open?: number;
}

export interface CoursesPref {
  grade: number;
  board: string;
  subjectId?: number;
}

const write = (key: string, value: unknown): void => {
  try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
};

/** Write-once-and-consume: taking a pref clears it so a later unrelated
 * visit to the same page isn't haunted by an old filter choice. */
const take = <T>(key: string): T | null => {
  try {
    const raw = sessionStorage.getItem(key);
    sessionStorage.removeItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};

export const setTextbookPref = (p: TextbookPref): void => write(TB_KEY, p);
export const takeTextbookPref = (): TextbookPref | null => take<TextbookPref>(TB_KEY);

export const setCoursesPref = (p: CoursesPref): void => write(COURSES_KEY, p);
export const takeCoursesPref = (): CoursesPref | null => take<CoursesPref>(COURSES_KEY);

/** Explore hub remembers its own last class/board for the whole session. */
const EXPLORE_KEY = 'gs_explore';
export interface ExplorePref { grade: number; board: string }
export const setExplorePref = (p: ExplorePref): void => write(EXPLORE_KEY, p);
export const peekExplorePref = (): ExplorePref | null => {
  try {
    const raw = sessionStorage.getItem(EXPLORE_KEY);
    return raw ? (JSON.parse(raw) as ExplorePref) : null;
  } catch {
    return null;
  }
};
