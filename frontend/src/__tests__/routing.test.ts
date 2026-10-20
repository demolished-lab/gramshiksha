import { describe, expect, it } from 'vitest';
import { parseRoute, pathFor } from '../routing';

describe('deep-link parsing', () => {
  it('accepts canonical paths and legacy hash links for courses and lessons', () => {
    expect(parseRoute('/course/42')).toEqual({ page: 'course', id: 42 });
    expect(parseRoute('/lesson/7')).toEqual({ page: 'lesson', id: 7 });
    expect(parseRoute('#/course/42')).toEqual({ page: 'course', id: 42 });
    expect(parseRoute('#/lesson/7')).toEqual({ page: 'lesson', id: 7 });
  });

  it.each(['/course', '/course/foo', '/lesson/0', '/lesson/-2', '/lesson/4/extra', '/course/99999999999999999999'])(
    'routes malformed parameterized path %s to not-found', (path) => {
      expect(parseRoute(path)).toEqual({ page: 'not-found' });
    },
  );

  it('keeps role-specific login and ordinary paths intact', () => {
    expect(parseRoute('/login/teacher')).toEqual({ page: 'login', sub: 'teacher' });
    expect(parseRoute('/explore/8')).toEqual({ page: 'explore', id: 8 });
    expect(parseRoute('/privacy')).toEqual({ page: 'privacy', id: undefined });
    expect(parseRoute('')).toEqual({ page: 'home', id: undefined });
    expect(parseRoute('/')).toEqual({ page: 'home', id: undefined });
  });

  it('builds canonical paths, never /home or a hash', () => {
    expect(pathFor('home')).toBe('/');
    expect(pathFor('')).toBe('/');
    expect(pathFor('courses')).toBe('/courses');
    expect(pathFor('course', 42)).toBe('/course/42');
    expect(pathFor('lesson', 7)).toBe('/lesson/7');
  });
});
