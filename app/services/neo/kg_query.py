"""
知识图谱查询服务
负责图谱的各种查询和检索操作
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from app.services.neo.graph_service import GraphService

logger = logging.getLogger(__name__)


class KGQuery:
    """知识图谱查询服务"""
    
    def __init__(self, graph_service: GraphService):
        """
        初始化知识图谱查询服务
        
        Args:
            graph_service: Neo4j 图服务
        """
        self.graph_service = graph_service
    
    def search_nodes(self, query: str, node_type: Optional[str] = None, 
                    limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索节点
        
        Args:
            query: 搜索文本
            node_type: 节点类型过滤（可选）
            limit: 返回数量限制
        
        Returns:
            节点列表
        """
        try:
            if node_type:
                cypher = f"""
                MATCH (n:{node_type})
                WHERE toLower(n.name) CONTAINS toLower($query)
                RETURN n
                LIMIT $limit
                """
            else:
                cypher = """
                MATCH (n)
                WHERE toLower(n.name) CONTAINS toLower($query)
                RETURN n
                LIMIT $limit
                """
            
            results = self.graph_service.execute_query(
                cypher,
                {"query": query, "limit": limit}
            )
            return results
        except Exception as e:
            logger.error(f"搜索节点失败: {e}")
            return []
    
    def get_node_context(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """
        获取节点的上下文信息（包括相关节点和关系）
        
        Args:
            node_id: 节点 ID
            depth: 关系深度
        
        Returns:
            包含中心节点、相关节点和关系的字典
        """
        try:
            # 获取中心节点
            cypher_center = "MATCH (n {id: $id}) RETURN n"
            center_nodes = self.graph_service.execute_query(cypher_center, {"id": node_id})
            
            if not center_nodes:
                logger.warning(f"节点不存在: {node_id}")
                return {"center": None, "related_nodes": [], "relations": []}
            
            center = center_nodes[0]
            
            # 获取相关节点和关系
            cypher_related = f"""
            MATCH (center {{id: $id}})-[r*1..{depth}]-(related)
            RETURN center, r, related
            LIMIT 100
            """
            related_results = self.graph_service.execute_query(
                cypher_related,
                {"id": node_id}
            )
            
            return {
                "center": center,
                "related": related_results,
                "depth": depth
            }
        except Exception as e:
            logger.error(f"获取节点上下文失败: {e}")
            return {"center": None, "related": [], "depth": 0}
    
    def find_paths(self, start_id: str, end_id: str, 
                  max_length: int = 5) -> List[List[Dict]]:
        """
        查找两个节点之间的所有路径
        
        Args:
            start_id: 起始节点 ID
            end_id: 结束节点 ID
            max_length: 最大路径长度
        
        Returns:
            路径列表
        """
        try:
            cypher = f"""
            MATCH path = allShortestPaths((a {{id: $start}})-[*1..{max_length}]-(b {{id: $end}}))
            RETURN path
            LIMIT 10
            """
            
            results = self.graph_service.execute_query(
                cypher,
                {"start": start_id, "end": end_id}
            )
            return results
        except Exception as e:
            logger.error(f"路径查询失败: {e}")
            return []
    
    def find_shortest_path(self, start_id: str, end_id: str) -> Optional[Dict]:
        """
        查找两个节点之间的最短路径
        
        Args:
            start_id: 起始节点 ID
            end_id: 结束节点 ID
        
        Returns:
            路径信息
        """
        try:
            cypher = """
            MATCH path = shortestPath((a {id: $start})-[*]-(b {id: $end}))
            RETURN path, length(path) as path_length
            """
            
            result = self.graph_service.execute_query_single(
                cypher,
                {"start": start_id, "end": end_id}
            )
            return result
        except Exception as e:
            logger.error(f"最短路径查询失败: {e}")
            return None
    
    def get_related_nodes(self, node_id: str, relation_type: Optional[str] = None,
                         direction: str = "all") -> List[Dict]:
        """
        获取与某个节点相关的节点
        
        Args:
            node_id: 节点 ID
            relation_type: 关系类型过滤（可选）
            direction: 关系方向 ('in', 'out', 'all')
        
        Returns:
            相关节点列表
        """
        try:
            if direction == "in":
                arrow = "<-"
            elif direction == "out":
                arrow = "->"
            else:
                arrow = "-"
            
            if relation_type:
                cypher = f"""
                MATCH (n {{id: $id}}){arrow}[r:{relation_type}]{arrow}(m)
                RETURN m, r
                """
            else:
                cypher = f"""
                MATCH (n {{id: $id}}){arrow}[r]{arrow}(m)
                RETURN m, r
                """
            
            results = self.graph_service.execute_query(cypher, {"id": node_id})
            return results
        except Exception as e:
            logger.error(f"获取相关节点失败: {e}")
            return []
    
    def get_relations_by_type(self, relation_type: str, limit: int = 50) -> List[Dict]:
        """
        获取特定类型的所有关系
        
        Args:
            relation_type: 关系类型
            limit: 返回数量限制
        
        Returns:
            关系列表
        """
        try:
            cypher = f"""
            MATCH (a)-[r:{relation_type}]->(b)
            RETURN a, r, b
            LIMIT $limit
            """
            
            results = self.graph_service.execute_query(cypher, {"limit": limit})
            return results
        except Exception as e:
            logger.error(f"获取关系列表失败: {e}")
            return []
    
    def get_node_degrees(self, node_id: str) -> Dict[str, int]:
        """
        获取节点的度数（入度、出度、总度数）
        
        Args:
            node_id: 节点 ID
        
        Returns:
            度数信息
        """
        try:
            cypher_in = "MATCH (n {id: $id})<-[r]-() RETURN count(r) as in_degree"
            cypher_out = "MATCH (n {id: $id})-[r]->() RETURN count(r) as out_degree"
            cypher_all = "MATCH (n {id: $id})-[r]-() RETURN count(r) as total_degree"
            
            in_result = self.graph_service.execute_query_single(cypher_in, {"id": node_id})
            out_result = self.graph_service.execute_query_single(cypher_out, {"id": node_id})
            all_result = self.graph_service.execute_query_single(cypher_all, {"id": node_id})
            
            return {
                "in_degree": in_result["in_degree"] if in_result else 0,
                "out_degree": out_result["out_degree"] if out_result else 0,
                "total_degree": all_result["total_degree"] if all_result else 0
            }
        except Exception as e:
            logger.error(f"获取节点度数失败: {e}")
            return {"in_degree": 0, "out_degree": 0, "total_degree": 0}
    
    def get_central_nodes(self, node_type: Optional[str] = None, limit: int = 10, database: Optional[str] = None) -> List[Dict]:
        """
        获取最中心的节点（按关系数量排序）
        
        Args:
            node_type: 节点类型过滤（可选）
            limit: 返回数量限制
        
        Returns:
            中心节点列表
        """
        try:
            if node_type:
                cypher = f"""
                MATCH (n:{node_type})
                WITH n, COUNT {{ (n)-[]-() }} as degree
                RETURN n, degree
                ORDER BY degree DESC
                LIMIT $limit
                """
            else:
                cypher = """
                MATCH (n)
                WITH n, COUNT { (n)-[]-() } as degree
                RETURN n, degree
                ORDER BY degree DESC
                LIMIT $limit
                """
            
            results = self.graph_service.execute_query(cypher, {"limit": limit}, database=database)
            return results
        except Exception as e:
            logger.error(f"获取中心节点失败: {e}")
            return []
    
    def query_by_properties(self, node_type: str, 
                           properties: Dict[str, Any], 
                           limit: int = 50) -> List[Dict]:
        """
        按属性查询节点
        
        Args:
            node_type: 节点类型
            properties: 属性过滤条件
            limit: 返回数量限制
        
        Returns:
            匹配的节点列表
        """
        try:
            # 构建 WHERE 子句
            where_parts = [f"n.{k} = ${k}" for k in properties.keys()]
            where_clause = " AND ".join(where_parts)
            
            cypher = f"""
            MATCH (n:{node_type})
            WHERE {where_clause}
            RETURN n
            LIMIT $limit
            """
            
            params = {**properties, "limit": limit}
            results = self.graph_service.execute_query(cypher, params)
            return results
        except Exception as e:
            logger.error(f"属性查询失败: {e}")
            return []
    
    def community_detection(self, limit: int = 20) -> List[Dict]:
        """
        社区检测（使用 Neo4j 的标签传播算法）
        
        Args:
            limit: 返回数量限制
        
        Returns:
            社区信息
        """
        try:
            # 这是一个简化的实现，实际应用可以使用 Neo4j Graph Algorithms
            cypher = """
            MATCH (n)
            WITH n, size((n)-[]-()) as degree
            RETURN n, degree
            ORDER BY degree DESC
            LIMIT $limit
            """
            
            results = self.graph_service.execute_query(cypher, {"limit": limit})
            return results
        except Exception as e:
            logger.error(f"社区检测失败: {e}")
            return []
    
    def get_graph_stats(self, database: Optional[str] = None) -> Dict[str, Any]:
        """
        获取图谱统计信息
        
        Returns:
            统计数据
        """
        try:
            stats = self.graph_service.get_graph_stats(database=database)

            cypher_communities = """
            MATCH (n)
            WHERE n.community_id IS NOT NULL
            RETURN count(DISTINCT n.community_id) as communities
            """
            
            # 获取节点类型统计
            cypher_labels = """
            MATCH (n)
            WITH labels(n) as labels
            UNWIND labels as label
            RETURN label, count(*) as count
            ORDER BY count DESC
            """
            
            community_row = self.graph_service.execute_query_single(
                cypher_communities,
                database=database,
            ) or {}
            label_stats = self.graph_service.execute_query(cypher_labels, database=database)
            
            # 获取关系类型统计
            cypher_rels = """
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            ORDER BY count DESC
            """
            
            rel_stats = self.graph_service.execute_query(cypher_rels, database=database)
            
            return {
                **stats,
                "communities": int(community_row.get("communities", 0) or 0),
                "node_types": {item.get("label"): item.get("count", 0) for item in label_stats},
                "relation_types": {item.get("type"): item.get("count", 0) for item in rel_stats}
            }
        except Exception as e:
            logger.error(f"获取图谱统计失败: {e}")
            return {}

    def get_document_analysis(self, limit: int = 20, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取文档分析数据（关键节点和类型分布）
        
        Args:
            limit: 返回文档数量限制
            database: Neo4j 数据库名（可选）
            
        Returns:
            文档分析列表
        """
        try:
            # 1. 获取文档列表
            cypher_docs = """
            MATCH (n)
            WHERE n.doc_id IS NOT NULL
            RETURN DISTINCT n.doc_id as doc_id, 
                   COALESCE(n.doc_title, n.source, n.doc_id) as title
            LIMIT $limit
            """
            docs = self.graph_service.execute_query(cypher_docs, {"limit": limit}, database=database)
            
            results = []
            for doc in docs:
                doc_id = doc.get('doc_id')
                title = doc.get('title')
                
                # 2. 获取该文档的关键节点（度数最高的前5个）
                cypher_key_nodes = """
                MATCH (n)
                WHERE n.doc_id = $doc_id OR n.source = $doc_id
                WITH n
                MATCH (n)-[r]-()
                RETURN n, count(r) as degree
                ORDER BY degree DESC
                LIMIT 5
                """
                key_nodes_data = self.graph_service.execute_query(cypher_key_nodes, {"doc_id": doc_id}, database=database)
                
                key_nodes = []
                for item in key_nodes_data:
                    node = item.get('n')
                    degree = item.get('degree')
                    # 提取标签
                    labels = list(getattr(node, 'labels', [])) if hasattr(node, 'labels') else []
                    # 提取名称
                    name = node.get('name') or node.get('title') or node.get('label') or 'Unknown'
                    
                    key_nodes.append({
                        "id": node.get('id'),
                        "name": name,
                        "labels": labels,
                        "degree": degree
                    })
                
                # 3. 获取该文档的节点类型分布
                cypher_types = """
                MATCH (n)
                WHERE n.doc_id = $doc_id OR n.source = $doc_id
                WITH labels(n) as labels
                UNWIND labels as label
                RETURN label, count(*) as count
                ORDER BY count DESC
                """
                types_data = self.graph_service.execute_query(cypher_types, {"doc_id": doc_id}, database=database)
                
                node_types = {item.get('label'): item.get('count') for item in types_data}
                
                results.append({
                    "doc_id": doc_id,
                    "title": title,
                    "key_nodes": key_nodes,
                    "node_types": node_types
                })
                
            return results
        except Exception as e:
            logger.error(f"获取文档分析失败: {e}")
            return []
