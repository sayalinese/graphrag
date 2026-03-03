import os


class Config:
	# 双写入，env配置，没配置就用写死的
	SQLALCHEMY_DATABASE_URI = os.getenv(
		'DATABASE_URL',
		'postgresql://postgres:weiwenhan1110@localhost:5432/postgres'
	)
	SQLALCHEMY_TRACK_MODIFICATIONS = False
	SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key')
	JWT_EXPIRES_SECONDS = int(os.getenv('JWT_EXPIRES_SECONDS', 7200))
	
	# Neo4j 配置
	NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
	NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', 'neo4j')
	NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'weiwenhan1110')
	
	# DeepSeek LLM 配置
	DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
	DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
	DEEPSEEK_API_BASE = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com/v1')
	
	# 文件上传配置
	UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads/temp')
	MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB 最大上传大小



