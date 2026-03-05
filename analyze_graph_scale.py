#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析Neo4j图数据库的规模和分布"""

import sys
sys.path.insert(0, 'c:\\Users\\16960\\Desktop\\项目')

from app import create_app

def analyze_graph():
    """详细分析图数据库规模"""
    app = create_app()
    with app.app_context():
        from app.extensions import get_neo4j_driver
        
        driver = get_neo4j_driver()
        with driver.session(database='medical') as session:
            
            # 1. 总体统计
            print("=" * 60)
            print("图数据库整体统计（medical 数据库）")
            print("=" * 60)
            
            # 节点总数
            result = session.run("MATCH (n) RETURN count(n) as total")
            total_nodes = result.single()['total']
            print(f"节点总数: {total_nodes:,}")
            
            # 边总数
            result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
            total_edges = result.single()['total']
            print(f"边总数: {total_edges:,}")
            
            # 2. 节点类型分布
            print("\n" + "=" * 60)
            print("节点类型分布")
            print("=" * 60)
            result = session.run("""
                MATCH (n) 
                RETURN labels(n)[0] as type, count(n) as count
                ORDER BY count DESC
            """)
            for record in result:
                label = record['type'] or 'untyped'
                count = record['count']
                print(f"{label:20} {count:10,}")
            
            # 3. 关系类型分布
            print("\n" + "=" * 60)
            print("关系类型分布")
            print("=" * 60)
            result = session.run("""
                MATCH ()-[r]->() 
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """)
            for record in result:
                rel_type = record['rel_type']
                count = record['count']
                print(f"{rel_type:20} {count:10,}")
            
            # 4. Document 统计
            print("\n" + "=" * 60)
            print("Document 节点详情")
            print("=" * 60)
            result = session.run("""
                MATCH (d:Document)
                RETURN count(d) as doc_count,
                       count(DISTINCT d.doc_id) as unique_docs
            """)
            record = result.single()
            print(f"Document 节点数: {record['doc_count']:,}")
            print(f"唯一 doc_id: {record['unique_docs']:,}")
            
            # 5. Entity 统计
            print("\n" + "=" * 60)
            print("Entity 节点详情")
            print("=" * 60)
            result = session.run("""
                MATCH (e:Entity)
                RETURN count(e) as entity_count,
                       count(DISTINCT e.eid) as unique_eids
            """)
            record = result.single()
            print(f"Entity 节点数: {record['entity_count']:,}")
            print(f"唯一 eid: {record['unique_eids']:,}")
            
            # 6. Chunk 统计
            print("\n" + "=" * 60)
            print("Chunk 节点详情")
            print("=" * 60)
            result = session.run("""
                MATCH (c:Chunk)
                RETURN count(c) as chunk_count,
                       count(DISTINCT c.doc_id) as unique_docs
            """)
            record = result.single()
            print(f"Chunk 节点数: {record['chunk_count']:,}")
            print(f"Chunk 关联的唯一文档: {record['unique_docs']:,}")
            
            # 7. 连接情况统计
            print("\n" + "=" * 60)
            print("节点连接情况")
            print("=" * 60)
            
            # Document-CONTAINS-Chunk
            result = session.run("""
                MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"Document-[:CONTAINS]->Chunk: {count:,}")
            
            # Entity-IN-Chunk
            result = session.run("""
                MATCH (e:Entity)-[:IN]->(c:Chunk)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"Entity-[:IN]->Chunk: {count:,}")
            
            # Entity-RELATED_TO-Entity
            result = session.run("""
                MATCH (e1:Entity)-[:RELATED_TO]->(e2:Entity)
                RETURN count(*) as count
            """)
            count = result.single()['count']
            print(f"Entity-[:RELATED_TO]->Entity: {count:,}")
            
            # 8. 孤立节点检查
            print("\n" + "=" * 60)
            print("孤立节点检查")
            print("=" * 60)
            
            # 没有任何关系的节点
            result = session.run("""
                MATCH (n)
                WHERE NOT (n)--()
                RETURN labels(n)[0] as type, count(n) as count
                ORDER BY count DESC
            """)
            records = list(result)
            if records:
                total_isolated = sum(r['count'] for r in records)
                print(f"完全孤立节点总数: {total_isolated:,}")
                for record in records:
                    print(f"  {record['type']:20} {record['count']:10,}")
            else:
                print("没有完全孤立的节点")
            
            # 9. 数据分布汇总
            print("\n" + "=" * 60)
            print("数据规模汇总")
            print("=" * 60)
            print(f"总节点数:      {total_nodes:10,}")
            print(f"总边数:        {total_edges:10,}")
            print(f"平均度数:      {total_edges/max(total_nodes,1):10.2f}")
            
            session.close()

if __name__ == '__main__':
    analyze_graph()
