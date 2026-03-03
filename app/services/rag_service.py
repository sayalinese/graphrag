"""
统一 RAG 服务层
兼容 GraphRAG 和传统向量 RAG
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from app.extensions import get_neo4j_driver
from app.utils.llm_utils import DeepSeekLLM
from app.services.neo import GraphService, KGBuilder, KGQuery, KGManager
from app.services.rag.rag_search import search_api

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """Minimal配置对象，兼容旧版 API 所需字段。"""

    top_k: int = 5
    threshold: float = 0.35
    max_citations: int = 4
    enable_rerank: bool = False
    rerank_top_k: int = 5


class RAGService:
    """统一 RAG 服务"""
    
    def __init__(self, mode: str = "graphrag", deepseek_api_key: str = ""):
        """
        初始化 RAG 服务
        
        Args:
            mode: RAG 模式 ('graphrag' 或 'vector')
            deepseek_api_key: DeepSeek API 密钥
        """
        self.mode = mode
        self.deepseek_api_key = deepseek_api_key
        
        # 初始化 Neo4j 相关服务
        if mode == "graphrag":
            driver = get_neo4j_driver()
            self.graph_service = GraphService(driver)
            self.kg_builder = KGBuilder(self.graph_service, DeepSeekLLM(deepseek_api_key))
            self.kg_query = KGQuery(self.graph_service)
            self.kg_manager = KGManager(self.graph_service)
        
        logger.info(f"✅ RAG 服务初始化成功 (模式: {mode})")
    
    def query(self, query_text: str, top_k: int = 5) -> Dict[str, Any]:
        """
        执行 RAG 查询
        
        Args:
            query_text: 查询文本
            top_k: 返回结果数量
        
        Returns:
            查询结果
        """
        if self.mode == "graphrag":
            return self._graphrag_query(query_text, top_k)
        else:
            return self._vector_query(query_text, top_k)
    
    def _graphrag_query(self, query_text: str, top_k: int) -> Dict[str, Any]:
        """GraphRAG 查询"""
        try:
            # 搜索相关节点
            nodes = self.kg_query.search_nodes(query_text, limit=top_k)
            
            result = {
                "mode": "graphrag",
                "query": query_text,
                "results": nodes,
                "count": len(nodes),
            }
            
            return result
        except Exception as e:
            logger.error(f"GraphRAG 查询失败: {e}")
            return {"mode": "graphrag", "query": query_text, "results": [], "count": 0, "error": str(e)}
    
    def _vector_query(self, query_text: str, top_k: int) -> Dict[str, Any]:
        """向量 RAG 查询（预留）"""
        logger.warning("向量 RAG 模式暂未实现")
        return {"mode": "vector", "query": query_text, "results": [], "count": 0}
    
    def build_from_text(self, text: str, document_id: str = "", 
                       document_title: str = "") -> Dict[str, Any]:
        """
        从文本构建知识图谱
        
        Args:
            text: 输入文本
            document_id: 文档 ID
            document_title: 文档标题
        
        Returns:
            构建结果
        """
        if self.mode != "graphrag":
            return {"success": False, "error": "此功能仅在 GraphRAG 模式下可用"}
        
        try:
            # 构建图文档
            graph_doc = self.kg_builder.build_from_text(text, document_id, document_title)
            
            # 保存到 Neo4j
            success = self.kg_builder.save_to_neo4j(graph_doc)
            
            return {
                "success": success,
                "document_id": document_id,
                "summary": graph_doc.get_summary()
            }
        except Exception as e:
            logger.error(f"知识图谱构建失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        if self.mode != "graphrag":
            return {"error": "此功能仅在 GraphRAG 模式下可用"}
        
        try:
            return self.kg_query.get_graph_stats()
        except Exception as e:
            logger.error(f"获取图谱统计失败: {e}")
            return {"error": str(e)}
    
    def search_nodes(self, query: str, node_type: Optional[str] = None, 
                    limit: int = 20) -> List[Dict]:
        """搜索节点"""
        if self.mode != "graphrag":
            return []
        
        try:
            return self.kg_query.search_nodes(query, node_type, limit)
        except Exception as e:
            logger.error(f"节点搜索失败: {e}")
            return []
    
    def get_node_context(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """获取节点上下文"""
        if self.mode != "graphrag":
            return {}
        
        try:
            return self.kg_query.get_node_context(node_id, depth)
        except Exception as e:
            logger.error(f"获取节点上下文失败: {e}")
            return {}
    
    def switch_mode(self, mode: str) -> bool:
        """切换 RAG 模式"""
        if mode not in ["graphrag", "vector"]:
            logger.error(f"无效的 RAG 模式: {mode}")
            return False
        
        self.mode = mode
        logger.info(f"✅ RAG 模式已切换为: {mode}")
        return True


class DisabledRAGService:
    """向后兼容的占位实现，确保旧版 RAG API 不至于 ImportError。"""

    def __init__(self):
        self.config = RAGConfig()
        self.mode = "vector"

    def update_config(self, new_cfg: RAGConfig) -> None:
        self.config = new_cfg

    def get_status(self) -> Dict[str, Any]:
        return {
            "success": False,
            "mode": self.mode,
            "available": False,
            "message": "RAG 向量检索尚未配置，已降级为空实现"
        }

    # === 旧接口占位 ===
    def query_knowledge_base(self, kb_id: int, query: str,
                              session_id: Optional[str] = None,
                              message_id: Optional[str] = None,
                              user_id: Optional[int] = None) -> Dict[str, Any]:
        engine = search_api.get_search_engine()
        if not engine:
             return {
                "success": False,
                "kb_id": kb_id,
                "query": query,
                "citations": [],
                "message_id": message_id,
                "error": "Search engine init failed"
            }
        
        try:
            results = engine.hybrid_search(kb_id=kb_id, query_text=query, top_k=5)
            
            citations = []
            for i, r in enumerate(results):
                 citations.append({
                     "score": r.get("fused_score"),
                     "content": r.get("content"),
                     "metadata": r.get("metadata"),
                     "id": r.get("doc_id"),
                     "rank": i + 1,
                     "source_type": "document"
                 })
                 
            return {
                "success": True,
                "kb_id": kb_id,
                "query": query,
                "citations": citations,
                "message_id": message_id
            }
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return {
                "success": False,
                "kb_id": kb_id,
                "query": query,
                "citations": [],
                "message_id": message_id,
                "error": str(e)
            }

    def query(self, query_text: str, top_k: int = 5) -> Dict[str, Any]:
        return {
            "success": False,
            "query": query_text,
            "mode": self.mode,
            "results": [],
            "error": "RAG vector service not configured"
        }

    def build_from_text(self, text: str, document_id: str = "",
                        document_title: str = "") -> Dict[str, Any]:
        return {"success": False, "error": "RAG vector service not configured"}

    def get_graph_stats(self) -> Dict[str, Any]:
        return {"success": False, "error": "RAG vector service not configured"}

    def search_nodes(self, query: str, node_type: Optional[str] = None,
                     limit: int = 20) -> List[Dict[str, Any]]:
        return []

    def get_node_context(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        return {}

    def switch_mode(self, mode: str) -> bool:
        self.mode = mode
        return True


# 兼容旧引用：提供一个默认的空实现实例
rag_service = DisabledRAGService()
