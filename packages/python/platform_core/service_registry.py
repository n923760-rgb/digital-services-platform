"""Audited, concurrency-safe service configuration independent of customer channels."""

import json
import re
from uuid import UUID, uuid4

import asyncpg

from platform_core.processors import PROCESSORS


class ServiceNotFound(ValueError):
    pass


class ServiceRevisionConflict(ValueError):
    pass


class ServiceUpdateRejected(ValueError):
    pass


SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
PROCESSOR_TYPES = {"ai", "tool", "template", "manual", "hybrid"}
PDF_INPUT_SCHEMA = {"min_files": 2, "max_files": 10, "file_mime": "application/pdf"}


def validate_new_entry(slug: str, name_ar: str, reason: str) -> tuple[str, str, str]:
    slug, name_ar, reason = slug.strip(), name_ar.strip(), reason.strip()
    if len(slug) > 60 or not SLUG.fullmatch(slug):
        raise ServiceUpdateRejected("invalid slug")
    if not 2 <= len(name_ar) <= 120:
        raise ServiceUpdateRejected("name must be 2–120 characters")
    if not 10 <= len(reason) <= 500:
        raise ServiceUpdateRejected("reason must be 10–500 characters")
    return slug, name_ar, reason


async def create_category(
    connection: asyncpg.Connection, actor_id: UUID, *, slug: str, name_ar: str, reason: str,
) -> UUID:
    slug, name_ar, reason = validate_new_entry(slug, name_ar, reason)
    async with connection.transaction():
        category_id = uuid4()
        created = await connection.fetchval("""INSERT INTO service_categories (id,slug,name_ar)
          VALUES ($1,$2,$3) ON CONFLICT (slug) DO NOTHING RETURNING id""",
          category_id, slug, name_ar)
        if created is None:
            existing = await connection.fetchrow(
                "SELECT id,name_ar FROM service_categories WHERE slug=$1", slug,
            )
            if existing["name_ar"] != name_ar:
                raise ServiceRevisionConflict("category slug already used")
            return existing["id"]
        await connection.execute("""INSERT INTO audit_logs
          (id,actor_admin_id,action,reason,metadata)
          VALUES ($1,$2,'CATEGORY_CREATED',$3,$4::jsonb)""",
          uuid4(), actor_id, reason,
          json.dumps({"category_id": str(category_id), "slug": slug, "name_ar": name_ar},
                     ensure_ascii=False))
        return category_id


async def create_service(
    connection: asyncpg.Connection, actor_id: UUID, *, category_id: UUID, slug: str,
    name_ar: str, description_ar: str, processor_type: str, base_price_halalas: int,
    input_schema: dict, reason: str,
) -> UUID:
    slug, name_ar, reason = validate_new_entry(slug, name_ar, reason)
    description_ar = description_ar.strip()
    if len(description_ar) > 1000:
        raise ServiceUpdateRejected("description too long")
    if processor_type not in PROCESSOR_TYPES:
        raise ServiceUpdateRejected("unknown processor type")
    if type(base_price_halalas) is not int or not 0 <= base_price_halalas <= 1_000_000:
        raise ServiceUpdateRejected("price must be between 0 and 10000 SAR")
    if not isinstance(input_schema, dict):
        raise ServiceUpdateRejected("input schema must be an object")
    try:
        schema_json = json.dumps(input_schema, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ServiceUpdateRejected("invalid input schema") from exc
    if len(schema_json.encode("utf-8")) > 4000:
        raise ServiceUpdateRejected("input schema too large")
    if slug == "merge-pdf" and (processor_type != "tool" or input_schema != PDF_INPUT_SCHEMA):
        raise ServiceUpdateRejected("merge-pdf needs its supported PDF schema")

    async with connection.transaction():
        if not await connection.fetchval("SELECT 1 FROM service_categories WHERE id=$1", category_id):
            raise ServiceNotFound("category not found")
        service_id = uuid4()
        created = await connection.fetchval("""INSERT INTO services
          (id,category_id,slug,name_ar,description_ar,processor_type,base_price_halalas,input_schema)
          VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
          ON CONFLICT (slug) DO NOTHING RETURNING id""",
          service_id, category_id, slug, name_ar, description_ar,
          processor_type, base_price_halalas, schema_json)
        if created is None:
            existing = await connection.fetchrow("""SELECT id,category_id,name_ar,description_ar,
              processor_type,base_price_halalas,input_schema FROM services WHERE slug=$1""", slug)
            stored_schema = existing["input_schema"]
            if isinstance(stored_schema, str):
                stored_schema = json.loads(stored_schema)
            if not (existing["category_id"] == category_id and existing["name_ar"] == name_ar
                    and existing["description_ar"] == description_ar
                    and existing["processor_type"] == processor_type
                    and existing["base_price_halalas"] == base_price_halalas
                    and stored_schema == input_schema):
                raise ServiceRevisionConflict("service slug already used")
            return existing["id"]
        await connection.execute("""INSERT INTO audit_logs
          (id,actor_admin_id,action,reason,metadata)
          VALUES ($1,$2,'SERVICE_CREATED',$3,$4::jsonb)""",
          uuid4(), actor_id, reason,
          json.dumps({"service_id": str(service_id), "category_id": str(category_id),
                      "slug": slug, "processor_type": processor_type, "enabled": False},
                     ensure_ascii=False))
        return service_id


async def update_service(
    connection: asyncpg.Connection, service_id: UUID, actor_id: UUID, *,
    expected_revision: int, reason: str, description_ar: str | None = None,
    base_price_halalas: int | None = None, enabled: bool | None = None,
    confirm: bool = False, allow_activation: bool = False,
) -> dict:
    """Lock service, validate the intended transition, then change and audit atomically."""
    reason = reason.strip()
    if not 10 <= len(reason) <= 500:
        raise ServiceUpdateRejected("reason must be 10–500 characters")
    if expected_revision < 1 or (description_ar is None and base_price_halalas is None
                                 and enabled is None):
        raise ServiceUpdateRejected("no valid update requested")
    if description_ar is not None and len(description_ar) > 1000:
        raise ServiceUpdateRejected("description too long")
    if base_price_halalas is not None and (type(base_price_halalas) is not int
                                           or not 0 <= base_price_halalas <= 1_000_000):
        raise ServiceUpdateRejected("price must be between 0 and 10000 SAR")
    if enabled is not None and type(enabled) is not bool:
        raise ServiceUpdateRejected("invalid enabled value")

    async with connection.transaction():
        row = await connection.fetchrow("""SELECT s.id,s.slug,s.processor_type,s.input_schema,
          s.description_ar,s.base_price_halalas,s.enabled,s.revision,
          c.enabled AS category_enabled FROM services s
          JOIN service_categories c ON c.id=s.category_id
          WHERE s.id=$1 FOR UPDATE OF s""", service_id)
        if row is None:
            raise ServiceNotFound("service not found")
        if row["revision"] != expected_revision:
            raise ServiceRevisionConflict("service was changed; reload before saving")

        description = row["description_ar"] if description_ar is None else description_ar.strip()
        price = row["base_price_halalas"] if base_price_halalas is None else base_price_halalas
        active = row["enabled"] if enabled is None else enabled
        if active == row["enabled"] and description == row["description_ar"] and price == row["base_price_halalas"]:
            return {"revision": row["revision"], "enabled": active,
                    "description_ar": description, "base_price_halalas": price}

        if enabled is not None and enabled != row["enabled"] and not confirm:
            raise ServiceUpdateRejected("confirm availability change explicitly")
        if active and not row["enabled"]:
            schema = row["input_schema"]
            if isinstance(schema, str):
                schema = json.loads(schema)
            safe_pdf_schema = (isinstance(schema, dict) and schema.get("min_files") == 2
                               and schema.get("max_files") == 10
                               and schema.get("file_mime") == "application/pdf")
            if not (allow_activation and row["category_enabled"] and row["processor_type"] == "tool"
                    and row["slug"] in PROCESSORS and safe_pdf_schema):
                raise ServiceUpdateRejected("service activation is unavailable")

        revision = row["revision"] + 1
        await connection.execute("""UPDATE services SET description_ar=$2,base_price_halalas=$3,
          enabled=$4,revision=$5,updated_at=now() WHERE id=$1""",
          service_id, description, price, active, revision)
        changes = {
            "service_id": str(service_id), "revision_before": row["revision"],
            "revision_after": revision,
            "before": {"description_ar": row["description_ar"],
                       "base_price_halalas": row["base_price_halalas"], "enabled": row["enabled"]},
            "after": {"description_ar": description,
                      "base_price_halalas": price, "enabled": active},
        }
        await connection.execute("""INSERT INTO audit_logs
          (id,actor_admin_id,action,reason,metadata) VALUES ($1,$2,'SERVICE_UPDATED',$3,$4::jsonb)""",
          uuid4(), actor_id, reason, json.dumps(changes, ensure_ascii=False))
        return {"revision": revision, "enabled": active,
                "description_ar": description, "base_price_halalas": price}
