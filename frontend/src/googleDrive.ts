/**
 * Google Drive import for Study Studio.
 *
 * The learner signs in to their own Google account with Google Identity
 * Services, then chooses one document in Google's own Picker. We request only
 * `drive.file`, so GramShiksha can read the file the learner selected and
 * nothing else. The access token stays in memory for this tab; GramShiksha
 * never receives a refresh token, a password or a cookie.
 *
 * The card is disabled until all three public values are present at build time:
 *   VITE_GOOGLE_CLIENT_ID=...apps.googleusercontent.com
 *   VITE_GOOGLE_PICKER_KEY=...        (browser API key, Picker API only)
 *   VITE_GOOGLE_APP_ID=...            (Google Cloud project number)
 *
 * The OAuth client's authorized JavaScript origin must include the site, and
 * the API key must allow the site plus https://docs.google.com/* (the Picker
 * iframe's origin). No client secret is used or needed.
 */

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime?: string;
  webViewLink?: string;
}

interface TokenResponse {
  access_token?: string;
  error?: string;
  error_description?: string;
}

interface TokenClient {
  requestAccessToken: (options?: { prompt?: string }) => void;
}

interface OAuth2 {
  initTokenClient: (config: {
    client_id: string;
    scope: string;
    callback: (response: TokenResponse) => void;
    error_callback?: (error: { message?: string; type?: string }) => void;
  }) => TokenClient;
}

interface PickerDocument {
  id: string;
  name: string;
  mimeType: string;
  url?: string;
  lastEditedUtc?: number;
}

interface PickerResponse {
  action?: string;
  docs?: PickerDocument[];
}

interface PickerView {
  setIncludeFolders: (include: boolean) => PickerView;
  setSelectFolderEnabled: (enabled: boolean) => PickerView;
  setMode: (mode: string) => PickerView;
  setMimeTypes: (mimeTypes: string) => PickerView;
}

interface PickerInstance {
  setVisible: (visible: boolean) => void;
}

interface PickerBuilder {
  addView: (view: PickerView) => PickerBuilder;
  setOAuthToken: (token: string) => PickerBuilder;
  setDeveloperKey: (key: string) => PickerBuilder;
  setAppId: (appId: string) => PickerBuilder;
  setCallback: (callback: (data: PickerResponse) => void) => PickerBuilder;
  build: () => PickerInstance;
}

interface PickerNamespace {
  PickerBuilder: new () => PickerBuilder;
  DocsView: new (viewId?: string) => PickerView;
  ViewId: { DOCS: string };
  DocsViewMode: { LIST: string };
  Action: { PICKED: 'picked'; CANCEL: 'cancel' };
  Response: { ACTION: 'action'; DOCUMENTS: 'docs' };
}

declare global {
  interface Window {
    gapi?: { load: (library: string, callback: () => void) => void };
    google?: {
      accounts?: { oauth2?: OAuth2 };
      picker?: PickerNamespace;
    };
  }
}

const GIS_SRC = 'https://accounts.google.com/gsi/client';
const GAPI_SRC = 'https://apis.google.com/js/api.js';
const DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.file';
const DOC_MIME = 'application/vnd.google-apps.document';
const MAX_TEXT = 120_000;

let identityLoader: Promise<void> | null = null;
let pickerLoader: Promise<void> | null = null;

const env = (key: string): string => {
  const viteValue = (import.meta as unknown as { env?: Record<string, string> }).env?.[key];
  if (typeof viteValue === 'string' && viteValue.trim()) return viteValue.trim();
  // Vitest can stub process.env but not Vite's frozen import.meta.env object.
  // The browser has no process global, so this fallback never runs in prod.
  const processEnv = (globalThis as {
    process?: { env?: Record<string, string | undefined> };
  }).process?.env;
  const processValue = processEnv?.[key];
  return typeof processValue === 'string' ? processValue.trim() : '';
};

/** Public OAuth client ID. Empty means the Drive card is not rendered at all. */
export const googleClientId = (): string => env('VITE_GOOGLE_CLIENT_ID');

/** Public browser key restricted to the Picker API and the Studio origins. */
export const googlePickerKey = (): string => env('VITE_GOOGLE_PICKER_KEY');

/** Google Cloud project number, used by the Picker to identify the app. */
export const googleAppId = (): string => env('VITE_GOOGLE_APP_ID');

export const driveImportEnabled = (): boolean =>
  Boolean(googleClientId() && googlePickerKey() && googleAppId());

export function loadGoogleIdentity(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Google sign-in only runs in a browser.'));
  if (window.google?.accounts?.oauth2) return Promise.resolve();
  if (identityLoader) return identityLoader;
  identityLoader = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('Google sign-in could not load.')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => {
      identityLoader = null;
      reject(new Error('Google sign-in could not load. Check your connection and try again.'));
    };
    document.head.appendChild(script);
  });
  return identityLoader;
}

export function loadGooglePicker(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Google Picker only runs in a browser.'));
  if (window.google?.picker) return Promise.resolve();
  if (pickerLoader) return pickerLoader;

  pickerLoader = new Promise<void>((resolve, reject) => {
    const loadLibrary = () => {
      const gapi = window.gapi;
      if (!gapi?.load) {
        reject(new Error('Google Picker could not load.'));
        return;
      }
      try {
        gapi.load('picker', () => {
          if (window.google?.picker) resolve();
          else reject(new Error('Google Picker could not load.'));
        });
      } catch {
        reject(new Error('Google Picker could not load.'));
      }
    };

    if (window.gapi?.load) {
      loadLibrary();
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GAPI_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', loadLibrary, { once: true });
      existing.addEventListener('error', () => {
        pickerLoader = null;
        reject(new Error('Google Picker could not load. Check your connection and try again.'));
      }, { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = GAPI_SRC;
    script.async = true;
    script.defer = true;
    script.onload = loadLibrary;
    script.onerror = () => {
      pickerLoader = null;
      reject(new Error('Google Picker could not load. Check your connection and try again.'));
    };
    document.head.appendChild(script);
  });
  return pickerLoader;
}

export async function requestDriveToken(clientId = googleClientId()): Promise<string> {
  if (!clientId) throw new Error('Google Drive import is not configured yet.');
  await loadGoogleIdentity();
  const oauth2 = window.google?.accounts?.oauth2;
  if (!oauth2) throw new Error('Google sign-in is unavailable in this browser.');
  return new Promise<string>((resolve, reject) => {
    const client = oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_SCOPE,
      callback: (response) => {
        if (response.access_token) resolve(response.access_token);
        else reject(new Error(response.error_description || response.error || 'Google did not return access.'));
      },
      error_callback: (error) => reject(new Error(error.message || 'Google sign-in was cancelled.')),
    });
    client.requestAccessToken({ prompt: 'consent' });
  });
}

/**
 * Open Google's own file picker. Resolves with the learner's chosen Google Doc,
 * or `null` when they close the picker without choosing anything.
 */
export async function pickGoogleDoc(token: string): Promise<DriveFile | null> {
  const pickerKey = googlePickerKey();
  const appId = googleAppId();
  if (!pickerKey) throw new Error('Google Picker is not configured yet.');
  await loadGooglePicker();
  const picker = window.google?.picker;
  if (!picker) throw new Error('Google Picker is unavailable in this browser.');

  return new Promise<DriveFile | null>((resolve, reject) => {
    let settled = false;
    const finish = (file: DriveFile | null) => {
      if (settled) return;
      settled = true;
      resolve(file);
    };
    const fail = (error: Error) => {
      if (settled) return;
      settled = true;
      reject(error);
    };

    try {
      const view = new picker.DocsView(picker.ViewId.DOCS)
        .setIncludeFolders(false)
        .setSelectFolderEnabled(false)
        .setMode(picker.DocsViewMode.LIST)
        .setMimeTypes(DOC_MIME);
      const builder = new picker.PickerBuilder()
        .addView(view)
        .setOAuthToken(token)
        .setDeveloperKey(pickerKey)
        .setCallback((data) => {
          const action = data.action;
          const doc = data.docs?.[0];
          if (action === picker.Action.PICKED) {
            if (!doc) {
              fail(new Error('Google did not return a document.'));
              return;
            }
            finish({
              id: doc.id,
              name: doc.name,
              mimeType: doc.mimeType,
              webViewLink: doc.url,
              modifiedTime: typeof doc.lastEditedUtc === 'number'
                ? new Date(doc.lastEditedUtc).toISOString()
                : undefined,
            });
          } else if (action === picker.Action.CANCEL) {
            finish(null);
          }
        });
      if (appId) builder.setAppId(appId);
      builder.build().setVisible(true);
    } catch {
      fail(new Error('Google Picker could not open.'));
    }
  });
}

const authHeaders = (token: string): HeadersInit => ({ Authorization: `Bearer ${token}` });

export async function exportGoogleDoc(token: string, file: DriveFile): Promise<string> {
  if (file.mimeType !== DOC_MIME) throw new Error('Choose a Google Doc exported from NotebookLM.');
  const url = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(file.id)}/export?mimeType=text/plain`;
  const response = await fetch(url, { headers: authHeaders(token) });
  if (response.status === 401) throw new Error('Google access expired. Connect again.');
  if (!response.ok) {
    throw new Error('This document could not be read. Make sure it is a Google Doc you can open.');
  }
  const text = (await response.text()).trim();
  if (text.length < 20) throw new Error('That document has no readable text yet.');
  return text.slice(0, MAX_TEXT);
}
