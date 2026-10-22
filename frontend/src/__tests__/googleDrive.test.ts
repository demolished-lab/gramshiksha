import { afterEach, describe, expect, it, vi } from 'vitest';
import { driveImportEnabled, exportGoogleDoc, googleClientId, listGoogleDocs, type DriveFile } from '../googleDrive';

const doc: DriveFile = {
  id: 'doc-123',
  name: 'Photosynthesis notes',
  mimeType: 'application/vnd.google-apps.document',
  webViewLink: 'https://docs.google.com/document/d/doc-123/edit',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Google Drive import helpers', () => {
  it('is disabled until a public client ID is configured', () => {
    expect(googleClientId()).toBe('');
    expect(driveImportEnabled()).toBe(false);
  });

  it('lists only Google Docs with the user access token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ files: [doc] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const files = await listGoogleDocs('tok');
    expect(files).toEqual([doc]);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('https://www.googleapis.com/drive/v3/files?');
    expect(new URL(url).searchParams.get('q')).toContain(
      "mimeType = 'application/vnd.google-apps.document'",
    );
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
  });

  it('exports the selected Google Doc as plain text', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('Photosynthesis notes with enough text.', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const text = await exportGoogleDoc('tok', doc);
    expect(text).toBe('Photosynthesis notes with enough text.');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/files/doc-123/export?mimeType=text/plain');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
  });

  it('rejects a file that is not a Google Doc', async () => {
    await expect(exportGoogleDoc('tok', { ...doc, mimeType: 'application/pdf' }))
      .rejects.toThrow(/Google Doc/);
  });

  it('turns an expired token into a reconnect message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })));
    await expect(listGoogleDocs('expired')).rejects.toThrow(/expired/i);
  });
});
