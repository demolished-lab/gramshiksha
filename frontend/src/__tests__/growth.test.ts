/**
 * Growth layer: referral codes must survive the round trip (?ref= → register
 * payload), share links must carry the page URL on every network, and the
 * money config must fail closed (all slots hidden) when the API is down.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  captureReferral, fetchGrowthConfig, getReferral, inviteLink, OFF_CONFIG, shareLinks,
} from '../growth';

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('referral capture', () => {
  it('stores a valid invite code from ?ref=', () => {
    expect(captureReferral('?ref=GS000123')).toBe('GS000123');
    expect(getReferral()).toBe('GS000123');
  });

  it('lowercases and drops garbage codes', () => {
    expect(captureReferral('?ref=gs0007')).toBe('GS0007');
    expect(captureReferral('?ref=hello')).toBeNull();
    expect(captureReferral('')).toBeNull();
  });

  it('getReferral ignores a poisoned value', () => {
    localStorage.setItem('gs_ref', 'hacked');
    expect(getReferral()).toBe('');
  });

  it('builds the canonical invite link', () => {
    expect(inviteLink('GS000123')).toBe(
      'https://gramshiksha-academy.vercel.app/?ref=GS000123#/home');
  });
});

describe('share links', () => {
  it('embeds the page URL on every network', () => {
    const targets = shareLinks('https://example.in/#/courses', 'Free lessons');
    for (const url of [targets.whatsapp, targets.telegram, targets.x, targets.facebook]) {
      expect(url).toContain(encodeURIComponent('https://example.in/#/courses'));
    }
    expect(targets.nativeAvailable).toBe(false); // node has no navigator.share
  });
});

describe('growth config', () => {
  it('caches the config for an hour', async () => {
    const cfg = { ...OFF_CONFIG, referral_enabled: true };
    fetchMock.mockResolvedValue(new Response(JSON.stringify(cfg), { status: 200 }));

    expect(await fetchGrowthConfig()).toEqual(cfg);
    expect(await fetchGrowthConfig()).toEqual(cfg);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('fails closed when the API is down', async () => {
    fetchMock.mockRejectedValue(new Error('network down'));
    const cfg = await fetchGrowthConfig();
    expect(cfg.ads).toBeNull();
    expect(cfg.donate).toBeNull();
    expect(cfg.affiliates).toEqual([]);
    expect(cfg.premium_url).toBeNull();
  });
});
