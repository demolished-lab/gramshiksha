import { apiMaterialUrl } from './api';
import { getToken, offlineStorageScope, removeDownload, saveDownload } from './auth';

const CACHE_NAME = 'gramshiksha-offline-materials-v1';
const MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024;

function materialRequest(materialId: number): Request {
  const scope = offlineStorageScope();
  if (!scope) throw new Error('Log in to save materials for offline use.');
  return new Request(new URL(`/__offline_materials__/${scope}/${materialId}`, location.origin));
}

export async function saveMaterialOffline(materialId: number, title: string): Promise<void> {
  const token = getToken();
  if (!token) throw new Error('Log in to save materials for offline use.');
  if (typeof caches === 'undefined') throw new Error('Offline file storage is not available in this browser.');

  const response = await fetch(apiMaterialUrl(materialId), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Download failed (${response.status}). Please try again.`);

  const blob = await response.blob();
  if (blob.size > MAX_DOWNLOAD_BYTES) throw new Error('This file is larger than the 10 MB offline limit.');
  const mimeType = response.headers.get('Content-Type') || blob.type || 'application/octet-stream';
  const request = materialRequest(materialId);
  const cache = await caches.open(CACHE_NAME);
  await cache.put(request, new Response(blob, { headers: { 'Content-Type': mimeType } }));

  const saved = saveDownload({
    material_id: materialId,
    title,
    saved_at: new Date().toISOString(),
    mime_type: mimeType,
    size_bytes: blob.size,
  });
  if (!saved) {
    await cache.delete(request);
    throw new Error('The file was downloaded, but this device could not save its offline index. Free up storage and retry.');
  }
}

export async function openOfflineMaterial(materialId: number): Promise<void> {
  if (typeof caches === 'undefined') throw new Error('Offline file storage is not available in this browser.');
  const cache = await caches.open(CACHE_NAME);
  const response = await cache.match(materialRequest(materialId));
  if (!response) throw new Error('This offline file is no longer on this device. Download it again while online.');

  const objectUrl = URL.createObjectURL(await response.blob());
  // A programmatic `_blank` click after an `await` has no user activation, so
  // phone browsers block it as a popup (or open a blank tab for a blob PDF).
  // Navigating this tab always works; Back returns to My Downloads.
  window.location.assign(objectUrl);
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

export async function removeOfflineMaterial(materialId: number): Promise<void> {
  removeDownload(materialId);
  if (typeof caches === 'undefined') return;
  const cache = await caches.open(CACHE_NAME);
  await cache.delete(materialRequest(materialId));
}
