"""Small authenticated local setup command; no dashboard or manual schema edits."""

import argparse
import asyncio
import logging
from getpass import getpass

import asyncpg

from platform_core.admin_auth import authenticate
from platform_core.config import get_settings
from platform_core.logging import configure_logging
from platform_core.service_registry import update_service
from platform_core.text_summary import SLUG

logger = logging.getLogger(__name__)


async def configure(args):
    settings = get_settings()
    configure_logging(settings.log_level)
    username = input("Owner username: ")
    password = getpass("Owner password: ")
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""), timeout=3)
    try:
        owner = await authenticate(connection, username, password)
        if owner is None or owner.role_code != "OWNER":
            logger.warning("summary_setup_not_authorized")
            raise PermissionError("OWNER credentials required")
        service = await connection.fetchrow("SELECT id,revision FROM services WHERE slug=$1", SLUG)
        if service is None:
            raise RuntimeError("Run the migrations first")
        result = await update_service(
            connection, owner.id, service["id"], expected_revision=service["revision"],
            base_price_stars=args.price_stars, enabled=True if args.activate else None,
            confirm=args.activate, allow_activation=settings.service_activation_enabled,
            reason=args.reason,
        )
        print(f"Service revision: {result['revision']}; enabled: {result['enabled']}")
    finally:
        await connection.close()


def main():
    parser = argparse.ArgumentParser(description="Configure the single text-summary service as OWNER")
    parser.add_argument("--price-stars", type=int, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--activate", action="store_true", help="Also requires SERVICE_ACTIVATION_ENABLED")
    args = parser.parse_args()
    try:
        asyncio.run(configure(args))
    except (ValueError, PermissionError, RuntimeError, asyncpg.PostgresError, OSError) as exc:
        logger.error("summary_setup_failed", extra={"error_class": type(exc).__name__})
        raise SystemExit("Setup failed; check role, revision, price and activation configuration") from None


if __name__ == "__main__":
    main()
