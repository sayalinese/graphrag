import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from langchain_core.documents import Document as LangChainDocument
from langchain_community.document_loaders import (
    UnstructuredFileLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    PyMuPDFLoader
)

from app.extensions import db
from app.models import KnowledgeBase, Document, DocumentChunk
from app.services.embedding import EmbeddingService
from app.services.splitting import (
    smart_split_md_html,
    smart_split_docx,
    smart_split_pdf,
    smart_split_excel,
    semantic_refine_with_embeddings
)
from app.services.async_tasks import submit_async_task

# 尝试导入 MinerU，如果未配置或未安装则可能不可用
try:
    from app.services.mineru import MinerUClient
except ImportError:
    MinerUClient = None

logger = logging.getLogger(__name__)

class DocumentManager:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    def get_kb_documents(self, kb_id: str) -> List[Dict]:
        """获取知识库下的所有文档"""
        docs = Document.query.filter_by(kb_id=kb_id).order_by(Document.created_at.desc()).all()
        return [d.to_dict() for d in docs]

    def get_document(self, doc_id: str) -> Optional[Document]:
        return Document.query.filter_by(doc_id=doc_id).first()

    def delete_document(self, doc_id: str) -> bool:
        """删除文档及其切片和向量数据"""
        doc = self.get_document(doc_id)
        if not doc:
            return False
        
        # 1. 删除向量库中的数据
        try:
            # 调用 EmbeddingService 删除向量
            # 假设默认 collection 为 default_collection，或者从 kb_id 推断
            # 这里暂时使用默认值，如果您的系统区分 collection，请传入正确的值
            self.embedding_service.delete_documents_by_doc_id(doc_id)
        except Exception as e:
            logger.error(f"Failed to delete vectors for doc {doc_id}: {e}")

        # 2. 删除数据库记录 (级联删除 chunks)
        db.session.delete(doc)
        db.session.commit()
        return True

    def preview_split(self, file_path: str, split_mode: str = 'smart', chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
        """
        预览切分结果，不入库
        """
        # 1. 加载
        docs = self._load_file(file_path)
        if not docs:
            return []

        # 2. 切分
        chunks = self._apply_splitting(docs, file_path, split_mode, chunk_size, overlap)
        if chunks is None:
            return []

        # 3. 格式化返回
        return [
            {
                "content": c.page_content,
                "metadata": c.metadata,
                "length": len(c.page_content)
            }
            for c in chunks
        ]

    def add_document(self, kb_id: str, file_path: str, filename: str, split_mode: str = 'smart', chunk_size: int = 500, overlap: int = 50) -> Document:
        """
        添加文档：加载 -> 切分 -> 存DB(Document+Chunks) -> 异步向量化
        返回 Document 对象，向量化在后台进行
        """
        kb = KnowledgeBase.query.filter_by(kb_id=kb_id).first()
        if not kb:
            raise ValueError(f"Knowledge Base {kb_id} not found")

        file_ext = os.path.splitext(filename)[-1].lower().replace('.', '')
        new_doc = Document(
            kb_id=kb.kb_id,
            filename=filename,
            file_path=file_path,
            file_type=file_ext,
            status='processing'
        )
        db.session.add(new_doc)
        db.session.commit()

        try:
            # 2. 加载与切分（可能抛出异常）
            raw_docs = self._load_file(file_path)
            if raw_docs is None:
                logger.error(f"raw_docs is None for {file_path}")
                raw_docs = []

            chunks = self._apply_splitting(raw_docs, file_path, split_mode, chunk_size, overlap)
            if chunks is None:
                logger.error(f"chunks is None for {file_path}")
                chunks = []

            # 3. 存入 DocumentChunk 表
            db_chunks = []
            for idx, chunk in enumerate(chunks):
                db_chunk = DocumentChunk(
                    doc_id=new_doc.doc_id,
                    content=chunk.page_content,
                    chunk_index=idx,
                    metadata_json=chunk.metadata
                )
                db_chunks.append(db_chunk)
            
            db.session.add_all(db_chunks)
            new_doc.chunk_count = len(chunks)
            new_doc.status = 'indexing'
            db.session.commit()

            # 4. 异步向量化
            doc_id = str(new_doc.doc_id)
            submit_async_task(
                self._async_vectorize_chunks,
                doc_id,
                chunks,
                kb_id
            )

            return new_doc

        except ValueError as e:
            # 转换或加载失败时，记录错误信息
            logger.error(f"File format error for {filename}: {e}")
            new_doc.status = 'failed'
            db.session.commit()
            raise
        except Exception as e:
            logger.error(f"Error processing document {filename}: {e}", exc_info=True)
            new_doc.status = 'failed'
            db.session.commit()
            raise

    def _async_vectorize_chunks(self, doc_id: str, chunks: List[LangChainDocument], kb_id: str):
        """
        后台异步向量化任务（运行在独立线程）
        """
        try:
            # 为每个 chunk 增加 doc_id 关联
            for c in chunks:
                c.metadata['doc_id'] = doc_id
                c.metadata['kb_id'] = str(kb_id)
            
            # 执行向量化并入库
            self.embedding_service.add_documents(chunks)
            
            # 更新文档状态为完成
            doc = Document.query.filter_by(doc_id=doc_id).first()
            if doc:
                doc.status = 'completed'
                db.session.commit()
                logger.info(f"Document {doc_id} vectorization completed")
        except Exception as e:
            logger.error(f"Error vectorizing document {doc_id}: {e}", exc_info=True)
            # 更新文档状态为失败
            try:
                doc = Document.query.filter_by(doc_id=doc_id).first()
                if doc:
                    doc.status = 'failed'
                    db.session.commit()
            except Exception as e2:
                logger.error(f"Failed to update document status: {e2}")

    def _load_file(self, file_path: str) -> List[LangChainDocument]:
        """
        加载文件，自动转换旧格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            LangChainDocument 列表
            
        Raises:
            ValueError: 文件转换或加载失败时抛出详细错误
        """
        ext = os.path.splitext(file_path)[-1].lower()
        
        # .doc 转 .docx
        if ext == '.doc':
            try:
                from app.services.doc_converter import convert_doc_to_docx, temporary_converted_file
                logger.info(f"Converting .doc file to .docx: {file_path}")
                with temporary_converted_file(file_path, convert_doc_to_docx, '.doc', '.docx') as docx_path:
                    return self._load_with_extension(docx_path, '.docx')
            except Exception as e:
                logger.error(f"Failed to convert and load .doc file {file_path}: {e}")
                raise ValueError(f"无法处理 .doc 文件: {str(e)}")
        
        # .xls 转 .xlsx
        if ext == '.xls':
            try:
                from app.services.doc_converter import convert_xls_to_xlsx, temporary_converted_file
                logger.info(f"Converting .xls file to .xlsx: {file_path}")
                with temporary_converted_file(file_path, convert_xls_to_xlsx, '.xls', '.xlsx') as xlsx_path:
                    return self._load_with_extension(xlsx_path, '.xlsx')
            except Exception as e:
                logger.error(f"Failed to convert and load .xls file {file_path}: {e}")
                raise ValueError(f"无法处理 .xls 文件: {str(e)}")
        
        # 直接加载其他格式
        return self._load_with_extension(file_path, ext)

    def _load_with_extension(self, file_path: str, ext: str) -> List[LangChainDocument]:
        """根据扩展名加载文件"""
        try:
            if ext == '.pdf':
                # 优先尝试 MinerU (如果配置了)
                # if MinerUClient and MinerUClient.is_available(): ...
                # 暂时默认用 PyMuPDF
                loader = PyMuPDFLoader(file_path)
            elif ext in ['.docx', '.doc']:
                loader = Docx2txtLoader(file_path)
            elif ext in ['.md', '.markdown']:
                # 使用 TextLoader 保留原始 Markdown 语法，而不是 UnstructuredMarkdownLoader
                loader = TextLoader(file_path, encoding='utf-8')
            elif ext in ['.xlsx', '.xls']:
                # Excel 双写：sheet 级 markdown + 行级记录
                try:
                    import pandas as pd  # type: ignore
                    xls = pd.read_excel(str(file_path), sheet_name=None, dtype=str)
                    docs: List[LangChainDocument] = []
                    def _esc(val: str) -> str:
                        return str(val if val is not None else "").replace("|","\\|").replace("\r"," ").replace("\n"," ").strip()
                    for sheet_name, df in (xls or {}).items():
                        try:
                            if df is None:
                                continue
                            df = df.fillna("")
                            cols_raw_all = list(df.columns)
                            cols_raw = [c for c in cols_raw_all if str(c).strip() and not str(c).strip().lower().startswith('unnamed') and str(c).strip().lower() != 'index']
                            if cols_raw:
                                df = df[cols_raw]
                            cols = [_esc(c) for c in cols_raw]
                            # sheet 级 markdown
                            lines = []
                            if cols:
                                header = "| " + " | ".join(cols) + " |"
                                divider = "| " + " | ".join(["---" for _ in cols]) + " |"
                                lines.append(header)
                                lines.append(divider)
                                for _, row in df.iterrows():
                                    vals = [_esc(row.get(c, "")) for c in cols_raw]
                                    lines.append("| " + " | ".join(vals) + " |")
                            else:
                                lines.append(str(df))
                            sheet_content = "\n".join(lines).strip() + "\n"
                            if sheet_content:
                                md_sheet = {
                                    "source": str(file_path),
                                    "sheet": str(sheet_name),
                                    "h2": str(sheet_name),
                                    "h3": " | ".join(cols) if cols else None,
                                    "start_index": 0,
                                    "chunk_type": "sheet"
                                }
                                docs.append(LangChainDocument(page_content=sheet_content, metadata=md_sheet))
                            # 行级
                            headers_join = " | ".join(cols) if cols else None
                            for ridx, row in df.iterrows():
                                row_vals = [_esc(row.get(c, "")) for c in cols_raw]
                                row_line = " | ".join(row_vals)
                                if not row_line.strip():
                                    continue
                                md_row = {
                                    "source": str(file_path),
                                    "sheet": str(sheet_name),
                                    "h2": str(sheet_name),
                                    "h3": headers_join,
                                    "row_index": int(ridx),
                                    "start_index": int(ridx),
                                    "chunk_type": "row"
                                }
                                docs.append(LangChainDocument(page_content=row_line, metadata=md_row))
                        except Exception:
                            continue
                    if docs:
                        return docs
                except Exception as e:
                    logger.warning(f"Pandas excel load failed: {e}, fallback to UnstructuredExcelLoader")
                
                # Fallback
                from langchain_community.document_loaders import UnstructuredExcelLoader
                loader = UnstructuredExcelLoader(file_path)
                return loader.load()
            else:
                loader = TextLoader(file_path, encoding='utf-8')
            
            return loader.load()

        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            return []


    def _apply_splitting(self, docs: List[LangChainDocument], file_path: str, mode: str, chunk_size: int, overlap: int) -> List[LangChainDocument]:
        """根据模式应用切分策略"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        # 基础递归切分器 (作为 fallback 或 二次切分)
        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
        )

        if mode == 'simple':
            return recursive_splitter.split_documents(docs)

        if mode == 'semantic':
            return semantic_refine_with_embeddings(
                docs,
                self.embedding_service,
                target_chunk_size=chunk_size,
                overlap=overlap
            )
        
        # 智能切分
        ext = os.path.splitext(file_path)[-1].lower()
        res = []
        
        # 注入 source metadata
        for d in docs:
            if 'source' not in d.metadata:
                d.metadata['source'] = file_path

        if ext in ['.md', '.markdown', '.html', '.htm']:
            res = smart_split_md_html(docs, recursive_splitter)
        elif ext == '.docx':
            res = smart_split_docx(docs, recursive_splitter)
        elif ext == '.pdf':
            res = smart_split_pdf(docs, recursive_splitter)
        elif ext in ['.xlsx', '.xls', '.csv']:
            # 需要专门的 Excel loader 配合，这里假设 docs 已经是文本形式
            # 实际可能需要 pandas 读取转为 Document
            res = smart_split_excel(docs, recursive_splitter)
        else:
            res = recursive_splitter.split_documents(docs)

        # 如果智能切分返回空（失败），回退到默认
        if not res and docs:
            res = recursive_splitter.split_documents(docs)
            
        return res

    def get_chunks(self, doc_id: str, page: int = 1, per_page: int = 20) -> Dict:
        """分页获取文档切片"""
        pagination = DocumentChunk.query.filter_by(doc_id=doc_id)\
            .order_by(DocumentChunk.chunk_index)\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': [c.to_dict() for c in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        }

    def deduplicate_chunks(self, doc_id: str) -> Dict:
        """
        文档内去重：计算所有 chunk 的相似度，标记重复内容
        注意：这里仅做演示，简单的完全重复检测。
        语义重复需要 O(N^2) 的向量比对，对于大文档较慢。
        """
        chunks = DocumentChunk.query.filter_by(doc_id=doc_id).order_by(DocumentChunk.chunk_index).all()
        if not chunks:
            return {"removed_count": 0}

        seen_hashes = set()
        to_delete = []
        
        import hashlib
        
        for chunk in chunks:
            # 简单基于内容的 MD5 去重
            content_hash = hashlib.md5(chunk.content.encode('utf-8')).hexdigest()
            if content_hash in seen_hashes:
                to_delete.append(chunk)
            else:
                seen_hashes.add(content_hash)
        
        count = len(to_delete)
        for item in to_delete:
            db.session.delete(item)
        
        if count > 0:
            db.session.commit()
            # 更新文档 chunk_count
            doc = Document.query.filter_by(doc_id=doc_id).first()
            if doc:
                doc.chunk_count = DocumentChunk.query.filter_by(doc_id=doc_id).count()
                db.session.commit()

        return {"removed_count": count}
