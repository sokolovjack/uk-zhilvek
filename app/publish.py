"""Publish CMS content into static docs/ for GitHub Pages."""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from app.db import ROOT, db, dump_json, list_articles, list_houses, list_pages
from app.uploads import sync_files_archive_to_docs, sync_uploads_to_docs

WEB = ROOT / "docs"
THEME = ROOT / "theme"

NAV = [
    ("/", "Главная"),
    ("/o-kompanii/", "О компании"),
    ("/uslugi/", "Услуги"),
    ("/vash-dom/", "Ваш дом"),
    ("/raskrytie-informacii/", "Раскрытие информации"),
    ("/novosti/", "Новости"),
    ("/kontakty/", "Контакты"),
]

def depth_of(path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    return "../" * len(parts)


def logo_html(prefix: str) -> str:
    return f'<img src="{prefix}assets/logo.png" width="48" height="48" alt="">'


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
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}assets/style.css">
<link rel="icon" href="{prefix}assets/favicon.ico" sizes="any">
<link rel="icon" type="image/png" href="{prefix}assets/favicon-16.png" sizes="16x16">
<link rel="icon" type="image/png" href="{prefix}assets/favicon-32.png" sizes="32x32">
<link rel="icon" type="image/png" href="{prefix}assets/favicon-48.png" sizes="48x48">
<link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon.png" sizes="180x180">
<link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon-152x152.png" sizes="152x152">
<link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon-167x167.png" sizes="167x167">
<link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon-180x180.png" sizes="180x180">
<link rel="manifest" href="{prefix}assets/site.webmanifest">
<meta name="theme-color" content="#253b80">
<meta name="msapplication-TileColor" content="#253b80">
<meta name="msapplication-config" content="{prefix}assets/browserconfig.xml">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ЖилВек">
<meta name="application-name" content="УК ЖилВек">
<meta name="mobile-web-app-capable" content="yes">
</head>
<body>
<div class="top-bar">
  <div class="wrap">
    <span>Московская обл., г. Жуковский, ул. Строительная д. 14 корп. 2</span>
    <div class="top-bar-contacts">
      <a href="tel:+74998423920">8 (499) 842-39-20</a>
      <span class="top-bar-sep">|</span>
      <a href="mailto:uk-zhilvek@mail.ru">uk-zhilvek@mail.ru</a>
    </div>
  </div>
</div>
<header class="site-head">
  <div class="wrap header-inner">
    <a class="logo" href="{prefix}index.html">
      {logo_html(prefix)}
      <span><b>УК «ЖилВек»</b><small>управляем домами</small></span>
    </a>
    <nav class="main">{"".join(nav_html)}</nav>
    <button class="burger" type="button" aria-label="Меню">Меню</button>
  </div>
</header>
{body}
<footer class="footer">
  <div class="wrap">
    <div class="footer-grid">
      <div>
        <h4>УК «ЖилВек»</h4>
        <p>Московская обл., г. Жуковский,<br>ул. Строительная д. 14 корп. 2</p>
        <a href="tel:+74998423920">8 (499) 842-39-20</a>
        <a href="mailto:uk-zhilvek@mail.ru">uk-zhilvek@mail.ru</a>
      </div>
      <div>
        <h4>Разделы</h4>
        <a href="{prefix}o-kompanii/">О компании</a>
        <a href="{prefix}vash-dom/">Ваш дом</a>
        <a href="{prefix}raskrytie-informacii/">Раскрытие информации</a>
        <a href="{prefix}kontakty/">Контакты</a>
      </div>
      <div>
        <h4>Жителям</h4>
        <a href="{prefix}priem-pokazanij-individualnyh-priborov-uchyota-vody/">Передать показания</a>
        <a href="{prefix}oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/">Оплатить ЖКУ</a>
        <a href="{prefix}faq/">Задать вопрос</a>
        <a href="{prefix}privacy-policy/">Политика конфиденциальности</a>
      </div>
    </div>
    <div class="copyright">© {year} ООО «УК «ЖилВек». Все права защищены.</div>
  </div>
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
        excerpt = escape(a.get("excerpt") or "")
        news.append(
            f'<a class="news-item" href="{href}">'
            f'<time class="news-date">{escape(fmt_date(a["published_at"]))}</time>'
            f'<div class="news-content"><h4>{escape(a["title"])}</h4>'
            f'{"<p>" + excerpt + "</p>" if excerpt else ""}</div></a>'
        )
    body = f"""
<section class="hero">
  <div class="wrap hero-grid">
    <div>
      <span class="badge">Жуковский · 30 домов</span>
      <h1>Приём показаний индивидуальных приборов учёта воды</h1>
      <p class="hero-desc">ООО «УК «ЖилВек» обслуживает многоквартирные дома в Жуковском: содержание, ремонт, документы и оперативные ответы жителям.</p>
      <div class="actions">
        <a class="btn btn-primary" href="priem-pokazanij-individualnyh-priborov-uchyota-vody/">Передать показания</a>
        <a class="btn btn-secondary" href="oplata-uslug-zhilishchno-kommunalnogo-hozyajstva/">Оплатить счёт</a>
        <a class="btn btn-outline" href="kontakty/">Написать в УК</a>
      </div>
    </div>
    <div class="meter-card">
      <h3>ИПУ воды</h3>
      <div class="meter-dates">15 – 25</div>
      <p>числа каждого месяца принимаем показания счётчиков воды. Передайте через личный кабинет МосОблЕИРЦ, на почту или лично в офисе.</p>
      <div class="emergency">
        <div class="emergency-icon">!</div>
        <div>
          <div class="emergency-text">Аварийная служба ЖКХ 24/7:</div>
          <a class="emergency-phone" href="tel:+78005503115">8 (800) 550-31-15</a>
        </div>
      </div>
    </div>
  </div>
</section>
<section class="stats">
  <div class="wrap stats-grid">
    <div><span class="stat-num">30</span><div class="stat-label">домов под управлением</div></div>
    <div><span class="stat-num">226 412</span><div class="stat-label">м² жилого фонда</div></div>
    <div><span class="stat-num">40</span><div class="stat-label">сотрудников в компании</div></div>
    <div><span class="stat-num">8 · 6 · 26</span><div class="stat-label">админ / инженеры / рабочие</div></div>
  </div>
</section>
<section class="section">
  <div class="wrap">
    <h2 class="section-title">Жителям</h2>
    <div class="cards-grid">
      <a class="card" href="vash-dom/">
        <h3>Ваш дом</h3>
        <p>Договоры управления, протоколы ОСС и отчёты по каждому адресу. Найдите свой дом в реестре.</p>
        <span class="card-link">Найти дом →</span>
      </a>
      <a class="card" href="uslugi/">
        <h3>Платные услуги</h3>
        <p>Прейскурант на работы сантехники и электрика. Оставьте заявку на вызов мастера онлайн.</p>
        <span class="card-link">Смотреть прайс →</span>
      </a>
      <a class="card" href="raskrytie-informacii/">
        <h3>Раскрытие информации</h3>
        <p>Тарифы, бухгалтерская отчётность и лицензионные требования в соответствии с законом.</p>
        <span class="card-link">Открыть документы →</span>
      </a>
    </div>
  </div>
</section>
<section class="section section-paper">
  <div class="wrap">
    <h2 class="section-title">Последние новости</h2>
    <div class="news-list">{"".join(news)}</div>
    <div class="news-more"><a class="btn btn-outline" href="novosti/">Все новости</a></div>
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
            f'<summary>{escape(h["name"])}</summary>'
            f'<div class="docs">{docs}</div></details>'
        )
    return (
        '<p class="muted">Документы открываются по ссылкам из карточки дома.</p>'
        + "".join(blocks)
    )


def build_news_list(articles: list[dict], prefix: str) -> str:
    rows = []
    for a in articles:
        excerpt = escape(a.get("excerpt") or "")
        rows.append(
            f'<a class="news-item" href="{prefix}{a["slug"].strip("/")}/">'
            f'<time class="news-date">{escape(fmt_date(a["published_at"]))}</time>'
            f'<div class="news-content"><h4>{escape(a["title"])}</h4>'
            f'{"<p>" + excerpt + "</p>" if excerpt else ""}</div></a>'
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
    theme_assets = THEME / "assets"
    asset_names = (
        "logo.png",
        "eds.jpg",
        "favicon.ico",
        "favicon-16.png",
        "favicon-32.png",
        "favicon-48.png",
        "favicon-180.png",
        "favicon-192.png",
        "apple-touch-icon.png",
        "apple-touch-icon-152x152.png",
        "apple-touch-icon-167x167.png",
        "apple-touch-icon-180x180.png",
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "mstile-150x150.png",
        "site.webmanifest",
        "browserconfig.xml",
    )
    for name in asset_names:
        src = theme_assets / name
        if not src.exists() and name == "logo.png":
            src = ROOT / "logo-100.png"
        if src.exists():
            shutil.copy2(src, assets / name)
    (WEB / ".nojekyll").write_text("", encoding="utf-8")
    sync_uploads_to_docs(WEB)
    sync_files_archive_to_docs(WEB)

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
    <button class="btn btn-secondary" type="submit">Отправить</button>
  </form>
    <p class="ok-msg">Обращение уйдёт на uk-zhilvek@mail.ru через почтовую программу.</p>
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
