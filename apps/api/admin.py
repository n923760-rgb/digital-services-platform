"""Authenticated, read-only operations API; permissions are always checked server-side."""

import hashlib
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from redis.exceptions import RedisError

from platform_core.admin_auth import (
    AdminIdentity,
    authenticate,
    create_session,
    has_permission,
    load_session,
    revoke_session,
)
from platform_core.config import get_settings

router = APIRouter(prefix="/api/admin")
COOKIE_NAME = "platform_admin_session"


@asynccontextmanager
async def database():
    db = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
    try:
        yield db
    finally:
        await db.close()


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin", "")
    parsed = urlsplit(origin)
    host = request.headers.get("host", "")
    scheme = "https" if get_settings().admin_cookie_secure else "http"
    if parsed.scheme != scheme or parsed.netloc != host or parsed.path or not origin:
        raise HTTPException(403, "Invalid origin")


class LoginForm(BaseModel):
    username: str
    password: str


async def identity(request: Request) -> AdminIdentity:
    token = request.cookies.get(COOKIE_NAME, "")
    async with database() as db:
        admin = await load_session(db, token)
    if not admin:
        raise HTTPException(401, "Sign in required")
    return admin


async def require_view(admin: AdminIdentity = Depends(identity)) -> AdminIdentity:
    async with database() as db:
        allowed = await has_permission(db, admin, "admin:view")
    if not allowed:
        raise HTTPException(403, "Access denied")
    return admin


async def require_audit(admin: AdminIdentity = Depends(identity)) -> AdminIdentity:
    async with database() as db:
        allowed = await has_permission(db, admin, "admin:audit")
    if not allowed:
        raise HTTPException(403, "Access denied")
    return admin


@router.post("/login")
async def login(request: Request, form: LoginForm, response: Response):
    check_origin(request)
    # One limit per IP+username, including unknown users; do not log raw usernames.
    ip = request.client.host if request.client else "unknown"
    key = "admin:login:" + hashlib.sha256(
        (ip + ":" + form.username.strip().lower()).encode()
    ).hexdigest()
    try:
        count = await request.app.state.redis.incr(key)
        if count == 1:
            await request.app.state.redis.expire(key, 900)
    except (RedisError, OSError) as exc:
        raise HTTPException(503, "Login temporarily unavailable") from exc
    if count > 5:
        raise HTTPException(429, "Too many attempts")
    async with database() as db:
        admin = await authenticate(db, form.username, form.password)
        if not admin:
            raise HTTPException(401, "Invalid credentials")
        token = await create_session(db, admin)
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=get_settings().admin_cookie_secure,
        samesite="strict", path="/api/admin", max_age=12 * 60 * 60,
    )
    return {"username": admin.username, "role": admin.role_code}


@router.post("/logout")
async def logout(request: Request, response: Response, admin: AdminIdentity = Depends(identity)):
    check_origin(request)
    async with database() as db:
        await revoke_session(db, request.cookies[COOKIE_NAME], admin)
    response.delete_cookie(COOKIE_NAME, path="/api/admin", secure=get_settings().admin_cookie_secure,
                           httponly=True, samesite="strict")
    return {"status": "signed_out"}


@router.get("/me")
async def me(admin: AdminIdentity = Depends(require_view)):
    return {"username": admin.username, "role": admin.role_code}


@router.get("/overview")
async def overview(_admin: AdminIdentity = Depends(require_view)):
    async with database() as db:
        row = await db.fetchrow("""SELECT
          (SELECT count(*) FROM orders WHERE created_at >= CURRENT_DATE) AS orders_today,
          (SELECT count(*) FROM orders WHERE status='PROCESSING') AS processing_orders,
          (SELECT count(*) FROM orders WHERE status='COMPLETED') AS completed_orders,
          (SELECT count(*) FROM orders WHERE status='FAILED') AS failed_orders,
          (SELECT count(*) FROM jobs WHERE status='FAILED') AS failed_jobs,
          (SELECT count(*) FROM delivery_outbox WHERE status='FAILED') AS failed_deliveries""")
    return dict(row)


@router.get("/orders")
async def orders(_admin: AdminIdentity = Depends(require_view)):
    async with database() as db:
        rows = await db.fetch("""SELECT o.id,o.status,o.channel,o.price_snapshot_halalas,
          o.currency,o.created_at,s.name_ar AS service_name,
          (SELECT count(*) FROM jobs j WHERE j.order_id=o.id AND j.status='FAILED') AS failed_jobs
          FROM orders o JOIN services s ON s.id=o.service_id
          ORDER BY o.created_at DESC,o.id DESC LIMIT 100""")
    return [{**dict(row), "id": str(row["id"])} for row in rows]


@router.get("/audit")
async def audit_events(_admin: AdminIdentity = Depends(require_audit)):
    async with database() as db:
        rows = await db.fetch("""SELECT l.id,l.action,l.reason,l.created_at,a.username
          FROM audit_logs l JOIN admins a ON a.id=l.actor_admin_id
          ORDER BY l.created_at DESC,l.id DESC LIMIT 100""")
    return [{**dict(row), "id": str(row["id"])} for row in rows]
