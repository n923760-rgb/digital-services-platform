"""Read services supported by a running processor; no channel owns registry state."""

import json
from dataclasses import dataclass
from uuid import UUID

import asyncpg

from platform_core.processors import PROCESSORS
from platform_core.service_registry import PDF_INPUT_SCHEMA
from platform_core.text_summary import SLUG, TEXT_INPUT_SCHEMA


@dataclass(frozen=True)
class CatalogService:
    id: UUID
    slug: str
    name_ar: str
    category_name_ar: str
    price_halalas: int
    price_stars: int | None = None
    description_ar: str = ""


async def available_services(
    connection: asyncpg.Connection, *, service_id: UUID | None = None, currency: str = "SAR",
) -> list[CatalogService]:
    """Only expose enabled services with a registered, schema-compatible processor."""
    if currency not in {"SAR", "XTR"}:
        raise ValueError("unsupported catalog currency")
    slugs = list(PROCESSORS)
    if not slugs:
        return []
    rows = await connection.fetch("""SELECT s.id,s.slug,s.name_ar,s.input_schema,
      s.base_price_halalas,s.base_price_stars,c.name_ar AS category_name_ar
      FROM services s JOIN service_categories c ON c.id=s.category_id
      WHERE s.enabled=true AND c.enabled=true AND s.processor_type='tool'
      AND s.slug=ANY($1::text[]) AND ($2::uuid IS NULL OR s.id=$2)
      ORDER BY c.name_ar,s.name_ar,s.id LIMIT 50""", slugs, service_id)
    catalog = []
    for row in rows:
        schema = row["input_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)
        if (row["slug"] != "merge-pdf" or schema != PDF_INPUT_SCHEMA
                or (currency == "XTR" and row["base_price_stars"] is None)):
            continue
        catalog.append(CatalogService(
            row["id"], row["slug"], row["name_ar"], row["category_name_ar"],
            row["base_price_halalas"], row["base_price_stars"],
        ))
    return catalog


async def available_summary_products(connection, *, service_id=None) -> list[CatalogService]:
    """Read current prices/availability for the direct bot; never advertise unfinished executors."""
    rows = await connection.fetch(
        """SELECT s.id,s.slug,s.name_ar,s.description_ar,s.base_price_halalas,
                  s.base_price_stars,s.input_schema,c.name_ar AS category_name_ar
           FROM services s JOIN service_categories c ON c.id=s.category_id
           WHERE s.enabled AND c.enabled AND s.processor_type='tool'
             AND s.processor_key=$1 AND s.base_price_stars BETWEEN 1 AND 100000
             AND ($2::uuid IS NULL OR s.id=$2)
           ORDER BY c.name_ar,s.name_ar,s.id LIMIT 50""", SLUG, service_id,
    )
    products = []
    for row in rows:
        schema = row["input_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)
        if schema == TEXT_INPUT_SCHEMA:
            products.append(CatalogService(
                row["id"], row["slug"], row["name_ar"], row["category_name_ar"],
                row["base_price_halalas"], row["base_price_stars"], row["description_ar"],
            ))
    return products
