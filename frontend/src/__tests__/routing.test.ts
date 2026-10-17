import { describe, expect, it } from 'vitest';
import { parseRoute } from '../routing';

describe('deep-link parsing', () => {
  it('accepts valid positive course and lesson ids', () => {
    expect(parseRoute('#/course/42')).toEqual({ page: 'course', id: 42 });
    expect(parseRoute('#/lesson/7')).toEqual({ page: 'lesson', id: 7 });
  });

  it.each(['#/course', '#/course/foo', '#/lesson/0', '#/lesson/-2', '#/lesson/4/extra', '#/course/99999999999999999999'])(
    'routes malformed parameterized link %s to not-found', (hash) => {
      expect(parseRoute(hash)).toEqual({ page: 'not-found' });
    },
  );

  it('keeps role-specific login and ordinary routes intact', () => {
    expect(parseRoute('#/login/teacher')).toEqual({ page: 'login', sub: 'teacher' });
    expect(parseRoute('#/explore/8')).toEqual({ page: 'explore', id: 8 });
    expect(parseRoute('')).toEqual({ page: 'home', id: undefined });
  });
});
