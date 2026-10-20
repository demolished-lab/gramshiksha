import { describe, expect, it } from 'vitest';
import { canonicalUrl, normalizePath, seoForPath } from '../seo';

describe('SEO route table', () => {
  it('normalises paths and builds one canonical URL shape', () => {
    expect(normalizePath('')).toBe('/');
    expect(normalizePath('/courses/?ref=GS0001')).toBe('/courses');
    expect(normalizePath('courses')).toBe('/courses');
    expect(canonicalUrl('/courses/')).toBe('https://gramshiksha-academy.vercel.app/courses');
    expect(canonicalUrl('/')).toBe('https://gramshiksha-academy.vercel.app/');
  });

  it('has unique, indexable metadata for every public route', () => {
    const paths = [
      '/', '/courses', '/materials', '/textbooks', '/practice', '/explore',
      ...Array.from({ length: 12 }, (_, i) => `/explore/${i + 1}`),
      '/about', '/contact', '/privacy', '/terms',
    ];
    const titles = paths.map((path) => seoForPath(path)?.title ?? '');
    const descriptions = paths.map((path) => seoForPath(path)?.description ?? '');
    expect(new Set(titles).size).toBe(paths.length);
    expect(new Set(descriptions).size).toBe(paths.length);
    for (const path of paths) {
      const entry = seoForPath(path);
      expect(entry, `missing SEO entry for ${path}`).not.toBeNull();
      expect(entry?.robots).toContain('index');
      expect(entry?.sitemap).toBe(true);
    }
  });

  it('expands class pages and rejects classes outside 1-12', () => {
    expect(seoForPath('/explore/8')?.title).toContain('Class 8');
    expect(seoForPath('/explore/8')?.h1).toBe('Class 8 Courses, Lessons & Practice');
    expect(seoForPath('/explore/13')).toBeNull();
    expect(seoForPath('/explore/0')).toBeNull();
    expect(seoForPath('/explore/abc')).toBeNull();
  });

  it('keeps private and dynamic screens out of the index', () => {
    for (const path of ['/dashboard', '/progress', '/downloads', '/teacher',
      '/parent', '/admin', '/login', '/login/student', '/doubts', '/course/42', '/lesson/7']) {
      expect(seoForPath(path)?.robots, path).toContain('noindex');
    }
    expect(seoForPath('/course/42')?.sitemap).toBeUndefined();
    expect(seoForPath('/no-such-page')).toBeNull();
  });

  it('gives the legal pages real search metadata', () => {
    for (const path of ['/about', '/contact', '/privacy', '/terms']) {
      const entry = seoForPath(path);
      expect(entry?.title).toMatch(/GramShiksha Academy|Privacy Policy|Terms of Use/);
      expect(entry?.description.length).toBeGreaterThan(80);
      expect(entry?.schema).not.toBeNull();
    }
  });
});
