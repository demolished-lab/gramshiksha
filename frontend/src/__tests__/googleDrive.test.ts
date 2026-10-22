import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  driveImportEnabled,
  exportGoogleDoc,
  googleAppId,
  googleClientId,
  googlePickerKey,
  pickGoogleDoc,
  requestDriveToken,
  type DriveFile,
} from '../googleDrive';

const DOC = 'application/vnd.google-apps.document';
const doc: DriveFile = {
  id: 'doc-123',
  name: 'Photosynthesis notes',
  mimeType: DOC,
  webViewLink: 'https://docs.google.com/document/d/doc-123/edit',
};

type PickerData = { action?: string; docs?: Array<Record<string, unknown>> };

function installPicker(action: 'picked' | 'cancel', selected = doc) {
  let callback: ((data: PickerData) => void) | undefined;

  class MockDocsView {
    setIncludeFolders() { return this; }
    setSelectFolderEnabled() { return this; }
    setMode() { return this; }
    setMimeTypes() { return this; }
  }

  class MockPickerBuilder {
    addView() { return this; }
    setOAuthToken() { return this; }
    setDeveloperKey() { return this; }
    setAppId() { return this; }
    setCallback(cb: (data: PickerData) => void) { callback = cb; return this; }
    build() {
      return {
        setVisible: () => {
          callback?.({
            action,
            docs: action === 'picked'
              ? [{
                id: selected.id,
                name: selected.name,
                mimeType: selected.mimeType,
                url: selected.webViewLink,
              }]
              : [],
          });
        },
      };
    }
  }

  vi.stubGlobal('window', {
    google: {
      picker: {
        PickerBuilder: MockPickerBuilder,
        DocsView: MockDocsView,
        ViewId: { DOCS: 'docs' },
        DocsViewMode: { LIST: 'list' },
        Action: { PICKED: 'picked', CANCEL: 'cancel' },
        Response: { ACTION: 'action', DOCUMENTS: 'docs' },
      },
    },
  });
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('Google Drive import helpers', () => {
  it('is disabled until every public picker value is configured', () => {
    expect(googleClientId()).toBe('');
    expect(googlePickerKey()).toBe('');
    expect(googleAppId()).toBe('');
    expect(driveImportEnabled()).toBe(false);

    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'client.apps.googleusercontent.com');
    vi.stubEnv('VITE_GOOGLE_PICKER_KEY', 'picker-key');
    vi.stubEnv('VITE_GOOGLE_APP_ID', '1234567890');
    expect(driveImportEnabled()).toBe(true);
  });

  it('requests only per-file Drive access', async () => {
    let scope = '';
    let prompt = '';
    vi.stubGlobal('window', {
      google: {
        accounts: {
          oauth2: {
            initTokenClient: (config: {
              scope: string;
              callback: (response: { access_token: string }) => void;
            }) => {
              scope = config.scope;
              return {
                requestAccessToken: (options?: { prompt?: string }) => {
                  prompt = options?.prompt ?? '';
                  config.callback({ access_token: 'tok' });
                },
              };
            },
          },
        },
      },
    });

    await expect(requestDriveToken('client')).resolves.toBe('tok');
    expect(scope).toBe('https://www.googleapis.com/auth/drive.file');
    expect(prompt).toBe('consent');
  });

  it('returns the document the learner picks in Google Picker', async () => {
    vi.stubEnv('VITE_GOOGLE_PICKER_KEY', 'picker-key');
    vi.stubEnv('VITE_GOOGLE_APP_ID', '1234567890');
    installPicker('picked');

    await expect(pickGoogleDoc('tok')).resolves.toEqual(doc);
  });

  it('returns null when the learner closes the picker', async () => {
    vi.stubEnv('VITE_GOOGLE_PICKER_KEY', 'picker-key');
    vi.stubEnv('VITE_GOOGLE_APP_ID', '1234567890');
    installPicker('cancel');

    await expect(pickGoogleDoc('tok')).resolves.toBeNull();
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
    await expect(exportGoogleDoc('expired', doc)).rejects.toThrow(/expired/i);
  });
});
