"""Internal Argon2id admin credentials, opaque sessions and database-enforced permissions."""

import asyncio
import hashlib
import re
import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

hasher = PasswordHasher()
USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}\Z")
SESSION_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class AdminIdentity:
    id: UUID
    username: str
    role_code: str


def validate_credentials(username: str, password: str) -> str:
    username = username.strip().lower()
    if not USERNAME.fullmatch(username) or not 12 <= len(password) <= 1024:
        raise ValueError("invalid admin credentials")
    return username


async def create_admin(
    connection: asyncpg.Connection, username: str, password: str, *, role_code: str,
) -> UUID:
    """Bootstrap/internal only; never expose as an unauthenticated HTTP route."""
    username = validate_credentials(username, password)
    if role_code not in {"OWNER", "OPERATOR"}:
        raise ValueError("unknown role")
    password_hash = await asyncio.to_thread(hasher.hash, password)
    admin_id = uuid4()
    await connection.execute(
        """INSERT INTO admins (id,username,password_hash,role_code)
           VALUES ($1,$2,$3,$4)""",
        admin_id, username, password_hash, role_code,
    )
    return admin_id


async def authenticate(
    connection: asyncpg.Connection, username: str, password: str,
) -> AdminIdentity | None:
    username = username.strip().lower()
    if not USERNAME.fullmatch(username) or not password or len(password) > 1024:
        return None
    row = await connection.fetchrow(
        "SELECT id,username,role_code,password_hash FROM admins WHERE username=$1 AND enabled=true",
        username,
    )
    if not row:
        return None
    try:
        await asyncio.to_thread(hasher.verify, row["password_hash"], password)
    except (VerificationError, InvalidHashError):
        return None
    return AdminIdentity(row["id"], row["username"], row["role_code"])


async def audit(
    connection: asyncpg.Connection, admin_id: UUID, action: str, reason: str | None = None,
) -> None:
    if not action or len(action) > 100:
        raise ValueError("invalid audit action")
    await connection.execute(
        "INSERT INTO audit_logs (id,actor_admin_id,action,reason) VALUES ($1,$2,$3,$4)",
        uuid4(), admin_id, action, reason,
    )


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


async def create_session(connection: asyncpg.Connection, admin: AdminIdentity) -> str:
    token = secrets.token_urlsafe(32)
    async with connection.transaction():
        await connection.execute(
            """INSERT INTO admin_sessions (token_hash,admin_id,expires_at)
               VALUES ($1,$2,now() + ($3 * interval '1 second'))""",
            token_digest(token), admin.id, SESSION_SECONDS,
        )
        await audit(connection, admin.id, "ADMIN_LOGIN")
    return token


async def load_session(connection: asyncpg.Connection, token: str) -> AdminIdentity | None:
    if not token or len(token) > 128:
        return None
    row = await connection.fetchrow(
        """SELECT a.id,a.username,a.role_code FROM admin_sessions s
           JOIN admins a ON a.id=s.admin_id WHERE s.token_hash=$1
           AND s.revoked_at IS NULL AND s.expires_at>now() AND a.enabled=true""",
        token_digest(token),
    )
    return AdminIdentity(row["id"], row["username"], row["role_code"]) if row else None


async def has_permission(
    connection: asyncpg.Connection, admin: AdminIdentity, permission: str,
) -> bool:
    return bool(await connection.fetchval(
        """SELECT 1 FROM role_permissions WHERE role_code=$1 AND permission=$2""",
        admin.role_code, permission,
    ))


async def revoke_session(connection: asyncpg.Connection, token: str, admin: AdminIdentity) -> None:
    async with connection.transaction():
        await connection.execute(
            """UPDATE admin_sessions SET revoked_at=now()
               WHERE token_hash=$1 AND admin_id=$2 AND revoked_at IS NULL""",
            token_digest(token), admin.id,
        )
        await audit(connection, admin.id, "ADMIN_LOGOUT")
