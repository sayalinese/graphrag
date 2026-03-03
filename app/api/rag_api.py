"""
RAG 查询 API 端点
"""

import logging
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

# 创建蓝图
rag_bp = Blueprint('rag', __name__, url_prefix='/api/rag')


def get_rag_service():
    """获取或创建 RAG 服务"""
    if not hasattr(current_app, 'rag_service'):
        from app.services.rag_service import RAGService
        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        current_app.rag_service = RAGService(mode='graphrag', deepseek_api_key=api_key)
    return current_app.rag_service


# ==================== 查询接口 ====================

@rag_bp.route('/query', methods=['POST'])
def rag_query():
    """执行 RAG 查询"""
    try:
        data = request.json
        query_text = data.get('query', '')
        mode = data.get('mode', 'graphrag')
        top_k = data.get('top_k', 5)
        
        if not query_text:
            return jsonify({"success": False, "error": "查询文本不能为空"}), 400
        
        rag_service = get_rag_service()
        
        # 切换模式
        if mode != rag_service.mode:
            rag_service.switch_mode(mode)
        
        # 执行查询
        result = rag_service.query(query_text, top_k=top_k)
        
        return jsonify({
            "success": True,
            "data": {
                "query": query_text,
                "mode": rag_service.mode,
                "results": result,
                "top_k": top_k
            }
        })
    except Exception as e:
        logger.error(f"RAG 查询失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 模式管理 ====================

@rag_bp.route('/modes', methods=['GET'])
def list_modes():
    """获取支持的查询模式"""
    try:
        modes = [
            {
                "name": "graphrag",
                "description": "基于知识图谱的检索增强生成",
                "enabled": True
            },
            {
                "name": "vector",
                "description": "基于向量相似度的检索增强生成",
                "enabled": False
            }
        ]
        return jsonify({"success": True, "data": modes})
    except Exception as e:
        logger.error(f"获取模式列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/mode', methods=['GET'])
def get_current_mode():
    """获取当前查询模式"""
    try:
        rag_service = get_rag_service()
        return jsonify({
            "success": True,
            "data": {
                "mode": rag_service.mode,
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"获取当前模式失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/mode', methods=['POST'])
def set_mode():
    """切换查询模式"""
    try:
        data = request.json
        mode = data.get('mode', 'graphrag')
        
        if mode not in ['graphrag', 'vector']:
            return jsonify({
                "success": False,
                "error": f"不支持的模式: {mode}"
            }), 400
        
        rag_service = get_rag_service()
        rag_service.switch_mode(mode)
        
        return jsonify({
            "success": True,
            "data": {
                "mode": rag_service.mode,
                "message": f"已切换至 {mode} 模式"
            }
        })
    except Exception as e:
        logger.error(f"切换模式失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 知识库管理 ====================

@rag_bp.route('/knowledge-base/stats', methods=['GET'])
def kb_stats():
    """获取知识库统计"""
    try:
        rag_service = get_rag_service()
        stats = rag_service.get_graph_stats()
        
        return jsonify({
            "success": True,
            "data": {
                "stats": stats,
                "mode": rag_service.mode,
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"获取知识库统计失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/knowledge-base/ingest', methods=['POST'])
def ingest_document():
    """向知识库添加文档"""
    try:
        data = request.json
        text = data.get('text', '')
        doc_id = data.get('document_id', '')
        doc_title = data.get('document_title', '')
        
        if not text:
            return jsonify({"success": False, "error": "文本不能为空"}), 400
        
        rag_service = get_rag_service()
        result = rag_service.build_from_text(text, doc_id, doc_title)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result,
            "message": f"已处理文档: {doc_title or doc_id}"
        })
    except Exception as e:
        logger.error(f"文档入库失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 调试接口 ====================

@rag_bp.route('/debug/config', methods=['GET'])
def get_config():
    """获取调试配置信息（仅开发环境）"""
    try:
        if not current_app.debug:
            return jsonify({"success": False, "error": "仅在开发环境可用"}), 403
        
        config = {
            "neo4j_uri": current_app.config.get('NEO4J_URI', 'N/A'),
            "deepseek_model": current_app.config.get('DEEPSEEK_MODEL', 'N/A'),
            "deepseek_api_base": current_app.config.get('DEEPSEEK_API_BASE', 'N/A'),
            "debug": current_app.debug
        }
        
        return jsonify({"success": True, "data": config})
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/debug/health', methods=['GET'])
def health_check():
    """健康检查"""
    try:
        from app.extensions import get_neo4j_driver
        from app.utils.llm_utils import DeepSeekLLM
        
        # 检查 Neo4j 连接
        neo4j_ok = False
        try:
            driver = get_neo4j_driver()
            if driver:
                neo4j_ok = True
        except:
            neo4j_ok = False
        
        # 检查 LLM 配置
        llm_ok = False
        try:
            llm = DeepSeekLLM(
                api_key=current_app.config.get('DEEPSEEK_API_KEY'),
                model=current_app.config.get('DEEPSEEK_MODEL')
            )
            llm_ok = True
        except:
            llm_ok = False
        
        status = "healthy" if (neo4j_ok and llm_ok) else "degraded"
        
        return jsonify({
            "success": True,
            "status": status,
            "data": {
                "neo4j": "connected" if neo4j_ok else "disconnected",
                "llm": "available" if llm_ok else "unavailable",
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return jsonify({
            "success": False,
            "status": "error",
            "error": str(e)
        }), 500
