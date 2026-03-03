"""
RAG 检索 API - pgvector 适配版本
支持混合搜索和重排功能
"""

import logging
from flask import request, jsonify
from . import bp  # 假设已在 __init__.py 中定义蓝图

from app.extensions import db
from app.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


def get_search_engine():
    """获取搜索引擎实例"""
    try:
        from app.services.rag.rag_search.pgvector_search import create_search_engine
        
        # 初始化向量模型
        embedding_service = EmbeddingService()
        embedding_model = embedding_service.embeddings
        
        return create_search_engine(db.session, embedding_model=embedding_model)
    except Exception as e:
        logger.error(f"初始化搜索引擎失败: {e}", exc_info=True)
        return None


# ==================== 知识库检索接口 ====================

@bp.route('/search/query_pgvector', methods=['POST'])
def query_pgvector():
    """
    pgvector 混合搜索接口
    
    请求体:
    {
        "kb_id": 1,
        "query": "查询文本",
        "top_k": 10,
        "vector_weight": 0.6,
        "bm25_weight": 0.4,
        "threshold": 0.0,
        "mode": "hybrid"  // "hybrid" | "rerank"
    }
    """
    try:
        data = request.get_json() or {}
        kb_id = data.get('kb_id')
        query_text = data.get('query', '').strip()
        top_k = max(1, min(int(data.get('top_k', 10)), 100))  # 1-100
        mode = data.get('mode', 'hybrid')  # hybrid | rerank
        
        # 参数验证
        if not query_text:
            return jsonify({
                'code': 400,
                'message': '查询文本不能为空'
            }), 400
        
        if not kb_id:
            return jsonify({
                'code': 400,
                'message': '知识库 ID 不能为空'
            }), 400
        
        search_engine = get_search_engine()
        if not search_engine:
            return jsonify({
                'code': 500,
                'message': '搜索引擎初始化失败'
            }), 500
        
        # 执行搜索
        if mode == 'rerank':
            results = search_engine.rerank_search(
                kb_id=kb_id,
                query_text=query_text,
                top_k=top_k,
                rerank_top_k=top_k * 5,
            )
        else:  # hybrid
            vector_weight = float(data.get('vector_weight', 0.6))
            bm25_weight = float(data.get('bm25_weight', 0.4))
            threshold = float(data.get('threshold', 0.0))
            
            results = search_engine.hybrid_search(
                kb_id=kb_id,
                query_text=query_text,
                top_k=top_k,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
                threshold=threshold,
            )
        
        return jsonify({
            'code': 0,
            'data': {
                'results': results,
                'count': len(results),
                'query': query_text,
                'kb_id': kb_id,
                'mode': mode,
                'top_k': top_k,
            },
            'message': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"查询失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': str(e)
        }), 500


@bp.route('/search/hybrid', methods=['POST'])
def search_hybrid():
    """
    统一的混合搜索接口
    兼容聊天模块调用
    
    请求体:
    {
        "kb_id": 1,
        "query": "查询文本",
        "top_k": 5
    }
    """
    try:
        data = request.get_json() or {}
        kb_id = data.get('kb_id')
        query_text = data.get('query', '').strip()
        top_k = max(1, min(int(data.get('top_k', 5)), 50))
        
        if not query_text or not kb_id:
            return jsonify({
                'code': 400,
                'message': '查询文本和知识库 ID 必填'
            }), 400
        
        search_engine = get_search_engine()
        if not search_engine:
            return jsonify({
                'code': 500,
                'message': '搜索引擎初始化失败'
            }), 500
        
        results = search_engine.hybrid_search(
            kb_id=kb_id,
            query_text=query_text,
            top_k=top_k,
            vector_weight=0.6,
            bm25_weight=0.4,
        )
        
        return jsonify({
            'code': 0,
            'data': {
                'results': results,
                'count': len(results),
            },
            'message': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"混合搜索失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e)
        }), 500


@bp.route('/search/vector', methods=['POST'])
def search_vector():
    """向量相似度搜索"""
    try:
        data = request.get_json() or {}
        kb_id = data.get('kb_id')
        query_text = data.get('query', '').strip()
        top_k = max(1, min(int(data.get('top_k', 10)), 100))
        
        if not query_text or not kb_id:
            return jsonify({
                'code': 400,
                'message': '查询文本和知识库 ID 必填'
            }), 400
        
        search_engine = get_search_engine()
        if not search_engine:
            return jsonify({
                'code': 500,
                'message': '搜索引擎初始化失败'
            }), 500
        
        query_vector = search_engine._get_query_embedding(query_text)
        if not query_vector:
            return jsonify({
                'code': 400,
                'message': '无法转换查询文本为向量'
            }), 400
        
        results = search_engine._vector_search(kb_id, query_vector, top_k)
        
        return jsonify({
            'code': 0,
            'data': {
                'results': results,
                'count': len(results),
            },
            'message': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"向量搜索失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e)
        }), 500


@bp.route('/search/bm25', methods=['POST'])
def search_bm25():
    """BM25 全文搜索"""
    try:
        data = request.get_json() or {}
        kb_id = data.get('kb_id')
        query_text = data.get('query', '').strip()
        top_k = max(1, min(int(data.get('top_k', 10)), 100))
        
        if not query_text or not kb_id:
            return jsonify({
                'code': 400,
                'message': '查询文本和知识库 ID 必填'
            }), 400
        
        search_engine = get_search_engine()
        if not search_engine:
            return jsonify({
                'code': 500,
                'message': '搜索引擎初始化失败'
            }), 500
        
        results = search_engine._bm25_search(kb_id, query_text, top_k)
        
        return jsonify({
            'code': 0,
            'data': {
                'results': results,
                'count': len(results),
            },
            'message': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"BM25 搜索失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e)
        }), 500


# ==================== 索引维护接口 ====================

@bp.route('/search/rebuild-index', methods=['POST'])
def rebuild_index():
    """
    重建索引接口（当前实现暂不需要索引维护）
    """
    try:
        return jsonify({
            'code': 0,
            'data': {
                'message': '暂未实现（当前使用关键词搜索）'
            },
            'message': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"索引重建失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e)
        }), 500


@bp.route('/search/stats', methods=['GET'])
def search_stats():
    """
    获取搜索引擎统计信息
    """
    try:
        kb_id = request.args.get('kb_id', type=int)
        
        from app.models import DocumentChunk, Document, KnowledgeBase
        
        query = DocumentChunk.query.join(
            Document, DocumentChunk.doc_id == Document.doc_id
        ).join(
            KnowledgeBase, Document.kb_id == KnowledgeBase.kb_id
        )
        if kb_id:
            query = query.filter(KnowledgeBase.id == kb_id)
        
        total_chunks = query.count()
        
        return jsonify({
            'code': 0,
            'data': {
                'total_chunks': total_chunks,
                'kb_id': kb_id,
            },
            'message': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e)
        }), 500
