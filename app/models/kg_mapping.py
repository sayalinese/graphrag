from datetime import datetime
from app.extensions import db

class KGMapping(db.Model):
    """知识图谱映射规则表"""
    __tablename__ = 'kg_mappings'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True, comment='映射类别: entity_type, relation_type, entity_synonym, node_color')
    source_key = db.Column(db.String(100), nullable=False, comment='源键 (如: 中文名称)')
    target_value = db.Column(db.String(100), nullable=False, comment='目标值 (如: Neo4j类型)')
    description = db.Column(db.String(255), nullable=True, comment='备注')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        # 同一个类别下，源键必须唯一
        db.UniqueConstraint('category', 'source_key', name='uq_category_source'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'source_key': self.source_key,
            'target_value': self.target_value,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
