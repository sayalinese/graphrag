"""
知识图谱管理服务
负责图谱的 CRUD 操作和维护
"""

import logging
from typing import Dict, List, Any, Optional
from app.models.neo_document import GraphNode, GraphRelation, NodeType, RelationType
from app.services.neo.graph_service import GraphService

logger = logging.getLogger(__name__)


class KGManager:
    """知识图谱管理器"""
    
    def __init__(self, graph_service: GraphService):
        """
        初始化知识图谱管理器
        
        Args:
            graph_service: Neo4j 图服务
        """
        self.graph_service = graph_service
    
    # ==================== 节点管理 ====================
    
    def add_node(self, node_id: str, node_type: str, 
                properties: Dict[str, Any]) -> bool:
        """
        添加节点
        
        Args:
            node_id: 节点 ID
            node_type: 节点类型
            properties: 节点属性
        
        Returns:
            是否添加成功
        """
        try:
            # 验证节点类型
            try:
                label = NodeType[node_type].value
            except KeyError:
                logger.error(f"无效的节点类型: {node_type}")
                return False
            
            # 使用 MERGE 避免重复
            return self.graph_service.merge_node(
                label=label,
                match_props={"id": node_id},
                set_props={
                    "name": properties.get("name", ""),
                    **{k: v for k, v in properties.items() if k != "name"}
                }
            ) is not None
        except Exception as e:
            logger.error(f"添加节点失败: {e}")
            return False
    
    def update_node(self, node_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新节点属性
        
        Args:
            node_id: 节点 ID
            updates: 更新的属性
        
        Returns:
            是否更新成功
        """
        try:
            result = self.graph_service.update_node(node_id, updates)
            return result is not None
        except Exception as e:
            logger.error(f"更新节点失败: {e}")
            return False
    
    def delete_node(self, node_id: str) -> bool:
        """
        删除节点
        
        Args:
            node_id: 节点 ID
        
        Returns:
            是否删除成功
        """
        try:
            return self.graph_service.delete_node(node_id, delete_relations=True)
        except Exception as e:
            logger.error(f"删除节点失败: {e}")
            return False
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """
        获取节点信息
        
        Args:
            node_id: 节点 ID
        
        Returns:
            节点信息
        """
        try:
            return self.graph_service.get_node_by_id(node_id)
        except Exception as e:
            logger.error(f"获取节点失败: {e}")
            return None
    
    def merge_nodes(self, keep_node_id: str, merge_node_ids: List[str]) -> bool:
        """
        合并多个节点到一个节点
        
        Args:
            keep_node_id: 保留的节点 ID
            merge_node_ids: 要合并的节点 ID 列表
        
        Returns:
            是否合并成功
        """
        try:
            logger.info(f"合并节点: {merge_node_ids} 到 {keep_node_id}")
            
            for merge_id in merge_node_ids:
                if merge_id == keep_node_id:
                    continue
                
                # 获取要合并的节点信息
                merge_node = self.graph_service.get_node_by_id(merge_id)
                if not merge_node:
                    logger.warning(f"找不到要合并的节点: {merge_id}")
                    continue
                
                # 重定向所有输入关系
                cypher_in = f"""
                MATCH (a)-[r]->(n {{id: $merge_id}})
                WHERE a.id <> $keep_id
                CREATE (a)-[new_r:{merge_node.get('type', 'RELATED_TO')}]->(b {{id: $keep_id}})
                SET new_r = r
                DELETE r
                """
                
                # 重定向所有输出关系
                cypher_out = f"""
                MATCH (n {{id: $merge_id}})-[r]->(b)
                WHERE b.id <> $keep_id
                CREATE (a {{id: $keep_id}})-[new_r:{merge_node.get('type', 'RELATED_TO')}]->(b)
                SET new_r = r
                DELETE r
                """
                
                self.graph_service.execute_query(cypher_in, {"merge_id": merge_id, "keep_id": keep_node_id})
                self.graph_service.execute_query(cypher_out, {"merge_id": merge_id, "keep_id": keep_node_id})
                
                # 删除要合并的节点
                self.delete_node(merge_id)
            
            logger.info(f"✅ 节点合并完成")
            return True
        except Exception as e:
            logger.error(f"节点合并失败: {e}")
            return False
    
    # ==================== 关系管理 ====================
    
    def add_relation(self, source_id: str, target_id: str, 
                    rel_type: str, properties: Optional[Dict] = None) -> bool:
        """
        添加关系
        
        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            rel_type: 关系类型
            properties: 关系属性
        
        Returns:
            是否添加成功
        """
        try:
            # 验证关系类型
            try:
                RelationType[rel_type]
            except KeyError:
                logger.error(f"无效的关系类型: {rel_type}")
                return False
            
            return self.graph_service.merge_relation(
                source_id=source_id,
                target_id=target_id,
                rel_type=rel_type,
                properties=properties or {}
            )
        except Exception as e:
            logger.error(f"添加关系失败: {e}")
            return False
    
    def update_relation(self, source_id: str, target_id: str, 
                       rel_type: str, updates: Dict[str, Any]) -> bool:
        """
        更新关系属性
        
        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            rel_type: 关系类型
            updates: 更新的属性
        
        Returns:
            是否更新成功
        """
        try:
            cypher = f"""
            MATCH (a {{id: $source}})-[r:{rel_type}]->(b {{id: $target}})
            SET r += $updates
            RETURN r
            """
            
            result = self.graph_service.execute_query_single(
                cypher,
                {"source": source_id, "target": target_id, "updates": updates}
            )
            return result is not None
        except Exception as e:
            logger.error(f"更新关系失败: {e}")
            return False
    
    def delete_relation(self, source_id: str, target_id: str, 
                       rel_type: Optional[str] = None) -> bool:
        """
        删除关系
        
        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            rel_type: 关系类型（如果为 None，删除所有关系）
        
        Returns:
            是否删除成功
        """
        try:
            if rel_type:
                cypher = f"""
                MATCH (a {{id: $source}})-[r:{rel_type}]->(b {{id: $target}})
                DELETE r
                """
            else:
                cypher = """
                MATCH (a {id: $source})-[r]->(b {id: $target})
                DELETE r
                """
            
            self.graph_service.execute_query(
                cypher,
                {"source": source_id, "target": target_id}
            )
            return True
        except Exception as e:
            logger.error(f"删除关系失败: {e}")
            return False
    
    # ==================== 批量操作 ====================
    
    def batch_add_nodes(self, nodes: List[Dict[str, Any]]) -> int:
        """
        批量添加节点
        
        Args:
            nodes: 节点列表，每个节点包含 id, type, properties
        
        Returns:
            成功添加的节点数
        """
        success_count = 0
        for node in nodes:
            if self.add_node(node["id"], node["type"], node.get("properties", {})):
                success_count += 1
        
        logger.info(f"批量添加节点: {success_count}/{len(nodes)} 成功")
        return success_count
    
    def batch_add_relations(self, relations: List[Dict[str, Any]]) -> int:
        """
        批量添加关系
        
        Args:
            relations: 关系列表，每个关系包含 source, target, type, properties
        
        Returns:
            成功添加的关系数
        """
        success_count = 0
        for relation in relations:
            if self.add_relation(
                relation["source"],
                relation["target"],
                relation["type"],
                relation.get("properties")
            ):
                success_count += 1
        
        logger.info(f"批量添加关系: {success_count}/{len(relations)} 成功")
        return success_count
    
    # ==================== 图谱维护 ====================
    
    def remove_duplicates(self) -> int:
        """
        移除重复节点（按名称）
        
        Returns:
            移除的重复数量
        """
        try:
            cypher = """
            MATCH (n1)-[r*0..1]->(n2)
            WHERE n1.name = n2.name AND n1 <> n2
            WITH n1, n2
            WHERE elementId(n1) < elementId(n2)
            CALL apoc.refactor.mergeNodes([n1, n2])
            YIELD node
            RETURN count(node) as merged_count
            """
            
            # 注意：这需要 APOC 库支持
            logger.warning("去重操作需要 Neo4j APOC 库支持")
            return 0
        except Exception as e:
            logger.error(f"去重操作失败: {e}")
            return 0
    
    def remove_orphan_nodes(self) -> int:
        """
        移除孤立节点（没有任何关系的节点）
        
        Returns:
            移除的孤立节点数
        """
        try:
            cypher = """
            MATCH (n)
            WHERE size((n)-[]-()) = 0
            DELETE n
            RETURN count(*) as deleted_count
            """
            
            result = self.graph_service.execute_query_single(cypher)
            deleted = result.get("deleted_count", 0) if result else 0
            logger.info(f"移除了 {deleted} 个孤立节点")
            return deleted
        except Exception as e:
            logger.error(f"移除孤立节点失败: {e}")
            return 0
    
    def validate_graph(self) -> Dict[str, Any]:
        """
        验证图的完整性
        
        Returns:
            验证报告
        """
        try:
            report = {
                "status": "OK",
                "issues": []
            }
            
            # 检查孤立节点
            cypher_orphan = """
            MATCH (n)
            WHERE size((n)-[]-()) = 0
            RETURN count(n) as orphan_count
            """
            
            orphan_result = self.graph_service.execute_query_single(cypher_orphan)
            orphan_count = orphan_result.get("orphan_count", 0) if orphan_result else 0
            
            if orphan_count > 0:
                report["issues"].append(f"发现 {orphan_count} 个孤立节点")
            
            # 检查无效的关系（指向不存在的节点）
            cypher_invalid = """
            MATCH (a)-[r]->(b)
            WHERE NOT EXISTS(b)
            RETURN count(r) as invalid_count
            """
            
            # 检查自环
            cypher_self_loop = """
            MATCH (n)-[r]->(n)
            RETURN count(r) as self_loop_count
            """
            
            self_loop_result = self.graph_service.execute_query_single(cypher_self_loop)
            self_loop_count = self_loop_result.get("self_loop_count", 0) if self_loop_result else 0
            
            if self_loop_count > 0:
                report["issues"].append(f"发现 {self_loop_count} 个自环关系")
            
            if report["issues"]:
                report["status"] = "WARNING"
            
            return report
        except Exception as e:
            logger.error(f"图验证失败: {e}")
            return {"status": "ERROR", "message": str(e)}
    
    # ==================== 备份和恢复 ====================
    
    def export_cypher_script(self) -> str:
        """
        导出为 Cypher 脚本
        
        Returns:
            Cypher 脚本
        """
        try:
            # 获取所有节点
            cypher_nodes = """
            MATCH (n)
            RETURN n
            """
            
            # 获取所有关系
            cypher_rels = """
            MATCH (a)-[r]->(b)
            RETURN a, r, b
            """
            
            nodes = self.graph_service.execute_query(cypher_nodes)
            rels = self.graph_service.execute_query(cypher_rels)
            
            script_parts = []
            
            # 生成 CREATE NODE 语句
            for node_result in nodes:
                node = node_result.get("n", {})
                labels = ",".join(node.get("labels", []))
                props = {k: v for k, v in node.items()}
                script_parts.append(f"CREATE (:{labels} {props})")
            
            # 生成 CREATE RELATION 语句
            for rel_result in rels:
                a = rel_result.get("a", {})
                r = rel_result.get("r", {})
                b = rel_result.get("b", {})
                rel_type = rel_result.get("type", "RELATED_TO")
                props = {k: v for k, v in r.items()}
                script_parts.append(f"MATCH (a {a}) MATCH (b {b}) CREATE (a)-[:{rel_type} {props}]->(b)")
            
            return ";\n".join(script_parts)
        except Exception as e:
            logger.error(f"导出 Cypher 脚本失败: {e}")
            return ""
