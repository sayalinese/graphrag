"""add expert_configs table

Revision ID: e3a1f9d2b5c7
Revises: b1f4d2a9c8e1
Create Date: 2026-04-09 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e3a1f9d2b5c7'
down_revision = 'b1f4d2a9c8e1'
branch_labels = None
depends_on = None


# 默认专家配置
DEFAULT_EXPERTS = [
    {
        'key': 'evidence',
        'title': '证据专家',
        'description': (
            '提炼与用户问题直接相关的事实证据、实体关系、原文片段和可验证依据。'
            '优先回答"图谱里明确能支持什么"，避免过早下结论。'
        ),
        'running_detail': '正在提取与问题最直接相关的证据链...',
        'enabled': True,
        'order': 1,
    },
    {
        'key': 'pathology',
        'title': '病理专家',
        'description': (
            '从病理/领域专家视角解释上述证据意味着什么。'
            '需要指出诊断价值、分类依据、风险提示或临床边界。'
        ),
        'running_detail': '正在从领域角度解释证据含义...',
        'enabled': True,
        'order': 2,
    },
    {
        'key': 'reviewer',
        'title': '审稿专家',
        'description': (
            '审查前面专家的结论是否严格被检索上下文支持。'
            '指出冲突、推断过度和仍需补充的信息。'
        ),
        'running_detail': '正在检查证据与结论是否一致...',
        'enabled': True,
        'order': 3,
    },
]


def upgrade():
    op.create_table(
        'expert_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('running_detail', sa.String(length=200), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )

    # 插入默认三个专家配置
    expert_configs = op.get_bind().execute
    table = sa.table(
        'expert_configs',
        sa.column('key', sa.String),
        sa.column('title', sa.String),
        sa.column('description', sa.Text),
        sa.column('running_detail', sa.String),
        sa.column('enabled', sa.Boolean),
        sa.column('order', sa.Integer),
        sa.column('updated_at', sa.DateTime),
    )
    from datetime import datetime
    now = datetime.utcnow()
    op.bulk_insert(table, [
        {**e, 'updated_at': now} for e in DEFAULT_EXPERTS
    ])


def downgrade():
    op.drop_table('expert_configs')
