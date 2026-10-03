import { describe, expect, it, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import StreamPicker, { streamName } from '../components/StreamPicker';

describe('StreamPicker', () => {
  it('renders nothing where streams do not exist', () => {
    expect(renderToString(
      <StreamPicker lang="en" streams={[]} value="" onChange={vi.fn()} />,
    )).toBe('');
  });

  it('offers only the streams actually present, translated', () => {
    const html = renderToString(
      <StreamPicker
        lang="hi"
        streams={[{ code: 'science', label_en: 'Science', books: 4 }]}
        value="science"
        onChange={vi.fn()}
      />,
    );
    expect(html).toContain('विज्ञान');
    expect(html).toContain('4');
    expect(streamName('commerce', 'mr')).toBe('वाणिज्य');
  });
});
