from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime


class NodeType(Enum):
    """节点类型"""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    PRODUCT = "PRODUCT"
    CONCEPT = "CONCEPT"
    EVENT = "EVENT"
    DOCUMENT = "DOCUMENT"


class RelationType(Enum):
    """关系类型"""
    # 基本关系
    LOCATED_IN = "LOCATED_IN"           # 位于
    WORKS_FOR = "WORKS_FOR"             # 工作于
    OWNS = "OWNS"                       # 拥有
    PART_OF = "PART_OF"                 # 属于
    KNOWS = "KNOWS"                     # 认识
    MENTIONS = "MENTIONS"               # 提及
    RELATED_TO = "RELATED_TO"           # 相关
    FOUNDED_BY = "FOUNDED_BY"           # 创立者
    PARTICIPATES_IN = "PARTICIPATES_IN" # 参与
    PRODUCES = "PRODUCES"               # 生产
    # 人物关系
    FRIEND_OF = "FRIEND_OF"             # 朋友
    ENEMY_OF = "ENEMY_OF"               # 敌人
    FAMILY_OF = "FAMILY_OF"             # 家人
    MASTER_OF = "MASTER_OF"             # 师父
    STUDENT_OF = "STUDENT_OF"           # 徒弟
    ALLY_OF = "ALLY_OF"                 # 盟友
    RIVAL_OF = "RIVAL_OF"               # 对手
    # 组织关系
    MEMBER_OF = "MEMBER_OF"             # 成员
    LEADER_OF = "LEADER_OF"             # 领导
    BELONGS_TO = "BELONGS_TO"           # 属于
    # 能力/物品关系
    HAS_ABILITY = "HAS_ABILITY"         # 拥有能力
    CREATED_BY = "CREATED_BY"           # 创造



@dataclass
class GraphNode:
    """Neo4j 节点"""
    id: str                                    # 唯一标识
    label: NodeType                            # 节点类型
    properties: Dict[str, Any] = field(default_factory=dict)  # 属性
    source: str = ""                           # 数据来源 (文档ID)
    embedding: Optional[List[float]] = None   # 节点向量表示（可选）
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_cypher_create(self) -> str:
        """生成 Cypher CREATE 语句"""
        props = self._escape_properties()
        props_str = ", ".join([f"{k}: {self._format_value(v)}" for k, v in props.items()])
        return f"CREATE (n:{self.label.value} {{{props_str}}})"
    
    def to_cypher_merge(self) -> str:
        """生成 Cypher MERGE 语句（去重）"""
        props = self._escape_properties()
        on_match = ", ".join([f"n.{k} = {self._format_value(v)}" for k, v in props.items()])
        return f"MERGE (n:{self.label.value} {{id: '{self.id}'}}) ON MATCH SET {on_match}"
    
    def _escape_properties(self) -> Dict[str, Any]:
        """转义属性"""
        return {
            "id": self.id,
            "name": self.properties.get("name", ""),
            "source": self.source,
            **{k: v for k, v in self.properties.items() if k != "name"}
        }
    
    @staticmethod
    def _format_value(value: Any) -> str:
        """格式化属性值"""
        if isinstance(value, str):
            escaped = value.replace("'", "\\'")
            return f"'{escaped}'"
        elif isinstance(value, bool):
            return str(value).lower()
        elif value is None:
            return "null"
        else:
            return str(value)


@dataclass
class GraphRelation:
    """Neo4j 关系"""
    source_id: str                      # 源节点 ID
    target_id: str                      # 目标节点 ID
    type: RelationType                  # 关系类型
    properties: Dict[str, Any] = field(default_factory=dict)  # 关系属性
    strength: float = 1.0               # 关系强度 (0-1)
    source_doc: str = ""                # 来自哪个文档
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_cypher_create(self) -> str:
        """生成 Cypher CREATE 关系语句"""
        props = self.properties.copy()
        props["strength"] = self.strength
        props["source"] = self.source_doc
        props_str = ", ".join([f"{k}: {GraphNode._format_value(v)}" for k, v in props.items()])
        return f"MATCH (a {{id: '{self.source_id}'}}), (b {{id: '{self.target_id}'}}) CREATE (a)-[r:{self.type.value} {{{props_str}}}]->(b)"
    
    def to_cypher_merge(self) -> str:
        """生成 Cypher MERGE 关系语句（去重）"""
        props = self.properties.copy()
        props["strength"] = self.strength
        props["source"] = self.source_doc
        props_str = ", ".join([f"{k}: {GraphNode._format_value(v)}" for k, v in props.items()])
        return f"MATCH (a {{id: '{self.source_id}'}}), (b {{id: '{self.target_id}'}}) MERGE (a)-[r:{self.type.value}]->(b) SET r += {{{props_str}}}"


@dataclass
class GraphDocument:
    """一个文档对应的完整图结构"""
    document_id: str                    # 文档ID
    document_title: str = ""            # 文档标题
    nodes: List[GraphNode] = field(default_factory=list)
    relations: List[GraphRelation] = field(default_factory=list)
    chunks: List[str] = field(default_factory=list)  # 文档分块
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_node(self, node: GraphNode):
        """添加节点"""
        # 检查是否存在重复
        if not any(n.id == node.id for n in self.nodes):
            self.nodes.append(node)
    
    def add_relation(self, relation: GraphRelation):
        """添加关系"""
        self.relations.append(relation)
    
    def add_nodes(self, nodes: List[GraphNode]):
        """批量添加节点"""
        for node in nodes:
            self.add_node(node)
    
    def add_relations(self, relations: List[GraphRelation]):
        """批量添加关系"""
        for relation in relations:
            self.add_relation(relation)
    
    def to_cypher_script(self) -> str:
        """生成完整的 Cypher 脚本"""
        script_parts = []
        
        # 创建节点
        for node in self.nodes:
            script_parts.append(node.to_cypher_merge())
        
        # 创建关系
        for relation in self.relations:
            script_parts.append(relation.to_cypher_merge())
        
        return ";\n".join(script_parts) + ";"
    
    def get_summary(self) -> Dict[str, Any]:
        """获取图谱摘要"""
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "node_count": len(self.nodes),
            "relation_count": len(self.relations),
            "node_types": {t.value: sum(1 for n in self.nodes if n.label == t) for t in NodeType},
            "relation_types": {t.value: sum(1 for r in self.relations if r.type == t) for t in RelationType},
            "chunks_count": len(self.chunks),
        }


# ==================== 查询辅助类 ====================

@dataclass
class NodeQueryResult:
    """节点查询结果"""
    id: str
    label: str
    properties: Dict[str, Any]
    relations_count: int = 0
    
    @classmethod
    def from_neo4j_record(cls, record):
        """从 Neo4j 查询结果转换"""
        node = record.get('node') or record.get('n')
        return cls(
            id=node.get('id'),
            label=list(node.labels)[0] if node.labels else '',
            properties=dict(node.items())
        )


@dataclass
class PathResult:
    """路径查询结果"""
    start_node: str
    end_node: str
    path_length: int
    nodes: List[str] = field(default_factory=list)
    relations: List[str] = field(default_factory=list)


# ==================== 配置常量 ====================

# Neo4j 操作配置
NEO4J_CONFIG = {
    "node_creation_timeout": 30,        # 节点创建超时（秒）
    "relation_creation_timeout": 30,    # 关系创建超时（秒）
    "merge_on_create": True,            # 创建时使用 MERGE 去重
    "batch_size": 100,                  # 批量操作的批大小
}

# 支持的关系类型映射
RELATION_KEYWORDS = {
    "位于": RelationType.LOCATED_IN,
    "工作": RelationType.WORKS_FOR,
    "拥有": RelationType.OWNS,
    "属于": RelationType.PART_OF,
    "认识": RelationType.KNOWS,
    "提及": RelationType.MENTIONS,
    "相关": RelationType.RELATED_TO,
    "创立": RelationType.FOUNDED_BY,
    "参与": RelationType.PARTICIPATES_IN,
    "生产": RelationType.PRODUCES,
}

# 支持的节点类型映射
NODE_KEYWORDS = {
    "人物": NodeType.PERSON,
    "组织": NodeType.ORGANIZATION,
    "地点": NodeType.LOCATION,
    "产品": NodeType.PRODUCT,
    "概念": NodeType.CONCEPT,
    "事件": NodeType.EVENT,
    "文档": NodeType.DOCUMENT,
}
