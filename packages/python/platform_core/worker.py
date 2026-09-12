import logging
from typing import ClassVar
from urllib.parse import urlparse

import asyncpg
import boto3
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from arq.connections import RedisSettings
from arq.cron import cron

from apps.telegram_bot.delivery import send_result
from platform_core.config import get_settings
from platform_core.delivery import (
    claim_delivery,
    fail_delivery,
    finish_delivery,
    recover_stale_deliveries,
)
from platform_core.files import FileUnavailable, InvalidFile, cleanup_expired_files
from platform_core.jobs import claim_job, complete_job, fail_job, pending_jobs, recover_stale_jobs
from platform_core.logging import configure_logging
from platform_core.pdf_isolation import PDFProcessorUnavailable
from platform_core.pdf_merge import InvalidPDF
from platform_core.processors import PROCESSORS
from platform_core.storage_s3 import S3Storage

settings = get_settings()
configure_logging(settings.log_level)
redis_url = urlparse(settings.redis_url)
logger = logging.getLogger(__name__)


async def worker_heartbeat(ctx) -> None:
    # ARQ writes its own health key; this no-op proves scheduled tasks can execute.
    return None


async def dispatch_pending(ctx) -> None:
    """Database PENDING rows survive Redis outages and are redispatched later."""
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        for job_id, attempt in await pending_jobs(connection):
            await ctx["redis"].enqueue_job(
                "process_job", str(job_id), _job_id=f"platform:{job_id}:{attempt}",
            )
    finally:
        await connection.close()


async def recover_processing(ctx) -> None:
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        recovered = await recover_stale_jobs(connection)
        if recovered:
            logger.warning("stale_jobs_recovered", extra={"count": recovered})
    finally:
        await connection.close()


async def dispatch_deliveries(ctx) -> None:
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    bot = None
    try:
        for _ in range(10):
            claim = await claim_delivery(connection)
            if claim is None:
                break
            if not settings.telegram_bot_token:
                logger.error("delivery_token_missing", extra={"order_id": str(claim.order_id)})
                await fail_delivery(connection, claim, "TELEGRAM_NOT_CONFIGURED", retryable=False)
                continue
            if bot is None:
                bot = Bot(token=settings.telegram_bot_token)
            try:
                storage = S3Storage(boto3.client(
                    "s3", endpoint_url=settings.object_storage_endpoint,
                    aws_access_key_id=settings.object_storage_access_key,
                    aws_secret_access_key=settings.object_storage_secret_key,
                    region_name=settings.object_storage_region,
                ))
                receipt = await send_result(
                    bot, connection, storage, settings.object_storage_bucket, claim,
                )
                await finish_delivery(connection, claim, receipt)
            except (FileUnavailable, TelegramBadRequest, TelegramForbiddenError, ValueError):
                logger.exception("delivery_permanent_failure", extra={"order_id": str(claim.order_id)})
                await fail_delivery(connection, claim, "DELIVERY_REJECTED", retryable=False)
            except Exception:
                logger.exception("delivery_transient_failure", extra={"order_id": str(claim.order_id)})
                await fail_delivery(connection, claim, "DELIVERY_ERROR", retryable=True)
    finally:
        if bot is not None:
            await bot.session.close()
        await connection.close()


async def recover_deliveries(ctx) -> None:
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        recovered = await recover_stale_deliveries(connection)
        if recovered:
            logger.warning("stale_deliveries_recovered", extra={"count": recovered})
    finally:
        await connection.close()


async def cleanup_files(ctx) -> None:
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        client = boto3.client(
            "s3", endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
        )
        deleted = await cleanup_expired_files(
            connection, S3Storage(client), settings.object_storage_bucket,
        )
        if deleted:
            logger.info("expired_files_deleted", extra={"count": deleted})
    finally:
        await connection.close()


async def process_job(ctx, job_id: str) -> None:
    """Process registered tools and retain successful output for later delivery."""
    from uuid import UUID

    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        claim = await claim_job(connection, UUID(job_id))
        if claim is None:
            return
        service = await connection.fetchrow(
            """SELECT s.slug,s.processor_type FROM orders o JOIN services s ON s.id=o.service_id
               WHERE o.id=$1""", claim.order_id,
        )
        processor = PROCESSORS.get(service["slug"]) if service["processor_type"] == "tool" else None
        if processor is None:
            logger.error("service_processor_unavailable", extra={"job_id": job_id})
            await fail_job(connection, claim, "PROCESSOR_UNAVAILABLE", retryable=False)
            return
        try:
            storage = S3Storage(boto3.client(
                "s3", endpoint_url=settings.object_storage_endpoint,
                aws_access_key_id=settings.object_storage_access_key,
                aws_secret_access_key=settings.object_storage_secret_key,
                region_name=settings.object_storage_region,
            ))
            result_file_id = await processor(
                connection, storage, settings.object_storage_bucket, claim.order_id,
                max_upload_bytes=settings.max_upload_bytes,
                retention_days=settings.file_retention_days,
            )
            await complete_job(connection, claim, result_file_id)
        except (InvalidPDF, InvalidFile, FileUnavailable, ValueError):
            logger.exception("service_input_invalid", extra={"job_id": job_id})
            await fail_job(connection, claim, "INVALID_INPUT", retryable=False)
        except PDFProcessorUnavailable:
            logger.exception("pdf_processor_unavailable", extra={"job_id": job_id})
            await fail_job(connection, claim, "PDF_PROCESSOR_UNAVAILABLE", retryable=True)
        except Exception:
            logger.exception("service_processing_failed", extra={"job_id": job_id})
            await fail_job(connection, claim, "PROCESSING_ERROR", retryable=True)
    finally:
        await connection.close()


class WorkerSettings:
    functions: ClassVar[list] = [process_job]
    max_jobs = 1
    cron_jobs: ClassVar[list] = [
        cron(worker_heartbeat, second={0, 30}),
        cron(dispatch_pending, second={5, 35}),
        cron(recover_processing, second={15, 45}),
        cron(dispatch_deliveries, second={10, 40}),
        cron(recover_deliveries, second={25, 55}),
        cron(cleanup_files, minute={0}, second={20}),
    ]
    job_timeout = 120
    redis_settings = RedisSettings(
        host=redis_url.hostname or "localhost",
        port=redis_url.port or 6379,
        database=int(redis_url.path.strip("/") or 0),
        password=redis_url.password,
    )
    health_check_key = "platform:worker:health"
