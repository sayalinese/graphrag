"""
RAG Search 模块初始化
"""

from flask import Blueprint

# 创建蓝图
bp = Blueprint('rag_search', __name__, url_prefix='/api/rag')
rag_search_bp = bp

# 导入 API 路由
from . import search_api  # noqa: F401, E402
