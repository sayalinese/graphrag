#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.insert(0, 'c:/Users/16960/Desktop/项目')

from sqlalchemy import text
from app import create_app
from app.extensions import db


def main():
    app = create_app()
    with app.app_context():
        statements = [
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
            """,
            "DROP VIEW IF EXISTS knowledge_bases",
            "DROP VIEW IF EXISTS documents",
            "DROP VIEW IF EXISTS document_chunks",
            "DROP VIEW IF EXISTS langchain_pg_collection",
            "DROP VIEW IF EXISTS langchain_pg_embedding",
            "CREATE OR REPLACE VIEW knowledge_bases AS SELECT * FROM kb_knowledge_bases",
            "CREATE OR REPLACE VIEW documents AS SELECT * FROM kb_documents",
            "CREATE OR REPLACE VIEW document_chunks AS SELECT * FROM kb_document_chunks",
            "CREATE OR REPLACE VIEW langchain_pg_collection AS SELECT * FROM kg_pg_collection",
            "CREATE OR REPLACE VIEW langchain_pg_embedding AS SELECT * FROM kg_pg_embedding",
        ]

        for sql in statements:
            db.session.execute(text(sql))
        db.session.commit()

        print('namespace migration applied')


if __name__ == '__main__':
    main()
