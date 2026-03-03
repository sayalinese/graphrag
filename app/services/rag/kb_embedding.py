import os
import logging
from typing import List, Optional
from pathlib import Path

# 避免 transformers 在加载 sentence_transformers 时拉起 TensorFlow/Keras 依赖
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

from langchain_core.documents import Document

# langchain_text_splitters 依赖 sentence_transformers，并会在导入时触发 transformers -> tensorflow -> keras；
# 在当前环境中会因为 Keras3 与 transformers 不兼容而崩溃。
# 这里做降级：若导入失败则使用 langchain 内置的 RecursiveCharacterTextSplitter。
try:  # pragma: no cover - 仅在依赖完备时执行
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception as exc:  # noqa: BLE001 - 我们需要捕获 ValueError 等任意异常
    logging.getLogger(__name__).warning(
        "langchain_text_splitters 导入失败，使用内置简化切分器: %s", exc
    )

    class RecursiveCharacterTextSplitter:
        """精简版递归文本切分器，仅依赖标准库，保证服务可用。"""

        def __init__(
            self,
            chunk_size: int = 512,
            chunk_overlap: int = 120,
            length_function= len,
            add_start_index: bool = True,
        ):
            self.chunk_size = max(chunk_size, 1)
            self.chunk_overlap = max(min(chunk_overlap, self.chunk_size - 1), 0)
            self.length_function = length_function
            self.add_start_index = add_start_index

        def split_text(self, text: str) -> List[str]:
            payload = text or ""
            total = self.length_function(payload)
            if total <= self.chunk_size:
                return [payload]
            chunks: List[str] = []
            start = 0
            while start < total:
                end = min(total, start + self.chunk_size)
                chunks.append(payload[start:end])
                if end >= total:
                    break
                start = max(0, end - self.chunk_overlap)
            return chunks or [payload]

        def split_documents(self, documents: List[Document]) -> List[Document]:
            results: List[Document] = []
            for doc in documents or []:
                text = getattr(doc, "page_content", "") or ""
                metadata = dict(getattr(doc, "metadata", {}) or {})
                cursor = 0
                for chunk in self.split_text(text):
                    chunk_meta = dict(metadata)
                    if self.add_start_index:
                        chunk_meta.setdefault("start_index", cursor)
                    results.append(Document(page_content=chunk, metadata=chunk_meta))
                    cursor += len(chunk) - self.chunk_overlap
                    if cursor < 0:
                        cursor = 0
            return results
try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:  # pragma: no cover - optional dependency
    HuggingFaceEmbeddings = None  # type: ignore
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings as LCEmbeddings

logger = logging.getLogger(__name__)

try:
    from app.services.api_setting.service import ApiSettingService  # type: ignore
except Exception:
    ApiSettingService = None  # type: ignore


class KBEmbeddingService:
    """向量化存储服务（pgvector）"""
    
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
                )
            else:
                self.embeddings = OpenAIEmbeddings(
                    model=openai_model,
                    openai_api_key=effective_api_key,
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
            self.embeddings = self._build_hf_embeddings(hf_model)
            self.is_normalized = True
            # 尝试用户自定义 huggingface 模型名
            if ApiSettingService:
                resolved = ApiSettingService.resolve('embedding', 'huggingface', user_id)
                if resolved.get('model_name') and resolved['model_name'] != hf_model:
                    self.model_name = resolved['model_name']
                    self.embeddings = self._build_hf_embeddings(self.model_name)

        # 文档切分器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=120,
            length_function=len,
            add_start_index=True,
        )

    def _build_hf_embeddings(self, model_name: str) -> LCEmbeddings:
        """构造 HuggingFace embeddings，若依赖缺失则退化为 no-op 实现。"""
        if HuggingFaceEmbeddings is None:
            logger.warning("sentence-transformers 未安装，使用降级的空 embeddings")
            return _NoOpEmbeddings()
        try:
            return HuggingFaceEmbeddings(
                model_name=model_name,
                encode_kwargs={"normalize_embeddings": True}
            )
        except Exception as exc:
            logger.warning("HuggingFaceEmbeddings 初始化失败，采用空 embeddings: %s", exc)
            return _NoOpEmbeddings()

    # 代理底层 embeddings 的 query/doc 接口，供 RAGService / pgvector 查询统一调用
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
    
    def get_embeddings_model_info(self) -> dict:
        """
        获取embeddings模型信息
        
        Returns:
            模型信息字典
        """
        # 兼容不同版本的TextSplitter属性命名
        chunk_size = getattr(self.text_splitter, 'chunk_size', None)
        if chunk_size is None:
            chunk_size = getattr(self.text_splitter, '_chunk_size', None)
        chunk_overlap = getattr(self.text_splitter, 'chunk_overlap', None)
        if chunk_overlap is None:
            chunk_overlap = getattr(self.text_splitter, '_chunk_overlap', None)

        return {
            'model_name': self.model_name,
            'use_openai': self.use_openai,
            'chunk_size': chunk_size,
            'chunk_overlap': chunk_overlap
        }
    
    def update_text_splitter_config(self, chunk_size: int = 800, chunk_overlap: int = 150):
        """
        更新文本切分配置
        
        Args:
            chunk_size: 块大小
            chunk_overlap: 块重叠大小
        """
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            add_start_index=True,
        )
        logger.info(f"Text splitter config updated: chunk_size={chunk_size}, chunk_overlap={chunk_overlap}") 


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


class _NoOpEmbeddings(LCEmbeddings):
    """在缺少 sentence_transformers 时的兜底实现，返回常量向量。"""

    def __init__(self, dimension: int = 768):
        self._dim = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * self._dim for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.0] * self._dim
