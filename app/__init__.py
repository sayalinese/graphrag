from flask import Flask, request
import os
from dotenv import load_dotenv

# Load .env from project root into environment so Config can read values
# This avoids hardcoding secrets in source while making .env values available at runtime
root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv(root_env)
from .config import Config
from .extensions import db, migrate, init_cors, init_neo4j, close_neo4j
from .services.async_tasks import init_task_queue, shutdown_task_queue
import atexit
import os
import logging
from app.services.neo.graphrag_service import GraphRAGService

from .api import bp as api_bp
from .services.auth import bp as auth_bp
from .services.user import bp as user_bp
from .services.upload import bp as upload_bp
from .api.kg_api import kg_bp
from .services.rag.rag_search import rag_search_bp

# 应用工厂，让run.py更简洁
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)
    
    @app.before_request
    def log_request_info():
        app.logger.info(f"Request: {request.method} {request.url}")
        app.logger.info(f"Origin: {request.headers.get('Origin')}")

    # 初始化异步任务队列
    init_task_queue(max_workers=2)

    # 初始化 PostgreSQL
    db.init_app(app)
    migrate.init_app(app, db)
    
    # 初始化 Neo4j
    init_neo4j(app)
    # 初始化 GraphRAG 服务（Neo4j + pgvector + 本地 embed + DeepSeek LLM）
    try:
        pg_conn = app.config.get('SQLALCHEMY_DATABASE_URI')
        pg_collection = os.getenv('PGVECTOR_COLLECTION', 'graphrag_collection')
        app.graphrag_service = GraphRAGService(
            neo_uri=app.config.get('NEO4J_URI'),
            neo_user=app.config.get('NEO4J_USERNAME'),
            neo_pwd=app.config.get('NEO4J_PASSWORD'),
            pg_conn=pg_conn,
            pg_collection=pg_collection,
            embed_model_name=os.getenv('EMBED_MODEL', 'all-MiniLM-L6-v2'),
            deepseek_api_key=app.config.get('DEEPSEEK_API_KEY', ''),
            deepseek_model=app.config.get('DEEPSEEK_MODEL', 'deepseek-chat'),
            deepseek_api_base=app.config.get('DEEPSEEK_API_BASE', 'https://api.deepseek.com/v1'),
        )
        atexit.register(lambda: getattr(app, 'graphrag_service', None) and app.graphrag_service.close())
    except Exception as e:
        app.logger.warning(f"初始化 GraphRAGService 失败: {e}")
    
    init_cors(app)

    # 注册蓝图
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(kg_bp, url_prefix='/api/kg')
    app.register_blueprint(rag_search_bp)
    
    # 重要: 不要在每个请求 teardown 时关闭 Neo4j 驱动，否则后续请求都会出现 defunct connection
    # 使用 atexit 注册在进程结束时关闭即可，避免频繁 close 导致连接失效
    atexit.register(close_neo4j)
    atexit.register(shutdown_task_queue)
    
    return app
