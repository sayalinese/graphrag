"""
Character API 路由
对接前端的角色管理功能
"""

from flask import request, jsonify
import logging

from . import bp
from app.models import Character
from app.models.expert_config import ExpertConfig
from app.extensions import db

logger = logging.getLogger(__name__)


@bp.route('/character/list', methods=['GET'])
def list_characters():
    """列出所有角色"""
    try:
        characters = Character.query.order_by(Character.created_at.desc()).all()
        return jsonify({
            'code': 0,
            'data': {
                'characters': [c.to_dict() for c in characters]
            },
            'message': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error listing characters: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/character/available', methods=['GET'])
def get_available_characters():
    """获取可用的角色列表"""
    try:
        characters = Character.query.filter_by(is_active=True).order_by(Character.created_at.desc()).all()
        return jsonify({
            'code': 0,
            'data': {
                'characters': [c.to_dict() for c in characters]
            },
            'message': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error getting available characters: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/character/<string:key>', methods=['GET'])
def get_character(key: str):
    """获取角色详情"""
    try:
        character = Character.query.filter_by(key=key).first()
        if not character:
            return jsonify({'code': 404, 'message': '角色不存在'}), 404
        
        return jsonify({
            'code': 0,
            'data': {
                'character': character.to_dict()
            },
            'message': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error getting character: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/character/create', methods=['POST'])
def create_character():
    """创建角色"""
    try:
        data = request.get_json()
        
        # 检查 key 是否存在
        if Character.query.filter_by(key=data.get('key')).first():
            return jsonify({'code': 400, 'message': '角色 Key 已存在'}), 400

        character = Character(
            key=data.get('key'),
            name=data.get('name'),
            product=data.get('product'),
            hobby=data.get('hobby'),
            personality=data.get('personality'),
            expertise=data.get('expertise', []),
            system_prompt=data.get('system_prompt', ''),
            avatar=data.get('avatar', ''),
            is_active=True
        )
        
        db.session.add(character)
        db.session.commit()

        return jsonify({
            'code': 0,
            'data': {
                'character': character.to_dict()
            },
            'message': 'success'
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating character: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/character/<int:id>', methods=['PUT'])
def update_character(id: int):
    """更新角色"""
    try:
        character = Character.query.get(id)
        if not character:
            return jsonify({'code': 404, 'message': '角色不存在'}), 404
            
        data = request.get_json()
        
        if 'name' in data: character.name = data['name']
        if 'product' in data: character.product = data['product']
        if 'hobby' in data: character.hobby = data['hobby']
        if 'personality' in data: character.personality = data['personality']
        if 'expertise' in data: character.expertise = data['expertise']
        if 'system_prompt' in data: character.system_prompt = data['system_prompt']
        if 'avatar' in data: character.avatar = data['avatar']
        if 'is_active' in data: character.is_active = data['is_active']
        
        db.session.commit()

        return jsonify({
            'code': 0,
            'data': {
                'character': character.to_dict()
            },
            'message': 'success'
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating character: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/character/<int:id>', methods=['DELETE'])
def delete_character(id: int):
    """删除角色"""
    try:
        character = Character.query.get(id)
        if not character:
            return jsonify({'code': 404, 'message': '角色不存在'}), 404
            
        db.session.delete(character)
        db.session.commit()

        return jsonify({'code': 0, 'message': 'success'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting character: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/character/<int:character_id>/toggle-status', methods=['POST'])
def toggle_character_status(character_id: int):
    """切换角色启用/禁用状态"""
    try:
        character = Character.query.get(character_id)
        if not character:
            return jsonify({'code': 404, 'message': '角色不存在'}), 404

        character.is_active = not character.is_active
        db.session.commit()

        return jsonify({
            'code': 0,
            'data': {
                'is_active': character.is_active
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error toggling character status: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'message': str(e)}), 500


# ─────────────────────────────────────────────
# 多专家配置 API
# ─────────────────────────────────────────────

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


def _ensure_expert_defaults():
    """确保三个默认专家配置存在（首次启动时自动初始化）"""
    from datetime import datetime
    for d in DEFAULT_EXPERTS:
        if not ExpertConfig.query.filter_by(key=d['key']).first():
            ec = ExpertConfig(
                key=d['key'],
                title=d['title'],
                description=d['description'],
                running_detail=d['running_detail'],
                enabled=d['enabled'],
                order=d['order'],
                updated_at=datetime.utcnow(),
            )
            db.session.add(ec)
    db.session.commit()


@bp.route('/expert/configs', methods=['GET'])
def list_expert_configs():
    """获取所有专家配置"""
    try:
        _ensure_expert_defaults()
        configs = ExpertConfig.query.order_by(ExpertConfig.order).all()
        return jsonify({
            'code': 0,
            'data': {'configs': [c.to_dict() for c in configs]},
            'message': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error listing expert configs: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/expert/config/<string:key>', methods=['PUT'])
def update_expert_config(key: str):
    """更新单个专家配置"""
    try:
        config = ExpertConfig.query.filter_by(key=key).first()
        if not config:
            return jsonify({'code': 404, 'message': '专家不存在'}), 404

        data = request.get_json() or {}
        if 'title' in data:
            config.title = data['title'].strip() or config.title
        if 'description' in data:
            config.description = data['description']
        if 'running_detail' in data:
            config.running_detail = data['running_detail']
        if 'enabled' in data:
            config.enabled = bool(data['enabled'])
        if 'order' in data:
            config.order = int(data['order'])

        db.session.commit()
        return jsonify({
            'code': 0,
            'data': {'config': config.to_dict()},
            'message': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error updating expert config: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'message': str(e)}), 500

