#!/usr/bin/env python3
"""Build static site from scraped ук-жилвек.рф content."""
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import datetime
from html import escape
from pathlib import Path
import shutil

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "docs"
DATA = json.loads((ROOT / "scraped/site.json").read_text(encoding="utf-8"))
TITLES = json.loads((ROOT / "scraped/news-titles.json").read_text(encoding="utf-8"))
ORIGIN = "https://xn----dtbjckjff1e.xn--p1ai"
SPAM = re.compile(r"celebs nude|3ds max|stl without|jayla", re.I)

NAV = [
    ("/", "Главная"),
    ("/o-kompanii/", "О компании"),
    ("/uslugi/", "Услуги"),
    ("/vash-dom/", "Ваш дом"),
    ("/raskrytie-informacii/", "Раскрытие"),
    ("/novosti/", "Новости"),
    ("/kontakty/", "Контакты"),
]

LOGO = """<svg viewBox="0 0 42 42" fill="none" aria-hidden="true">
  <rect width="42" height="42" rx="12" fill="#1c4638"/>
  <path d="M8 24 L21 12 L34 24 V33 H8 Z" fill="#f4efe6"/>
  <rect x="18" y="24" width="6" height="9" fill="#c45e2b"/>
</svg>"""


def by_slug() -> dict:
    out = {}
    for p in DATA["pages"]:
        out[p["slug"]] = p
        out[p["slug"].rstrip("/")] = p
    return out


PAGES = by_slug()


def encode_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    url = url.replace("http://ук-жилвек.рф", ORIGIN).replace("https://ук-жилвек.рф", ORIGIN)
    url = url.replace("http://xn----dtbjckjff1e.xn--p1ai", ORIGIN)
    if url.startswith("//"):
        url = "https:" + url
    parts = urllib.parse.urlsplit(url)
    if not parts.scheme:
        return url
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%._-")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def local_path(href: str) -> str | None:
    if not href:
        return None
    raw = href.split("#")[0]
    if raw.startswith("/"):
        path = raw
    elif ORIGIN in raw or "ук-жилвек.рф" in raw or "xn----dtbjckjff1e" in raw:
        path = urllib.parse.urlparse(raw).path
    else:
        return None
    path = urllib.parse.unquote(path)
    if path.startswith("/wp-content/") or path.startswith("/wp-"):
        return None
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    if path == "//" or path == "":
        path = "/"
    mapping = {
        "/privacy-policy/": "/privacy-policy/",
        "/santekhnicheskie-raboty/": "/santekhnicheskie-raboty/",
        "/elektromontazhnye-raboty/": "/elektromontazhnye-raboty/",
        "/oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/": "/oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/",
        "/oplata-uslug-zhilishchno-kommunalnogo-hozyajstva": "/oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/",
        "/priem-pokazanij-individualnyh-priborov-uchyota-vody/": "/priem-pokazanij-individualnyh-priborov-uchyota-vody/",
        "/category/novosti/": "/novosti/",
        "/category/sobytiya/": "/novosti/",
    }
    return mapping.get(path, path)


def depth_of(rel: str) -> str:
    parts = [p for p in rel.strip("/").split("/") if p]
    n = max(len(parts) - 1, 0) if rel.endswith(".html") else len(parts)
    if rel in ("index.html", "/index.html"):
        n = 0
    return "../" * n


def page_file(path: str) -> Path:
    path = path if path.startswith("/") else "/" + path
    if path == "/":
        return WEB / "index.html"
    return WEB / path.strip("/") / "index.html"


def slug_title(slug: str) -> str:
    last = slug.rstrip("/").split("/")[-1]
    last = last.replace("-", " ")
    return last[:1].upper() + last[1:] if last else "Новость"


def news_title(page: dict) -> str:
    url = page.get("url", "").rstrip("/")
    decoded = urllib.parse.unquote(url)
    for key, title in TITLES.items():
        if urllib.parse.unquote(key.rstrip("/")) == decoded or key.rstrip("/") == url:
            return title
        if urllib.parse.unquote(key).split("/")[-1] == decoded.split("/")[-1]:
            return title
    return slug_title(page["slug"])


def news_date(slug: str) -> str:
    m = re.search(r"(20\d{2})/(\d{2})/(\d{2})", slug)
    if not m:
        return ""
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"


def news_iso(slug: str) -> str:
    m = re.search(r"(20\d{2})/(\d{2})/(\d{2})", slug)
    return "-".join(m.groups()) if m else ""


def all_news() -> list[dict]:
    seen = set()
    items = []
    for p in DATA["pages"]:
        if p["kind"] != "post":
            continue
        if p["slug"] in seen:
            continue
        seen.add(p["slug"])
        items.append(p)
    items.sort(key=lambda x: news_iso(x["slug"]), reverse=True)
    return items


def clean_body(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    root = soup.select_one(".entry-content") or soup
    for t in root.select("script, style, form, iframe"):
        t.decompose()
    for a in root.find_all("a", href=True):
        href = a["href"]
        loc = local_path(href)
        if loc:
            a["href"] = loc
        elif re.search(r"\.(pdf|docx?|xlsx?|zip|rtf)($|\?)", href, re.I) or "/wp-content/" in href:
            a["href"] = encode_url(href)
            a["target"] = "_blank"
            a["rel"] = "noopener"
        for attr in list(a.attrs):
            if attr.startswith("data-"):
                del a[attr]
    for tag in root.find_all(True):
        if tag.has_attr("class"):
            del tag["class"]
        if tag.has_attr("style"):
            del tag["style"]
    inner = "".join(str(c) for c in root.contents)
    inner = re.sub(r"\n{3,}", "\n", inner)
    return inner.strip()


def houses() -> list[dict]:
    raw = PAGES.get("vash-dom", {}).get("html", "")
    soup = BeautifulSoup(raw, "lxml")
    out = []
    root = soup.select_one(".entry-content") or soup
    headings = root.find_all("h3")
    groups = root.select(".wpsm_panel-group")
    for name_el, group in zip(headings, groups):
        name = re.sub(r"\s+", " ", name_el.get_text(" ", strip=True)).strip() or "Дом"
        docs = []
        for a in group.select(".wpsm_panel-body a[href]"):
            href = a.get("href", "")
            text = a.get_text(" ", strip=True) or "Документ"
            if href:
                docs.append({"text": text, "href": encode_url(href)})
        out.append({"name": name, "docs": docs})
    return out


def disclosure_links() -> list[dict]:
    raw = PAGES.get("raskrytie-informacii", {}).get("html", "")
    soup = BeautifulSoup(raw, "lxml")
    items = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        if text and href and "/wp-content/" in href:
            items.append({"text": text, "href": encode_url(href)})
    return items


def company_docs() -> list[dict]:
    raw = PAGES.get("o-kompanii", {}).get("html", "")
    soup = BeautifulSoup(raw, "lxml")
    items = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        if text and href and ("/wp-content/" in href or re.search(r"\.(pdf|docx?)$", href, re.I)):
            items.append({"text": text, "href": encode_url(href)})
    return items


def chrome(title: str, desc: str, path: str, body: str, active: str = "") -> str:
    prefix = depth_of(path if path != "/" else "index.html")
    nav = []
    for href, label in NAV:
        on = " is-on" if (active or path) == href else ""
        nav.append(f'<a class="{on.strip()}" href="{prefix}{href.lstrip("/")}{"index.html" if False else href if href!="/" else "index.html"}">{label}</a>')
    # fix nav hrefs with prefix
    nav_html = []
    for href, label in NAV:
        url = (prefix + "index.html") if href == "/" else prefix + href.strip("/") + "/"
        cls = "is-on" if (active or path).rstrip("/") == href.rstrip("/") or (href == "/" and path == "/") else ""
        nav_html.append(f'<a class="{cls}" href="{url}">{label}</a>')
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Manrope:wght@400;500;650;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<div class="topbar">
  <div class="wrap">
    <span>УК «ЖилВек» · Жуковский</span>
    <span>
      <a href="tel:+74998423920">8 499 842-39-20</a> ·
      <a href="mailto:uk-zhilvek@mail.ru">uk-zhilvek@mail.ru</a> ·
      круглосуточно ЭДС <a href="tel:+78005503115">8 800 550-31-15</a>
    </span>
  </div>
</div>
<header class="site-head">
  <div class="wrap">
    <a class="logo" href="{prefix}index.html">
      {LOGO}
      <span><b>УК «ЖилВек»</b><small>управляем домами Жуковского</small></span>
    </a>
    <button class="burger" type="button" aria-label="Меню">Меню</button>
    <nav class="main">{"".join(nav_html)}</nav>
  </div>
</header>
{body}
<footer>
  <div class="wrap f-grid">
    <div>
      <h4>ООО «УК «ЖилВек»</h4>
      <p>140185, Московская область, г. Жуковский, ул. Строительная, д. 14, корп. 2, пом. 2</p>
      <p>ИНН 7703461801 · ОГРН 1187746657295<br>лицензия на управление МКД</p>
    </div>
    <div>
      <h4>Жителям</h4>
      <a href="{prefix}priem-pokazanij-individualnyh-priborov-uchyota-vody/">Передать показания</a>
      <a href="{prefix}oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/">Оплатить ЖКУ</a>
      <a href="{prefix}vash-dom/">Документы дома</a>
      <a href="{prefix}raskrytie-informacii/">Раскрытие информации</a>
      <a href="{prefix}faq/">Вопрос-ответ</a>
    </div>
    <div>
      <h4>Компания</h4>
      <a href="{prefix}o-kompanii/">О компании</a>
      <a href="{prefix}uslugi/">Платные услуги</a>
      <a href="{prefix}kontakty/">Контакты</a>
      <a href="{prefix}rekvizity/">Реквизиты</a>
      <a href="{prefix}privacy-policy/">Политика конфиденциальности</a>
    </div>
  </div>
  <div class="wrap copy">© {year} ООО «Управляющая компания «ЖилВек». Контент перенесён с ук-жилвек.рф</div>
</footer>
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def write(path: str, html: str) -> None:
    f = page_file(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(html, encoding="utf-8")


def news_cards(prefix: str, limit: int | None = None) -> str:
    rows = []
    for p in all_news()[: limit or 999]:
        title = news_title(p)
        date = news_date(p["slug"])
        href = prefix + p["slug"].strip("/") + "/"
        soup = BeautifulSoup(p.get("html") or "", "lxml")
        text = soup.get_text(" ", strip=True)
        if SPAM.search(text):
            excerpt = ""
        else:
            excerpt = text[:180] + ("…" if len(text) > 180 else "")
        rows.append(
            f'<a class="card news-item" href="{href}"><time>{escape(date)}</time><div><h3>{escape(title)}</h3><p class="muted">{escape(excerpt)}</p></div></a>'
        )
    return '<div class="news-list">' + "".join(rows) + "</div>"


def home() -> str:
    news = []
    for p in all_news()[:6]:
        title = news_title(p)
        date = news_date(p["slug"])
        href = p["slug"].strip("/") + "/"
        soup = BeautifulSoup(p.get("html") or "", "lxml")
        text = soup.get_text(" ", strip=True)
        excerpt = "" if SPAM.search(text) else (text[:140] + ("…" if len(text) > 140 else ""))
        news.append(
            f'<a class="card news-item" href="{href}"><time>{escape(date)}</time><div><strong>{escape(title)}</strong><p class="muted">{escape(excerpt)}</p></div></a>'
        )
    body = f"""
<section class="hero">
  <div class="wrap hero-grid">
    <div>
      <p class="kicker">Жуковский · 23 дома</p>
      <h1>Дом в порядке — каждый день, а не только в отчёте</h1>
      <p class="lead">ООО «УК «ЖилВек» обслуживает многоквартирные дома в Жуковском: содержание, ремонт, документы и ответы жителям без очереди в тёмном кабинете.</p>
      <div class="actions">
        <a class="btn btn-p" href="priem-pokazanij-individualnyh-priborov-uchyota-vody/">Передать показания</a>
        <a class="btn btn-s" href="oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/">Оплатить счёт</a>
        <a class="btn btn-g" href="kontakty/">Написать в УК</a>
      </div>
    </div>
    <div class="meter-card">
      <p class="kicker">ИПУ воды</p>
      <div class="num">15–25</div>
      <p>числа каждого месяца принимаем показания счётчиков воды. Можно через ЕРСИУ, почту или офис.</p>
      <p class="muted">Аварийная служба ЖКХ 24/7: <a href="tel:+78005503115">8 800 550-31-15</a></p>
    </div>
  </div>
</section>
<div class="wrap stats">
  <div class="card stat"><b>23</b><span>дома под управлением</span></div>
  <div class="card stat"><b>143 182</b><span>м² жилого фонда</span></div>
  <div class="card stat"><b>20</b><span>сотрудников в компании</span></div>
  <div class="card stat"><b>с 2018</b><span>года работаем в городе</span></div>
</div>
<section class="section">
  <div class="wrap">
    <h2>Что можно сделать на сайте</h2>
    <div class="grid-3">
      <a class="card" href="vash-dom/"><h3>Ваш дом</h3><p class="muted">Договоры управления, протоколы ОСС и отчёты по каждому адресу.</p></a>
      <a class="card" href="uslugi/"><h3>Платные услуги</h3><p class="muted">Прейскурант сантехники и электрики — без сюрпризов в счёте.</p></a>
      <a class="card" href="raskrytie-informacii/"><h3>Раскрытие информации</h3><p class="muted">Тарифы и бухгалтерская отчётность, как требует стандарт раскрытия.</p></a>
    </div>
  </div>
</section>
<section class="section">
  <div class="wrap grid-2">
    <div>
      <h2>Последние новости</h2>
      <div class="news-list">{"".join(news)}</div>
      <p><a href="novosti/">Все новости</a></p>
    </div>
    <div>
      <h2>Обратная связь</h2>
      <div class="card">
        <p class="muted">Форма уходит письмом на uk-zhilvek@mail.ru. Для аварии звоните диспетчеру.</p>
        <form class="form feedback">
          <input name="name" required placeholder="Ваше имя">
          <input name="contact" required placeholder="Телефон или email">
          <textarea name="message" rows="5" placeholder="Обращение"></textarea>
          <p class="muted">Отправляя форму, вы соглашаетесь с <a href="privacy-policy/">политикой конфиденциальности</a>.</p>
          <button class="btn btn-p" type="submit">Отправить</button>
        </form>
        <p class="ok-msg">Откроется почтовая программа. Если нет — напишите на uk-zhilvek@mail.ru</p>
      </div>
    </div>
  </div>
</section>
"""
    return chrome(
        "УК «ЖилВек» — управляющая компания в Жуковском",
        "ООО УК ЖилВек: обслуживание МКД в Жуковском, показания ИПУ, оплата ЖКУ, документы домов и раскрытие информации.",
        "/",
        body,
        "/",
    )


def simple_page(path: str, heading: str, inner: str, desc: str, crumb: str = "") -> str:
    crumbs = crumb or f'<a href="../index.html">Главная</a> / {escape(heading)}'
    # home-relative crumbs using depth
    prefix = depth_of(path)
    crumbs = f'<a href="{prefix}index.html">Главная</a> / {escape(heading)}'
    body = f"""
<section class="page-hero"><div class="wrap">
  <p class="crumb">{crumbs}</p>
  <h1>{escape(heading)}</h1>
</div></section>
<section class="section"><div class="wrap">{inner}</div></section>
"""
    return chrome(f"{heading} — УК «ЖилВек»", desc, path, body, path)


def build() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    assets = WEB / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "app.js"):
        src = ROOT / "theme" / name
        if src.exists():
            shutil.copy2(src, assets / name)
    (WEB / ".nojekyll").write_text("", encoding="utf-8")
    write("/", home())

    # about
    docs = "".join(f'<li><a href="{d["href"]}" target="_blank" rel="noopener">{escape(d["text"])}</a></li>' for d in company_docs())
    about = """
<div class="grid-2">
  <div class="prose">
    <p>Общество с ограниченной ответственностью «Управляющая компания «ЖилВек». Сокращённое наименование: ООО УК «ЖилВек».</p>
    <h2>Юридический адрес</h2>
    <p>140185 Московская обл., г. Жуковский, ул. Строительная, д. 14, корпус 2, помещение 2</p>
    <h2>Фактический адрес</h2>
    <p>140185 Московская обл., г. Жуковский, ул. Строительная, д. 14, корпус 2, помещение 2</p>
    <h2>Генеральный директор</h2>
    <p>Казарин Александр Сергеевич</p>
    <h2>Документы компании</h2>
    <ul>""" + docs + """</ul>
  </div>
  <div>
    <div class="card"><h3>Реквизиты</h3>
      <p>ОГРН 1187746657295<br>ИНН 7703461801<br>КПП 504001001<br>ОКПО 31616410<br>ОКВЭД 68.32.1<br>ОКТМО 45380000<br>ОКОПФ 12300<br>ОКФС 16</p>
      <p>Расчётный счёт 40702810340000076775<br>БИК 044525225<br>ПАО Сбербанк г. Москва<br>к/с 30101810400000000225</p>
      <p><a href="../rekvizity/">Страница реквизитов</a></p>
    </div>
  </div>
</div>
<div class="stats" style="margin-top:24px">
  <div class="card stat"><b>23</b><span>домов под управлением</span></div>
  <div class="card stat"><b>143 182,22</b><span>м² площади домов</span></div>
  <div class="card stat"><b>20</b><span>сотрудников</span></div>
  <div class="card stat"><b>4 / 3 / 14</b><span>администрация / инженеры / рабочие</span></div>
</div>
"""
    write("/o-kompanii/", simple_page("/o-kompanii/", "О компании", about, "Реквизиты, лицензия и сведения об ООО УК ЖилВек."))

    uslugi = """
<p class="lead">Платные работы сверх содержания общего имущества — по прейскуранту.</p>
<div class="grid-2">
  <a class="card" href="../santekhnicheskie-raboty/"><h3>Сантехнические услуги</h3><p class="muted">Вызов сантехника, замена приборов, стояки, канализация. Материалы отдельно.</p></a>
  <a class="card" href="../elektromontazhnye-raboty/"><h3>Электромонтажные услуги</h3><p class="muted">Вызов электрика, автоматы, щитки, освещение, поиск неисправности.</p></a>
</div>
"""
    write("/uslugi/", simple_page("/uslugi/", "Услуги", uslugi, "Платные сантехнические и электромонтажные услуги УК ЖилВек."))

    for slug, heading in [
        ("santekhnicheskie-raboty", "Сантехнические работы"),
        ("elektromontazhnye-raboty", "Электромонтажные работы"),
    ]:
        inner = f'<div class="prose">{clean_body(PAGES[slug]["html"])}</div>'
        write(f"/{slug}/", simple_page(f"/{slug}/", heading, inner, f"Прейскурант: {heading} УК ЖилВек."))

    house_html = ['<input class="search" id="houseSearch" type="search" placeholder="Найти дом — улица или номер">']
    for h in houses():
        docs_h = "".join(
            f'<a href="{d["href"]}" target="_blank" rel="noopener">{escape(d["text"])}<span class="muted">PDF / DOC</span></a>'
            for d in h["docs"]
        )
        house_html.append(
            f'<details class="house" data-name="{escape(h["name"])}"><summary>{escape(h["name"])} <span class="muted">{len(h["docs"])} док.</span></summary><div class="docs">{docs_h}</div></details>'
        )
    write(
        "/vash-dom/",
        simple_page(
            "/vash-dom/",
            "Ваш дом",
            "<p class=\"muted\">Документы открываются с текущего сайта ук-жилвек.рф — договоры, протоколы ОСС, решения ГЖИ и отчёты.</p>"
            + "".join(house_html),
            "Документы по домам под управлением УК ЖилВек в Жуковском.",
        ),
    )

    disc = "".join(
        f'<a class="card" href="{d["href"]}" target="_blank" rel="noopener"><h3>{escape(d["text"])}</h3><p class="muted">Скачать документ</p></a>'
        for d in disclosure_links()
    )
    write(
        "/raskrytie-informacii/",
        simple_page(
            "/raskrytie-informacii/",
            "Раскрытие информации",
            '<div class="grid-3">' + (disc or "<p>Документы появятся после выгрузки.</p>") + "</div>",
            "Тарифы и бухгалтерская отчётность ООО УК ЖилВек.",
        ),
    )

    contacts = """
<div class="contacts-grid">
  <div class="card">
    <p class="kicker">Авария · 24/7</p>
    <h3>Единая диспетчерская служба ЖКХ</h3>
    <a class="phone" href="tel:+78005503115">8 800 550-31-15</a>
  </div>
  <div class="card">
    <p class="kicker">Управляющая компания</p>
    <a class="phone" href="tel:+74998423920">8 499 842-39-20</a>
    <p>Диспетчер УК: <a href="tel:+79774777978">8 977 477-79-78</a><br>
    <a href="tel:+79162339063">8 916 233-90-63</a></p>
    <p><a href="mailto:uk-zhilvek@mail.ru">uk-zhilvek@mail.ru</a></p>
  </div>
  <div class="card">
    <h3>Начисления и тарифы</h3>
    <p>МосОблЕИРЦ — <a href="https://mosobleirc.ru" target="_blank" rel="noopener">mosobleirc.ru</a>, тел. <a href="tel:+74994440100">8 499 444-01-00</a></p>
    <p>ЕРСИУ — <a href="https://zhukerciu.ru" target="_blank" rel="noopener">zhukerciu.ru</a>, тел. <a href="tel:+79651142900">8 965 114-29-00</a><br>
    <span class="muted">для адресов: Полевая 52, Маяковского 8, Нижегородская 28Б к. 1–4</span></p>
  </div>
  <div class="card">
    <h3>Время работы</h3>
    <p>Понедельник–пятница 08:00–17:00, перерыв 13:00–14:00</p>
    <p>Приём населения 09:00–16:00, перерыв 13:00–14:00, кроме пятницы (работа с документами)</p>
    <p>Приём генерального директора по личным вопросам — по записи, четверг 10:00–17:00, тел. 8 916 233-90-63</p>
  </div>
</div>
<div class="card" style="margin-top:14px">
  <h3>Адрес офиса</h3>
  <p>140185, Московская обл., г. Жуковский, ул. Строительная, д. 14, корп. 2, помещение 2</p>
  <iframe title="Карта" src="https://yandex.ru/map-widget/v1/?ll=38.1445%2C55.5974&z=16&text=%D0%96%D1%83%D0%BA%D0%BE%D0%B2%D1%81%D0%BA%D0%B8%D0%B9%20%D0%A1%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F%2014" width="100%" height="320" frameborder="0" style="border:0;border-radius:12px"></iframe>
</div>
<div class="card" style="margin-top:14px">
  <h3>Написать обращение</h3>
  <form class="form feedback">
    <input name="name" required placeholder="Ваше имя">
    <input name="contact" required placeholder="Телефон или email">
    <textarea name="message" rows="5" placeholder="Обращение"></textarea>
    <p class="muted">Согласие с <a href="../privacy-policy/">политикой конфиденциальности</a></p>
    <button class="btn btn-p" type="submit">Отправить</button>
  </form>
  <p class="ok-msg">Откроется почтовая программа.</p>
</div>
"""
    write("/kontakty/", simple_page("/kontakty/", "Контакты", contacts, "Телефоны, график и адрес УК ЖилВек в Жуковском."))

    oplata = """
<div class="prose">
  <p>Оплатить коммунальные услуги можно после того, как придёт квитанция — в личный кабинет или на бумаге.</p>
  <h2>По QR-коду с квитанции</h2>
  <p>QR-код в правом верхнем углу квитанции на оплату ЖКХ. В приложении банка отсканируйте код камерой смартфона — подтянутся реквизиты и сумма.</p>
  <p>Как именно работает оплата по QR, уточняйте в банке, который выпустил карту.</p>
  <h2>Где ещё оплатить</h2>
  <ul>
    <li><a href="https://mosobleirc.ru" target="_blank" rel="noopener">Личный кабинет МосОблЕИРЦ</a></li>
    <li><a href="https://zhukerciu.ru" target="_blank" rel="noopener">ЕРСИУ — zhukerciu.ru</a> (Полевая 52, Маяковского 8, Нижегородская 28Б)</li>
  </ul>
</div>
"""
    write(
        "/oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/",
        simple_page(
            "/oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/",
            "Оплата услуг ЖКХ",
            oplata,
            "Как оплатить квитанцию УК ЖилВек: QR-код, МосОблЕИРЦ, ЕРСИУ.",
        ),
    )

    meters = """
<div class="prose">
  <p><strong>Приём показаний ИПУ воды — с 15 по 25 число каждого месяца.</strong></p>
  <p>Передать показатели можно одним из способов:</p>
  <h2>На сайте ЕРСИУ</h2>
  <p><a href="https://zhukerciu.ru" target="_blank" rel="noopener">zhukerciu.ru</a>, тел. 8 965 114-29-00 — адреса Полевая 52, Маяковского 8, Нижегородская 28Б к. 1, 2, 3, 4 и паркинг.</p>
  <h2>На почту</h2>
  <p>Письмом на <a href="mailto:uk-zhilvek@mail.ru">uk-zhilvek@mail.ru</a></p>
  <h2>На бумаге в офисе</h2>
  <p>Московская обл., г. Жуковский, ул. Строительная, д. 14, корпус 2, помещение 2. Пн–пт 08:00–17:00.</p>
</div>
"""
    write(
        "/priem-pokazanij-individualnyh-priborov-uchyota-vody/",
        simple_page(
            "/priem-pokazanij-individualnyh-priborov-uchyota-vody/",
            "Приём показаний ИПУ воды",
            meters,
            "Передать показания счётчиков воды в УК ЖилВек с 15 по 25 число.",
        ),
    )

    faq = """
<div class="prose">
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
</div>
"""
    write("/faq/", simple_page("/faq/", "Вопрос-ответ", faq, "Частые вопросы жителей УК ЖилВек."))

    rekv = f'<div class="prose">{clean_body(PAGES["rekvizity"]["html"])}</div>'
    write("/rekvizity/", simple_page("/rekvizity/", "Реквизиты", rekv, "Банковские и налоговые реквизиты ООО УК ЖилВек."))

    privacy = f'<div class="prose">{clean_body(PAGES["privacy-policy"]["html"])}</div>'
    write("/privacy-policy/", simple_page("/privacy-policy/", "Политика конфиденциальности", privacy, "Политика обработки персональных данных ООО УК ЖилВек."))

    # news index + posts
    write(
        "/novosti/",
        simple_page("/novosti/", "Новости", news_cards("../"), "Новости и объявления УК ЖилВек."),
    )
    write("/category/novosti/", simple_page("/category/novosti/", "Новости", news_cards("../../"), "Лента новостей УК ЖилВек."))
    write("/category/sobytiya/", simple_page("/category/sobytiya/", "События", news_cards("../../"), "События УК ЖилВек."))

    for p in all_news():
        title = news_title(p)
        date = news_date(p["slug"])
        soup = BeautifulSoup(p.get("html") or "", "lxml")
        text = soup.get_text(" ", strip=True)
        if SPAM.search(text) or not text.strip():
            inner = f'<p class="muted">{escape(date)}</p><div class="prose"><p>Текст объявления на исходном сайте не сохранился или был повреждён. Заголовок перенесён как на ук-жилвек.рф.</p></div>'
        else:
            inner = f'<p class="muted">{escape(date)}</p><div class="prose">{clean_body(p["html"])}</div>'
        path = "/" + p["slug"].strip("/") + "/"
        write(path, simple_page(path, title, inner, title))

    print("built pages into", WEB)


if __name__ == "__main__":
    build()
