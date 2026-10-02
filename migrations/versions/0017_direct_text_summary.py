"""Direct text summary inputs/results; preserve all existing financial history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0017_direct_text_summary"
down_revision = "0016_telegram_stars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("star_invoices", sa.Column("input_text_digest", sa.Text()))
    op.create_table(
        "summary_inputs",
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("telegram_workflows.id"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("input_digest", sa.Text(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "telegram_message_id", name="summary_input_message_unique"),
        sa.CheckConstraint("char_length(input_text) BETWEEN 20 AND 4000", name="summary_input_length"),
    )
    op.execute("""CREATE TRIGGER summary_inputs_immutable BEFORE UPDATE ON summary_inputs
               FOR EACH ROW EXECUTE FUNCTION reject_payment_event_mutation();""")
    op.create_table(
        "summary_results",
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), primary_key=True),
        sa.Column("result_text", sa.Text(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(result_text) BETWEEN 1 AND 1800", name="summary_result_length"),
    )
    op.execute("""CREATE OR REPLACE FUNCTION protect_star_invoice_snapshot() RETURNS trigger
               LANGUAGE plpgsql AS $$
               BEGIN
                 IF ROW(NEW.user_id,NEW.workflow_id,NEW.quote_revision,NEW.service_id,
                        NEW.amount_stars,NEW.file_ids,NEW.terms_digest,NEW.terms_text,NEW.created_at,
                        NEW.input_text_digest)
                    IS DISTINCT FROM
                    ROW(OLD.user_id,OLD.workflow_id,OLD.quote_revision,OLD.service_id,
                        OLD.amount_stars,OLD.file_ids,OLD.terms_digest,OLD.terms_text,OLD.created_at,
                        OLD.input_text_digest)
                    OR (OLD.order_id IS NOT NULL AND NEW.order_id IS DISTINCT FROM OLD.order_id)
                    OR (OLD.checkout_query_id IS NOT NULL
                        AND NEW.checkout_query_id IS DISTINCT FROM OLD.checkout_query_id) THEN
                   RAISE EXCEPTION 'Stars invoice snapshot is immutable';
                 END IF;
                 RETURN NEW;
               END; $$;""")
    # Register a disabled service only. No price, customer payment or business activation.
    op.execute("""INSERT INTO service_categories (id,slug,name_ar)
               VALUES ('f4808518-8ae7-4721-90be-cb6abdb35974','text-services','خدمات نصية')
               ON CONFLICT (slug) DO NOTHING""")
    op.execute("""INSERT INTO services
               (id,category_id,slug,name_ar,description_ar,processor_type,base_price_halalas,input_schema)
               SELECT 'c09ec7bb-d1a9-4be1-97af-f0c5c0390555',id,'summarize-text','تلخيص النص',
                      'تلخيص محلي باختيار جمل من النص؛ ليس ذكاء اصطناعيًا توليديًا.',
                      'tool',0,'{"max_characters":4000}'::jsonb
               FROM service_categories WHERE slug='text-services'
               ON CONFLICT (slug) DO NOTHING""")


def downgrade() -> None:
    raise RuntimeError("Keep summary/financial history; rollback application with additive schema intact")
