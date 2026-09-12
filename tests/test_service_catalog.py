"""Only registry-enabled, processor-supported services reach Telegram's catalog."""

import os
from uuid import uuid4

import asyncpg
import pytest
from platform_core.service_catalog import available_services


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    transaction = connection.transaction()
    await transaction.start()
    try:
        yield connection
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_catalog_filters_unsupported_services_and_rechecks_availability(db):
    category_id, proposed_id, unknown_id = uuid4(), uuid4(), uuid4()
    await db.execute("INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'أدوات')",
                     category_id, str(category_id))
    await db.execute("""INSERT INTO services
      (id,category_id,slug,name_ar,processor_type,base_price_halalas,input_schema,enabled)
      VALUES ($1,$2,'merge-pdf','دمج PDF','tool',700,$3::jsonb,true)
      ON CONFLICT (slug) DO NOTHING""",
      proposed_id, category_id, '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}')
    merge_id = await db.fetchval("SELECT id FROM services WHERE slug='merge-pdf'")
    await db.execute("""UPDATE service_categories SET enabled=true
      WHERE id=(SELECT category_id FROM services WHERE id=$1)""", merge_id)
    await db.execute("""INSERT INTO services
      (id,category_id,slug,name_ar,processor_type,base_price_halalas,enabled)
      VALUES ($1,$2,$3,'غير مدعومة','tool',250,true)""", unknown_id, category_id, str(unknown_id))
    await db.execute("""UPDATE services SET enabled=true,base_price_halalas=1350,
      input_schema=$2::jsonb WHERE id=$1""", merge_id,
      '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}')
    listed = await available_services(db)
    assert any(item.id == merge_id and item.price_halalas == 1350 for item in listed)
    assert all(item.id != unknown_id for item in listed)
    assert [item.id for item in await available_services(db, service_id=merge_id)] == [merge_id]
    await db.execute("UPDATE services SET input_schema='{}'::jsonb WHERE id=$1", merge_id)
    assert await available_services(db, service_id=merge_id) == []
    await db.execute("""UPDATE services SET enabled=false,
      input_schema=$2::jsonb WHERE id=$1""", merge_id,
      '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}')
    assert await available_services(db, service_id=merge_id) == []
