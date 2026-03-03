from datetime import datetime

from ..extensions import db


class Character(db.Model):
    __tablename__ = 'characters'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    product = db.Column(db.String(200), nullable=False)
    hobby = db.Column(db.String(200), nullable=False)
    personality = db.Column(db.String(500), nullable=False)
    expertise = db.Column(db.JSON, nullable=False, default=list)
    system_prompt = db.Column(db.Text, nullable=False, default='')
    avatar = db.Column(db.String(255), nullable=False, default='')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "product": self.product,
            "hobby": self.hobby,
            "personality": self.personality,
            "expertise": self.expertise or [],
            "system_prompt": self.system_prompt or "",
            "avatar": self.avatar or "",
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_ai_character_payload(self):
        return {
            "name": self.name,
            "product": self.product,
            "hobby": self.hobby,
            "personality": self.personality,
            "expertise": self.expertise or [],
            "system_prompt": self.system_prompt or "",
            "avatar": self.avatar or "",
        }
