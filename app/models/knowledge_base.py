"""
Knowledge Base 模型 - 知识库和文档存储
"""

from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSON, UUID
import uuid

from ..extensions import db


class KnowledgeBase(db.Model):
    """知识库模型"""
    __tablename__ = 'knowledge_bases'

    id = db.Column(db.Integer, primary_key=True)
    kb_id = db.Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关系
    documents = db.relationship('Document', backref='knowledge_base', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'kb_id': str(self.kb_id),
            'name': self.name,
            'description': self.description,
            'user_id': self.user_id,
            'document_count': len(self.documents),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Document(db.Model):
    """文档模型"""
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    doc_id = db.Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    kb_id = db.Column(UUID(as_uuid=True), db.ForeignKey('knowledge_bases.kb_id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(1024), nullable=True)
    content = db.Column(db.Text, nullable=True)
    file_type = db.Column(db.String(50), nullable=False)  # 'pdf', 'txt', 'docx', 'url', etc.
    status = db.Column(db.String(50), default='processing')  # 'processing', 'completed', 'failed'
    chunk_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'doc_id': str(self.doc_id),
            'kb_id': str(self.kb_id),
            'filename': self.filename,
            'file_type': self.file_type,
            'status': self.status,
            'chunk_count': self.chunk_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentChunk(db.Model):
    """文档切片模型 - 用于存储切分后的文本块"""
    __tablename__ = 'document_chunks'

    id = db.Column(db.Integer, primary_key=True)
    chunk_id = db.Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    doc_id = db.Column(UUID(as_uuid=True), db.ForeignKey('documents.doc_id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)  # 在文档中的顺序
    metadata_json = db.Column(JSON, nullable=True)  # 存储额外的元数据
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # 关系
    document = db.relationship('Document', backref=db.backref('chunks', lazy=True, cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'chunk_id': str(self.chunk_id),
            'doc_id': str(self.doc_id),
            'content': self.content,
            'chunk_index': self.chunk_index,
            'metadata': self.metadata_json,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
