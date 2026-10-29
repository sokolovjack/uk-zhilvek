"""SQLite storage for CMS content."""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "cms.db"


def slugify_segment(text: str, fallback: str = "novost") -> str:
    """Make URL segment from title; keep Cyrillic like existing news URLs."""
    text = (text or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^\w\-а-яА-Я]+", "", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return (text or fallback)[:80]


def make_article_slug(conn: sqlite3.Connection, title: str, published_at: str, article_id: int | None = None) -> str:
    date_part = (published_at or now()[:10]).strip()[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
        y, m, d = date_part.split("-")
        prefix = f"{y}/{m}/{d}"
    else:
        prefix = date_part.replace("-", "/")
    base = f"{prefix}/{slugify_segment(title)}"
    candidate = base
    n = 2
    while True:
        row = conn.execute("SELECT id FROM articles WHERE slug = ?", (candidate,)).fetchone()
        if not row or (article_id is not None and row["id"] == article_id):
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slug TEXT NOT NULL UNIQUE,
              title TEXT NOT NULL,
              heading TEXT NOT NULL,
              body_html TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              published INTEGER NOT NULL DEFAULT 1,
              sort_order INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS articles (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slug TEXT NOT NULL UNIQUE,
              title TEXT NOT NULL,
              body_html TEXT NOT NULL DEFAULT '',
              excerpt TEXT NOT NULL DEFAULT '',
              published_at TEXT NOT NULL,
              published INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS houses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              sort_order INTEGER NOT NULL DEFAULT 0,
              published INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS house_docs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              house_id INTEGER NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
              title TEXT NOT NULL,
              url TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS article_docs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              title TEXT NOT NULL,
              url TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0
            );
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


# ---- pages ----

def list_pages(conn: sqlite3.Connection, published_only: bool = False) -> list[dict]:
    q = "SELECT * FROM pages"
    if published_only:
        q += " WHERE published = 1"
    q += " ORDER BY sort_order, title"
    return [dict(r) for r in conn.execute(q).fetchall()]


def get_page(conn: sqlite3.Connection, page_id: int | None = None, slug: str | None = None) -> dict | None:
    if page_id is not None:
        return row_to_dict(conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone())
    return row_to_dict(conn.execute("SELECT * FROM pages WHERE slug = ?", (slug,)).fetchone())


def save_page(conn: sqlite3.Connection, data: dict, page_id: int | None = None) -> int:
    fields = {
        "slug": data["slug"].strip("/"),
        "title": data["title"].strip(),
        "heading": data["heading"].strip(),
        "body_html": data.get("body_html") or "",
        "description": data.get("description") or "",
        "published": 1 if data.get("published", True) else 0,
        "sort_order": int(data.get("sort_order") or 0),
        "updated_at": now(),
    }
    if page_id:
        conn.execute(
            """UPDATE pages SET slug=:slug, title=:title, heading=:heading, body_html=:body_html,
               description=:description, published=:published, sort_order=:sort_order, updated_at=:updated_at
               WHERE id=:id""",
            {**fields, "id": page_id},
        )
        return page_id
    cur = conn.execute(
        """INSERT INTO pages(slug, title, heading, body_html, description, published, sort_order, updated_at)
           VALUES(:slug, :title, :heading, :body_html, :description, :published, :sort_order, :updated_at)""",
        fields,
    )
    return int(cur.lastrowid)


def delete_page(conn: sqlite3.Connection, page_id: int) -> None:
    conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))


# ---- articles ----

def list_article_docs(conn: sqlite3.Connection, article_id: int) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM article_docs WHERE article_id = ? ORDER BY sort_order, id", (article_id,)
        ).fetchall()
    ]


def list_articles(conn: sqlite3.Connection, published_only: bool = False) -> list[dict]:
    q = "SELECT * FROM articles"
    if published_only:
        q += " WHERE published = 1"
    q += " ORDER BY published_at DESC, id DESC"
    articles = [dict(r) for r in conn.execute(q).fetchall()]
    for a in articles:
        a["docs"] = list_article_docs(conn, a["id"])
    return articles


def get_article(conn: sqlite3.Connection, article_id: int | None = None, slug: str | None = None) -> dict | None:
    if article_id is not None:
        a = row_to_dict(conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone())
    else:
        a = row_to_dict(conn.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone())
    if a:
        a["docs"] = list_article_docs(conn, a["id"])
    return a


def save_article(conn: sqlite3.Connection, data: dict, article_id: int | None = None) -> int:
    title = data["title"].strip()
    published_at = (data.get("published_at") or now()[:10]).strip()[:10]
    slug = (data.get("slug") or "").strip().strip("/")
    if not slug:
        slug = make_article_slug(conn, title, published_at, article_id=article_id)
    fields = {
        "slug": slug,
        "title": title,
        "body_html": data.get("body_html") or "",
        "excerpt": data.get("excerpt") or "",
        "published_at": published_at,
        "published": 1 if data.get("published", True) else 0,
        "updated_at": now(),
    }
    if article_id:
        conn.execute(
            """UPDATE articles SET slug=:slug, title=:title, body_html=:body_html, excerpt=:excerpt,
               published_at=:published_at, published=:published, updated_at=:updated_at WHERE id=:id""",
            {**fields, "id": article_id},
        )
        aid = article_id
    else:
        cur = conn.execute(
            """INSERT INTO articles(slug, title, body_html, excerpt, published_at, published, updated_at)
               VALUES(:slug, :title, :body_html, :excerpt, :published_at, :published, :updated_at)""",
            fields,
        )
        aid = int(cur.lastrowid)

    if "docs" in data:
        conn.execute("DELETE FROM article_docs WHERE article_id = ?", (aid,))
        for i, doc in enumerate(data["docs"] or []):
            title = (doc.get("title") or doc.get("text") or "").strip()
            url = (doc.get("url") or doc.get("href") or "").strip()
            if not title or not url:
                continue
            conn.execute(
                "INSERT INTO article_docs(article_id, title, url, sort_order) VALUES(?, ?, ?, ?)",
                (aid, title, url, i),
            )
    return aid


def delete_article(conn: sqlite3.Connection, article_id: int) -> None:
    conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))


# ---- houses ----

def list_houses(conn: sqlite3.Connection, published_only: bool = False) -> list[dict]:
    q = "SELECT * FROM houses"
    if published_only:
        q += " WHERE published = 1"
    q += " ORDER BY sort_order, name"
    houses = [dict(r) for r in conn.execute(q).fetchall()]
    for h in houses:
        h["docs"] = list_house_docs(conn, h["id"])
    return houses


def get_house(conn: sqlite3.Connection, house_id: int) -> dict | None:
    h = row_to_dict(conn.execute("SELECT * FROM houses WHERE id = ?", (house_id,)).fetchone())
    if h:
        h["docs"] = list_house_docs(conn, house_id)
    return h


def list_house_docs(conn: sqlite3.Connection, house_id: int) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM house_docs WHERE house_id = ? ORDER BY sort_order, id", (house_id,)
        ).fetchall()
    ]


def save_house(conn: sqlite3.Connection, data: dict, house_id: int | None = None) -> int:
    fields = {
        "name": data["name"].strip(),
        "sort_order": int(data.get("sort_order") or 0),
        "published": 1 if data.get("published", True) else 0,
        "updated_at": now(),
    }
    if house_id:
        conn.execute(
            "UPDATE houses SET name=:name, sort_order=:sort_order, published=:published, updated_at=:updated_at WHERE id=:id",
            {**fields, "id": house_id},
        )
        hid = house_id
    else:
        cur = conn.execute(
            "INSERT INTO houses(name, sort_order, published, updated_at) VALUES(:name, :sort_order, :published, :updated_at)",
            fields,
        )
        hid = int(cur.lastrowid)

    if "docs" in data:
        conn.execute("DELETE FROM house_docs WHERE house_id = ?", (hid,))
        for i, doc in enumerate(data["docs"] or []):
            title = (doc.get("title") or doc.get("text") or "").strip()
            url = (doc.get("url") or doc.get("href") or "").strip()
            if not title or not url:
                continue
            conn.execute(
                "INSERT INTO house_docs(house_id, title, url, sort_order) VALUES(?, ?, ?, ?)",
                (hid, title, url, i),
            )
    return hid


def delete_house(conn: sqlite3.Connection, house_id: int) -> None:
    conn.execute("DELETE FROM houses WHERE id = ?", (house_id,))


def export_content(conn: sqlite3.Connection) -> dict:
    return {
        "exported_at": now(),
        "pages": list_pages(conn),
        "articles": list_articles(conn),
        "houses": list_houses(conn),
        "settings": {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")},
    }


def dump_json(path: Path | None = None) -> Path:
    path = path or (ROOT / "data" / "content.json")
    with db() as conn:
        data = export_content(conn)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
