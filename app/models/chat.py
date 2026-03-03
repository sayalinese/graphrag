from datetime import datetime

from ..extensions import db


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # 可选会话名称（持久化前端命名）
    name = db.Column(db.String(128), nullable=True, index=True)
    # 绑定前端用户（可为空以兼容匿名会话）
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    # 可选绑定知识库（会话级 RAG）
    kb_id = db.Column(db.Integer, nullable=True, index=True)
    character_key = db.Column(db.String(100), nullable=False)
    max_context_length = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=True, default=None)
    updated_at = db.Column(db.DateTime, nullable=True, default=None)

    messages = db.relationship(
        'ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan'
    )

    def touch(self):
        now = datetime.utcnow()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.String(64),
        db.ForeignKey('chat_sessions.session_id'),
        index=True,
        nullable=False,
    )
    role = db.Column(db.String(20), nullable=False)  # 'user' | 'assistant' | 'system'
    content = db.Column(db.Text, nullable=False)
    # RAG 引文/来源（可选）：[{kb_id, doc_id, page, score, text, metadata}]
    sources = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=True, default=None, index=True)
