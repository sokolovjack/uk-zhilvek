#!/usr/bin/env python3
"""Rewrite WordPress media URLs in CMS DB to local /файлы/... paths."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "файлы" / "manifest.json"
DB = ROOT / "data" / "cms.db"
FILES_DIR = ROOT / "файлы"
DOCS_FILES = ROOT / "docs" / "файлы"

HOSTS = (
    "xn----dtbjckjff1e.xn--p1ai",
    "ук-жилвек.рф",
    "www.xn----dtbjckjff1e.xn--p1ai",
    "www.ук-жилвек.рф",
)


def norm_url(url: str) -> str:
    url = (url or "").strip().strip("\\").rstrip("\\")
    url = url.replace("\\/", "/")
    url = re.sub(r"^(https?:)+//", "https://", url, flags=re.I)
    url = re.sub(r"^http:https://", "https://", url, flags=re.I)
    url = re.sub(r"^https:http://", "https://", url, flags=re.I)
    if url.startswith("//"):
        url = "https:" + url
    for h in HOSTS:
        url = url.replace(f"http://{h}", f"https://{h}")
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(parts.path or "")
    # salvage host stuck inside path
    m = re.search(r"(?:xn----dtbjckjff1e\.xn--p1ai|ук-жилвек\.рф)(/wp-content/uploads/.+)$", path)
    if m:
        path = m.group(1)
    return path


def public_path(local_rel: str) -> str:
    """файлы/дома/... → /файлы/дома/... (UTF-8, slash-safe)."""
    rel = local_rel
    if rel.startswith("файлы/"):
        rel = rel[len("файлы/") :]
    parts = Path(rel).parts
    enc = "/".join(urllib.parse.quote(p, safe="()._-") for p in parts)
    return "/файлы/" + enc


def build_maps(manifest: dict) -> tuple[dict[str, str], dict[str, str]]:
    by_path: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for e in manifest.get("downloaded") or []:
        local = e.get("local")
        url = e.get("url") or ""
        if not local:
            continue
        abs_local = ROOT / local
        if not abs_local.is_file():
            continue
        pub = public_path(local)
        path = norm_url(url)
        if path:
            by_path[path] = pub
            by_path[urllib.parse.quote(path, safe="/")] = pub
        name = Path(urllib.parse.unquote(path or local)).name
        if name and name not in by_name:
            by_name[name] = pub
        # also index by local filename
        lname = abs_local.name
        if lname not in by_name:
            by_name[lname] = pub
    return by_path, by_name


def resolve(url: str, by_path: dict[str, str], by_name: dict[str, str]) -> str | None:
    path = norm_url(url)
    if path in by_path:
        return by_path[path]
    # try without size suffix -123x456 before extension
    m = re.match(r"^(.+?)-\d+x\d+(\.[A-Za-z0-9]+)$", path)
    if m:
        alt = m.group(1) + m.group(2)
        if alt in by_path:
            return by_path[alt]
    name = Path(path).name
    if name in by_name:
        return by_name[name]
    if m:
        name2 = Path(m.group(1) + m.group(2)).name
        if name2 in by_name:
            return by_name[name2]
    return None


WP_URL_RE = re.compile(
    r"""(?:https?:)?(?://|https?://)?(?:xn----dtbjckjff1e\.xn--p1ai|ук-жилвек\.рф)?/wp-content/uploads/[^\s\"'<>\\]+""",
    re.I,
)
# broken pasted hosts inside attributes
BROKEN_WP_RE = re.compile(
    r"""https?://[^\"'\s]*wp-content/uploads/[^\s\"'<>\\]+""",
    re.I,
)


def rewrite_html(html: str, by_path: dict[str, str], by_name: dict[str, str]) -> tuple[str, int]:
    if not html:
        return html, 0
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        raw = m.group(0)
        # trim trailing punctuation from regex greed
        raw_clean = raw.rstrip("\\).,;")
        found = resolve(raw_clean, by_path, by_name)
        if found:
            n += 1
            return found + raw[len(raw_clean) :]
        return raw

    out = WP_URL_RE.sub(repl, html)
    out = BROKEN_WP_RE.sub(repl, out)
    # relative wp-content left from scrape
    out2, n2 = rewrite_relative(out, by_path, by_name)
    return out2, n + n2


def rewrite_relative(html: str, by_path: dict[str, str], by_name: dict[str, str]) -> tuple[str, int]:
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        raw = m.group(0)
        found = resolve(raw, by_path, by_name)
        if found:
            n += 1
            return found
        return raw

    return re.sub(r"/wp-content/uploads/[^\s\"'<>\\]+", repl, html), n


def sync_files_to_docs() -> None:
    if DOCS_FILES.exists() or DOCS_FILES.is_symlink():
        if DOCS_FILES.is_symlink() or DOCS_FILES.is_file():
            DOCS_FILES.unlink()
        else:
            shutil.rmtree(DOCS_FILES)
    # copytree — надёжнее symlink на сервере/StaticFiles
    shutil.copytree(
        FILES_DIR,
        DOCS_FILES,
        ignore=shutil.ignore_patterns("manifest.json", "README.md", "__pycache__"),
    )


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_path, by_name = build_maps(manifest)
    print(f"Index: {len(by_path)} paths, {len(by_name)} basenames")

    sync_files_to_docs()
    print(f"Synced {FILES_DIR} → {DOCS_FILES}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    total = 0

    for table, col in (("pages", "body_html"), ("articles", "body_html")):
        rows = conn.execute(f"SELECT id, {col} FROM {table}").fetchall()
        for r in rows:
            new, n = rewrite_html(r[col] or "", by_path, by_name)
            if n:
                conn.execute(f"UPDATE {table} SET {col} = ? WHERE id = ?", (new, r["id"]))
                total += n
                print(f"  {table}#{r['id']}: {n} links")

    docs = conn.execute("SELECT id, url FROM house_docs").fetchall()
    miss = 0
    for r in docs:
        url = r["url"] or ""
        if "/файлы/" in url and not url.startswith("http"):
            continue
        found = resolve(url, by_path, by_name)
        if found:
            conn.execute("UPDATE house_docs SET url = ? WHERE id = ?", (found, r["id"]))
            total += 1
        elif "wp-content" in url or url.startswith("http"):
            miss += 1
            print(f"  MISS house_doc#{r['id']}: {urllib.parse.unquote(url)[-90:]}")

    conn.commit()
    conn.close()

    # refresh content.json + static site
    import sys

    sys.path.insert(0, str(ROOT))
    from app.db import dump_json
    from app.publish import publish

    dump_json()
    publish()
    print(f"\nDone. Rewrote {total} links, missing house docs: {miss}")


if __name__ == "__main__":
    main()
