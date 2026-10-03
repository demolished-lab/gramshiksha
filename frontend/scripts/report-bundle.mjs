import { gzipSync } from 'node:zlib';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const assetsDir = new URL('../dist/assets/', import.meta.url);
const assets = await readdir(assetsDir);
const initialJs = assets.find((name) => /^index-.*\.js$/.test(name));
const initialCss = assets.find((name) => /^index-.*\.css$/.test(name));
if (!initialJs || !initialCss) throw new Error('Build assets not found. Run npm run build first.');

const report = async (name) => {
  const bytes = await readFile(join(assetsDir.pathname, name));
  const gzip = gzipSync(bytes).byteLength;
  return { name, bytes: bytes.byteLength, gzip };
};
const [js, css] = await Promise.all([report(initialJs), report(initialCss)]);
const kb = (value) => `${(value / 1024).toFixed(2)} KB`;
console.log(`Initial JS:  ${kb(js.bytes)} (${kb(js.gzip)} gzip)`);
console.log(`Initial CSS: ${kb(css.bytes)} (${kb(css.gzip)} gzip)`);
console.log(`Route chunks: ${assets.filter((name) => /\.js$/.test(name) && name !== initialJs).length}`);
if (js.gzip > 70 * 1024) throw new Error(`Initial JS gzip budget exceeded: ${kb(js.gzip)} > 70 KB`);
if (css.gzip > 8 * 1024) throw new Error(`Initial CSS gzip budget exceeded: ${kb(css.gzip)} > 8 KB`);
