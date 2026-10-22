/**
 * Native Study Studio parser.
 *
 * The learner generates notes, a study guide or a question set in their own
 * NotebookLM/Gemini Notebook account, then pastes the text into GramShiksha.
 * This module turns that plain text into a native pack: overview, key points,
 * flashcards, quiz questions and a revision checklist. It is deliberately
 * dependency-free and deterministic so the same text always produces the same
 * pack, and so it works on a low-end phone with no network.
 */

export interface Flashcard {
  front: string;
  back: string;
}

export interface StudyPack {
  id: string;
  title: string;
  sourceUrl: string;
  createdAt: string;
  overview: string;
  keyPoints: string[];
  flashcards: Flashcard[];
  quiz: Flashcard[];
  checklist: string[];
  /** Device-local study state: card fronts marked "known". */
  reviewed?: string[];
  /** Device-local study state: checklist items ticked. */
  checked?: string[];
}

const MAX_INPUT = 120_000;
const MAX_POINTS = 8;
const MAX_CARDS = 12;
const MAX_QUIZ = 8;

const uid = (): string => {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  } catch {
    // Older WebViews on low-end phones have no crypto.randomUUID.
  }
  return `pack-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
};

const clean = (value: string): string =>
  value
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\*\*/g, '')
    .replace(/^#+\s*/, '')
    .trim();

const stripBullet = (line: string): string =>
  line.replace(/^\s*(?:[-*•–—]|\d+[.)])\s+/, '').trim();

const isBullet = (line: string): boolean =>
  /^\s*(?:[-*•–—]|\d+[.)])\s+/.test(line);

const sentences = (text: string): string[] =>
  text
    .split(/(?<=[.!?।])\s+/)
    .map(clean)
    .filter((sentence) => sentence.length >= 12);

const trimTo = (value: string, max: number): string =>
  value.length <= max ? value : `${value.slice(0, max - 1).trimEnd()}…`;

const unique = (values: string[]): string[] => {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const key = value.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      out.push(value);
    }
  }
  return out;
};

function linesOf(raw: string): string[] {
  return raw
    .slice(0, MAX_INPUT)
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => clean(line))
    .filter(Boolean);
}

function qaPairs(lines: string[]): Flashcard[] {
  const pairs: Flashcard[] = [];
  for (let i = 0; i < lines.length - 1; i += 1) {
    const question = lines[i].match(/^(?:Q|Question)\s*[:.-]\s*(.+)$/i);
    const answer = lines[i + 1].match(/^(?:A|Answer)\s*[:.-]\s*(.+)$/i);
    if (question && answer) {
      pairs.push({ front: clean(question[1]), back: clean(answer[1]) });
      i += 1;
    }
  }
  return pairs;
}

function termPairs(lines: string[]): Flashcard[] {
  const pairs: Flashcard[] = [];
  for (const line of lines) {
    const match = line.match(/^([^:–—-]{2,80})\s*[:–—-]\s+(.{2,400})$/);
    if (match) {
      const front = clean(match[1]);
      const back = clean(match[2]);
      // "Chapter 1: ..." is a heading, not a definition. Skip obvious headings.
      if (!/^(chapter|unit|lesson|part|topic|section)\b/i.test(front)) {
        pairs.push({ front, back });
      }
    }
  }
  return pairs;
}

function headingPairs(lines: string[]): Flashcard[] {
  const pairs: Flashcard[] = [];
  for (let i = 0; i < lines.length - 1; i += 1) {
    const heading = lines[i];
    const short = heading.length >= 3 && heading.length <= 80 && !/[.!?।]$/.test(heading);
    const next = lines[i + 1];
    if (short && next.length >= 25 && !isBullet(next)) {
      const answer = sentences(next)[0] ?? next;
      pairs.push({ front: heading, back: trimTo(answer, 260) });
    }
  }
  return pairs;
}

export function buildStudyPack(input: {
  title: string;
  text: string;
  sourceUrl?: string;
}): StudyPack {
  const title = clean(input.title) || 'Untitled study pack';
  const lines = linesOf(input.text);
  const paragraphs: string[] = [];
  let buffer: string[] = [];
  for (const line of lines) {
    if (isBullet(line)) {
      if (buffer.length) {
        paragraphs.push(buffer.join(' '));
        buffer = [];
      }
    } else {
      buffer.push(line);
    }
  }
  if (buffer.length) paragraphs.push(buffer.join(' '));

  const allSentences = unique(paragraphs.flatMap(sentences));
  const bulletPoints = unique(lines.filter(isBullet).map(stripBullet).filter((line) => line.length >= 8));
  const keyPoints = (bulletPoints.length >= 3 ? bulletPoints : allSentences)
    .filter((point) => point.length >= 10)
    .slice(0, MAX_POINTS)
    .map((point) => trimTo(point, 240));

  const overview = trimTo(
    paragraphs[0] || allSentences.slice(0, 3).join(' ') || keyPoints.slice(0, 3).join(' '),
    600,
  );

  const cards = unique(
    [...qaPairs(lines), ...termPairs(lines), ...headingPairs(lines)]
      .map((card) => `${card.front}\u0000${card.back}`),
  ).map((pair) => {
    const [front, back] = pair.split('\u0000');
    return { front, back };
  });

  const fallbackCards: Flashcard[] = keyPoints
    .filter((point) => point.length <= 90)
    .map((point) => ({ front: `What do you know about: ${point}?`, back: point }));
  const flashcards = (cards.length ? cards : fallbackCards).slice(0, MAX_CARDS);

  const quiz = flashcards.slice(0, MAX_QUIZ).map((card) => ({
    front: /[?？]$/.test(card.front) ? card.front : `What is ${card.front}?`,
    back: card.back,
  }));

  const checklist = unique([
    ...keyPoints.map((point) => `I can explain: ${trimTo(point, 120)}`),
    ...flashcards.slice(0, 5).map((card) => `I can recall: ${trimTo(card.front, 120)}`),
  ]).slice(0, 12);

  return {
    id: uid(),
    title,
    sourceUrl: (input.sourceUrl ?? '').trim().slice(0, 500),
    createdAt: new Date().toISOString(),
    overview,
    keyPoints,
    flashcards,
    quiz,
    checklist,
  };
}

export function packHtml(pack: StudyPack): string {
  const escape = (value: string): string =>
    value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  const list = (items: string[]): string =>
    items.length
      ? `<ul>${items.map((item) => `<li>${escape(item)}</li>`).join('')}</ul>`
      : '<p class="muted">No items.</p>';
  const cards = (items: Flashcard[], label: string): string =>
    items.length
      ? `<ol>${items.map((card) => `<li><strong>${escape(card.front)}</strong><br>${escape(card.back)}</li>`).join('')}</ol>`
      : `<p class="muted">No ${label} yet.</p>`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escape(pack.title)} | GramShiksha Study Studio</title>
<style>
  body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; line-height: 1.6; max-width: 820px; margin: 24px auto; padding: 0 16px; color: #0f172a; }
  h1 { color: #2563eb; } h2 { margin-top: 28px; }
  .badge { display: inline-block; background: #eaf1ff; color: #1d4ed8; border-radius: 999px; padding: 2px 10px; font-size: .75rem; font-weight: 700; }
  .muted { color: #64748b; } ol li { margin-bottom: 10px; }
  @media print { body { margin: 0; } }
</style>
</head>
<body>
  <p class="badge">GramShiksha Study Studio · imported by the learner</p>
  <h1>${escape(pack.title)}</h1>
  <p class="muted">Created ${escape(new Date(pack.createdAt).toLocaleString())}${pack.sourceUrl ? ` · source: ${escape(pack.sourceUrl)}` : ''}</p>
  <h2>Overview</h2><p>${escape(pack.overview) || '<span class="muted">No overview.</span>'}</p>
  <h2>Key points</h2>${list(pack.keyPoints)}
  <h2>Flashcards</h2>${cards(pack.flashcards, 'flashcards')}
  <h2>Quiz</h2>${cards(pack.quiz, 'quiz questions')}
  <h2>Revision checklist</h2>${list(pack.checklist)}
</body>
</html>`;
}
