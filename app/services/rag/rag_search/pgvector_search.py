import hashlib
import logging
import os
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from langchain_community.vectorstores import PGVector

from app.config import Config

logger = logging.getLogger(__name__)


class PgvectorSearchEngine:
    """pgvector 搜索引擎 - 支持混合搜索 + 重排"""

    def __init__(self, session: Session, embedding_model=None) -> None:
        self.session = session
        self.embedding_model = embedding_model
        self.vector_connection = (
            os.getenv("PGVECTOR_CONNECTION_STRING") or Config.SQLALCHEMY_DATABASE_URI
        )
        self.vector_collection = os.getenv("PGVECTOR_COLLECTION", "default_collection")
        self._vector_store: Optional[PGVector] = None

    def _get_query_embedding(self, text: str) -> Optional[List[float]]:
        if not self.embedding_model:
            logger.warning("未配置向量模型，跳过向量搜索")
            return None

        try:
            return self.embedding_model.embed_query(text)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"向量化查询文本失败: {exc}")
            return None

    def _get_vector_store(self) -> Optional[PGVector]:
        if not self.embedding_model:
            return None
        if self._vector_store is not None:
            return self._vector_store
        try:
            self._vector_store = PGVector(
                connection_string=self.vector_connection,
                collection_name=self.vector_collection,
                embedding_function=self.embedding_model,
            )
            return self._vector_store
        except Exception as exc:  # noqa: BLE001
            logger.error(f"初始化 PGVector 失败: {exc}", exc_info=True)
            self._vector_store = None
            return None

    @staticmethod
    def _distance_to_similarity(distance: Optional[float]) -> float:
        if distance is None:
            return 0.0
        try:
            similarity = 1.0 / (1.0 + max(float(distance), 0.0))
            return round(similarity, 6)
        except Exception:  # noqa: BLE001
            return 0.0

    @staticmethod
    def _hash_content(doc_id: Optional[str], content: str) -> str:
        digest = hashlib.md5((content or "").encode("utf-8", "ignore")).hexdigest()
        return f"vec_{doc_id or 'chunk'}_{digest}"

    @staticmethod
    def _keyword_score(query_text: str, content: str) -> float:
        if not query_text or not content:
            return 0.0
        snippet = content[:400]
        ratio = SequenceMatcher(None, query_text, snippet).quick_ratio()
        occurrences = content.count(query_text)
        freq = occurrences * len(query_text) / max(len(content), len(query_text), 1)
        direct_hit = 1.0 if query_text in content else 0.0
        score = (direct_hit * 0.6) + (min(freq, 1.0) * 0.2) + (ratio * 0.2)
        return round(min(max(score, ratio), 1.0), 6)

    def hybrid_search(
        self,
        kb_id: int,
        query_text: str,
        top_k: int = 10,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        try:
            query_vector = self._get_query_embedding(query_text)
            vector_results = (
                self._vector_search(kb_id, query_vector, top_k * 2)
                if query_vector
                else []
            )
            bm25_results = self._bm25_search(kb_id, query_text, top_k * 2)
            return self._merge_results(
                vector_results,
                bm25_results,
                vector_weight,
                bm25_weight,
                threshold,
                top_k,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"混合搜索失败: {exc}", exc_info=True)
            raise

    def _vector_search(
        self,
        kb_id: int,
        query_vector: List[float],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        try:
            from app.models import DocumentChunk, KnowledgeBase

            kb_row = (
                self.session.query(KnowledgeBase.kb_id)
                .filter(KnowledgeBase.id == kb_id)
                .first()
            )
            if not kb_row or not kb_row.kb_id:
                logger.warning("知识库 %s 不存在或未配置 kb_id", kb_id)
                return []

            vector_store = self._get_vector_store()
            if not vector_store:
                return []

            try:
                docs_with_scores = vector_store.similarity_search_with_score_by_vector(
                    query_vector,
                    k=limit,
                    filter={"kb_id": str(kb_row.kb_id)},
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(f"PGVector 向量检索失败: {exc}", exc_info=True)
                return []

            if not docs_with_scores:
                return []

            doc_ids: List[str] = []
            for doc, _ in docs_with_scores:
                metadata = doc.metadata or {}
                doc_id = metadata.get("doc_id")
                if not doc_id:
                    continue
                try:
                    uuid.UUID(doc_id)
                    doc_ids.append(doc_id)
                except Exception:  # noqa: BLE001
                    continue

            chunk_rows: Dict[str, List[Any]] = {}
            doc_filenames: Dict[str, str] = {}  # 存储 doc_id -> filename 映射
            if doc_ids:
                uuid_values = {uuid.UUID(value) for value in doc_ids}
                
                # 查询 chunks
                rows = (
                    self.session.query(
                        DocumentChunk.id,
                        DocumentChunk.doc_id,
                        DocumentChunk.content,
                        DocumentChunk.metadata_json,
                        DocumentChunk.created_at,
                    )
                    .filter(DocumentChunk.doc_id.in_(list(uuid_values)))
                    .all()
                )
                for row in rows:
                    chunk_rows.setdefault(str(row.doc_id), []).append(row)
                
                # 查询文件名
                from app.models import Document
                doc_rows = (
                    self.session.query(Document.doc_id, Document.filename)
                    .filter(Document.doc_id.in_(list(uuid_values)))
                    .all()
                )
                for doc_row in doc_rows:
                    doc_filenames[str(doc_row.doc_id)] = doc_row.filename

            results: List[Dict[str, Any]] = []
            for doc, distance in docs_with_scores:
                metadata = dict(doc.metadata or {})
                doc_id_str = metadata.get("doc_id")
                chunk_row = None
                if doc_id_str and doc_id_str in chunk_rows:
                    for row in chunk_rows[doc_id_str]:
                        if row.content == doc.page_content:
                            chunk_row = row
                            break

                metadata_payload = dict(metadata)
                identifier = None
                created_at_iso = metadata.get("created_at")
                if chunk_row:
                    identifier = chunk_row.id
                    if chunk_row.metadata_json:
                        metadata_payload = {**chunk_row.metadata_json, **metadata_payload}
                    if chunk_row.created_at:
                        created_at_iso = chunk_row.created_at.isoformat()
                else:
                    identifier = metadata.get("chunk_id") or self._hash_content(
                        doc_id_str, doc.page_content
                    )
                
                # 添加文件名到 metadata
                if doc_id_str and doc_id_str in doc_filenames:
                    metadata_payload["filename"] = doc_filenames[doc_id_str]

                results.append(
                    {
                        "id": identifier,
                        "kb_id": kb_id,
                        "doc_id": doc_id_str,
                        "content": doc.page_content,
                        "metadata": metadata_payload,
                        "vector_score": self._distance_to_similarity(distance),
                        "distance": float(distance) if distance is not None else None,
                        "score_type": "vector",
                        "created_at": created_at_iso,
                    }
                )

            return results
        except Exception as exc:  # noqa: BLE001
            logger.error(f"向量搜索失败: {exc}", exc_info=True)
            return []

    def _bm25_search(
        self,
        kb_id: int,
        query_text: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """基于关键词全文搜索"""
        try:
            from app.models import Document, DocumentChunk, KnowledgeBase

            results = (
                self.session.query(
                    DocumentChunk.id,
                    DocumentChunk.doc_id,
                    DocumentChunk.content,
                    DocumentChunk.metadata_json,
                    DocumentChunk.created_at,
                    Document.filename,  # 添加文件名
                )
                .join(Document, DocumentChunk.doc_id == Document.doc_id)
                .join(KnowledgeBase, Document.kb_id == KnowledgeBase.kb_id)
                .filter(
                    KnowledgeBase.id == kb_id,
                    DocumentChunk.content.ilike(f"%{query_text}%"),
                )
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": row.id,
                    "kb_id": kb_id,
                    "doc_id": str(row.doc_id) if row.doc_id else None,
                    "content": row.content,
                    "metadata": {**(row.metadata_json or {}), "filename": row.filename},
                    "bm25_score": self._keyword_score(query_text, row.content or ""),
                    "score_type": "bm25",
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in results
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"BM25 搜索失败: {exc}", exc_info=True)
            return []

    def _merge_results(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        vector_weight: float,
        bm25_weight: float,
        threshold: float,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        合并两个搜索结果
        1. 去重（按 chunk_id）
        2. 加权合并分数
        3. 按总分排序
        4. 过滤和截断
        """
        merged: Dict[Any, Dict[str, Any]] = {}

        for result in vector_results:
            chunk_id = result["id"]
            merged[chunk_id] = {
                **result,
                "vector_score": result.get("vector_score", 0.0),
                "bm25_score": 0.0,
                "fused_score": 0.0,
            }

        for result in bm25_results:
            chunk_id = result["id"]
            if chunk_id in merged:
                merged[chunk_id]["bm25_score"] = result.get("bm25_score", 0.0)
            else:
                merged[chunk_id] = {
                    **result,
                    "vector_score": 0.0,
                    "bm25_score": result.get("bm25_score", 0.0),
                    "fused_score": 0.0,
                }

        for payload in merged.values():
            vector_score = payload.get("vector_score", 0.0)
            bm25_score = min(payload.get("bm25_score", 0.0), 1.0)
            payload["fused_score"] = vector_weight * vector_score + bm25_weight * bm25_score

        sorted_results = sorted(
            merged.values(), key=lambda item: item["fused_score"], reverse=True
        )
        filtered = [item for item in sorted_results if item["fused_score"] >= threshold]
        final_results = filtered[:top_k]

        for rank, item in enumerate(final_results, start=1):
            item["rank"] = rank

        return final_results

    def rerank_search(
        self,
        kb_id: int,
        query_text: str,
        top_k: int = 10,
        rerank_top_k: int = 50,
        reranker=None,
    ) -> List[Dict[str, Any]]:
        """
        使用重排器的高级搜索
        
        1. 先执行混合搜索获取 top_k*5 的候选
        2. 使用重排器重新排序
        3. 返回 top_k 结果
        
        Args:
            kb_id: 知识库 ID
            query_text: 查询文本
            top_k: 最终返回结果数
            rerank_top_k: 重排前的候选数量
            reranker: 重排模型
        """
        try:
            # 获取候选
            candidates = self.hybrid_search(
                kb_id,
                query_text,
                top_k=rerank_top_k,
                vector_weight=0.5,
                bm25_weight=0.5,
            )
            
            if not candidates or not reranker:
                # 没有候选或没有重排器，直接返回
                return candidates[:top_k]
            
            # 重排
            query_content_pairs = [
                [query_text, result['content']]
                for result in candidates
            ]
            
            rerank_scores = reranker.rank(query_content_pairs)
            
            # 更新分数
            for i, result in enumerate(candidates):
                result['rerank_score'] = rerank_scores[i]
            
            # 按重排分数排序
            reranked = sorted(
                candidates,
                key=lambda x: x.get('rerank_score', 0),
                reverse=True
            )
            
            # 更新排名
            for rank, result in enumerate(reranked[:top_k], 1):
                result['rank'] = rank
            
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"重排搜索失败: {e}")
            # 降级到混合搜索
            return self.hybrid_search(kb_id, query_text, top_k)


def create_search_engine(
    db_session: Session,
    embedding_model=None,
) -> PgvectorSearchEngine:
    """工厂函数：创建搜索引擎"""
    return PgvectorSearchEngine(db_session, embedding_model)
