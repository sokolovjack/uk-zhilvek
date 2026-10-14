"""Local file uploads for CMS documents."""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.db import ROOT

UPLOAD_DIR = ROOT / "uploads"
PUBLIC_PREFIX = "/uploads/"
ALLOWED_EXT = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".rtf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}
MAX_BYTES = 40 * 1024 * 1024  # 40 MB


def ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def safe_stem(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r"[^\w.\-а-яА-ЯёЁ]+", "_", name, flags=re.UNICODE).strip("._")
    return (name or "file")[:80]


def save_upload(file: UploadFile) -> str:
    """Save uploaded file and return public URL path like /uploads/...."""
    ensure_upload_dir()
    original = file.filename or "file.bin"
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Тип файла {ext or '(без расширения)'} не поддерживается")

    data = file.file.read()
    if len(data) > MAX_BYTES:
        raise ValueError("Файл больше 40 МБ")
    if not data:
        raise ValueError("Пустой файл")

    filename = f"{uuid.uuid4().hex[:10]}_{safe_stem(original)}{ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(data)
    return f"{PUBLIC_PREFIX}{filename}"


def sync_uploads_to_docs(docs_dir: Path) -> None:
    """Copy uploaded files into docs/uploads for GitHub Pages."""
    ensure_upload_dir()
    target = docs_dir / "uploads"
    target.mkdir(parents=True, exist_ok=True)
    for src in UPLOAD_DIR.iterdir():
        if src.is_file() and not src.name.startswith("."):
            shutil.copy2(src, target / src.name)


def is_upload_file(value) -> bool:
    return hasattr(value, "filename") and hasattr(value, "file")
