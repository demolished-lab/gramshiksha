/**
 * api.ts is the whole network surface of the app, so these tests pin the
 * framing rules the backend depends on: bearer token, JSON vs multipart
 * bodies, 401 session handling and how FastAPI error payloads reach the UI.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  apiCourses, apiLogin, apiMaterialUrl, apiMe, apiUploadMaterial,
} from '../api';

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const fetchMock = vi.fn<typeof fetch>();

const lastCall = () => {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  return {
    url: String(url),
    init: init ?? {},
    headers: ((init?.headers ?? {}) as Record<string, string>),
  };
};

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('request framing', () => {
  it('sends the bearer token and a JSON content type', async () => {
    localStorage.setItem('gs_token', 'tok-123');
    fetchMock.mockResolvedValue(jsonResponse(200, { name: 'Asha' }));

    await apiMe();

    const { url, headers } = lastCall();
    expect(url).toBe('/api/auth/me');
    expect(headers.Authorization).toBe('Bearer tok-123');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('omits Authorization when nobody is logged in', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}));

    await apiMe();

    expect(lastCall().headers.Authorization).toBeUndefined();
  });

  it('posts multipart uploads untouched', async () => {
    // Regression: FormData used to go through JSON.stringify, which produces
    // "{}" — the backend then answered 422 for every material upload.
    const fd = new FormData();
    fd.set('title', 'My notes');
    fd.set('file', new File(['%PDF-1.4 fake'], 'notes.pdf', { type: 'application/pdf' }));
    fetchMock.mockResolvedValue(jsonResponse(201, { id: 1, status: 'pending' }));

    await apiUploadMaterial(fd);

    const { init, headers } = lastCall();
    expect(init.body).toBe(fd);
    expect(headers['Content-Type']).toBeUndefined(); // browser sets the boundary
  });

  it('sends login as form-encoded credentials with no bearer token', async () => {
    localStorage.setItem('gs_token', 'stale-token');
    fetchMock.mockResolvedValue(jsonResponse(200, { access_token: 'fresh' }));

    await apiLogin('learner@x.in', 'Secret@123');

    const { url, init, headers } = lastCall();
    expect(url).toBe('/api/auth/token');
    expect(headers['Content-Type']).toBe('application/x-www-form-urlencoded');
    expect(String(init.body)).toBe('username=learner%40x.in&password=Secret%40123');
    expect(headers.Authorization).toBeUndefined();
  });
});

describe('error handling', () => {
  it('clears the session on 401 so the UI falls back to login', async () => {
    localStorage.setItem('gs_token', 'expired');
    localStorage.setItem('gs_user', JSON.stringify({ name: 'Asha' }));
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'Could not validate credentials' }));

    await expect(apiMe()).rejects.toThrow('Could not validate credentials');

    expect(localStorage.getItem('gs_token')).toBeNull();
    expect(localStorage.getItem('gs_user')).toBeNull();
  });

  it('surfaces FastAPI validation arrays as readable errors', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(422, { detail: [{ loc: ['body', 'name'], msg: 'field required' }] }));

    await expect(apiMe()).rejects.toThrow('field required');
  });

  it('keeps statusText when the error body is not JSON', async () => {
    fetchMock.mockResolvedValue(new Response('boom', { status: 503, statusText: 'Offline' }));

    await expect(apiMe()).rejects.toThrow('Offline');
  });
});

describe('query building', () => {
  it('drops null/undefined/empty filters instead of sending them', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { total: 0, items: [] }));

    await apiCourses({ class_grade: 8, board: null, subject_id: undefined, difficulty: '', limit: 10 });

    expect(lastCall().url).toBe('/api/courses?class_grade=8&limit=10');
  });

  it('builds download URLs against the api prefix', () => {
    expect(apiMaterialUrl(3)).toBe('/api/materials/3/download');
  });
});
