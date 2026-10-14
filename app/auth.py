"""Simple session auth for admin."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from itsdangerous import BadSignature, URLSafeSerializer

SECRET = os.environ.get("CMS_SECRET", "zhilvek-local-dev-change-me")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "zhilvek2026")
COOKIE = "zhilvek_admin"


def serializer() -> URLSafeSerializer:
    return URLSafeSerializer(SECRET, salt="admin-session")


def check_password(username: str, password: str) -> bool:
    u_ok = hmac.compare_digest(username.strip(), ADMIN_USER)
    p_ok = hmac.compare_digest(password, ADMIN_PASSWORD)
    return u_ok and p_ok


def make_session(username: str) -> str:
    return serializer().dumps({"u": username, "n": secrets.token_hex(8)})


def read_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        data = serializer().loads(token)
        return data.get("u")
    except BadSignature:
        return None


def password_hint() -> str:
    """Never expose real password; used only in local README."""
    return hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()[:8]
