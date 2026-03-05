"""namespace kb/kg tables

Revision ID: 9f1c2b7e4a10
Revises: 80a1139a5e60
Create Date: 2026-03-04 18:02:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9f1c2b7e4a10'
down_revision = '80a1139a5e60'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.kb_knowledge_bases') IS NULL
               AND to_regclass('public.knowledge_bases') IS NOT NULL THEN
                ALTER TABLE knowledge_bases RENAME TO kb_knowledge_bases;
            END IF;

            IF to_regclass('public.kb_documents') IS NULL
               AND to_regclass('public.documents') IS NOT NULL THEN
                ALTER TABLE documents RENAME TO kb_documents;
            END IF;

            IF to_regclass('public.kb_document_chunks') IS NULL
               AND to_regclass('public.document_chunks') IS NOT NULL THEN
                ALTER TABLE document_chunks RENAME TO kb_document_chunks;
            END IF;

            IF to_regclass('public.kg_pg_collection') IS NULL
               AND to_regclass('public.langchain_pg_collection') IS NOT NULL THEN
                ALTER TABLE langchain_pg_collection RENAME TO kg_pg_collection;
            END IF;

            IF to_regclass('public.kg_pg_embedding') IS NULL
               AND to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
                ALTER TABLE langchain_pg_embedding RENAME TO kg_pg_embedding;
            END IF;
        END
        $$;
        """
    )

    op.execute("DROP VIEW IF EXISTS knowledge_bases")
    op.execute("DROP VIEW IF EXISTS documents")
    op.execute("DROP VIEW IF EXISTS document_chunks")
    op.execute("DROP VIEW IF EXISTS langchain_pg_collection")
    op.execute("DROP VIEW IF EXISTS langchain_pg_embedding")

    op.execute("CREATE OR REPLACE VIEW knowledge_bases AS SELECT * FROM kb_knowledge_bases")
    op.execute("CREATE OR REPLACE VIEW documents AS SELECT * FROM kb_documents")
    op.execute("CREATE OR REPLACE VIEW document_chunks AS SELECT * FROM kb_document_chunks")
    op.execute("CREATE OR REPLACE VIEW langchain_pg_collection AS SELECT * FROM kg_pg_collection")
    op.execute("CREATE OR REPLACE VIEW langchain_pg_embedding AS SELECT * FROM kg_pg_embedding")


def downgrade():
    op.execute("DROP VIEW IF EXISTS langchain_pg_embedding")
    op.execute("DROP VIEW IF EXISTS langchain_pg_collection")
    op.execute("DROP VIEW IF EXISTS document_chunks")
    op.execute("DROP VIEW IF EXISTS documents")
    op.execute("DROP VIEW IF EXISTS knowledge_bases")

    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.langchain_pg_embedding') IS NULL
               AND to_regclass('public.kg_pg_embedding') IS NOT NULL THEN
                ALTER TABLE kg_pg_embedding RENAME TO langchain_pg_embedding;
            END IF;

            IF to_regclass('public.langchain_pg_collection') IS NULL
               AND to_regclass('public.kg_pg_collection') IS NOT NULL THEN
                ALTER TABLE kg_pg_collection RENAME TO langchain_pg_collection;
            END IF;

            IF to_regclass('public.document_chunks') IS NULL
               AND to_regclass('public.kb_document_chunks') IS NOT NULL THEN
                ALTER TABLE kb_document_chunks RENAME TO document_chunks;
            END IF;

            IF to_regclass('public.documents') IS NULL
               AND to_regclass('public.kb_documents') IS NOT NULL THEN
                ALTER TABLE kb_documents RENAME TO documents;
            END IF;

            IF to_regclass('public.knowledge_bases') IS NULL
               AND to_regclass('public.kb_knowledge_bases') IS NOT NULL THEN
                ALTER TABLE kb_knowledge_bases RENAME TO knowledge_bases;
            END IF;
        END
        $$;
        """
    )
