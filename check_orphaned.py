from sqlalchemy import text
import os
import re

from app import create_app
from app.extensions import db


TARGET_DB = "medical"


def vector_collection_for_db(db_name: str) -> str:
    base = os.getenv("PGVECTOR_COLLECTION", "graphrag_collection")
    safe = re.sub(r"[^0-9a-zA-Z_]+", "_", (db_name or "").strip().lower()).strip("_") or "default"
    return f"{base}__{safe}"


def main():
    app = create_app()

    with app.app_context():
        rag = getattr(app, "graphrag_service", None)
        if not rag:
            print("[ERROR] app.graphrag_service 未初始化")
            return

        print(f"=== Neo4j 数据库: {TARGET_DB} ===")
        with rag._use_database(TARGET_DB):
            with rag._session() as sess:
                total_chunks = dict(sess.run("MATCH (c:Chunk) RETURN count(c) AS c").single() or {})
                graph_chunks = dict(sess.run("MATCH (d:Document)-[:CONTAINS]->(c:Chunk) RETURN count(DISTINCT c) AS c").single() or {})
                no_vec = dict(sess.run("MATCH (c:Chunk) WHERE c.vec_id IS NULL OR c.vec_id = '' RETURN count(c) AS c").single() or {})
                no_doc_rel = dict(sess.run("MATCH (c:Chunk) WHERE NOT EXISTS { MATCH (d:Document)-[:CONTAINS]->(c) } RETURN count(c) AS c").single() or {})
                orphaned_union = dict(
                    sess.run(
                        """
                        MATCH (c:Chunk)
                        WHERE (c.vec_id IS NULL OR c.vec_id = '')
                           OR NOT EXISTS { MATCH (d:Document)-[:CONTAINS]->(c) }
                        RETURN count(c) AS c
                        """
                    ).single()
                    or {}
                )

        print(f"Chunk总数: {(total_chunks or {}).get('c', 0)}")
        print(f"GraphChunk(有CONTAINS): {(graph_chunks or {}).get('c', 0)}")
        print(f"无vec_id: {(no_vec or {}).get('c', 0)}")
        print(f"无Document关系: {(no_doc_rel or {}).get('c', 0)}")
        print(f"孤立并集: {(orphaned_union or {}).get('c', 0)}")

        with rag._use_database(TARGET_DB):
            with rag._session() as sess:
                sample = [
                    dict(r)
                    for r in sess.run(
                        """
                        MATCH (c:Chunk)
                        RETURN elementId(c) AS eid,
                               c.doc_id AS doc_id,
                               c.idx AS idx,
                               c.vec_id AS vec_id,
                               EXISTS { MATCH (d:Document)-[:CONTAINS]->(c) } AS has_doc_rel
                        ORDER BY c.doc_id, c.idx
                        LIMIT 20
                        """
                    )
                ]
        print("\n--- Chunk样本(前20) ---")
        for row in sample:
            print(
                f"eid={row.get('eid')} doc_id={row.get('doc_id')} idx={row.get('idx')} "
                f"vec_id={row.get('vec_id')} has_doc_rel={row.get('has_doc_rel')}"
            )

        with rag._use_database(TARGET_DB):
            with rag._session() as sess:
                doc_id_rows = [
                    dict(r)
                    for r in sess.run(
                        """
                        MATCH (c:Chunk)
                        WHERE c.doc_id IS NOT NULL
                        RETURN c.doc_id AS doc_id, count(*) AS cnt
                        ORDER BY cnt DESC
                        LIMIT 20
                        """
                    )
                ]

        neo_doc_ids = [str(r.get("doc_id")) for r in doc_id_rows if r.get("doc_id") is not None]
        print("\n--- Neo4j Chunk doc_id Top20 ---")
        for row in doc_id_rows:
            print(f"doc_id={row.get('doc_id')} cnt={row.get('cnt')}")

        print("\n=== PostgreSQL 表检查 ===")
        total_doc_chunks = db.session.execute(text("SELECT COUNT(*) FROM kb_document_chunks")).scalar() or 0
        total_docs = db.session.execute(text("SELECT COUNT(*) FROM kb_documents")).scalar() or 0
        print(f"kb_document_chunks 总行数: {total_doc_chunks}")
        print(f"kb_documents 总行数: {total_docs}")

        if neo_doc_ids:
            matched_chunk_rows = db.session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM kb_document_chunks
                    WHERE doc_id::text = ANY(:doc_ids)
                    """
                ),
                {"doc_ids": neo_doc_ids},
            ).scalar() or 0
            matched_doc_rows = db.session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM kb_documents
                    WHERE doc_id::text = ANY(:doc_ids)
                    """
                ),
                {"doc_ids": neo_doc_ids},
            ).scalar() or 0
            print(f"与Neo4j Chunk doc_id匹配的 kb_document_chunks 行数: {matched_chunk_rows}")
            print(f"与Neo4j Chunk doc_id匹配的 kb_documents 行数: {matched_doc_rows}")

        vector_table = app.config.get("PG_VECTOR_TABLE") or "kg_pg_embedding"
        try:
            vec_count = db.session.execute(text(f"SELECT COUNT(*) FROM {vector_table}")).scalar() or 0
        except Exception:
            vec_count = 0
        print(f"{vector_table} 总行数: {vec_count}")

        scoped_collection = vector_collection_for_db(TARGET_DB)
        try:
            scoped_vec_count = db.session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM kg_pg_embedding e
                    JOIN kg_pg_collection c ON e.collection_id = c.uuid
                    WHERE c.name = :name
                    """
                ),
                {"name": scoped_collection},
            ).scalar() or 0
        except Exception:
            scoped_vec_count = 0
        print(f"{scoped_collection} 向量行数: {scoped_vec_count}")


if __name__ == "__main__":
    main()
