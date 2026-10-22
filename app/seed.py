"""Import scraped content into CMS database."""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from app.db import (
    ROOT,
    get_page,
    get_setting,
    init_db,
    db,
    save_article,
    save_house,
    save_page,
    set_setting,
)

ORIGIN = "https://xn----dtbjckjff1e.xn--p1ai"
SPAM = re.compile(r"celebs nude|3ds max|stl without|jayla", re.I)

EDITABLE_PAGES = [
    ("o-kompanii", "О компании", "О компании"),
    ("uslugi", "Услуги", "Услуги"),
    ("santekhnicheskie-raboty", "Сантехнические работы", "Сантехнические работы"),
    ("elektromontazhnye-raboty", "Электромонтажные работы", "Электромонтажные работы"),
    ("vash-dom", "Ваш дом", "Ваш дом"),
    ("raskrytie-informacii", "Раскрытие информации", "Раскрытие информации"),
    ("kontakty", "Контакты", "Контакты"),
    ("oplata-uslug-zhilishchno-kommunalnogo-hozyajstva", "Оплата услуг ЖКХ", "Оплата услуг ЖКХ"),
    ("priem-pokazanij-individualnyh-priborov-uchyota-vody", "Приём показаний ИПУ воды", "Приём показаний ИПУ воды"),
    ("faq", "Вопрос-ответ", "Вопрос-ответ"),
    ("rekvizity", "Реквизиты", "Реквизиты"),
    ("privacy-policy", "Политика конфиденциальности", "Политика конфиденциальности"),
    ("home", "Главная", "Главная"),
]


def encode_url(url: str) -> str:
    if not url:
        return url
    url = url.strip().replace("http://ук-жилвек.рф", ORIGIN).replace("https://ук-жилвек.рф", ORIGIN)
    url = url.replace("http://xn----dtbjckjff1e.xn--p1ai", ORIGIN)
    if url.startswith("//"):
        url = "https:" + url
    parts = urllib.parse.urlsplit(url)
    if not parts.scheme:
        return url
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%._-")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def clean_body(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    root = soup.select_one(".entry-content") or soup
    for t in root.select("script, style, form, iframe"):
        t.decompose()
    for a in root.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\.(pdf|docx?|xlsx?|zip|rtf)($|\?)", href, re.I) or "/wp-content/" in href:
            a["href"] = encode_url(href)
            a["target"] = "_blank"
            a["rel"] = "noopener"
        for attr in list(a.attrs):
            if attr.startswith("data-"):
                del a[attr]
    for tag in root.find_all(True):
        for attr in ("class", "style"):
            if tag.has_attr(attr):
                del tag[attr]
    return "".join(str(c) for c in root.contents).strip()


def by_slug(pages: list[dict]) -> dict:
    out = {}
    for p in pages:
        out[p["slug"]] = p
        out[p["slug"].rstrip("/")] = p
    return out


def news_title(page: dict, titles: dict) -> str:
    url = page.get("url", "").rstrip("/")
    decoded = urllib.parse.unquote(url)
    for key, title in titles.items():
        if urllib.parse.unquote(key.rstrip("/")) == decoded or key.rstrip("/") == url:
            return title
        if urllib.parse.unquote(key).split("/")[-1] == decoded.split("/")[-1]:
            return title
    last = page["slug"].rstrip("/").split("/")[-1].replace("-", " ")
    return last[:1].upper() + last[1:] if last else "Новость"


def news_date(slug: str) -> str:
    m = re.search(r"(20\d{2})/(\d{2})/(\d{2})", slug)
    return "-".join(m.groups()) if m else now_date()


def now_date() -> str:
    from datetime import date

    return date.today().isoformat()


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
            text = a.get_text(" ", strip=True) or "Документ"
            if href:
                docs.append({"title": text, "url": encode_url(href)})
        out.append({"name": name, "docs": docs})
    return out


def default_faq() -> str:
    return """
<p>На исходном сайте раздел «Вопрос-ответ» был пустым. Ниже — ответы из рабочих страниц компании.</p>
<h2>Когда передавать показания воды?</h2>
<p>С 15 по 25 число каждого месяца — через ЕРСИУ, почту uk-zhilvek@mail.ru или в офисе.</p>
<h2>Куда звонить при аварии?</h2>
<p>Единая диспетчерская ЖКХ круглосуточно: 8 800 550-31-15. Диспетчер УК: 8 977 477-79-78.</p>
<h2>Как оплатить квитанцию?</h2>
<p>По QR-коду в банковском приложении, в кабинете МосОблЕИРЦ или ЕРСИУ.</p>
<h2>Где отчёты по моему дому?</h2>
<p>В разделе «Ваш дом» — договор, протоколы и отчёты по адресу.</p>
<h2>Как заказать сантехника или электрика?</h2>
<p>Прейскурант в разделе «Услуги». Заявка — по телефонам УК или через форму на сайте.</p>
"""


def default_home() -> str:
    return """
<p class="kicker-text">Жуковский · 23 дома</p>
<p>ООО «УК «ЖилВек» обслуживает многоквартирные дома в Жуковском: содержание, ремонт, документы и ответы жителям.</p>
<p><strong>Показания ИПУ воды принимаются с 15 по 25 число каждого месяца.</strong></p>
"""


def seed(force: bool = False) -> None:
    init_db()
    with db() as conn:
        if get_setting(conn, "seeded") == "1" and not force:
            print("CMS already seeded. Use --force to reimport.")
            return

    scraped_path = ROOT / "scraped" / "site.json"
    titles_path = ROOT / "scraped" / "news-titles.json"
    if not scraped_path.exists() or not titles_path.exists():
        raise FileNotFoundError(
            "Нужны scraped/site.json и scraped/news-titles.json для первичного импорта"
        )
    scraped = json.loads(scraped_path.read_text(encoding="utf-8"))
    titles = json.loads(titles_path.read_text(encoding="utf-8"))
    pages_map = by_slug(scraped["pages"])

    with db() as conn:
        if force:
            conn.executescript(
                "DELETE FROM house_docs; DELETE FROM houses; DELETE FROM articles; DELETE FROM pages;"
            )

        set_setting(conn, "site_name", "УК «ЖилВек»")
        set_setting(conn, "phone", "8 499 842-39-20")
        set_setting(conn, "email", "uk-zhilvek@mail.ru")
        set_setting(conn, "eds_phone", "8 800 550-31-15")
        set_setting(conn, "address", "140185, Московская область, г. Жуковский, ул. Строительная, д. 14, корп. 2, пом. 2")

        for i, (slug, title, heading) in enumerate(EDITABLE_PAGES):
            existing = get_page(conn, slug=slug)
            if existing and not force:
                continue
            src = pages_map.get(slug)
            if slug == "home":
                body = default_home()
                desc = "ООО УК ЖилВек: обслуживание МКД в Жуковском"
            elif slug == "faq":
                body = default_faq() if not (src and (src.get("text") or "").strip()) else clean_body(src.get("html", ""))
                desc = "Частые вопросы жителей УК ЖилВек"
            elif slug == "vash-dom":
                body = "<p>Документы по домам управляются в разделе «Дома» админки. На сайте отображается актуальный список.</p>"
                desc = "Документы по домам под управлением УК ЖилВек"
            elif src:
                body = clean_body(src.get("html", ""))
                desc = title
            else:
                body = f"<p>{heading}</p>"
                desc = title
            save_page(
                conn,
                {
                    "slug": slug,
                    "title": title,
                    "heading": heading,
                    "body_html": body,
                    "description": desc,
                    "published": True,
                    "sort_order": i,
                },
                page_id=existing["id"] if existing else None,
            )

        seen = set()
        for p in scraped["pages"]:
            if p["kind"] != "post" or p["slug"] in seen:
                continue
            seen.add(p["slug"])
            soup = BeautifulSoup(p.get("html") or "", "lxml")
            text = soup.get_text(" ", strip=True)
            if SPAM.search(text):
                body = ""
                excerpt = ""
            else:
                body = clean_body(p.get("html", ""))
                excerpt = text[:180] + ("…" if len(text) > 180 else "")
            title = news_title(p, titles)
            save_article(
                conn,
                {
                    "slug": p["slug"].strip("/"),
                    "title": title,
                    "body_html": body,
                    "excerpt": excerpt,
                    "published_at": news_date(p["slug"]),
                    "published": True,
                },
            )

        vash = pages_map.get("vash-dom")
        for i, house in enumerate(extract_houses(vash.get("html", "") if vash else "")):
            save_house(
                conn,
                {
                    "name": house["name"],
                    "sort_order": i,
                    "published": True,
                    "docs": house["docs"],
                },
            )

        set_setting(conn, "seeded", "1")
        print("Seeded CMS database at", ROOT / "data" / "cms.db")


if __name__ == "__main__":
    import sys

    seed(force="--force" in sys.argv)
