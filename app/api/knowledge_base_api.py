"""
Knowledge Base (KB) API 路由
对接前端的知识库管理功能
"""

from flask import request, jsonify, current_app
from datetime import datetime, timezone
from pathlib import Path
import logging
import uuid
import os

from . import bp
from app.models import KnowledgeBase, Document
from app.extensions import db
from app.services.doc_magene import DocumentManager

logger = logging.getLogger(__name__)


def find_kb(kb_id):
    """Helper to find KB by ID (int) or UUID string"""
    if str(kb_id).isdigit():
        return KnowledgeBase.query.filter_by(id=int(kb_id)).first()
    try:
        uuid_val = uuid.UUID(str(kb_id))
        return KnowledgeBase.query.filter_by(kb_id=uuid_val).first()
    except ValueError:
        return None


# ============ 知识库 CRUD ============


@bp.route('/kb/list', methods=['GET'])
def list_knowledge_bases():
    """列出知识库"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        user_id = request.args.get('user_id', type=int)

        query = KnowledgeBase.query
        if user_id:
            query = query.filter_by(user_id=user_id)

        total = query.count()
        kbs = query.order_by(KnowledgeBase.created_at.desc()).limit(limit).offset(offset).all()

        return jsonify({
            'code': 0,
            'data': {
                'knowledge_bases': [kb.to_dict() for kb in kbs],
                'total': total
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error listing knowledge bases: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/create', methods=['POST'])
def create_knowledge_base():
    """创建知识库"""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        description = data.get('description', '')
        user_id = data.get('user_id')

        if not name:
            return jsonify({'code': 400, 'message': '知识库名称不能为空'}), 400

        kb = KnowledgeBase(
            name=name,
            description=description,
            user_id=user_id
        )

        db.session.add(kb)
        db.session.commit()

        return jsonify({
            'code': 0,
            'data': {
                'knowledge_base': kb.to_dict()
            },
            'message': 'success'
        }), 201

    except Exception as e:
        logger.error(f"Error creating knowledge base: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>', methods=['GET'])
def get_knowledge_base(kb_id):
    """获取知识库详情"""
    try:
        kb = find_kb(kb_id)

        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404

        kb_dict = kb.to_dict()
        kb_dict['documents'] = [doc.to_dict() for doc in kb.documents]

        return jsonify({
            'code': 0,
            'data': {
                'knowledge_base': kb_dict
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error getting knowledge base: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>', methods=['PUT'])
def update_knowledge_base(kb_id):
    """更新知识库"""
    try:
        kb = find_kb(kb_id)

        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404

        data = request.get_json() or {}

        if 'name' in data:
            kb.name = data['name']
        if 'description' in data:
            kb.description = data['description']

        kb.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            'code': 0,
            'data': {
                'knowledge_base': kb.to_dict()
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error updating knowledge base: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>', methods=['DELETE'])
def delete_knowledge_base(kb_id):
    """删除知识库"""
    try:
        kb = find_kb(kb_id)

        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404

        db.session.delete(kb)
        db.session.commit()

        return jsonify({'code': 0, 'message': 'success'}), 200

    except Exception as e:
        logger.error(f"Error deleting knowledge base: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'message': str(e)}), 500


# ============ 文档管理 ============


@bp.route('/kb/<kb_id>/upload', methods=['POST'])
def upload_document(kb_id):
    """上传文档到知识库"""
    try:
        kb = find_kb(kb_id)

        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404

        if 'file' not in request.files:
            return jsonify({'code': 400, 'message': '没有上传文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'code': 400, 'message': '文件名不能为空'}), 400

        # 获取切分参数
        split_mode = request.form.get('split_mode', 'smart')
        chunk_size = int(request.form.get('chunk_size', 500))
        overlap = int(request.form.get('overlap', 50))

        # 生成安全的文件名
        original_filename = file.filename
        file_ext = Path(original_filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"

        upload_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'uploads/kb'))
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / unique_filename

        file.save(str(file_path))

        # 使用 DocumentManager 处理文档
        manager = DocumentManager()
        doc = manager.add_document(
            kb_id=str(kb.kb_id),
            file_path=str(file_path),
            filename=original_filename,
            split_mode=split_mode,
            chunk_size=chunk_size,
            overlap=overlap
        )

        return jsonify({
            'code': 0,
            'data': {
                'document': doc.to_dict()
            },
            'message': 'success'
        }), 201

    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/documents/preview', methods=['POST'])
def preview_document_split():
    """预览文档切分结果"""
    try:
        if 'file' not in request.files:
            return jsonify({'code': 400, 'message': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'code': 400, 'message': '文件名不能为空'}), 400

        # 获取切分参数
        split_mode = request.form.get('split_mode', 'smart')
        chunk_size = int(request.form.get('chunk_size', 500))
        overlap = int(request.form.get('overlap', 50))

        # 保存临时文件
        original_filename = file.filename
        file_ext = Path(original_filename).suffix
        unique_filename = f"preview_{uuid.uuid4()}{file_ext}"
        
        temp_dir = Path(current_app.config.get('UPLOAD_FOLDER', 'uploads/temp'))
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / unique_filename
        
        file.save(str(file_path))

        try:
            manager = DocumentManager()
            chunks = manager.preview_split(
                file_path=str(file_path),
                split_mode=split_mode,
                chunk_size=chunk_size,
                overlap=overlap
            )
            
            return jsonify({
                'code': 0,
                'data': {
                    'chunks': chunks,
                    'total_count': len(chunks)
                },
                'message': 'success'
            }), 200
        finally:
            # 清理临时文件
            if file_path.exists():
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Error previewing document split: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/document/<doc_id>/chunks', methods=['GET'])
def get_document_chunks(doc_id):
    """获取文档切片列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        manager = DocumentManager()
        result = manager.get_chunks(doc_id, page, per_page)
        
        return jsonify({
            'code': 0,
            'data': result,
            'message': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>/document/<doc_id>/content', methods=['GET'])
def get_document_content(kb_id, doc_id):
    """获取已上传文档的原文内容（返回 JSON 格式文本内容）"""
    try:
        # 1. 查找知识库（兼容 int ID 或 UUID string）
        kb = find_kb(kb_id)
        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404
        
        # 2. 找到文档记录（用正确的 UUID）
        doc = Document.query.filter_by(kb_id=kb.kb_id, doc_id=doc_id).first()
        if not doc:
            return jsonify({'code': 404, 'message': '文档不存在'}), 404
        
        if not doc.file_path or not os.path.exists(doc.file_path):
            return jsonify({'code': 404, 'message': '原文文件已删除'}), 404
        
        # 3. 直接读取原始文件内容（不经过任何处理）
        file_path = doc.file_path
        
        # 路径修正：如果直接访问找不到文件，尝试相对于项目根目录查找
        if not os.path.exists(file_path):
            project_root = os.path.dirname(current_app.root_path)
            possible_path = os.path.join(project_root, file_path)
            if os.path.exists(possible_path):
                file_path = possible_path
            else:
                # 尝试绝对路径拼接
                # 假设 file_path 是相对路径，如 uploads/kb/xxx
                # 尝试拼接 current_app.root_path (app/)
                possible_path_app = os.path.join(current_app.root_path, file_path)
                if os.path.exists(possible_path_app):
                    file_path = possible_path_app
        
        if not os.path.exists(file_path):
             return jsonify({'code': 404, 'message': f'文件未找到: {doc.file_path}'}), 404

        ext = os.path.splitext(file_path)[-1].lower()
        
        # 为常见文本格式直接读取
        if ext in ['.txt', '.md', '.markdown']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # 尝试 GBK 编码（解决中文乱码问题）
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                except Exception:
                    # 最后尝试忽略错误
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
        elif ext in ['.docx']:
            # 使用 python-docx 读取 Word 文档的原始文本
            try:
                from docx import Document as DocxDocument
                docx_doc = DocxDocument(file_path)
                # 提取所有段落
                paragraphs = []
                for p in docx_doc.paragraphs:
                    # 直接获取文本，python-docx 自动处理编码
                    text = p.text
                    if text.strip():
                        paragraphs.append(text)
                content = '\n'.join(paragraphs)
                if not content.strip():
                    content = '[Word 文档为空]'
            except ImportError:
                logger.warning("python-docx not installed, falling back to file path only")
                content = f"[文档文件]: {doc.filename}"
            except Exception as e:
                logger.warning(f"Error reading DOCX: {e}")
                content = f"[无法读取 Word 文档]: {str(e)}"
        elif ext in ['.pdf']:
            # 对于 PDF，使用 pypdf 提取文本内容
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                # 提取所有页面的文本
                pages_text = []
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    if text:
                        pages_text.append(f"--- 第 {page_num} 页 ---\n{text}")
                content = '\n\n'.join(pages_text)
                if not content.strip():
                    content = f"[PDF 文件为空或无法提取文本]: {doc.filename}"
            except ImportError:
                logger.warning("pypdf not installed, using placeholder")
                content = f"[PDF 文件] {doc.filename} - 需要安装 pypdf 来提取文本"
            except Exception as e:
                logger.warning(f"Error extracting PDF text: {e}")
                content = f"[无法提取 PDF 内容]: {str(e)}"
        else:
            # 其他格式尝试通用文本读取（UTF-8）
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception as e:
                logger.warning(f"Cannot read file as text: {e}")
                content = f"[无法读取内容]: {doc.filename}"
        
        if not content or not content.strip():
            return jsonify({
                'code': 400, 
                'message': '无法读取文件内容或文件为空'
            }), 400
        
        return jsonify({
            'code': 0,
            'data': {
                'content': content
            },
            'message': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting document content: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>/document/<doc_id>/file', methods=['GET'])
def get_document_file(kb_id, doc_id):
    """获取已上传文档的原始文件（二进制返回，用于 PDF 等直接显示）"""
    try:
        from flask import send_file
        
        # 1. 查找知识库（兼容 int ID 或 UUID string）
        kb = find_kb(kb_id)
        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404
        
        # 2. 找到文档记录（用正确的 UUID）
        doc = Document.query.filter_by(kb_id=kb.kb_id, doc_id=doc_id).first()
        if not doc:
            return jsonify({'code': 404, 'message': '文档不存在'}), 404
        
        file_path = doc.file_path
        
        # 调试日志
        logger.info(f"Original file_path: {file_path}")
        logger.info(f"CWD: {os.getcwd()}")
        logger.info(f"App Root: {current_app.root_path}")
        
        # 路径修正逻辑
        final_path = None
        
        # 1. 尝试直接访问（绝对路径或相对于 CWD）
        if file_path and os.path.exists(file_path):
            final_path = file_path
        
        # 2. 尝试相对于项目根目录 (假设 CWD 是项目根目录，或者 file_path 是相对于项目根目录的)
        if not final_path and file_path:
            # 获取项目根目录 (假设 app/../)
            project_root = os.path.dirname(current_app.root_path)
            possible_path = os.path.join(project_root, file_path)
            if os.path.exists(possible_path):
                final_path = possible_path
        
        # 3. 尝试相对于 app 目录
        if not final_path and file_path:
            possible_path = os.path.join(current_app.root_path, file_path)
            if os.path.exists(possible_path):
                final_path = possible_path
                
        # 4. 尝试硬编码的 uploads 目录修正 (处理可能的路径前缀重复)
        if not final_path and file_path:
            # 如果 file_path 包含 uploads/kb，尝试直接在项目根目录下找 uploads/kb
            if 'uploads' in file_path:
                # 提取 uploads 之后的部分
                part = file_path[file_path.find('uploads'):]
                project_root = os.path.dirname(current_app.root_path)
                possible_path = os.path.join(project_root, part)
                if os.path.exists(possible_path):
                    final_path = possible_path

        if not final_path:
            logger.error(f"File not found: {doc.file_path}")
            return jsonify({'code': 404, 'message': f'文件未找到: {doc.file_path}'}), 404
            
        # 转换为绝对路径，避免 send_file 问题
        final_path = os.path.abspath(final_path)
        logger.info(f"Serving file: {final_path}")
        
        # 3. 返回文件
        # 确定 MIME type
        mimetype = 'application/octet-stream'
        if doc.file_type == 'pdf':
            mimetype = 'application/pdf'
        elif doc.file_type == 'docx':
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif doc.file_type == 'xlsx':
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif doc.file_type == 'xls':
            mimetype = 'application/vnd.ms-excel'
            
        return send_file(
            final_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=doc.filename
        )
        
    except Exception as e:
        logger.error(f"Error getting document file: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/document/<doc_id>/dedupe', methods=['POST'])
def deduplicate_document(doc_id):
    """文档切片去重"""
    try:
        manager = DocumentManager()
        result = manager.deduplicate_chunks(doc_id)
        
        return jsonify({
            'code': 0,
            'data': result,
            'message': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error deduplicating document: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>/stats', methods=['GET'])
def kb_stats(kb_id):
    """获取知识库统计信息"""
    try:
        kb = find_kb(kb_id)

        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404

        docs = kb.documents
        total_chunks = sum(doc.chunk_count for doc in docs)

        return jsonify({
            'code': 0,
            'data': {
                'stats': {
                    'kb_id': str(kb.kb_id),
                    'name': kb.name,
                    'document_count': len(docs),
                    'total_chunks': total_chunks,
                    'completed_docs': len([d for d in docs if d.status == 'completed']),
                    'processing_docs': len([d for d in docs if d.status == 'processing']),
                    'failed_docs': len([d for d in docs if d.status == 'failed']),
                }
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error getting KB stats: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>/documents', methods=['GET'])
def list_documents(kb_id):
    """获取知识库文档列表"""
    try:
        kb = find_kb(kb_id)
        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404

        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        query = Document.query.filter_by(kb_id=kb.kb_id)
        total = query.count()
        docs = query.order_by(Document.created_at.desc()).limit(limit).offset(offset).all()
        
        return jsonify({
            'code': 0,
            'data': {
                'items': [doc.to_dict() for doc in docs],
                'total': total,
                'limit': limit,
                'offset': offset
            },
            'message': 'success'
        })
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/kb/<kb_id>/document/<doc_id>', methods=['DELETE'])
def delete_document(kb_id, doc_id):
    """删除文档"""
    try:
        kb = find_kb(kb_id)
        if not kb:
            return jsonify({'code': 404, 'message': '知识库不存在'}), 404

        manager = DocumentManager()
        # 验证文档是否属于该知识库
        doc = manager.get_document(doc_id)
        if not doc:
            return jsonify({'code': 404, 'message': '文档不存在'}), 404
        
        if str(doc.kb_id) != str(kb.kb_id):
            return jsonify({'code': 400, 'message': '文档不属于该知识库'}), 400

        success = manager.delete_document(doc_id)
        if success:
            return jsonify({'code': 0, 'message': 'success'}), 200
        else:
            return jsonify({'code': 500, 'message': '删除失败'}), 500

    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500
