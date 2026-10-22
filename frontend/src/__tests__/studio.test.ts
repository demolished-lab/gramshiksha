import { describe, expect, it } from 'vitest';
import { buildStudyPack, packHtml } from '../studio';

const NOTES = `Photosynthesis
Photosynthesis is the process by which green plants make their own food using sunlight, water and carbon dioxide.
Chlorophyll: the green pigment in leaves that absorbs sunlight.
Stomata: tiny pores on a leaf that let carbon dioxide in and oxygen out.
- Plants need sunlight, water and carbon dioxide.
- Chlorophyll absorbs light energy.
- Oxygen is released as a by-product.
- Glucose is stored as starch.
Question: Why are leaves green?
Answer: Chlorophyll reflects green light and absorbs the other colours.`;

describe('Study Studio text parser', () => {
  it('turns a copied study guide into a native pack', () => {
    const pack = buildStudyPack({ title: 'Photosynthesis', text: NOTES });
    expect(pack.title).toBe('Photosynthesis');
    expect(pack.overview).toMatch(/green plants/i);
    expect(pack.keyPoints).toContain('Plants need sunlight, water and carbon dioxide.');
    expect(pack.flashcards.some((card) => card.front === 'Chlorophyll')).toBe(true);
    expect(pack.flashcards.some((card) => card.front === 'Why are leaves green?')).toBe(true);
    expect(pack.quiz.length).toBeGreaterThan(0);
    expect(pack.checklist.length).toBeGreaterThan(0);
    expect(pack.id).toBeTruthy();
  });

  it('falls back to sentences when the import has no bullet points', () => {
    const pack = buildStudyPack({
      title: 'Water cycle',
      text: 'Water evaporates from the sea. It forms clouds in the sky. Rain falls back to the ground. The cycle repeats every day.',
    });
    expect(pack.keyPoints.length).toBeGreaterThan(0);
    expect(pack.flashcards.length).toBeGreaterThan(0);
    expect(pack.overview).toMatch(/Water evaporates/i);
  });

  it('never throws on an empty import and keeps the title safe', () => {
    const pack = buildStudyPack({ title: '   ', text: '' });
    expect(pack.title).toBe('Untitled study pack');
    expect(pack.overview).toBe('');
    expect(pack.flashcards).toEqual([]);
    expect(pack.quiz).toEqual([]);
  });

  it('escapes imported text in the downloadable HTML', () => {
    const pack = buildStudyPack({
      title: '<script>alert(1)</script>',
      text: '<b>Do not run this</b>. It is only text. Another safe sentence follows here.',
    });
    const html = packHtml(pack);
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).not.toContain('<script>alert(1)</script>');
  });
});
