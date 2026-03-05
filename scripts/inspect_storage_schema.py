#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.insert(0, 'c:/Users/16960/Desktop/项目')

from app import create_app
from app.extensions import db
from sqlalchemy import text


def print_rows(title, sql, params=None):
    print(f"\n=== {title} ===")
    rows = db.session.execute(text(sql), params or {}).fetchall()
    for row in rows:
        print(" | ".join(str(x) for x in row))


def main():
    app = create_app()
    with app.app_context():
        print_rows(
            "constraints: kb_document_chunks",
            """
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'kb_document_chunks'
            ORDER BY conname
            """,
        )
        print_rows(
            "indexes: kb_document_chunks",
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'kb_document_chunks'
            ORDER BY indexname
            """,
        )
        print_rows(
            "constraints: kg_pg_embedding",
            """
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'kg_pg_embedding'
            ORDER BY conname
            """,
        )
        print_rows(
            "indexes: kg_pg_embedding",
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'kg_pg_embedding'
            ORDER BY indexname
            """,
        )


if __name__ == '__main__':
    main()
