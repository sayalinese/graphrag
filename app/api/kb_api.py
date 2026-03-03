from flask import request, jsonify
from . import api_bp
import logging
from datetime import datetime, timezone

import jwt

logger = logging.getLogger(__name__)


@api_bp.route('/rag/config', methods=['GET'])
def rag_get_config():
    """获取 RAG 配置"""
    try:
        from app.services.rag_service import rag_service
        cfg = rag_service.config
        return jsonify({
            'code': 0,
            'data': {
                'config': {
                    'top_k': cfg.top_k,
                    'threshold': cfg.threshold,
                    'max_citations': cfg.max_citations,
                    'enable_rerank': getattr(cfg, 'enable_rerank', False),
                    'rerank_top_k': getattr(cfg, 'rerank_top_k', cfg.top_k),
                }
            },
            'message': 'success'
        })
    except Exception as e:
        logger.error(f"RAG config get error: {e}")
        return jsonify({'code': 400, 'message': str(e)}), 400


@api_bp.route('/rag/status', methods=['GET'])
def rag_status():
    """获取 RAG 服务状态"""
    try:
        from app.services.rag_service import rag_service
        status = rag_service.get_status()
        return jsonify({
            'code': 0,
            'data': status,
            'message': 'success'
        })
    except Exception as e:
        logger.error(f"RAG status error: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@api_bp.route('/rag/config', methods=['POST'])
def rag_update_config():
    """更新 RAG 配置"""
    try:
        from app.services.rag_service import rag_service, RAGConfig
        from app.config import Config
        
        data = request.get_json(silent=True) or {}
        # 兼容前端 axios 传 { data: {...} } 的包裹写法
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], dict):
            data = data['data']
        old = rag_service.config
        new_cfg = RAGConfig(
            top_k=int(data.get('top_k', old.top_k)),
            threshold=float(data.get('threshold', old.threshold)),
            max_citations=int(data.get('max_citations', old.max_citations)),
            enable_rerank=bool(data.get('enable_rerank', getattr(old, 'enable_rerank', False))),
            rerank_top_k=int(data.get('rerank_top_k', getattr(old, 'rerank_top_k', old.top_k))),
        )
        rag_service.update_config(new_cfg)
        return jsonify({'code': 0, 'message': 'success'})
    except Exception as e:
        logger.error(f"Update RAG config error: {e}")
        return jsonify({'code': 400, 'message': str(e)}), 400


@api_bp.route('/rag/query', methods=['POST'])
def rag_query():
    """执行 RAG 知识库查询"""
    try:
        from app.services.rag_service import rag_service
        from app.config import Config
        
        data = request.get_json(silent=True) or {}
        # 兼容前端 axios 传 { data: {...} }
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], dict):
            data = data['data']
        kb_id = int(data.get('kb_id'))
        query = str(data.get('query', '')).strip()
        if not kb_id or not query:
            return jsonify({'code': 400, 'message': 'kb_id and query are required'}), 400
        # 可选解析 user_id（Bearer JWT）
        user_id = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            try:
                payload = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"], options={"verify_exp": True})
                sub = payload.get('sub') or {}
                if isinstance(sub, dict) and sub.get('kind') in ('user','admin'):
                    user_id = sub.get('user_id')
            except Exception:
                user_id = None
        result = rag_service.query_knowledge_base(kb_id, query, user_id=user_id)
        # 附带调试信息：实际使用的 user_id
        result['effective_user_id'] = user_id
        return jsonify({
            'code': 0,
            'data': result,
            'message': 'success'
        })
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return jsonify({'code': 400, 'message': str(e)}), 400
