/**
 * Google Drive import for Study Studio.
 *
 * This is the official, user-consented route: the learner signs in to their own
 * Google account with Google Identity Services, grants read-only Drive access,
 * and picks a Google Doc that NotebookLM exported. The access token stays in
 * memory for this tab; GramShiksha never receives a refresh token, a password
 * or a cookie.
 *
 * It is disabled until a public OAuth client ID is present at build time:
 *   VITE_GOOGLE_CLIENT_ID=...apps.googleusercontent.com
 * The authorized JavaScript origin must be the production site.
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

declare global {
  interface Window {
    google?: { accounts?: { oauth2?: OAuth2 } };
  }
}

const GIS_SRC = 'https://accounts.google.com/gsi/client';
const DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.readonly';
const DOC_MIME = 'application/vnd.google-apps.document';
const MAX_TEXT = 120_000;

let loader: Promise<void> | null = null;

const env = (key: string): string => {
  const value = (import.meta as unknown as { env?: Record<string, string> }).env?.[key];
  return typeof value === 'string' ? value.trim() : '';
};

/** Public client ID. Empty means the Drive card is not rendered at all. */
export const googleClientId = (): string => env('VITE_GOOGLE_CLIENT_ID');

export const driveImportEnabled = (): boolean => Boolean(googleClientId());

export function loadGoogleIdentity(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Google sign-in only runs in a browser.'));
  if (window.google?.accounts?.oauth2) return Promise.resolve();
  if (loader) return loader;
  loader = new Promise<void>((resolve, reject) => {
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
      loader = null;
      reject(new Error('Google sign-in could not load. Check your connection and try again.'));
    };
    document.head.appendChild(script);
  });
  return loader;
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

const authHeaders = (token: string): HeadersInit => ({ Authorization: `Bearer ${token}` });

export async function listGoogleDocs(token: string): Promise<DriveFile[]> {
  const params = new URLSearchParams({
    q: `trashed = false and mimeType = '${DOC_MIME}'`,
    orderBy: 'modifiedTime desc',
    pageSize: '20',
    fields: 'files(id,name,mimeType,modifiedTime,webViewLink)',
  });
  const response = await fetch(`https://www.googleapis.com/drive/v3/files?${params.toString()}`, {
    headers: authHeaders(token),
  });
  if (response.status === 401) throw new Error('Google access expired. Connect again.');
  if (!response.ok) throw new Error('Google Drive could not list your documents.');
  const body = await response.json() as { files?: DriveFile[] };
  return Array.isArray(body.files) ? body.files : [];
}

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
