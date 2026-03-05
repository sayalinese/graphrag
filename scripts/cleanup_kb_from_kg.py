"""
清理串扰数据：
1. 删除 Neo4j medical 中 doc_id 属于 kb_documents 的所有 :Chunk / :Document 节点
2. 删除 kg_pg_embedding 中对应的 169 个向量
3. 若 graphrag_collection__medical collection 为空则删除之
"""
import sys
sys.path.insert(0, r'c:/Users/16960/Desktop/项目')
from app import create_app

app = create_app()
with app.app_context():
    from app.extensions import db, get_neo4j_driver

    driver = get_neo4j_driver()

    # ────────────────────────────────────────────────
    # Step 1: 从 PostgreSQL 获取需要清理的 doc_id 列表
    # ────────────────────────────────────────────────
    overlap_rows = db.session.execute(db.text("""
        SELECT DISTINCT e.cmetadata->>'doc_id' as doc_id
        FROM kg_pg_embedding e
        JOIN kg_pg_collection c ON c.uuid = e.collection_id
        WHERE e.cmetadata->>'doc_id' IN (
            SELECT doc_id::text FROM kb_documents
        )
    """)).fetchall()

    dirty_doc_ids = [r[0] for r in overlap_rows]
    print("需要清理的 KB doc_id (%d 个):" % len(dirty_doc_ids))
    for d in dirty_doc_ids:
        print("  %s" % d)

    if not dirty_doc_ids:
        print("没有需要清理的数据，退出。")
        sys.exit(0)

    # ────────────────────────────────────────────────
    # Step 2: 删除 Neo4j medical 中的脏 :Chunk 节点
    # ────────────────────────────────────────────────
    print("\n[Step 2] 清理 Neo4j medical :Chunk 节点 ...")
    with driver.session(database='medical') as sess:
        # 先统计
        before_count = sess.run("""
            MATCH (c:Chunk) WHERE c.doc_id IN $ids RETURN COUNT(c) as cnt
        """, ids=dirty_doc_ids).single()['cnt']
        print("  待删除 Chunk 数: %d" % before_count)

        # 删除 Chunk 节点及所有关系
        result = sess.run("""
            MATCH (c:Chunk) WHERE c.doc_id IN $ids
            DETACH DELETE c
        """, ids=dirty_doc_ids)
        summary = result.consume()
        print("  已删除 Chunk 节点: %d" % summary.counters.nodes_deleted)

    # ────────────────────────────────────────────────
    # Step 3: 删除 Neo4j medical 中的脏 :Document 节点（包括 repair_* 重建的）
    # ────────────────────────────────────────────────
    print("\n[Step 3] 清理 Neo4j medical :Document 节点 ...")
    with driver.session(database='medical') as sess:
        before_doc_count = sess.run("""
            MATCH (d:Document) WHERE d.doc_id IN $ids RETURN COUNT(d) as cnt
        """, ids=dirty_doc_ids).single()['cnt']
        print("  待删除 Document 数: %d" % before_doc_count)

        result = sess.run("""
            MATCH (d:Document) WHERE d.doc_id IN $ids
            DETACH DELETE d
        """, ids=dirty_doc_ids)
        summary = result.consume()
        print("  已删除 Document 节点: %d" % summary.counters.nodes_deleted)

    # ────────────────────────────────────────────────
    # Step 4: 删除 kg_pg_embedding 中对应向量
    # ────────────────────────────────────────────────
    print("\n[Step 4] 清理 kg_pg_embedding 向量 ...")
    # 构造 SQL IN 列表
    placeholders = ','.join(["'%s'" % d for d in dirty_doc_ids])
    before_vec = db.session.execute(db.text("""
        SELECT COUNT(*) FROM kg_pg_embedding
        WHERE cmetadata->>'doc_id' IN (%s)
    """ % placeholders)).scalar()
    print("  待删除向量数: %d" % before_vec)

    db.session.execute(db.text("""
        DELETE FROM kg_pg_embedding
        WHERE cmetadata->>'doc_id' IN (%s)
    """ % placeholders))
    db.session.commit()
    print("  向量已删除")

    # ────────────────────────────────────────────────
    # Step 5: 检查 graphrag_collection__medical 是否为空，若空则删除 collection 记录
    # ────────────────────────────────────────────────
    print("\n[Step 5] 检查 collection 状态 ...")
    col_stats = db.session.execute(db.text("""
        SELECT c.name, COUNT(e.uuid) as vec_count
        FROM kg_pg_collection c
        LEFT JOIN kg_pg_embedding e ON e.collection_id = c.uuid
        GROUP BY c.uuid, c.name
        ORDER BY c.name
    """)).fetchall()

    print("  当前各 collection 向量数:")
    for row in col_stats:
        print("    %s: %d" % (row[0], row[1]))

    # 删除空的 graphrag_collection__medical collection 记录（可选，PGVector 会自动重建）
    # 保留空 collection 记录不影响功能

    # ────────────────────────────────────────────────
    # Step 6: 验证 Neo4j medical 剩余的合法节点
    # ────────────────────────────────────────────────
    print("\n[Step 6] 验证 Neo4j medical 剩余节点 ...")
    with driver.session(database='medical') as sess:
        remaining = sess.run("""
            MATCH (n)
            WHERE NOT n:Chunk AND NOT n:Document
            RETURN labels(n) as labels, COUNT(n) as cnt
            ORDER BY cnt DESC
            LIMIT 10
        """).data()
        print("  剩余非Chunk/Document节点:")
        for r in remaining:
            print("    %s: %d" % (r['labels'], r['cnt']))

        chunk_remaining = sess.run("MATCH (c:Chunk) RETURN COUNT(c) as cnt").single()['cnt']
        doc_remaining = sess.run("MATCH (d:Document) RETURN COUNT(d) as cnt").single()['cnt']
        print("  剩余 :Chunk 节点: %d" % chunk_remaining)
        print("  剩余 :Document 节点: %d" % doc_remaining)

    print("\n====== 清理完成 ======")
    print("  kg_pg_embedding 中 KB 串扰向量已全部删除")
    print("  Neo4j medical 中 KB 来源节点已全部删除")
    print("  可以重新导入真正的 medical GraphRAG 数据了")
