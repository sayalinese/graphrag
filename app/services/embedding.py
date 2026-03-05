import os
import logging
from typing import List, Optional
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores import PGVector
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings as LCEmbeddings
from app.config import Config

logger = logging.getLogger(__name__)

# try:
#     from app.services.api_setting.service import ApiSettingService  # type: ignore
# except Exception:
#     ApiSettingService = None  # type: ignore
ApiSettingService = None

class _BatchingEmbeddings(LCEmbeddings):
    """对底层 Embeddings 做客户端分批，兼容第三方端点的批量限制。实现标准 Embeddings 接口。"""
    def __init__(self, base, env_var: str = "OPENAI_EMBEDDING_BATCH_SIZE", default_batch: int = 64, normalize_output: bool = False):
        self._base = base
        self._normalize = bool(normalize_output)
        try:
            bs = int(os.getenv(env_var, str(default_batch)))
            if bs <= 0:
                bs = default_batch
        except Exception:
            bs = default_batch
        self._batch_size = bs

    @property
    def model(self):
        # 透明暴露可能被上层读取的属性
        return getattr(self._base, 'model', None)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        out: List[List[float]] = []
        bs = max(1, int(self._batch_size))
        for i in range(0, len(texts), bs):
            chunk = texts[i:i+bs]
            vecs = self._base.embed_documents(chunk)
            if vecs:
                if self._normalize:
                    vecs = [self._unit(v) for v in vecs]
                out.extend(vecs)
        return out

    def embed_query(self, text: str) -> List[float]:
        v = self._base.embed_query(text)
        return self._unit(v) if self._normalize else v

    def _unit(self, v: List[float]) -> List[float]:
        try:
            import math
            n = math.sqrt(sum(x*x for x in v))
            if n > 0:
                return [x / n for x in v]
        except Exception:
            pass
        return v

class EmbeddingService:
    """向量化存储服务"""
    
    def __init__(self, model_name: str = "BAAI/bge-m3", 
                 use_openai: bool = False, openai_api_key: Optional[str] = None,
                 user_id: int | None = None):
        """
        初始化embedding服务
        
        Args:
            model_name: HuggingFace模型名称
            use_openai: 是否使用OpenAI embeddings
            openai_api_key: OpenAI API密钥
        """
        # PGVector 连接配置
        self.connection_string = (
            os.getenv("PGVECTOR_CONNECTION_STRING")
            or Config.SQLALCHEMY_DATABASE_URI
        )
        self.default_collection = os.getenv("PGVECTOR_COLLECTION", "default_collection")

        # 根据环境变量自动选择提供方，默认使用 HuggingFace
        provider = os.getenv("EMBEDDING_PROVIDER", "huggingface").strip().lower()
        self.use_openai = use_openai or provider in ("openai", "openai_compatible")
        # 标记当前 embedding 是否已做 L2 归一化（影响相似度映射）
        self.is_normalized = False

        if self.use_openai:
            # 优先读取显式传入的 key，否则从环境读取
            effective_api_key = openai_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LOCAL_KEY")
            openai_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
            # openai_compatible 或者提供了自定义 BASE_URL 时，设置 base_url
            if provider == "openai_compatible":
                base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LOCAL_URL")
            else:
                # 如果显式提供 OPENAI_BASE_URL，也允许 OpenAI 直连时自定义
                base_url = os.getenv("OPENAI_BASE_URL")

            # 尝试用户自定义解析（embedding/openai_compatible）
            if ApiSettingService:
                resolved = ApiSettingService.resolve('embedding', 'openai_compatible', user_id)
                if resolved.get('api_key'):
                    effective_api_key = resolved['api_key']
                if resolved.get('base_url'):
                    base_url = resolved['base_url']
                if resolved.get('model_name'):
                    openai_model = resolved['model_name']

            self.model_name = openai_model
            if base_url:
                self.embeddings = OpenAIEmbeddings(
                    model=openai_model,
                    openai_api_key=effective_api_key,
                    base_url=base_url,
                    tiktoken_enabled=False,
                )
            else:
                self.embeddings = OpenAIEmbeddings(
                    model=openai_model,
                    openai_api_key=effective_api_key,
                    tiktoken_enabled=False,
                )
            # 对 OpenAI 兼容端点增加客户端归一化，提升相似度稳定性
            # 先分批包装，再在包装内部进行单位化
            self.is_normalized = True
            self.embeddings = _BatchingEmbeddings(self.embeddings, normalize_output=True)
        else:
            # HuggingFace 路径，允许通过环境覆盖模型名
            hf_model = os.getenv("HUGGINGFACE_EMBEDDING_MODEL", model_name)
            self.model_name = hf_model
            # 统一使用归一化后的向量，便于余弦相似度/内积检索稳定
            self.embeddings = HuggingFaceEmbeddings(
                model_name=hf_model,
                encode_kwargs={"normalize_embeddings": True}
            )
            self.is_normalized = True
            # 尝试用户自定义 huggingface 模型名
            if ApiSettingService:
                resolved = ApiSettingService.resolve('embedding', 'huggingface', user_id)
                if resolved.get('model_name') and resolved['model_name'] != hf_model:
                    self.model_name = resolved['model_name']
                    self.embeddings = HuggingFaceEmbeddings(
                        model_name=self.model_name,
                        encode_kwargs={"normalize_embeddings": True}
                    )

        # 文档切分器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            length_function=len,
        )

    # 代理底层 embeddings 的 query/doc 接口，供 RAGService / ES 查询统一调用
    def embed_query(self, text: str) -> List[float]:  # type: ignore
        try:
            return self.embeddings.embed_query(text)
        except Exception as e:
            logger.error(f"embed_query failed: {e}")
            raise

    def embed_documents(self, texts: List[str]) -> List[List[float]]:  # type: ignore
        if not texts:
            return []
        try:
            return self.embeddings.embed_documents(texts)
        except Exception as e:
            logger.error(f"embed_documents failed: {e}")
            raise

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        切分文档为小块
        
        Args:
            documents: 原始文档列表
            
        Returns:
            切分后的文档块列表
        """
        try:
            return self.text_splitter.split_documents(documents)
        except Exception as e:
            logger.error(f"Error splitting documents: {str(e)}")
            raise
    
    def create_vector_store(self, documents: List[Document], 
                           vector_store_path: Optional[str] = None) -> PGVector:
        """
        创建向量存储 (PGVector)
        
        Args:
            documents: 文档列表
            vector_store_path: (已废弃，保留兼容) 集合名称或路径
            
        Returns:
            PGVector向量存储对象
        """
        try:
            # 过滤空白文档
            clean_docs = [d for d in documents if (getattr(d, 'page_content', None) or '').strip()]
            if not clean_docs:
                raise ValueError("No non-empty documents to index")
            
            # 使用 vector_store_path 作为 collection_name，如果未提供则使用默认
            collection_name = (
                os.path.basename(vector_store_path)
                if vector_store_path
                else self.default_collection
            )
            
            vector_store = PGVector.from_documents(
                embedding=self.embeddings,
                documents=clean_docs,
                collection_name=collection_name,
                connection_string=self.connection_string,
            )
            
            logger.info(f"Vector store created in PGVector collection: {collection_name}")
            return vector_store
            
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise

    def add_documents(self, documents: List[Document], vector_store_path: Optional[str] = None) -> PGVector:
        """
        添加文档到向量库 (兼容旧接口)
        """
        return self.upsert_documents(documents, vector_store_path or self.default_collection)

    def upsert_documents(self, documents: List[Document], vector_store_path: str) -> PGVector:
        """
        将文档增量写入 PGVector
        """
        try:
            # 过滤空白文档
            documents = [d for d in documents if (getattr(d, 'page_content', None) or '').strip()]
            if not documents:
                raise ValueError("No non-empty documents to upsert")
            
            collection_name = (
                os.path.basename(vector_store_path)
                if vector_store_path
                else self.default_collection
            )
            
            # PGVector.from_documents 会自动处理增量添加（如果 collection 已存在）
            vector_store = PGVector.from_documents(
                embedding=self.embeddings,
                documents=documents,
                collection_name=collection_name,
                connection_string=self.connection_string,
            )
            
            logger.info(f"Vector store upserted to PGVector collection: {collection_name} (added {len(documents)} docs)")
            return vector_store
        except Exception as e:
            logger.error(f"Error upserting documents: {str(e)}")
            raise
    
    def load_vector_store(self, vector_store_path: str) -> PGVector:
        """
        加载已存在的向量存储 (PGVector)
        
        Args:
            vector_store_path: 集合名称或路径
            
        Returns:
            PGVector向量存储对象
        """
        try:
            collection_name = (
                os.path.basename(vector_store_path)
                if vector_store_path
                else self.default_collection
            )
            
            vector_store = PGVector(
                collection_name=collection_name,
                connection_string=self.connection_string,
                embedding_function=self.embeddings,
            )
            
            logger.info(f"Vector store loaded from PGVector collection: {collection_name}")
            return vector_store
            
        except Exception as e:
            logger.error(f"Error loading vector store: {str(e)}")
            raise
    
    def search_documents(self, vector_store: PGVector, query: str, 
                        top_k: int = 3) -> List[Document]:
        """
        搜索相关文档
        
        Args:
            vector_store: PGVector向量存储对象
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            相关文档列表
        """
        try:
            results = vector_store.similarity_search(query, k=top_k)
            return results
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            raise

    def update_text_splitter_config(self, chunk_size: int, chunk_overlap: int):
        """动态更新切分器配置（用于单次请求覆盖）。"""
        self.text_splitter.chunk_size = chunk_size
        self.text_splitter.chunk_overlap = chunk_overlap

    def get_embeddings_model_info(self):
        """返回当前模型信息（用于前端展示或默认值）。"""
        return {
            'model_name': getattr(self, 'model_name', 'unknown'),
            'chunk_size': self.text_splitter.chunk_size,
            'chunk_overlap': self.text_splitter.chunk_overlap
        }

    def delete_documents_by_doc_id(self, doc_id: str, vector_store_path: Optional[str] = None):
        """
        根据 doc_id 删除向量
        """
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(self.connection_string)
            
            collection_name = (
                os.path.basename(vector_store_path)
                if vector_store_path
                else self.default_collection
            )
            
            with engine.connect() as conn:
                # 1. Get collection_uuid
                result = conn.execute(text("SELECT uuid FROM kg_pg_collection WHERE name = :name"), {"name": collection_name})
                row = result.fetchone()
                if not row:
                    return
                collection_uuid = row[0]
                
                # 2. Delete embeddings
                # Note: cmetadata is usually a jsonb column
                conn.execute(
                    text("DELETE FROM kg_pg_embedding WHERE collection_id = :coll_id AND cmetadata ->> 'doc_id' = :doc_id"),
                    {"coll_id": collection_uuid, "doc_id": str(doc_id)}
                )
                conn.commit()
                logger.info(f"Deleted vectors for doc_id {doc_id} from collection {collection_name}")
                
        except Exception as e:
            logger.error(f"Error deleting documents by doc_id: {str(e)}")
            # Don't raise, just log, to allow DB deletion to proceed

def get_embedding_model():
    """获取全局默认的 embedding 模型实例"""
    service = EmbeddingService()
    return service.embeddings

