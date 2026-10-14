#!/usr/bin/env python3
"""Download all documents from ук-жилвек.рф into local folders by house / section."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SCRAPED = ROOT / "scraped" / "site.json"
OUT = ROOT / "файлы"
ORIGIN = "https://xn----dtbjckjff1e.xn--p1ai"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ZhilvekFileMirror/1.0)"}
FILE_RE = re.compile(r"\.(pdf|docx?|xlsx?|zip|rtf|jpe?g|png|webp)($|\?)", re.I)


def encode_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    url = url.replace("http://ук-жилвек.рф", ORIGIN).replace("https://ук-жилвек.рф", ORIGIN)
    url = url.replace("http://xn----dtbjckjff1e.xn--p1ai", ORIGIN)
    url = re.sub(r"^(https?:)+//", "https://", url, flags=re.I)
    url = re.sub(r"^http:https://", "https://", url, flags=re.I)
    url = re.sub(r"^http:http://", "http://", url, flags=re.I)
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        url = ORIGIN + url
    # fix broken double hosts pasted into path
    url = url.replace(ORIGIN + "/" + "xn----dtbjckjff1e.xn--p1ai", ORIGIN)
    url = url.replace(ORIGIN + "//", ORIGIN + "/")
    parts = urllib.parse.urlsplit(url)
    if not parts.netloc:
        # still broken — try to salvage path with host inside
        m = re.search(r"(xn----dtbjckjff1e\.xn--p1ai)(/.*)$", url)
        if m:
            parts = urllib.parse.urlsplit("https://" + m.group(1) + m.group(2))
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%._-")
    return urllib.parse.urlunsplit((parts.scheme or "https", parts.netloc, path, parts.query, ""))


def safe_name(text: str, fallback: str = "file") -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = text.strip(" ._")
    return (text or fallback)[:120]


def filename_from_url(url: str) -> str:
    name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rstrip("/").split("/")[-1])
    return safe_name(name, "document")


def unique_path(folder: Path, filename: str) -> Path:
    dest = folder / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    i = 2
    while True:
        cand = folder / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


def download(url: str, dest: Path) -> tuple[bool, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True, "exists"
    encoded = encode_url(url)
    try:
        req = urllib.request.Request(encoded, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if not data:
            return False, "empty"
        dest.write_bytes(data)
        return True, f"ok {len(data)}"
    except Exception as e:
        return False, str(e)


def extract_houses(html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "lxml")
    root = soup.select_one(".entry-content") or soup
    headings = root.find_all("h3")
    groups = root.select(".wpsm_panel-group")
    out = []
    for name_el, group in zip(headings, groups):
        name = re.sub(r"\s+", " ", name_el.get_text(" ", strip=True)).strip() or "Дом"
        docs = []
        for a in group.select(".wpsm_panel-body a[href]"):
            href = a.get("href", "")
            text = a.get_text(" ", strip=True) or filename_from_url(href)
            if href and FILE_RE.search(href):
                docs.append({"title": text, "url": href})
        out.append({"name": name, "docs": docs})
    return out


def collect_page_files(pages: list[dict]) -> dict[str, list[dict]]:
    by_section: dict[str, list[dict]] = defaultdict(list)
    seen_in_section: dict[str, set[str]] = defaultdict(set)

    def add(section: str, title: str, url: str, source: str):
        enc = encode_url(url)
        if not enc or not FILE_RE.search(enc):
            return
        key = urllib.parse.unquote(enc)
        if key in seen_in_section[section]:
            return
        seen_in_section[section].add(key)
        by_section[section].append({"title": title, "url": url, "source": source})

    pages_map = {}
    for p in pages:
        pages_map[p["slug"]] = p

    # houses
    vash = pages_map.get("vash-dom")
    if vash:
        for house in extract_houses(vash.get("html", "")):
            folder = f"дома/{safe_name(house['name'])}"
            for d in house["docs"]:
                add(folder, d["title"], d["url"], "vash-dom")

    # company / licenses
    for slug, section in [
        ("o-kompanii", "компания_и_лицензии"),
        ("raskrytie-informacii", "раскрытие_информации"),
        ("rekvizity", "компания_и_лицензии"),
    ]:
        p = pages_map.get(slug)
        if not p:
            continue
        soup = BeautifulSoup(p.get("html") or "", "lxml")
        for a in soup.find_all("a", href=True):
            add(section, a.get_text(" ", strip=True) or filename_from_url(a["href"]), a["href"], slug)
        for f in p.get("files") or []:
            add(section, f.get("text") or "", f.get("href") or "", slug)

    # all other pages / posts
    for p in pages:
        slug = p.get("slug") or "page"
        if slug in ("vash-dom", "o-kompanii", "raskrytie-informacii"):
            continue
        soup = BeautifulSoup(p.get("html") or "", "lxml")
        kind = p.get("kind") or "page"
        section = "новости" if kind == "post" else f"страницы/{safe_name(slug)}"
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if FILE_RE.search(href) or "/wp-content/uploads/" in href:
                add(section, a.get_text(" ", strip=True) or filename_from_url(href), href, slug)
        for f in p.get("files") or []:
            add(section, f.get("text") or "", f.get("href") or "", slug)
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if FILE_RE.search(src) or "/wp-content/uploads/" in src:
                add(
                    f"изображения/{safe_name(slug)}",
                    img.get("alt") or filename_from_url(src),
                    src,
                    slug,
                )

    return by_section


def main() -> None:
    data = json.loads(SCRAPED.read_text(encoding="utf-8"))
    sections = collect_page_files(data["pages"])
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = {"base": ORIGIN, "downloaded": [], "failed": [], "sections": {}}
    total = sum(len(v) for v in sections.values())
    print(f"Found {total} unique files in {len(sections)} folders")

    n = 0
    for section, items in sorted(sections.items()):
        folder = OUT / section
        folder.mkdir(parents=True, exist_ok=True)
        manifest["sections"][section] = []
        for item in items:
            n += 1
            url = item["url"]
            title = item["title"] or filename_from_url(url)
            # stable name from remote filename so re-runs do not duplicate
            raw_name = filename_from_url(encode_url(url))
            if "." not in raw_name:
                ext = Path(raw_name).suffix or ".bin"
                raw_name = safe_name(title) + (ext if ext.startswith(".") else ".bin")
            # if title-named file already exists from previous run, reuse it
            title_name = safe_name(title) + Path(raw_name).suffix
            existing_title = folder / title_name
            existing_raw = folder / raw_name
            if existing_title.exists() and existing_title.stat().st_size > 0:
                dest = existing_title
            elif existing_raw.exists() and existing_raw.stat().st_size > 0:
                dest = existing_raw
            else:
                dest = folder / raw_name
            ok, msg = download(url, dest)
            rel = str(dest.relative_to(ROOT))
            entry = {
                "title": title,
                "url": encode_url(url),
                "local": rel if ok else None,
                "source": item["source"],
                "status": msg,
            }
            manifest["sections"][section].append(entry)
            if ok:
                manifest["downloaded"].append(entry)
                print(f"[{n}/{total}] OK  {section}/{dest.name}", flush=True)
            else:
                manifest["failed"].append({**entry, "error": msg})
                print(f"[{n}/{total}] FAIL {section}/{dest.name}: {msg}", flush=True)
            time.sleep(0.05)

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\nDone. OK={len(manifest['downloaded'])} FAIL={len(manifest['failed'])}\nSaved to {OUT}"
    )


if __name__ == "__main__":
    main()
