"""Real HTTP/proxy/catalog proof against the explicitly disposable admin CI deployment."""

import asyncio
import os
import secrets
import socket
from uuid import UUID, uuid4

import asyncpg
import httpx

from platform_core.admin_auth import create_admin
from platform_core.config import get_settings
from platform_core.login_limits import login_keys
from platform_core.service_catalog import available_summary_products
from platform_core.text_summary import SLUG, TEXT_INPUT_SCHEMA


async def main():
    settings = get_settings()
    if (os.environ.get("CI_CATALOG_TEST") != "1" or settings.telegram_bot_token
            or settings.telegram_stars_enabled or settings.telegram_orders_enabled):
        raise RuntimeError("catalog smoke requires an isolated CI database with no live bot/billing")
    db = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        with socket.create_connection(("caddy", 80), timeout=5) as connection:
            source_ip = connection.getsockname()[0]
        username = "ci-proxy-" + uuid4().hex
        headers = {
            "Host": "localhost", "Origin": "http://localhost", "Content-Type": "application/json",
            "X-Forwarded-For": "203.0.113.123", "X-Real-IP": "203.0.113.123",
        }
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            for url in ("http://caddy/api/admin/login", "http://api:8000/api/admin/login"):
                result = await client.post(url, headers=headers, json={"username": username, "password": "invalid"})
                assert result.status_code == 401
        assert await db.fetchval("SELECT attempts FROM admin_login_counters WHERE login_key=$1",
                                 login_keys(source_ip, username)[2]) == 2
        assert not await db.fetchval("SELECT 1 FROM admin_login_counters WHERE login_key=$1",
                                     login_keys("203.0.113.123", username)[2])
        print("DB-only proxy identity PASS: real client retained; forwarded spoof rejected")
        if os.environ.get("CI_CATALOG_IDENTITY_ONLY") == "1":
            return
        owner, password = "owner-" + uuid4().hex, secrets.token_urlsafe(32)
        await create_admin(db, owner, password, role_code="OWNER")
        async with httpx.AsyncClient(base_url="http://caddy", timeout=10, trust_env=False,
                                     headers={"Host": "localhost", "Origin": "http://localhost"}) as client:
            assert (await client.get("/admin")).status_code == 200
            assert (await client.get("/api/admin/services")).status_code == 401
            assert (await client.post("/api/admin/login", json={"username": owner, "password": password})).status_code == 200
            assert (await client.get("/api/admin/me")).json()["service_activation_enabled"]
            category = (await client.get("/api/admin/categories")).json()
            category_id = next(c["id"] for c in category if c["slug"] == "text-services")
            data = {
                "category_id": category_id, "slug": "ci-product-" + uuid4().hex,
                "name_ar": "خدمة اختبار من اللوحة", "description_ar": "تلخيص محلي",
                "processor_type": "tool", "processor_key": SLUG, "base_price_halalas": 0,
                "base_price_stars": 13, "input_schema": TEXT_INPUT_SCHEMA,
                "reason": "Disposable real HTTP catalog test",
            }
            created = await client.post("/api/admin/services", json=data)
            assert created.status_code == 200 and not created.json()["enabled"]
            product = UUID(created.json()["id"])
            assert await available_summary_products(db, service_id=product) == []
            path = f"/api/admin/services/{product}"
            changed = {"expected_revision": 1, "name_ar": "منتج محدّث", "base_price_stars": 17,
                       "reason": "Disposable price and name edit"}
            assert (await client.patch(path, json=changed, headers={"Origin": "http://evil.test"})).status_code == 403
            assert (await client.patch(path, json=changed)).status_code == 200
            assert (await client.patch(path, json=changed)).status_code == 409
            active = {"expected_revision": 2, "enabled": True, "confirm": True,
                      "reason": "Disposable product activation"}
            assert (await client.patch(path, json=active)).status_code == 200
            current = await available_summary_products(db, service_id=product)
            assert len(current) == 1 and current[0].name_ar == "منتج محدّث" and current[0].price_stars == 17
            stopped = {"expected_revision": 3, "enabled": False, "confirm": True,
                       "reason": "Disposable product withdrawal"}
            assert (await client.patch(path, json=stopped)).status_code == 200
            assert await available_summary_products(db, service_id=product) == []
            assert (await client.post("/api/admin/logout")).status_code == 200
            assert (await client.get("/api/admin/services")).status_code == 401
        print("Real minimal admin HTTP/catalog PASS: login, draft, rename/price, conflict, activate, withdraw, logout")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
