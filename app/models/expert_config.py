from datetime import datetime
from ..extensions import db


class ExpertConfig(db.Model):
    """多专家协作模式下各专家的配置（名称、指令、状态等）"""
    __tablename__ = 'expert_configs'

    id = db.Column(db.Integer, primary_key=True)
    # 固定标识：evidence | pathology | reviewer
    key = db.Column(db.String(64), unique=True, nullable=False)
    # 显示名称，如"证据专家"
    title = db.Column(db.String(100), nullable=False)
    # 向 LLM 下达的角色指令
    description = db.Column(db.Text, nullable=False, default='')
    # 运行时显示给用户的提示文字
    running_detail = db.Column(db.String(200), nullable=False, default='')
    # 启用/禁用
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    # 排序（越小越先执行）
    order = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'title': self.title,
            'description': self.description,
            'running_detail': self.running_detail,
            'enabled': self.enabled,
            'order': self.order,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
