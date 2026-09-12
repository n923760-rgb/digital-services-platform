"""Authenticated, read-only operations API; permissions are always checked server-side."""

import hashlib
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from platform_core.admin_auth import (
    AdminIdentity,
    authenticate,
    create_session,
    has_permission,
    load_session,
    revoke_session,
)
from platform_core.backup_status import backup_health
from platform_core.config import get_settings
from platform_core.service_registry import (
    ServiceNotFound,
    ServiceRevisionConflict,
    ServiceUpdateRejected,
    update_service,
)
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt
from redis.exceptions import RedisError

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


AUTH_DEPENDENCY = Depends(identity)


async def require_view(admin: AdminIdentity = AUTH_DEPENDENCY) -> AdminIdentity:
    async with database() as db:
        allowed = await has_permission(db, admin, "admin:view")
    if not allowed:
        raise HTTPException(403, "Access denied")
    return admin


async def require_audit(admin: AdminIdentity = AUTH_DEPENDENCY) -> AdminIdentity:
    async with database() as db:
        allowed = await has_permission(db, admin, "admin:audit")
    if not allowed:
        raise HTTPException(403, "Access denied")
    return admin


async def require_manage(admin: AdminIdentity = AUTH_DEPENDENCY) -> AdminIdentity:
    async with database() as db:
        allowed = await has_permission(db, admin, "admin:manage")
    if not allowed:
        raise HTTPException(403, "Access denied")
    return admin


VIEW_DEPENDENCY = Depends(require_view)
AUDIT_DEPENDENCY = Depends(require_audit)
MANAGE_DEPENDENCY = Depends(require_manage)


class ServiceUpdateForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: StrictInt
    reason: str
    description_ar: str | None = None
    base_price_halalas: StrictInt | None = None
    enabled: StrictBool | None = None
    confirm: StrictBool = False


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
async def logout(request: Request, response: Response, admin: AdminIdentity = AUTH_DEPENDENCY):
    check_origin(request)
    async with database() as db:
        await revoke_session(db, request.cookies[COOKIE_NAME], admin)
    response.delete_cookie(COOKIE_NAME, path="/api/admin", secure=get_settings().admin_cookie_secure,
                           httponly=True, samesite="strict")
    return {"status": "signed_out"}


@router.get("/me")
async def me(admin: AdminIdentity = VIEW_DEPENDENCY):
    return {"username": admin.username, "role": admin.role_code,
            "service_activation_enabled": get_settings().service_activation_enabled}


@router.get("/overview")
async def overview(_admin: AdminIdentity = VIEW_DEPENDENCY):
    async with database() as db:
        row = await db.fetchrow("""SELECT
          (SELECT count(*) FROM orders WHERE created_at >= CURRENT_DATE) AS orders_today,
          (SELECT count(*) FROM orders WHERE status='PROCESSING') AS processing_orders,
          (SELECT count(*) FROM orders WHERE status='COMPLETED') AS completed_orders,
          (SELECT count(*) FROM orders WHERE status='FAILED') AS failed_orders,
          (SELECT count(*) FROM jobs WHERE status='FAILED') AS failed_jobs,
          (SELECT count(*) FROM delivery_outbox WHERE status='FAILED') AS failed_deliveries,
          (SELECT count(*) FROM payments WHERE status='PAID' AND paid_at >= CURRENT_DATE)
            AS wallet_topups_today,
          (SELECT count(*) FROM payments WHERE status='FAILED') AS failed_payments""")
    return {**dict(row), "backup": backup_health(get_settings().backup_status_path)}


@router.get("/orders")
async def orders(_admin: AdminIdentity = VIEW_DEPENDENCY):
    async with database() as db:
        rows = await db.fetch("""SELECT o.id,o.status,o.channel,o.price_snapshot_halalas,
          o.currency,o.created_at,s.name_ar AS service_name,
          (SELECT count(*) FROM jobs j WHERE j.order_id=o.id AND j.status='FAILED') AS failed_jobs
          FROM orders o JOIN services s ON s.id=o.service_id
          ORDER BY o.created_at DESC,o.id DESC LIMIT 100""")
    return [{**dict(row), "id": str(row["id"])} for row in rows]


@router.get("/services")
async def services(_admin: AdminIdentity = VIEW_DEPENDENCY):
    async with database() as db:
        rows = await db.fetch("""SELECT s.id,s.slug,s.name_ar,s.description_ar,
          s.base_price_halalas,s.processor_type,s.enabled,s.revision,
          c.name_ar AS category_name_ar FROM services s
          JOIN service_categories c ON c.id=s.category_id
          ORDER BY c.name_ar,s.name_ar,s.id LIMIT 200""")
    return [{**dict(row), "id": str(row["id"])} for row in rows]


@router.patch("/services/{service_id}")
async def edit_service(request: Request, service_id: UUID, form: ServiceUpdateForm,
                       admin: AdminIdentity = MANAGE_DEPENDENCY):
    check_origin(request)
    async with database() as db:
        try:
            return await update_service(
                db, service_id, admin.id,
                expected_revision=form.expected_revision,
                reason=form.reason,
                description_ar=form.description_ar,
                base_price_halalas=form.base_price_halalas,
                enabled=form.enabled,
                confirm=form.confirm,
                allow_activation=get_settings().service_activation_enabled,
            )
        except ServiceNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except ServiceRevisionConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except ServiceUpdateRejected as exc:
            raise HTTPException(422, str(exc)) from exc


@router.get("/attention")
async def attention(_admin: AdminIdentity = VIEW_DEPENDENCY):
    """Bounded operational failures; never return customer input or raw exception messages."""
    async with database() as db:
        jobs = await db.fetch("""SELECT j.id,j.order_id,j.error_code,j.attempt_count,
          j.max_attempts,j.completed_at AS failed_at,s.name_ar AS service_name
          FROM jobs j JOIN orders o ON o.id=j.order_id
          JOIN services s ON s.id=o.service_id
          WHERE j.status='FAILED' ORDER BY j.completed_at DESC NULLS LAST,j.id DESC LIMIT 20""")
        deliveries = await db.fetch("""SELECT d.id,d.order_id,d.error_code,d.attempt_count,
          d.max_attempts,d.completed_at AS failed_at,s.name_ar AS service_name
          FROM delivery_outbox d JOIN orders o ON o.id=d.order_id
          JOIN services s ON s.id=o.service_id
          WHERE d.status='FAILED' ORDER BY d.completed_at DESC NULLS LAST,d.id DESC LIMIT 20""")
        payments = await db.fetch("""SELECT id,provider,amount_halalas,created_at
          FROM payments WHERE status='FAILED' ORDER BY created_at DESC,id DESC LIMIT 20""")
    return {
        "jobs": [{**dict(row), "id": str(row["id"]), "order_id": str(row["order_id"])}
                 for row in jobs],
        "deliveries": [{**dict(row), "id": str(row["id"]), "order_id": str(row["order_id"])}
                       for row in deliveries],
        "payments": [{**dict(row), "id": str(row["id"])} for row in payments],
    }


@router.get("/audit")
async def audit_events(_admin: AdminIdentity = AUDIT_DEPENDENCY):
    async with database() as db:
        rows = await db.fetch("""SELECT l.id,l.action,l.reason,l.created_at,a.username
          FROM audit_logs l JOIN admins a ON a.id=l.actor_admin_id
          ORDER BY l.created_at DESC,l.id DESC LIMIT 100""")
    return [{**dict(row), "id": str(row["id"])} for row in rows]
