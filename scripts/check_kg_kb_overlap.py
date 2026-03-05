"""
检查 kg_pg_embedding 与 kb_documents 之间的 doc_id 串扰情况
以及 Neo4j medical 数据库中 Document 节点的真实来源
"""
import sys
sys.path.insert(0, r'c:/Users/16960/Desktop/项目')
from app import create_app

app = create_app()
with app.app_context():
    from app.extensions import db, get_neo4j_driver

    driver = get_neo4j_driver()

    # 1. 找出 kg_pg_embedding 里与 kb_documents 重叠的 doc_id
    overlap_rows = db.session.execute(db.text("""
        SELECT
            e.cmetadata->>'doc_id' as doc_id,
            c.name as collection,
            COUNT(e.uuid) as vec_cnt
        FROM kg_pg_embedding e
        JOIN kg_pg_collection c ON c.uuid = e.collection_id
        WHERE e.cmetadata->>'doc_id' IN (
            SELECT doc_id::text FROM kb_documents
        )
        GROUP BY e.cmetadata->>'doc_id', c.name
        ORDER BY c.name, doc_id
    """)).fetchall()

    print("=== kg_pg_embedding 中 doc_id 与 kb_documents 重叠 (共 %d 个 doc_id) ===" % len(overlap_rows))
    overlap_ids = set()
    for row in overlap_rows:
        overlap_ids.add(row[0])
        print("  doc_id=%s  collection=%s  vec_count=%d" % (row[0], row[1], row[2]))

    # 2. kb_documents 列表
    kb_rows = db.session.execute(db.text("""
        SELECT d.doc_id::text, d.filename, kb.name as kb_name
        FROM kb_documents d
        JOIN kb_knowledge_bases kb ON kb.kb_id = d.kb_id
        ORDER BY kb.name, d.filename
    """)).fetchall()

    print("\n=== kb_documents 完整列表 (%d 条) ===" % len(kb_rows))
    for row in kb_rows:
        flag = " *** 已串入KG ***" if row[0] in overlap_ids else ""
        print("  doc_id=%s  kb=%s  file=%s%s" % (row[0], row[2], row[1], flag))

    # 3. Neo4j medical 里的 Document 节点
    print("\n=== Neo4j medical :Document 节点 ===")
    kb_doc_ids_in_neo = []
    with driver.session(database='medical') as sess:
        docs = sess.run("""
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            WITH d, COUNT(c) as chunk_count
            RETURN d.doc_id as doc_id, d.filename as filename,
                   d.source as source, chunk_count
            ORDER BY d.filename
        """).data()

        for d in docs:
            doc_id_str = str(d.get('doc_id', 'N/A'))
            flag = " *** 与KB重叠 ***" if doc_id_str in overlap_ids else ""
            if doc_id_str in overlap_ids:
                kb_doc_ids_in_neo.append(d)
            print("  doc_id=%s  filename=%s  chunks=%d%s" % (
                doc_id_str, d.get('filename', 'N/A'), d.get('chunk_count', 0), flag))

    # 3b. Neo4j medical Chunk 节点里有没有重叠的 doc_id
    print("\n=== Neo4j medical :Chunk - doc_id 与 kb 重叠统计 ===")
    with driver.session(database='medical') as sess:
        chunk_overlap = sess.run("""
            MATCH (c:Chunk)
            WHERE c.doc_id IN $ids
            RETURN c.doc_id as doc_id, COUNT(c) as cnt
        """, ids=list(overlap_ids)).data()
        if chunk_overlap:
            for row in chunk_overlap:
                print("  doc_id=%s  chunk_count=%d" % (row['doc_id'], row['cnt']))
        else:
            print("  (无重叠的 Chunk 节点)")

    # 4. 汇总问题
    print("\n=== 问题汇总 ===")
    total_bad_vecs = sum(r[2] for r in overlap_rows)
    print("  kg_pg_embedding 中混入 KB 数据的向量数: %d" % total_bad_vecs)
    print("  涉及 doc_id 数量: %d" % len(overlap_ids))
    print("  Neo4j medical 中与 kb_documents 重叠的 Document 节点数: %d" % len(kb_doc_ids_in_neo))
    print()
    if kb_doc_ids_in_neo:
        print("原因: 这些文档被同时上传到 KB(传统RAG) 和 Neo4j GraphRAG，导致相同 doc_id 出现在两套存储里")
        print()
        print("处理方案:")
        print("  A) 若 Neo4j medical 里这些文档有效   -> 向量数据正确，无需处理")
        print("  B) 若 Neo4j medical 里这些文档是误录 -> 需从 Neo4j 删除节点，再清理 kg_pg_embedding")
    else:
        print("Neo4j medical 中不存在对应 Document 节点！")
        print("这意味着这些向量的 doc_id 可能是 Chunk 节点属性直接带来的，需确认 Chunk 来源")
