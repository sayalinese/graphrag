from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from neo4j import GraphDatabase
from flask import current_app
import logging

# 核心扩展实例
db = SQLAlchemy()
migrate = Migrate()

neo4j_driver = None
logger = logging.getLogger(__name__)

def init_neo4j(app):
	"""初始化 Neo4j 驱动"""
	global neo4j_driver
	try:
		neo4j_driver = GraphDatabase.driver(
			app.config['NEO4J_URI'],
			auth=(app.config['NEO4J_USERNAME'], app.config['NEO4J_PASSWORD']),
			encrypted=False
		)
		# 验证连接
		neo4j_driver.verify_connectivity()
		logger.info(" Neo4j 连接成功")
	except Exception as e:
		logger.warning(f"Neo4j 连接失败: {e}，将在需要时尝试重连")
		neo4j_driver = None
		# 不中断应用启动

def close_neo4j():
	"""关闭 Neo4j 驱动"""
	global neo4j_driver
	if neo4j_driver:
		neo4j_driver.close()
		logger.info("Neo4j 驱动已关闭")

def get_neo4j_driver():
	"""获取 Neo4j 驱动，若失效则尝试重连"""
	global neo4j_driver
	if not neo4j_driver:
		# 延迟初始化
		init_neo4j(current_app)
	else:
		try:
			neo4j_driver.verify_connectivity()
		except Exception:
			# 重新建立连接
			neo4j_driver = None
			init_neo4j(current_app)
	return neo4j_driver

def init_cors(app):
	# 对接前端，开发环境允许所有来源
	CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True, allow_headers=["Content-Type", "Authorization", "Accept", "Accept-Language"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
