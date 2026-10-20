"""Storage backend: local default + Cloudinary ref parsing (no network)."""
import os

import pytest
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.storage import CLOUDINARY_PREFIX, delete_ref, download_target, save_upload

ALLOWED = {".pdf": "application/pdf"}
MAX = 1024


def _upload(filename: str, data: bytes) -> UploadFile:
    import io
    return UploadFile(file=io.BytesIO(data), filename=filename)


def test_cloudinary_disabled_by_default():
    assert settings.cloudinary_enabled is False


def _patch_dir(st, monkeypatch, tmp_path):
    monkeypatch.setattr(st, "UPLOAD_DIR", str(tmp_path / "uploads"))


def test_local_save_and_download_target(tmp_path, monkeypatch):
    import app.storage as st
    _patch_dir(st, monkeypatch, tmp_path)
    ref, size = save_upload(_upload("notes.pdf", b"%PDF-1.4 fake"), ALLOWED, MAX)
    assert ref.startswith("uploads/") and size > 0
    kind, target = download_target(ref)
    assert kind == "file" and os.path.exists(target)


def test_rejects_bad_ext_and_oversize(tmp_path, monkeypatch):
    import app.storage as st
    _patch_dir(st, monkeypatch, tmp_path)
    with pytest.raises(HTTPException):
        save_upload(_upload("notes.txt", b"dummy"), ALLOWED, MAX)
    with pytest.raises(HTTPException):
        save_upload(_upload("big.pdf", b"x" * (MAX + 1)), ALLOWED, MAX)


def test_cloudinary_image_public_id_drops_duplicate_extension(monkeypatch):
    import cloudinary.uploader

    import app.storage as st

    monkeypatch.setattr(settings, "cloudinary_cloud_name", "testcloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "testkey")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "testsecret")
    seen = {}

    def fake_upload(*a, **k):
        seen.update(k)
        return {"resource_type": "image", "public_id": "gramshiksha/abc.pdf",
                "bytes": 8}

    monkeypatch.setattr(cloudinary.uploader, "upload", fake_upload)
    ref, size = st._save_cloudinary(b"%PDF-1.4", ".pdf")
    # Cloudinary's image delivery URL adds the format, so the upload public_id
    # must not contain it too (otherwise "<id>.pdf.pdf" is the real URL).
    assert not seen["public_id"].endswith(".pdf")
    assert ref == "cloudinary://image/gramshiksha/abc"
    assert size == 8


def test_cloudinary_raw_public_id_keeps_extension(monkeypatch):
    import cloudinary.uploader

    import app.storage as st

    monkeypatch.setattr(settings, "cloudinary_cloud_name", "testcloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "testkey")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "testsecret")
    monkeypatch.setattr(cloudinary.uploader, "upload", lambda *a, **k: {
        "resource_type": "raw", "public_id": "gramshiksha/abc.pdf",
        "bytes": 8,
    })
    ref, _ = st._save_cloudinary(b"%PDF-1.4", ".pdf")
    assert ref == "cloudinary://raw/gramshiksha/abc.pdf"


def test_malformed_cloudinary_ref_is_404():
    with pytest.raises(HTTPException):
        download_target(f"{CLOUDINARY_PREFIX}no-rtype-here")


def test_delete_local_file(tmp_path, monkeypatch):
    import app.storage as st
    _patch_dir(st, monkeypatch, tmp_path)
    ref, _ = save_upload(_upload("del.pdf", b"%PDF-1.4 fake"), ALLOWED, MAX)
    _, target = download_target(ref)
    assert os.path.exists(target)
    delete_ref(ref)
    assert not os.path.exists(target)
