"""Publish CMS content into static docs/ for GitHub Pages."""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from app.db import ROOT, db, dump_json, list_articles, list_houses, list_pages
from app.uploads import sync_uploads_to_docs

WEB = ROOT / "docs"
THEME = ROOT / "theme"

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


def depth_of(path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    return "../" * len(parts)


def page_file(path: str) -> Path:
    if path == "/":
        return WEB / "index.html"
    return WEB / path.strip("/") / "index.html"


def write(path: str, html: str) -> None:
    f = page_file(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(html, encoding="utf-8")


def fmt_date(iso: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m:
        return iso or ""
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"


def chrome(title: str, desc: str, path: str, body: str) -> str:
    prefix = depth_of(path if path != "/" else "")
    nav_html = []
    for href, label in NAV:
        url = (prefix + "index.html") if href == "/" else prefix + href.strip("/") + "/"
        cls = "is-on" if path.rstrip("/") == href.rstrip("/") or (href == "/" and path == "/") else ""
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
  <div class="wrap copy">© {year} ООО «Управляющая компания «ЖилВек»</div>
</footer>
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def simple_page(path: str, heading: str, inner: str, desc: str) -> str:
    prefix = depth_of(path)
    body = f"""
<section class="page-hero"><div class="wrap">
  <p class="crumb"><a href="{prefix}index.html">Главная</a> / {escape(heading)}</p>
  <h1>{escape(heading)}</h1>
</div></section>
<section class="section"><div class="wrap">{inner}</div></section>
"""
    return chrome(f"{heading} — УК «ЖилВек»", desc, path, body)


def build_home(articles: list[dict]) -> str:
    news = []
    for a in articles[:6]:
        href = a["slug"].strip("/") + "/"
        news.append(
            f'<a class="card news-item" href="{href}"><time>{escape(fmt_date(a["published_at"]))}</time>'
            f'<div><strong>{escape(a["title"])}</strong><p class="muted">{escape(a.get("excerpt") or "")}</p></div></a>'
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
        "ООО УК ЖилВек: обслуживание МКД в Жуковском, показания ИПУ, оплата ЖКУ, документы домов.",
        "/",
        body,
    )


def public_doc_url(url: str, prefix: str = "../") -> str:
    """Rewrite /uploads/... for static pages (GitHub Pages project path safe)."""
    if url.startswith("/uploads/"):
        return prefix + url.lstrip("/")
    return url


def build_houses(houses: list[dict]) -> str:
    blocks = ['<input class="search" id="houseSearch" type="search" placeholder="Найти дом — улица или номер">']
    for h in houses:
        docs = "".join(
            f'<a href="{escape(public_doc_url(d["url"]))}" target="_blank" rel="noopener">{escape(d["title"])}'
            f'<span class="muted">файл</span></a>'
            for d in h.get("docs") or []
        )
        blocks.append(
            f'<details class="house" data-name="{escape(h["name"])}">'
            f'<summary>{escape(h["name"])} <span class="muted">{len(h.get("docs") or [])} док.</span></summary>'
            f'<div class="docs">{docs}</div></details>'
        )
    return (
        '<p class="muted">Документы открываются по ссылкам из карточки дома.</p>'
        + "".join(blocks)
    )


def build_news_list(articles: list[dict], prefix: str) -> str:
    rows = []
    for a in articles:
        rows.append(
            f'<a class="card news-item" href="{prefix}{a["slug"].strip("/")}/">'
            f'<time>{escape(fmt_date(a["published_at"]))}</time>'
            f'<div><h3>{escape(a["title"])}</h3><p class="muted">{escape(a.get("excerpt") or "")}</p></div></a>'
        )
    return '<div class="news-list">' + "".join(rows) + "</div>"


def publish() -> Path:
    WEB.mkdir(parents=True, exist_ok=True)
    assets = WEB / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "app.js"):
        src = THEME / name
        if src.exists():
            shutil.copy2(src, assets / name)
    (WEB / ".nojekyll").write_text("", encoding="utf-8")
    sync_uploads_to_docs(WEB)

    with db() as conn:
        pages = {p["slug"]: p for p in list_pages(conn, published_only=True)}
        articles = list_articles(conn, published_only=True)
        houses = list_houses(conn, published_only=True)

    write("/", build_home(articles))

    for slug, page in pages.items():
        if slug == "home":
            continue
        if slug == "vash-dom":
            inner = build_houses(houses)
        else:
            inner = f'<div class="prose">{page.get("body_html") or ""}</div>'
            if slug == "uslugi" and not (page.get("body_html") or "").strip():
                inner = """
<p class="lead">Платные работы сверх содержания общего имущества — по прейскуранту.</p>
<div class="grid-2">
  <a class="card" href="../santekhnicheskie-raboty/"><h3>Сантехнические услуги</h3><p class="muted">Вызов сантехника, замена приборов, стояки, канализация.</p></a>
  <a class="card" href="../elektromontazhnye-raboty/"><h3>Электромонтажные услуги</h3><p class="muted">Вызов электрика, автоматы, щитки, освещение.</p></a>
</div>
"""
            if slug == "kontakty":
                # keep editable body, append form if missing
                body = page.get("body_html") or ""
                if "feedback" not in body:
                    body += """
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
                inner = f'<div class="prose">{body}</div>' if '<div class="contacts' not in body else body
        path = f"/{slug}/"
        write(path, simple_page(path, page["heading"], inner, page.get("description") or page["title"]))

    write("/novosti/", simple_page("/novosti/", "Новости", build_news_list(articles, "../"), "Новости УК ЖилВек"))

    for a in articles:
        path = "/" + a["slug"].strip("/") + "/"
        body_html = a.get("body_html") or ""
        if not body_html.strip():
            inner = (
                f'<p class="muted">{escape(fmt_date(a["published_at"]))}</p>'
                f'<div class="prose"><p>Текст объявления пока не заполнен. Отредактируйте статью в админке.</p></div>'
            )
        else:
            inner = f'<p class="muted">{escape(fmt_date(a["published_at"]))}</p><div class="prose">{body_html}</div>'
        write(path, simple_page(path, a["title"], inner, a["title"]))

    dump_json()
    return WEB


if __name__ == "__main__":
    out = publish()
    print("Published to", out)
