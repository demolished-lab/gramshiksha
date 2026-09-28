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
