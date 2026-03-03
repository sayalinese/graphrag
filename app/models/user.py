from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True)
    # 使用 werkzeug 默认 scrypt 会生成较长的哈希串，128 可能不够，这里扩到 256
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), default='user', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    avatar = db.Column(db.String(256))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def touch_login(self):
        self.last_login_at = datetime.utcnow()
