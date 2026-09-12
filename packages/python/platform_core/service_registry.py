"""Audited, concurrency-safe service configuration independent of customer channels."""

import json
from uuid import UUID, uuid4

import asyncpg

from platform_core.processors import PROCESSORS


class ServiceNotFound(ValueError):
    pass


class ServiceRevisionConflict(ValueError):
    pass


class ServiceUpdateRejected(ValueError):
    pass


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
