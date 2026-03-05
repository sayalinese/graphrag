#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 Neo4j 数据库归属收口历史全局向量（graphrag_collection）。

流程：
1) 扫描所有在线 Neo4j 数据库（排除 system）
2) 对每个数据库执行 migrate（把可确认归属的向量迁到分库 collection）
3) 删除历史全局 collection 剩余向量，实现彻底清空
"""

import sys
sys.path.insert(0, 'c:/Users/16960/Desktop/项目')

from sqlalchemy import text

from app import create_app
from app.extensions import db, get_neo4j_driver

SOURCE_COLLECTION = 'graphrag_collection'


def _list_online_databases():
    driver = get_neo4j_driver()
    names = []
    with driver.session(database='system') as sess:
        rows = sess.run("SHOW DATABASES YIELD name, currentStatus RETURN name, currentStatus")
        for r in rows:
            name = str(r.get('name') or '').strip()
            status = str(r.get('currentStatus') or '').strip().lower()
            if not name or name.lower() == 'system':
                continue
            if status and status not in ('online', 'started'):
                continue
            names.append(name)
    names = sorted(set(names))
    return names


def _get_collection_uuid(name: str):
    row = db.session.execute(
        text("SELECT uuid FROM kg_pg_collection WHERE name = :name"),
        {'name': name},
    ).fetchone()
    return row[0] if row else None


def _count_collection(name: str) -> int:
    row = db.session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM kg_pg_embedding e
            JOIN kg_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :name
            """
        ),
        {'name': name},
    ).fetchone()
    return int(row[0]) if row else 0


def _delete_all_from_collection(name: str) -> int:
    collection_uuid = _get_collection_uuid(name)
    if not collection_uuid:
        return 0
    result = db.session.execute(
        text("DELETE FROM kg_pg_embedding WHERE collection_id = :cid"),
        {'cid': collection_uuid},
    )
    db.session.commit()
    return int(getattr(result, 'rowcount', 0) or 0)


def main():
    app = create_app()
    with app.app_context():
        svc = getattr(app, 'graphrag_service', None)
        if not svc:
            raise RuntimeError('app.graphrag_service 未初始化')

        db_names = _list_online_databases()
        print(f"扫描到数据库: {db_names}")

        before_global = _count_collection(SOURCE_COLLECTION)
        print(f"全局集合 {SOURCE_COLLECTION} 初始向量数: {before_global}")

        details = []
        for name in db_names:
            res = svc.reconcile_legacy_vectors(
                database=name,
                strategy='migrate',
                source_collection=SOURCE_COLLECTION,
            )
            details.append((name, res))
            moved = res.get('moved', 0) if isinstance(res, dict) else 0
            matched = res.get('matched_with_database', 0) if isinstance(res, dict) else 0
            source_after = res.get('source_total_after') if isinstance(res, dict) else None
            print(f"[{name}] matched={matched}, moved={moved}, source_after={source_after}")

        after_migrate_global = _count_collection(SOURCE_COLLECTION)
        print(f"迁移后全局集合剩余: {after_migrate_global}")

        deleted_remaining = _delete_all_from_collection(SOURCE_COLLECTION)
        final_global = _count_collection(SOURCE_COLLECTION)

        print("\n=== 收口总结 ===")
        print(f"初始全局向量: {before_global}")
        print(f"迁移后剩余: {after_migrate_global}")
        print(f"批量删除剩余: {deleted_remaining}")
        print(f"最终全局剩余: {final_global}")

        print("\n=== 分库迁移详情 ===")
        for name, res in details:
            if not isinstance(res, dict):
                print(f"{name}: 非法响应 -> {res}")
                continue
            print(
                f"{name}: success={res.get('success')} matched={res.get('matched_with_database', 0)} "
                f"moved={res.get('moved', 0)} target_after={res.get('target_total_after', '-') }"
            )


if __name__ == '__main__':
    main()
