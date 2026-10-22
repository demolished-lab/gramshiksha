#!/usr/bin/env node
/**
 * Vercel REST fallback for environments where the CLI dies with `fetch failed`.
 *
 * The CLI is still the primary path (`scripts/deploy.sh --frontend`). This
 * script uploads the already-built `dist/` directory as a prebuilt static
 * deployment, so it needs no install or build step on Vercel:
 *
 *   npm run build
 *   VERCEL_TOKEN=... VERCEL_ORG_ID=... VERCEL_PROJECT_ID=... npm run deploy:api
 *
 * Tokens stay in the environment. The deployment uses the checked-in
 * `vercel.json` for rewrites, headers and the API proxy.
 */
import { readFile, readdir, stat } from 'node:fs/promises';
import { join, relative, sep } from 'node:path';

const token = process.env.VERCEL_TOKEN?.trim();
const teamId = process.env.VERCEL_ORG_ID?.trim();
const projectId = process.env.VERCEL_PROJECT_ID?.trim();

if (!token || !teamId || !projectId) {
  console.error('Set VERCEL_TOKEN, VERCEL_ORG_ID and VERCEL_PROJECT_ID first.');
  process.exit(2);
}

const root = process.cwd();
const dist = join(root, 'dist');
const configPath = join(root, 'vercel.json');

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await walk(full));
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

const headers = {
  Authorization: `Bearer ${token}`,
  'Content-Type': 'application/json',
};

async function api(path, init = {}) {
  const response = await fetch(`https://api.vercel.com${path}`, {
    ...init,
    headers: { ...headers, ...(init.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error?.message || body.message || `Vercel API ${response.status}`);
  }
  return body;
}

const files = [];
for (const path of await walk(dist)) {
  const rel = relative(dist, path).split(sep).join('/');
  files.push({
    file: `dist/${rel}`,
    data: (await readFile(path)).toString('base64'),
    encoding: 'base64',
  });
}
files.push({
  file: 'vercel.json',
  data: (await readFile(configPath)).toString('base64'),
  encoding: 'base64',
});

const payload = {
  name: 'gramshiksha',
  project: projectId,
  target: 'production',
  files,
  projectSettings: {
    framework: null,
    buildCommand: 'true',
    outputDirectory: 'dist',
    installCommand: 'true',
    devCommand: null,
  },
};

const created = await api(
  `/v13/deployments?forceNew=1&teamId=${encodeURIComponent(teamId)}`,
  { method: 'POST', body: JSON.stringify(payload) },
);
console.log(`Deployment ${created.id}: ${created.url}`);

for (let attempt = 1; attempt <= 40; attempt += 1) {
  const deployment = await api(
    `/v13/deployments/${encodeURIComponent(created.id)}?teamId=${encodeURIComponent(teamId)}`,
  );
  console.log(`  ${attempt}: ${deployment.readyState}`);
  if (deployment.readyState === 'READY') {
    console.log(`Production aliases: ${(deployment.alias || []).join(', ') || '(none reported)'}`);
    process.exit(0);
  }
  if (deployment.readyState === 'ERROR' || deployment.readyState === 'CANCELED') {
    console.error(`Deployment failed: ${deployment.errorMessage || deployment.readyState}`);
    process.exit(1);
  }
  await new Promise((resolve) => setTimeout(resolve, 10_000));
}
console.error('Deployment did not become ready within 6 minutes.');
process.exit(1);
