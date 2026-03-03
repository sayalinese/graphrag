"""
知识图谱构建服务
负责从文本中提取实体和关系，并构建 Neo4j 图谱
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from app.models.neo_document import (
    GraphNode, GraphRelation, GraphDocument, 
    NodeType, RelationType, NODE_KEYWORDS, RELATION_KEYWORDS
)
from app.utils.llm_utils import DeepSeekLLM, EntityModel, RelationModel
from app.services.neo.graph_service import GraphService
from app.services.neo.mapping_manager import MappingManager

logger = logging.getLogger(__name__)


class KGBuilder:
    """知识图谱构建器"""
    
    def __init__(self, graph_service: GraphService, llm: DeepSeekLLM):
        """
        初始化知识图谱构建器
        
        Args:
            graph_service: Neo4j 图服务
            llm: DeepSeek LLM 实例
        """
        self.graph_service = graph_service
        self.llm = llm
        self.mapping_manager = MappingManager()
    
    def build_from_text(self, text: str, document_id: str = "", document_title: str = "") -> GraphDocument:
        """
        从文本构建完整的图文档
        
        Args:
            text: 输入文本
            document_id: 文档 ID
            document_title: 文档标题
        
        Returns:
            构建的图文档
        """
        logger.info(f"开始构建知识图谱: {document_title}")
        
        # 创建图文档
        graph_doc = GraphDocument(
            document_id=document_id,
            document_title=document_title,
        )
        
        # 步骤 1: 实体提取
        logger.info("步骤 1: 提取实体...")
        entities = self.llm.extract_entities(text)
        logger.info(f"提取了 {len(entities)} 个实体")
        
        # 步骤 2: 实体转换为图节点
        logger.info("步骤 2: 转换为图节点...")
        nodes = self._entities_to_nodes(entities, document_id)
        graph_doc.add_nodes(nodes)
        logger.info(f"创建了 {len(nodes)} 个节点")
        
        # 步骤 3: 关系提取
        logger.info("步骤 3: 提取关系...")
        relations = self.llm.extract_relations(text, entities)
        logger.info(f"提取了 {len(relations)} 个关系")
        
        # 步骤 4: 关系转换为图关系
        logger.info("步骤 4: 转换为图关系...")
        graph_relations = self._relations_to_graph_relations(relations, entities, document_id)
        graph_doc.add_relations(graph_relations)
        logger.info(f"创建了 {len(graph_relations)} 个关系")
        
        logger.info(f"✅ 知识图谱构建完成")
        return graph_doc
    
    def build_from_chunks(self, chunks: List[str], document_id: str = "", 
                         document_title: str = "") -> GraphDocument:
        """
        从多个文本块构建图文档（支持长文档分块处理）
        
        Args:
            chunks: 文本块列表
            document_id: 文档 ID
            document_title: 文档标题
        
        Returns:
            合并后的图文档
        """
        logger.info(f"从 {len(chunks)} 个文本块构建知识图谱")
        
        merged_graph = GraphDocument(
            document_id=document_id,
            document_title=document_title,
            chunks=chunks,
        )
        
        # 处理每个块
        for i, chunk in enumerate(chunks):
            logger.info(f"处理文本块 {i+1}/{len(chunks)}")
            
            if not chunk.strip():
                continue
            
            # 从块构建临时图
            temp_graph = self.build_from_text(
                text=chunk,
                document_id=document_id,
                document_title=f"{document_title}_chunk_{i}"
            )
            
            # 合并节点（去重）
            self._merge_nodes(merged_graph, temp_graph)
            
            # 添加关系
            merged_graph.add_relations(temp_graph.relations)
        
        logger.info(f"✅ 文本块知识图谱构建完成")
        return merged_graph
    
    def save_to_neo4j(self, graph_doc: GraphDocument) -> bool:
        """
        将图文档保存到 Neo4j
        
        Args:
            graph_doc: 图文档
        
        Returns:
            是否保存成功
        """
        try:
            logger.info(f"保存图文档到 Neo4j: {graph_doc.document_id}")
            
            # 保存节点
            logger.info(f"保存 {len(graph_doc.nodes)} 个节点...")
            for node in graph_doc.nodes:
                self.graph_service.merge_node(
                    label=node.label.value,
                    match_props={"id": node.id},
                    set_props={
                        "name": node.properties.get("name", ""),
                        "source": node.source,
                        **{k: v for k, v in node.properties.items() if k != "name"}
                    }
                )
            
            # 保存关系
            logger.info(f"保存 {len(graph_doc.relations)} 个关系...")
            for relation in graph_doc.relations:
                self.graph_service.merge_relation(
                    source_id=relation.source_id,
                    target_id=relation.target_id,
                    rel_type=relation.type.value,
                    properties={
                        "strength": relation.strength,
                        "source_doc": relation.source_doc,
                        **relation.properties
                    }
                )
            
            logger.info(f"✅ 图文档保存成功")
            return True
        except Exception as e:
            logger.error(f"保存图文档失败: {e}")
            return False
    
    def _parse_entity_type(self, entity_type: str) -> NodeType:
        """
        解析实体类型，支持复合类型如 "组织/概念"
        按优先级返回第一个匹配的类型
        """
        # 优先级顺序：人物 > 组织 > 地点 > 物品 > 事件 > 概念
        priority_order = [
            NodeType.PERSON,
            NodeType.ORGANIZATION, 
            NodeType.LOCATION,
            NodeType.PRODUCT,
            NodeType.EVENT,
            NodeType.CONCEPT,
        ]
        
        # 获取当前的实体映射
        entity_type_map = self.mapping_manager.get_entity_type_map()
        
        # 分割复合类型（支持 / 和 、 分隔符）
        parts = [p.strip() for p in entity_type.replace('、', '/').split('/')]
        
        # 收集所有匹配的类型
        matched_types = []
        for part in parts:
            # 先尝试中文映射
            if part in entity_type_map:
                matched_types.append(entity_type_map[part])
            else:
                # 再尝试英文枚举
                try:
                    matched_types.append(NodeType[part.upper()])
                except KeyError:
                    pass
        
        # 按优先级返回
        if matched_types:
            for priority_type in priority_order:
                if priority_type in matched_types:
                    return priority_type
            return matched_types[0]
        
        return NodeType.CONCEPT
    
    def _entities_to_nodes(self, entities: List[EntityModel], 
                          document_id: str) -> List[GraphNode]:
        """
        将 LLM 提取的实体转换为图节点
        
        Args:
            entities: 实体列表
            document_id: 文档 ID
        
        Returns:
            图节点列表
        """
        nodes = []
        
        for entity in entities:
            # 转换实体类型（支持中文、英文和复合类型）
            node_type = self._parse_entity_type(entity.entity_type)
            
            # 创建节点
            node = GraphNode(
                id=entity.entity_id,
                label=node_type,
                properties={
                    "name": entity.entity_name,
                    "description": entity.description,
                    **entity.attributes
                },
                source=document_id
            )
            
            nodes.append(node)
        
        return nodes
    
    def _parse_relation_type(self, relation_type: str) -> RelationType:
        """
        解析关系类型，支持中文和英文
        """
        # 获取当前的关系映射
        relation_type_map = self.mapping_manager.get_relation_type_map()
        
        # 先尝试中文映射
        if relation_type in relation_type_map:
            return relation_type_map[relation_type]
        
        # 再尝试英文枚举（大写）
        try:
            return RelationType[relation_type.upper()]
        except KeyError:
            pass
        
        # 最后默认为 RELATED_TO
        logger.warning(f"未知的关系类型: {relation_type}，默认为 RELATED_TO")
        return RelationType.RELATED_TO
    
    def _relations_to_graph_relations(self, relations: List[RelationModel], 
                                      entities: List[EntityModel],
                                      document_id: str) -> List[GraphRelation]:
        """
        将 LLM 提取的关系转换为图关系
        
        Args:
            relations: 关系列表
            entities: 实体列表（用于匹配 ID）
            document_id: 文档 ID
        
        Returns:
            图关系列表
        """
        graph_relations = []
        
        # 建立实体名称到 ID 的映射
        entity_name_to_id = {e.entity_name: e.entity_id for e in entities}
        
        for relation in relations:
            # 获取源和目标实体 ID
            source_id = entity_name_to_id.get(relation.source_entity)
            target_id = entity_name_to_id.get(relation.target_entity)
            
            if not source_id or not target_id:
                logger.warning(f"无法匹配实体 ID: {relation.source_entity} -> {relation.target_entity}")
                continue
            
            # 转换关系类型（支持英文和中文）
            rel_type = self._parse_relation_type(relation.relation_type)
            
            # 创建关系
            graph_relation = GraphRelation(
                source_id=source_id,
                target_id=target_id,
                type=rel_type,
                properties={"description": relation.relation_description},
                strength=relation.strength,
                source_doc=document_id
            )
            
            graph_relations.append(graph_relation)
        
        return graph_relations
    
    def _merge_nodes(self, target_graph: GraphDocument, 
                    source_graph: GraphDocument):
        """
        合并节点（去重）
        
        Args:
            target_graph: 目标图文档
            source_graph: 源图文档
        """
        for source_node in source_graph.nodes:
            # 检查是否存在相同 ID 的节点
            existing_node = next(
                (n for n in target_graph.nodes if n.id == source_node.id),
                None
            )
            
            if existing_node:
                # 更新节点信息（合并属性）
                existing_node.properties.update(source_node.properties)
                logger.debug(f"合并了节点: {source_node.id}")
            else:
                # 添加新节点
                target_graph.add_node(source_node)
    
    def update_graph(self, graph_doc: GraphDocument, updates: Dict[str, Any]) -> bool:
        """
        更新已有的图文档
        
        Args:
            graph_doc: 图文档
            updates: 更新信息
        
        Returns:
            是否更新成功
        """
        try:
            logger.info(f"更新图文档: {graph_doc.document_id}")
            
            # 更新文档元数据
            graph_doc.metadata.update(updates)
            
            # 重新保存到 Neo4j
            return self.save_to_neo4j(graph_doc)
        except Exception as e:
            logger.error(f"更新图文档失败: {e}")
            return False
    
    def get_graph_summary(self, graph_doc: GraphDocument) -> Dict[str, Any]:
        """
        获取图文档摘要
        
        Args:
            graph_doc: 图文档
        
        Returns:
            摘要信息
        """
        return graph_doc.get_summary()
