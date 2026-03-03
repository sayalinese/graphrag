from datetime import datetime
from ..extensions import db

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_activity_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # 反向关系，允许 user.sessions 访问
    user = db.relationship('User', backref='sessions')
