"""Read services supported by a running processor; no channel owns registry state."""

import json
from dataclasses import dataclass
from uuid import UUID

import asyncpg

from platform_core.processors import PROCESSORS
from platform_core.service_registry import PDF_INPUT_SCHEMA


@dataclass(frozen=True)
class CatalogService:
    id: UUID
    slug: str
    name_ar: str
    category_name_ar: str
    price_halalas: int


async def available_services(
    connection: asyncpg.Connection, *, service_id: UUID | None = None,
) -> list[CatalogService]:
    """Only expose enabled services with a registered, schema-compatible processor."""
    slugs = list(PROCESSORS)
    if not slugs:
        return []
    rows = await connection.fetch("""SELECT s.id,s.slug,s.name_ar,s.input_schema,
      s.base_price_halalas,c.name_ar AS category_name_ar
      FROM services s JOIN service_categories c ON c.id=s.category_id
      WHERE s.enabled=true AND c.enabled=true AND s.processor_type='tool'
      AND s.slug=ANY($1::text[]) AND ($2::uuid IS NULL OR s.id=$2)
      ORDER BY c.name_ar,s.name_ar,s.id LIMIT 50""", slugs, service_id)
    catalog = []
    for row in rows:
        schema = row["input_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)
        if row["slug"] != "merge-pdf" or schema != PDF_INPUT_SCHEMA:
            continue
        catalog.append(CatalogService(
            row["id"], row["slug"], row["name_ar"], row["category_name_ar"],
            row["base_price_halalas"],
        ))
    return catalog
