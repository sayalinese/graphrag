"""
Chat API 路由
对接前端的聊天对话功能
"""

from flask import request, jsonify, Response, stream_with_context
from datetime import datetime, timezone
from typing import Optional
import json
import logging
import uuid

from . import bp
from app.models import ChatSession, ChatMessage, Character, User
from app.extensions import db

logger = logging.getLogger(__name__)


def get_chat_manager():
    """延迟导入 chat_manager 以避免循环依赖"""
    from app.workflows.langchain.chat import chat_manager
    return chat_manager


def resolve_character_name(character_key: Optional[str]) -> str:
    """Try to resolve a character name without raising when missing."""
    if not character_key:
        return ''

    character = Character.query.filter_by(key=character_key).first()
    return character.name if character else character_key


# ============ 会话管理 ============


@bp.route('/chat/session/create', methods=['POST'])
def create_session():
    """创建新聊天会话"""
    try:
        data = request.get_json() or {}
        character_id = data.get('character_id', 'student')
        name = data.get('name', '')
        kb_id = data.get('kb_id')
        max_context_length = data.get('max_context_length', 10)
        user_id = data.get('user_id')  # 可选

        # 从后端创建会话
        chat_mgr = get_chat_manager()
        session_id = chat_mgr.create_session(
            character_id=character_id,
            name=name or f"会话-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            kb_id=kb_id,
            max_context_length=max_context_length,
            user_id=user_id
        )

        return jsonify({
            'code': 0,
            'data': {
                'session_id': session_id
            },
            'message': 'success'
        }), 201

    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/chat/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """获取会话详情"""
    try:
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'code': 404, 'message': '会话不存在'}), 404

        return jsonify({
            'code': 0,
            'data': {
                'session': {
                    'session_id': session.session_id,
                    'name': session.name,
                    'character_key': session.character_key,
                    'character_name': resolve_character_name(session.character_key),
                    'max_context_length': session.max_context_length,
                    'kb_id': session.kb_id,
                    'user_id': session.user_id,
                    'created_at': session.created_at.isoformat() if session.created_at else None,
                    'updated_at': session.updated_at.isoformat() if session.updated_at else None,
                    'message_count': ChatMessage.query.filter_by(session_id=session_id).count(),
                }
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/chat/sessions', methods=['GET'])
def list_sessions():
    """列出用户的所有会话"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        user_id = request.args.get('user_id', type=int)

        query = ChatSession.query
        if user_id:
            query = query.filter_by(user_id=user_id)

        total = query.count()
        sessions = query.order_by(ChatSession.updated_at.desc()).limit(limit).offset(offset).all()

        return jsonify({
            'code': 0,
            'data': {
                'sessions': [
                    {
                        'session_id': s.session_id,
                        'name': s.name,
                        'character_key': s.character_key,
                        'character_name': resolve_character_name(s.character_key),
                        'max_context_length': s.max_context_length,
                        'kb_id': s.kb_id,
                        'user_id': s.user_id,
                        'created_at': s.created_at.isoformat() if s.created_at else None,
                        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
                        'message_count': ChatMessage.query.filter_by(session_id=s.session_id).count(),
                    }
                    for s in sessions
                ],
                'total': total
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/chat/session/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """删除会话"""
    try:
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'code': 404, 'message': '会话不存在'}), 404

        # 删除会话的所有消息
        ChatMessage.query.filter_by(session_id=session_id).delete()
        db.session.delete(session)
        db.session.commit()

        return jsonify({'code': 0, 'message': 'success'}), 200

    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'message': str(e)}), 500


# ============ 消息收发 ============


@bp.route('/chat/send', methods=['POST'])
def send_message():
    """发送单轮消息"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        content = data.get('user_message')
        character_id = data.get('character_id', 'student')
        max_context_length = data.get('max_context_length', 10)
        user_id = data.get('user_id')
        kb_id = data.get('kb_id')
        enable_web_search = data.get('enable_web_search', False)

        if not session_id or not content:
            return jsonify({'code': 400, 'message': '会话ID和消息内容不能为空'}), 400

        # 调用聊天服务
        chat_mgr = get_chat_manager()
        result = chat_mgr.get_chat_service(user_id=user_id).chat(
            session_id=session_id,
            user_message=content,
            character_id=character_id,
            max_context_length=max_context_length,
            user_id=user_id,
            kb_id=kb_id,
            enable_web_search=enable_web_search
        )

        if result.get('success'):
            return jsonify({
                'code': 0,
                'data': {
                    'session_id': session_id,
                    'response': result.get('response'),
                    'character': result.get('character'),
                    'sources': result.get('sources'),
                    'context_length': result.get('context_length'),
                    'timestamp': result.get('timestamp')
                },
                'message': 'success'
            }), 200
        else:
            return jsonify({
                'code': 500,
                'message': result.get('error', '聊天失败'),
                'data': {
                    'session_id': session_id
                }
            }), 500

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/chat/stream', methods=['GET'])
def stream_message():
    """流式发送消息（SSE）"""
    try:
        session_id = request.args.get('session_id')
        content = request.args.get('user_message')
        character_id = request.args.get('character_id', 'student')
        max_context_length = request.args.get('max_context_length', 10, type=int)
        user_id = request.args.get('user_id', type=int)
        kb_id = request.args.get('kb_id', type=int)
        enable_web_search = request.args.get('enable_web_search') == 'true'

        if not session_id or not content:
            return jsonify({'code': 400, 'message': '会话ID和消息内容不能为空'}), 400

        def generate():
            try:
                # 调用流式聊天服务
                chat_mgr = get_chat_manager()
                for chunk in chat_mgr.get_chat_service(user_id=user_id).chat_stream(
                    session_id=session_id,
                    user_message=content,
                    character_id=character_id,
                    max_context_length=max_context_length,
                    kb_id=kb_id,
                    enable_web_search=enable_web_search
                ):
                    # 确保每个chunk立即发送
                    yield f"data: {json.dumps(chunk)}\n\n"
                    import sys
                    sys.stdout.flush()  # 强制刷新缓冲

            except Exception as e:
                logger.error(f"Error in stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
            'Content-Type': 'text/event-stream; charset=utf-8',
        }), 200

    except Exception as e:
        logger.error(f"Error in stream_message: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


# ============ 历史和上下文 ============


@bp.route('/chat/history/<session_id>', methods=['GET'])
def get_history(session_id: str):
    """获取会话的消息历史"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(
            ChatMessage.timestamp.asc()
        ).limit(limit).offset(offset).all()

        return jsonify({
            'code': 0,
            'data': {
                'messages': [
                    {
                        'id': str(m.id),
                        'session_id': m.session_id,
                        'role': m.role,
                        'content': m.content,
                        'sources': m.sources,
                        'timestamp': m.timestamp.isoformat() if m.timestamp else None,
                    }
                    for m in messages
                ]
            },
            'message': 'success'
        }), 200

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@bp.route('/chat/session/<session_id>/clear', methods=['POST'])
def clear_context(session_id: str):
    """清空会话上下文（内存缓存）"""
    try:
        # 清除内存中的上下文
        from app.workflows.langchain.langchain_context import context_manager
        context_manager.clear_conversation(session_id)

        return jsonify({'code': 0, 'message': 'success'}), 200

    except Exception as e:
        logger.error(f"Error clearing context: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500

