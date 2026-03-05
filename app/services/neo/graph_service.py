"""
Neo4j 基础图操作服务
负责 Neo4j 驱动连接、查询执行等基础操作
"""

import logging
from typing import Dict, List, Any, Optional
from neo4j import Driver
from neo4j.exceptions import DriverError, Neo4jError

logger = logging.getLogger(__name__)


class GraphService:
    """Neo4j 图数据库基础服务"""
    
    def __init__(self, driver: Driver):
        self._driver = driver

    @property
    def driver(self):
        """动态获取驱动：若为 None 则尝试重连（不在每次查询时验证连通性）"""
        if self._driver is None:
            try:
                from app.extensions import get_neo4j_driver
                self._driver = get_neo4j_driver()
            except Exception as e:
                logger.warning(f"Neo4j 重连失败: {e}")
        return self._driver

    @driver.setter
    def driver(self, value):
        self._driver = value

    def _session(self, database: Optional[str] = None):
        if database:
            return self.driver.session(database=database)
        return self.driver.session()
    
    def execute_query(self, query: str, parameters: Optional[Dict] = None, database: Optional[str] = None) -> List[Dict]:
        """执行 Cypher 查询，遇到驱动级错误时自动重连一次"""
        if not self.driver:
            logger.error("Neo4j driver is not initialized. Cannot execute query.")
            return []
        try:
            with self._session(database) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except DriverError as e:
            # 驱动断开，清空缓存触发下次重连
            logger.warning(f"Neo4j 驱动异常，重置连接: {e}")
            self._driver = None
            raise
        except Neo4jError as e:
            logger.error(f"Neo4j 查询执行失败: {e}")
            raise
    
    def execute_query_single(self, query: str, parameters: Optional[Dict] = None, database: Optional[str] = None) -> Optional[Dict]:
        """执行单条查询结果的查询"""
        results = self.execute_query(query, parameters, database=database)
        return results[0] if results else None
    
    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict:
        """
        创建单个节点
        
        Args:
            label: 节点标签
            properties: 节点属性
        
        Returns:
            创建的节点信息
        """
        query = f"CREATE (n:{label} $props) RETURN n"
        result = self.execute_query_single(query, {"props": properties})
        return result
    
    def create_nodes_batch(self, label: str, nodes_data: List[Dict[str, Any]], database: Optional[str] = None) -> int:
        """
        批量创建节点
        
        Args:
            label: 节点标签
            nodes_data: 节点数据列表
        
        Returns:
            创建的节点数量
        """
        if not self.driver:
            logger.error("Neo4j driver is not initialized. Cannot execute query.")
            return 0
        try:
            with self._session(database) as session:
                for node_data in nodes_data:
                    session.run(f"CREATE (n:{label} $props)", {"props": node_data})
                return len(nodes_data)
        except Exception as e:
            logger.error(f"批量创建节点失败: {e}")
            raise
    
    def merge_node(self, label: str, match_props: Dict, set_props: Dict) -> Dict:
        """
        使用 MERGE 创建或更新节点（去重）
        
        Args:
            label: 节点标签
            match_props: 匹配属性
            set_props: 设置属性
        
        Returns:
            节点信息
        """
        # MERGE 花括号内使用 key: $value 语法
        match_str = ", ".join([f"{k}: ${k}" for k in match_props.keys()])
        # SET 子句使用 n.key = $value 语法
        set_str = ", ".join([f"n.{k} = ${k}" for k in set_props.keys()])
        
        all_params = {**match_props, **set_props}
        query = f"MERGE (n:{label} {{{match_str}}}) SET {set_str} RETURN n"
        
        result = self.execute_query_single(query, all_params)
        return result
    
    def get_node_by_id(self, node_id: str, label: Optional[str] = None) -> Optional[Dict]:
        """
        根据 ID 获取节点
        
        Args:
            node_id: 节点 ID
            label: 节点标签（可选）
        
        Returns:
            节点信息
        """
        if label:
            query = f"MATCH (n:{label} {{id: $id}}) RETURN n"
        else:
            query = "MATCH (n {{id: $id}}) RETURN n"
        
        result = self.execute_query_single(query, {"id": node_id})
        return result
    
    def get_nodes_by_label(self, label: str, limit: int = 100) -> List[Dict]:
        """
        根据标签获取节点列表
        
        Args:
            label: 节点标签
            limit: 返回数量限制
        
        Returns:
            节点列表
        """
        query = f"MATCH (n:{label}) RETURN n LIMIT $limit"
        return self.execute_query(query, {"limit": limit})
    
    def search_nodes(self, search_text: str, label: Optional[str] = None) -> List[Dict]:
        """
        搜索节点（按名称）
        
        Args:
            search_text: 搜索文本
            label: 节点标签（可选）
        
        Returns:
            匹配的节点列表
        """
        if label:
            query = f"""
            MATCH (n:{label})
            WHERE toLower(n.name) CONTAINS toLower($text)
            RETURN n
            LIMIT 20
            """
        else:
            query = """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($text)
            RETURN n
            LIMIT 20
            """
        
        return self.execute_query(query, {"text": search_text})
    
    def update_node(self, node_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
        """
        更新节点属性
        
        Args:
            node_id: 节点 ID
            updates: 要更新的属性
        
        Returns:
            更新后的节点
        """
        set_str = ", ".join([f"n.{k} = ${k}" for k in updates.keys()])
        query = f"MATCH (n {{id: $id}}) SET {set_str} RETURN n"
        
        all_params = {"id": node_id, **updates}
        result = self.execute_query_single(query, all_params)
        return result
    
    def delete_node(self, node_id: str, delete_relations: bool = True) -> bool:
        """
        删除节点
        
        Args:
            node_id: 节点 ID
            delete_relations: 是否同时删除相关关系
        
        Returns:
            是否删除成功
        """
        if delete_relations:
            query = "MATCH (n {id: $id}) DETACH DELETE n"
        else:
            query = "MATCH (n {id: $id}) DELETE n"
        
        try:
            self.execute_query(query, {"id": node_id})
            return True
        except Exception as e:
            logger.error(f"删除节点失败: {e}")
            return False
    
    def create_relation(self, source_id: str, target_id: str, rel_type: str, 
                       properties: Optional[Dict] = None) -> bool:
        """
        创建关系
        
        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            rel_type: 关系类型
            properties: 关系属性
        
        Returns:
            是否创建成功
        """
        query = f"""
        MATCH (a {{id: $source}})
        MATCH (b {{id: $target}})
        CREATE (a)-[r:{rel_type} $props]->(b)
        RETURN r
        """
        
        try:
            self.execute_query(query, {
                "source": source_id,
                "target": target_id,
                "props": properties or {}
            })
            return True
        except Exception as e:
            logger.error(f"创建关系失败: {e}")
            return False
    
    def merge_relation(self, source_id: str, target_id: str, rel_type: str,
                      properties: Optional[Dict] = None) -> bool:
        """
        使用 MERGE 创建或更新关系（去重）
        
        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            rel_type: 关系类型
            properties: 关系属性
        
        Returns:
            是否成功
        """
        query = f"""
        MATCH (a {{id: $source}})
        MATCH (b {{id: $target}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN r
        """
        
        try:
            self.execute_query(query, {
                "source": source_id,
                "target": target_id,
                "props": properties or {}
            })
            return True
        except Exception as e:
            logger.error(f"合并关系失败: {e}")
            return False
    
    def get_relations(self, node_id: str) -> List[Dict]:
        """
        获取节点的所有关系
        
        Args:
            node_id: 节点 ID
        
        Returns:
            关系列表
        """
        query = """
        MATCH (n {id: $id})-[r]-(m)
        RETURN n, r, m
        """
        return self.execute_query(query, {"id": node_id})
    
    def find_path(self, start_id: str, end_id: str, max_length: int = 5) -> Optional[List[Dict]]:
        """
        查找两个节点之间的路径
        
        Args:
            start_id: 起始节点 ID
            end_id: 结束节点 ID
            max_length: 最大路径长度
        
        Returns:
            路径中的节点和关系
        """
        query = f"""
        MATCH path = shortestPath((a {{id: $start}})-[*1..{max_length}]-(b {{id: $end}}))
        RETURN path
        """
        
        try:
            result = self.execute_query_single(query, {"start": start_id, "end": end_id})
            return result
        except Exception as e:
            logger.error(f"路径查询失败: {e}")
            return None
    
    def get_graph_stats(self) -> Dict[str, int]:
        """
        获取图谱统计信息
        
        Returns:
            统计数据
        """
        try:
            node_count_query = "MATCH (n) RETURN count(n) as count"
            rel_count_query = "MATCH ()-[r]-() RETURN count(r) as count"
            
            node_count = self.execute_query_single(node_count_query)["count"]
            rel_count = self.execute_query_single(rel_count_query)["count"]
            avg_degree = rel_count / node_count if node_count else 0.0
            
            return {
                "total_nodes": node_count,
                "total_relations": rel_count,
                "average_degree": round(avg_degree, 4),
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"total_nodes": 0, "total_relations": 0, "average_degree": 0.0}

    def get_connection_info(self) -> Dict[str, Any]:
        """获取 Neo4j 连接与数据库信息"""
        info: Dict[str, Any] = {
            "uri": "",
            "host": "",
            "version": "",
            "edition": "",
            "databases": []
        }
        try:
            uri = self.driver._uri if hasattr(self.driver, '_uri') else ""
            info["uri"] = uri
            if uri.startswith("bolt://"):
                info["host"] = uri.replace("bolt://", "").split(":")[0]
            # 组件版本
            if not self.driver: return []
            with self.driver.session() as session:
                comp_res = session.run("CALL dbms.components()")
                for record in comp_res:
                    info["version"] = record.get("versions")[0] if record.get("versions") else ""
                    info["edition"] = record.get("edition", "")
                    break
                # 数据库列表
                db_res = session.run("SHOW DATABASES")
                info["databases"] = [
                    {
                        "name": r.get("name"),
                        "type": r.get("type"),
                        "address": r.get("address"),
                        "currentStatus": r.get("currentStatus"),
                        "access": r.get("access"),
                        "role": r.get("role"),
                        "default": r.get("default"),
                    } for r in db_res
                ]
            return info
        except Exception as e:
            logger.error(f"获取连接信息失败: {e}")
            info["error"] = str(e)
            return info
    
    def clear_graph(self) -> bool:
        """
        清空整个图（谨慎使用！）
        
        Returns:
            是否清空成功
        """
        try:
            self.execute_query("MATCH (n) DETACH DELETE n")
            logger.warning("图谱已清空")
            return True
        except Exception as e:
            logger.error(f"清空图谱失败: {e}")
            return False
