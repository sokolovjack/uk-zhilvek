#!/usr/bin/env python3
"""Scrape ук-жилвек.рф into JSON + downloaded documents."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

BASE = "https://xn----dtbjckjff1e.xn--p1ai"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scraped"
DOCS = DATA / "docs"
IMAGES = DATA / "images"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ZhilvekSiteRebuild/1.0)"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def soup(url: str) -> BeautifulSoup:
    html = get(url)
    return BeautifulSoup(html, "lxml")


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def loc_from_sitemap(xml: bytes) -> list[str]:
    s = BeautifulSoup(xml, "xml")
    return [u.text.strip() for u in s.find_all("loc")]


def extract_main(doc: BeautifulSoup) -> dict:
    title = clean_text(doc.title.get_text() if doc.title else "")
    h1 = doc.find("h1")
    heading = clean_text(h1.get_text()) if h1 else title
    content = (
        doc.select_one("#primary")
        or doc.select_one(".entry-content")
        or doc.select_one("article")
        or doc.select_one("main")
        or doc.body
    )
    # drop nav/footer/header if nested
    if content:
        for sel in ["header", "footer", "nav", ".site-header", ".site-footer", ".menu"]:
            for n in content.select(sel):
                n.decompose()
    html = str(content) if content else ""
    text = content.get_text("\n", strip=True) if content else ""
    links = []
    files = []
    images = []
    if content:
        for a in content.find_all("a", href=True):
            href = a["href"]
            item = {"href": href, "text": clean_text(a.get_text())}
            links.append(item)
            if re.search(r"\.(pdf|docx?|xlsx?|zip|rtf)$", href, re.I):
                files.append(item)
        for img in content.find_all("img", src=True):
            images.append({"src": img["src"], "alt": img.get("alt", "")})
    return {
        "title": title,
        "heading": heading,
        "text": text,
        "html": html,
        "links": links,
        "files": files,
        "images": images,
    }


def slug_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.strip("/")
    if not path:
        return "index"
    path = urllib.parse.unquote(path)
    path = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ/_-]+", "-", path)
    return path.strip("-") or "page"


def download_file(url: str, dest_dir: Path) -> str | None:
    if url.startswith("/"):
        url = BASE + url
    if not url.startswith("http"):
        return None
    name = urllib.parse.unquote(url.split("?")[0].rstrip("/").split("/")[-1])
    name = re.sub(r"[^\w.\-а-яА-ЯёЁ]+", "_", name)[:180]
    if not name:
        return None
    dest = dest_dir / name
    if dest.exists() and dest.stat().st_size > 0:
        return str(dest.relative_to(ROOT))
    try:
        data = get(url)
        dest.write_bytes(data)
        return str(dest.relative_to(ROOT))
    except Exception as e:
        print("  download fail", url, e)
        return None


def extra_house_urls(vash_dom_html: str) -> list[str]:
    s = BeautifulSoup(vash_dom_html, "lxml")
    urls = []
    for a in s.find_all("a", href=True):
        href = a["href"]
        if "xn----dtbjckjff1e" in href or href.startswith("/") or "ук-жилвек" in href:
            full = href if href.startswith("http") else urllib.parse.urljoin(BASE + "/", href)
            if any(x in full for x in ["/dom", "/house", "/vash-dom/", "/mkd", "/adres"]):
                urls.append(full)
            # also capture likely building pages
            if re.search(r"/20\d{2}/", full):
                continue
            path = urllib.parse.urlparse(full).path
            if path.count("/") >= 1 and path not in ("/",):
                urls.append(full)
    return urls


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)

    pages_xml = get(f"{BASE}/wp-sitemap-posts-page-1.xml")
    posts_xml = get(f"{BASE}/wp-sitemap-posts-post-1.xml")
    cats_xml = get(f"{BASE}/wp-sitemap-taxonomies-category-1.xml")
    page_urls = loc_from_sitemap(pages_xml)
    post_urls = loc_from_sitemap(posts_xml)
    cat_urls = loc_from_sitemap(cats_xml)

    # known extra
    extra = [
        f"{BASE}/privacy-policy",
        f"{BASE}/?s=",
        f"{BASE}/category/novosti/",
        f"{BASE}/category/sobytiya/",
    ]
    all_urls = []
    seen = set()
    for u in page_urls + post_urls + cat_urls + extra:
        u = u.rstrip("/") + ("/" if not u.endswith("/") and "?" not in u else "")
        if u not in seen:
            seen.add(u)
            all_urls.append(u)

    pages = []
    for i, url in enumerate(all_urls, 1):
        print(f"[{i}/{len(all_urls)}] {url}")
        try:
            doc = soup(url)
        except Exception as e:
            print("  FAIL", e)
            continue
        item = extract_main(doc)
        item["url"] = url
        item["slug"] = slug_from_url(url)
        item["kind"] = (
            "post"
            if "/20" in urllib.parse.urlparse(url).path[:6]
            else "category"
            if "/category/" in url
            else "page"
        )
        local_files = []
        for f in item["files"]:
            p = download_file(f["href"], DOCS)
            if p:
                local_files.append({**f, "local": p})
        item["local_files"] = local_files
        pages.append(item)
        time.sleep(0.15)

    # follow house/service child links from vash-dom and uslugi
    follow_from = [p for p in pages if p["slug"] in ("vash-dom", "uslugi", "raskrytie-informacii")]
    extra_found = []
    for p in follow_from:
        for a in p["links"]:
            href = a["href"]
            if href.startswith("/"):
                href = BASE + href
            if "xn----dtbjckjff1e" not in href and "ук-жилвек" not in href:
                continue
            path = urllib.parse.urlparse(href).path
            if path.startswith("/wp-") or path.startswith("/feed"):
                continue
            u = href.split("#")[0]
            if u not in seen and u.startswith("http"):
                extra_found.append(u)
                seen.add(u)

    for i, url in enumerate(extra_found, 1):
        print(f"[extra {i}/{len(extra_found)}] {url}")
        try:
            doc = soup(url)
        except Exception as e:
            print("  FAIL", e)
            continue
        item = extract_main(doc)
        item["url"] = url
        item["slug"] = slug_from_url(url)
        item["kind"] = "page"
        local_files = []
        for f in item["files"]:
            p = download_file(f["href"], DOCS)
            if p:
                local_files.append({**f, "local": p})
        item["local_files"] = local_files
        pages.append(item)
        time.sleep(0.15)

    out = {"base": BASE, "pages": pages}
    (DATA / "site.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", DATA / "site.json", "pages", len(pages))


if __name__ == "__main__":
    main()
