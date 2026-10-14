"""CMS + static site for УК ЖилВек."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import auth
from app.db import (
    ROOT,
    db,
    delete_article,
    delete_house,
    get_article,
    get_house,
    get_page,
    init_db,
    list_articles,
    list_houses,
    list_pages,
    save_article,
    save_house,
    save_page,
)
from app.publish import publish
from app.seed import seed

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

app = FastAPI(title="УК ЖилВек CMS")
app.mount("/admin/static", StaticFiles(directory=str(APP_DIR / "static")), name="admin-static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed(force=False)
    if not (ROOT / "docs" / "index.html").exists():
        publish()


def current_user(request: Request) -> str | None:
    return auth.read_session(request.cookies.get(auth.COOKIE))


def require_user(request: Request) -> str:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    return user


def flash_redirect(url: str, message: str) -> RedirectResponse:
    resp = RedirectResponse(url, status_code=303)
    resp.set_cookie("flash", quote(message, safe=""), max_age=8, httponly=True)
    return resp


def read_flash(request: Request) -> str:
    raw = request.cookies.get("flash", "")
    return unquote(raw) if raw else ""


def render(request: Request, name: str, ctx: dict, status: int = 200) -> HTMLResponse:
    response = templates.TemplateResponse(
        request,
        name,
        {**ctx, "request": request, "flash": ctx.get("flash") or read_flash(request)},
        status_code=status,
    )
    if request.cookies.get("flash"):
        response.delete_cookie("flash")
    return response


# -------- auth --------

@app.get("/admin/login", response_class=HTMLResponse)
def login_form(request: Request):
    if current_user(request):
        return RedirectResponse("/admin/", status_code=303)
    resp = templates.TemplateResponse(
        request,
        "admin/login.html",
        {"request": request, "user": None, "flash": read_flash(request), "section": "login"},
    )
    if request.cookies.get("flash"):
        resp.delete_cookie("flash")
    return resp


@app.post("/admin/login")
def login(username: str = Form(...), password: str = Form(...)):
    if not auth.check_password(username, password):
        return flash_redirect("/admin/login", "Неверный логин или пароль")
    resp = RedirectResponse("/admin/", status_code=303)
    resp.set_cookie(auth.COOKIE, auth.make_session(username), httponly=True, samesite="lax")
    return resp


@app.post("/admin/logout")
def logout():
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie(auth.COOKIE)
    return resp


# -------- dashboard --------

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        counts = {
            "articles": len(list_articles(conn)),
            "houses": len(list_houses(conn)),
            "pages": len(list_pages(conn)),
        }
    return render(
        request,
        "admin/dashboard.html",
        {"user": user, "section": "dash", "counts": counts, "flash": ""},
    )


# -------- articles --------

@app.get("/admin/articles", response_class=HTMLResponse)
def articles_list(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        items = list_articles(conn)
    return render(request, "admin/articles.html", {"user": user, "section": "articles", "articles": items, "flash": ""})


@app.get("/admin/articles/new", response_class=HTMLResponse)
def article_new(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    return render(
        request,
        "admin/article_edit.html",
        {"user": user, "section": "articles", "item": None, "today": date.today().isoformat(), "flash": ""},
    )


@app.get("/admin/articles/{article_id}", response_class=HTMLResponse)
def article_edit(request: Request, article_id: int):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        item = get_article(conn, article_id=article_id)
    if not item:
        raise HTTPException(404)
    return render(
        request,
        "admin/article_edit.html",
        {"user": user, "section": "articles", "item": item, "today": date.today().isoformat(), "flash": ""},
    )


@app.post("/admin/articles/new")
def article_create(
    request: Request,
    title: str = Form(...),
    slug: str = Form(...),
    published_at: str = Form(...),
    excerpt: str = Form(""),
    body_html: str = Form(""),
    published: str | None = Form(None),
):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        aid = save_article(
            conn,
            {
                "title": title,
                "slug": slug,
                "published_at": published_at,
                "excerpt": excerpt,
                "body_html": body_html,
                "published": published == "1",
            },
        )
    return flash_redirect(f"/admin/articles/{aid}", "Статья сохранена")


@app.post("/admin/articles/{article_id}")
def article_update(
    request: Request,
    article_id: int,
    title: str = Form(...),
    slug: str = Form(...),
    published_at: str = Form(...),
    excerpt: str = Form(""),
    body_html: str = Form(""),
    published: str | None = Form(None),
):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        if not get_article(conn, article_id=article_id):
            raise HTTPException(404)
        save_article(
            conn,
            {
                "title": title,
                "slug": slug,
                "published_at": published_at,
                "excerpt": excerpt,
                "body_html": body_html,
                "published": published == "1",
            },
            article_id=article_id,
        )
    return flash_redirect(f"/admin/articles/{article_id}", "Статья сохранена")


@app.post("/admin/articles/{article_id}/delete")
def article_delete(request: Request, article_id: int):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        delete_article(conn, article_id)
    return flash_redirect("/admin/articles", "Статья удалена")


# -------- houses --------

@app.get("/admin/houses", response_class=HTMLResponse)
def houses_list(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        items = list_houses(conn)
    return render(request, "admin/houses.html", {"user": user, "section": "houses", "houses": items, "flash": ""})


@app.get("/admin/houses/new", response_class=HTMLResponse)
def house_new(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    return render(request, "admin/house_edit.html", {"user": user, "section": "houses", "item": None, "flash": ""})


@app.get("/admin/houses/{house_id}", response_class=HTMLResponse)
def house_edit(request: Request, house_id: int):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        item = get_house(conn, house_id)
    if not item:
        raise HTTPException(404)
    return render(request, "admin/house_edit.html", {"user": user, "section": "houses", "item": item, "flash": ""})


def _docs_from_form(doc_title: list[str], doc_url: list[str]) -> list[dict]:
    docs = []
    for title, url in zip(doc_title, doc_url):
        title, url = title.strip(), url.strip()
        if title and url:
            docs.append({"title": title, "url": url})
    return docs


@app.post("/admin/houses/new")
async def house_create(request: Request):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    form = await request.form()
    docs = _docs_from_form(form.getlist("doc_title"), form.getlist("doc_url"))
    with db() as conn:
        hid = save_house(
            conn,
            {
                "name": str(form.get("name") or ""),
                "sort_order": int(form.get("sort_order") or 0),
                "published": form.get("published") == "1",
                "docs": docs,
            },
        )
    return flash_redirect(f"/admin/houses/{hid}", "Дом сохранён")


@app.post("/admin/houses/{house_id}")
async def house_update(request: Request, house_id: int):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    form = await request.form()
    docs = _docs_from_form(form.getlist("doc_title"), form.getlist("doc_url"))
    with db() as conn:
        if not get_house(conn, house_id):
            raise HTTPException(404)
        save_house(
            conn,
            {
                "name": str(form.get("name") or ""),
                "sort_order": int(form.get("sort_order") or 0),
                "published": form.get("published") == "1",
                "docs": docs,
            },
            house_id=house_id,
        )
    return flash_redirect(f"/admin/houses/{house_id}", "Дом сохранён")


@app.post("/admin/houses/{house_id}/delete")
def house_delete(request: Request, house_id: int):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        delete_house(conn, house_id)
    return flash_redirect("/admin/houses", "Дом удалён")


# -------- pages --------

@app.get("/admin/pages", response_class=HTMLResponse)
def pages_list(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        items = list_pages(conn)
    return render(request, "admin/pages.html", {"user": user, "section": "pages", "pages": items, "flash": ""})


@app.get("/admin/pages/{page_id}", response_class=HTMLResponse)
def page_edit(request: Request, page_id: int):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        item = get_page(conn, page_id=page_id)
    if not item:
        raise HTTPException(404)
    return render(request, "admin/page_edit.html", {"user": user, "section": "pages", "item": item, "flash": ""})


@app.post("/admin/pages/{page_id}")
def page_update(
    request: Request,
    page_id: int,
    heading: str = Form(...),
    title: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    body_html: str = Form(""),
    sort_order: int = Form(0),
    published: str | None = Form(None),
):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        if not get_page(conn, page_id=page_id):
            raise HTTPException(404)
        save_page(
            conn,
            {
                "heading": heading,
                "title": title,
                "slug": slug,
                "description": description,
                "body_html": body_html,
                "sort_order": sort_order,
                "published": published == "1",
            },
            page_id=page_id,
        )
    return flash_redirect(f"/admin/pages/{page_id}", "Страница сохранена")


# -------- publish --------

@app.get("/admin/publish", response_class=HTMLResponse)
def publish_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    flash = read_flash(request)
    return render(
        request,
        "admin/publish.html",
        {"user": user, "section": "publish", "last_result": flash, "flash": flash},
    )


@app.post("/admin/publish")
def publish_now(request: Request):
    if not current_user(request):
        return RedirectResponse("/admin/login", status_code=303)
    out = publish()
    return flash_redirect("/admin/publish", f"Сайт обновлён: {out}")


# Public site last — must not shadow /admin routes
app.mount("/", StaticFiles(directory=str(ROOT / "docs"), html=True), name="site")
