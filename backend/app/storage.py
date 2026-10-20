"""Upload storage — local disk by default, Cloudinary when configured.

`Material.file_path` holds either:
  - "uploads/<random>.<ext>"            → local file under backend/uploads/
  - "cloudinary://<resource_type>/<public_id>" → Cloudinary asset
    (resource_type is image|video|raw, returned by the upload call —
    delivery URLs require the exact type, "auto" is upload-only)

No schema change needed, so existing SQLite/Postgres DBs keep working.
Cloudinary SDK is imported lazily so local dev never needs the package.
"""
import io
import logging
import os
import time
import uuid

from fastapi import HTTPException, UploadFile

from .config import settings

log = logging.getLogger("gramshiksha")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

CLOUDINARY_PREFIX = "cloudinary://"


def _looks_like(data: bytes, ext: str) -> bool:
    """Cheap signature check — the extension alone is attacker-controlled.

    A .pdf that is really HTML, or a .pptx that is really a zip bomb, would
    otherwise be stored and later served/opened. This is not a full parser;
    it stops the obvious "rename any file" attack.
    """
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == ".mp3":
        return data[:3] == b"ID3" or (
            len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    if ext == ".m4a":
        return data[4:8] == b"ftyp"
    if ext == ".pptx":
        return data[:4] in (b"PK\x03\x04", b"PK\x05\x06")
    signature = {
        ".pdf": b"%PDF-",
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
    }.get(ext)
    return bool(signature) and data.startswith(signature)


def save_upload(file: UploadFile, allowed_ext: dict[str, str], max_size: int) -> tuple[str, int]:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(422, f"File type {ext or '(none)'} not allowed. Allowed: {sorted(allowed_ext)}")
    data = file.file.read(max_size + 1)
    if len(data) > max_size:
        raise HTTPException(422, "File too large (max 10 MB)")
    if not _looks_like(data, ext):
        raise HTTPException(422, f"File content does not look like a valid {ext} file")
    if settings.cloudinary_enabled:
        return _save_cloudinary(data, ext)
    return _save_local(data, ext)


def _save_local(data: bytes, ext: str) -> tuple[str, int]:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    return f"uploads/{name}", len(data)


def _save_cloudinary(data: bytes, ext: str) -> tuple[str, int]:
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(cloud_name=settings.cloudinary_cloud_name,
                      api_key=settings.cloudinary_api_key,
                      api_secret=settings.cloudinary_api_secret, secure=True)
    public_id = f"{settings.cloudinary_folder}/{uuid.uuid4().hex}{ext}"
    try:
        res = cloudinary.uploader.upload(
            io.BytesIO(data), public_id=public_id, resource_type="auto",
            unique_filename=False, overwrite=False)
    except Exception as exc:  # noqa: BLE001 — surfacing as 502 keeps UX honest
        log.warning("Cloudinary upload failed: %s", exc)
        raise HTTPException(502, "Upload storage unavailable — please retry") from exc
    rtype = res.get("resource_type", "raw")
    return f"{CLOUDINARY_PREFIX}{rtype}/{res['public_id']}", int(res.get("bytes", len(data)))


def _split_ref(file_path: str) -> tuple[str, str]:
    """cloudinary://<rtype>/<public_id> → (rtype, public_id)."""
    rest = file_path[len(CLOUDINARY_PREFIX):]
    rtype, _, public_id = rest.partition("/")
    if rtype not in ("image", "video", "raw") or not public_id:
        raise HTTPException(404, "File missing")
    return rtype, public_id


def _local_path(file_path: str) -> str:
    """Resolve a stored local ref to an absolute path.

    Refs are always "uploads/<uuid>.<ext>" (see _save_local), so only the
    basename is trusted — the file lives directly in UPLOAD_DIR. Deriving the
    root from `dirname(UPLOAD_DIR) + file_path` silently broke as soon as
    UPLOAD_DIR wasn't literally named "uploads", and it would have honoured a
    traversal sequence in file_path too.
    """
    full = os.path.join(UPLOAD_DIR, os.path.basename(file_path))
    return os.path.normpath(full)


def download_target(file_path: str) -> tuple[str, str]:
    """Return ("redirect", url) for Cloudinary or ("file", abs_path) for local."""
    if file_path.startswith(CLOUDINARY_PREFIX):
        rtype, public_id = _split_ref(file_path)
        return "redirect", _signed_url(rtype, public_id)
    return "file", _local_path(file_path)


def _signed_url(rtype: str, public_id: str, ttl_s: int = 3600) -> str:
    """Short-lived signed URL — preserves approval/visibility checks for
    private/pending assets even though bytes live on a CDN."""
    import cloudinary
    from cloudinary.utils import cloudinary_url

    cloudinary.config(cloud_name=settings.cloudinary_cloud_name,
                      api_key=settings.cloudinary_api_key,
                      api_secret=settings.cloudinary_api_secret, secure=True)
    url, _ = cloudinary_url(public_id, resource_type=rtype, type="upload",
                            sign_url=True, expires_at=int(time.time()) + ttl_s)
    return url


def delete_ref(file_path: str) -> None:
    if file_path.startswith(CLOUDINARY_PREFIX):
        rtype, public_id = _split_ref(file_path)
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(cloud_name=settings.cloudinary_cloud_name,
                              api_key=settings.cloudinary_api_key,
                              api_secret=settings.cloudinary_api_secret, secure=True)
            cloudinary.uploader.destroy(public_id, resource_type=rtype, invalidate=True)
        except Exception as exc:  # noqa: BLE001 — DB row still deleted; log only
            log.warning("Cloudinary destroy failed for %s: %s", public_id, exc)
        return
    full = _local_path(file_path)
    if full and os.path.exists(full):
        os.remove(full)
