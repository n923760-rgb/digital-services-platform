"""Create the first owner interactively from the API container's terminal."""

import asyncio
import getpass

import asyncpg

from platform_core.admin_auth import create_admin
from platform_core.config import get_settings


async def bootstrap(username: str, password: str) -> None:
    db = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
    try:
        async with db.transaction():
            await db.execute("SELECT pg_advisory_xact_lock(918249001)")
            if await db.fetchval("SELECT count(*) FROM admins WHERE role_code='OWNER'"):
                raise ValueError("Owner already exists; bootstrap is disabled")
            await create_admin(db, username, password, role_code="OWNER")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(bootstrap(input("Owner username: "), getpass.getpass("Owner password: ")))
    print("Owner created")
