/**
 * Designated logins hit their own endpoints with the same form encoding as
 * the generic login, and surface the server's message (including the 403
 * "this page is for teachers/students" hint) instead of swallowing it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiStudentLogin, apiTeacherLogin } from '../api';

const fetchMock = vi.fn<typeof fetch>();

const lastCall = () => {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  return { url: String(url), init: init ?? {} };
};

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('designated role logins', () => {
  it('posts teacher credentials to the teacher endpoint', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ access_token: 't', role: 'teacher' }), { status: 200 }));
    const res = await apiTeacherLogin('teach@x.in', 'pw123456');
    expect(res.role).toBe('teacher');
    const { url, init } = lastCall();
    expect(url).toBe('/api/auth/token/teacher');
    expect((init as RequestInit).method).toBe('POST');
    expect(String((init as RequestInit).body)).toContain('username=teach%40x.in');
  });

  it('posts student credentials to the student endpoint', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ access_token: 's', role: 'student' }), { status: 200 }));
    await apiStudentLogin('stu@x.in', 'pw123456');
    expect(lastCall().url).toBe('/api/auth/token/student');
  });

  it('surfaces the 403 role-mismatch message', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'This login page is for teachers' }), { status: 403 }));
    await expect(apiTeacherLogin('stu@x.in', 'pw123456')).rejects.toThrow(
      'This login page is for teachers');
  });
});
