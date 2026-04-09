import json
import logging
from copy import deepcopy
from datetime import datetime

from flask import jsonify, request

from . import bp
from app.extensions import db
from app.models import MenuConfig, User
from app.services.auth import _decode_token

logger = logging.getLogger(__name__)


DEFAULT_MENU_TREE = [
    {
        'id': 1,
        'type': 'catalog',
        'name': 'Dashboard',
        'title': 'page.dashboard.title',
        'path': '/dashboard',
        'redirect': '/analytics',
        'icon': 'lucide:layout-dashboard',
        'status': 1,
        'children': [
            {
                'id': 11,
                'pid': 1,
                'name': 'Analytics',
                'type': 'menu',
                'title': 'page.dashboard.analytics',
                'path': '/analytics',
                'component': '/dashboard/analytics/index',
                'icon': 'lucide:area-chart',
                'status': 1,
            },
            {
                'id': 12,
                'pid': 1,
                'name': 'Workspace',
                'type': 'menu',
                'title': 'page.dashboard.workspace',
                'path': '/workspace',
                'component': '/dashboard/workspace/index',
                'icon': 'carbon:workspace',
                'status': 1,
            },
        ],
    },
    {
        'id': 2,
        'type': 'catalog',
        'name': 'SystemRoot',
        'title': 'page.system.title',
        'path': '/system',
        'redirect': '/system/role',
        'icon': 'carbon:cloud-service-management',
        'status': 1,
        'children': [
            {
                'id': 21,
                'pid': 2,
                'name': 'SystemRole',
                'type': 'menu',
                'title': 'page.system.role.list',
                'path': '/system/role',
                'component': '/system/role/index',
                'icon': 'carbon:user-role',
                'status': 1,
            },
            {
                'id': 22,
                'pid': 2,
                'name': 'SystemMenu',
                'type': 'menu',
                'title': 'page.system.menu.name',
                'path': '/system/menu',
                'component': '/system/menu/index',
                'icon': 'carbon:menu',
                'status': 1,
            },
            {
                'id': 23,
                'pid': 2,
                'name': 'SystemUser',
                'type': 'menu',
                'title': 'page.system.user.list',
                'path': '/system/user',
                'component': '/system/user/index',
                'icon': 'carbon:user-avatar',
                'status': 1,
            },
        ],
    },
    {
        'id': 3,
        'type': 'catalog',
        'name': 'KgRoot',
        'title': 'page.kg.title',
        'path': '/kg',
        'redirect': '/kg/preview',
        'icon': 'lucide:network',
        'status': 1,
        'children': [
            {
                'id': 31,
                'pid': 3,
                'name': 'KgDashboard',
                'type': 'menu',
                'title': 'page.kg.dashboard',
                'path': '/kg/dashboard',
                'component': '/kg/kg_dashboard/index',
                'icon': 'mdi:view-dashboard-outline',
                'status': 1,
            },
            {
                'id': 32,
                'pid': 3,
                'name': 'KgPreview',
                'type': 'menu',
                'title': 'page.kg.preview',
                'path': '/kg/preview',
                'component': '/kg/kg_preview/index',
                'icon': 'mdi:eye-outline',
                'status': 1,
            },
            {
                'id': 33,
                'pid': 3,
                'name': 'KgExplain',
                'type': 'menu',
                'title': '医疗诊断',
                'path': '/kg/explain',
                'component': '/kg/kg_explain/index',
                'icon': 'mdi:graph-outline',
                'status': 1,
            },
            {
                'id': 34,
                'pid': 3,
                'name': 'KgConstruct',
                'type': 'menu',
                'title': 'page.kg.construct',
                'path': '/kg/construct',
                'component': '/kg/kg_construct/index',
                'icon': 'mdi:database-plus-outline',
                'status': 1,
            },
            {
                'id': 35,
                'pid': 3,
                'name': 'KgManagement',
                'type': 'menu',
                'title': 'page.kg.management',
                'path': '/kg/management',
                'component': '/kg/kg_management/index',
                'icon': 'mdi:cog-outline',
                'status': 1,
            },
            {
                'id': 36,
                'pid': 3,
                'name': 'KgCharacter',
                'type': 'menu',
                'title': 'page.kg.character',
                'path': '/kg/character',
                'component': '/kb/character/index',
                'icon': 'lucide:users',
                'status': 1,
            },
        ],
    },
    {
        'id': 4,
        'type': 'catalog',
        'name': 'KBRoot',
        'title': 'page.kb.title',
        'path': '/kb',
        'redirect': '/kb/chat',
        'icon': 'lucide:book-open',
        'status': 0,
        'children': [
            {
                'id': 41,
                'pid': 4,
                'name': 'KBChat',
                'type': 'menu',
                'title': 'page.kb.chat',
                'path': '/kb/chat',
                'component': '/kb/chat/index',
                'icon': 'lucide:message-square',
                'status': 0,
            },
            {
                'id': 42,
                'pid': 4,
                'name': 'KBManagement',
                'type': 'menu',
                'title': 'page.kb.management',
                'path': '/kb/management',
                'component': '/kb/management/index',
                'icon': 'lucide:database',
                'status': 0,
            },
            {
                'id': 43,
                'pid': 4,
                'name': 'KBDocument',
                'type': 'menu',
                'title': '文档管理',
                'path': '/kb/document',
                'component': '/kb/document/index',
                'icon': 'lucide:file-text',
                'status': 0,
            },
            {
                'id': 44,
                'pid': 4,
                'name': 'CharacterManagement',
                'type': 'menu',
                'title': 'page.kb.character',
                'path': '/kb/character',
                'component': '/kb/character/index',
                'icon': 'lucide:users',
                'status': 0,
            },
            {
                'id': 45,
                'pid': 4,
                'name': 'KBSearch',
                'type': 'menu',
                'title': '知识库搜索',
                'path': '/kb/search',
                'component': '/kb/search/index',
                'icon': 'lucide:search',
                'status': 0,
            },
        ],
    },
    {
        'id': 5,
        'type': 'catalog',
        'name': 'ChatRoot',
        'title': 'page.chat.title',
        'path': '/chat',
        'redirect': '/chat/ai',
        'icon': 'lucide:message-square',
        'status': 0,
        'children': [
            {
                'id': 51,
                'pid': 5,
                'name': 'ChatAI',
                'type': 'menu',
                'title': 'page.chat.title',
                'path': '/chat/ai',
                'component': '/chat/chat_ai/index',
                'icon': 'lucide:bot-message-square',
                'status': 1,
            },
            {
                'id': 52,
                'pid': 5,
                'name': 'ChatManagement',
                'type': 'menu',
                'title': 'page.chat.management',
                'path': '/chat/management',
                'component': '/chat/chat_management/index',
                'icon': 'lucide:settings-2',
                'status': 1,
            },
        ],
    },
    {
        'id': 6,
        'type': 'catalog',
        'name': 'BoardRoot',
        'title': 'page.board.title',
        'path': '/board',
        'redirect': '/board/gate',
        'icon': 'lucide:image',
        'status': 0,
        'children': [],
    },
]


def _clone_default_menus():
    return deepcopy(DEFAULT_MENU_TREE)


def _decode_request_user():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, (jsonify({'code': 401, 'message': 'missing bearer token'}), 401)

    token = auth.split(' ', 1)[1]
    user_id = _decode_token(token)
    if not user_id:
        return None, (jsonify({'code': 401, 'message': 'invalid token'}), 401)

    user = User.query.get(user_id)
    if not user or not user.is_active:
        return None, (jsonify({'code': 404, 'message': 'user not found'}), 404)

    return user, None


def _deserialize_menu_data(raw_value):
    try:
        parsed = json.loads(raw_value or '[]')
        return parsed if isinstance(parsed, list) else _clone_default_menus()
    except (TypeError, json.JSONDecodeError):
        logger.warning('菜单配置反序列化失败，回退到默认菜单')
        return _clone_default_menus()


def _serialize_menu_data(menu_tree):
    return json.dumps(menu_tree, ensure_ascii=False)


def _get_or_create_menu_config(user_id):
    config = MenuConfig.query.filter_by(user_id=user_id).first()
    if config:
        return config, _deserialize_menu_data(config.menu_data)

    menus = _clone_default_menus()
    config = MenuConfig(user_id=user_id, menu_data=_serialize_menu_data(menus))
    db.session.add(config)
    db.session.commit()
    return config, menus


def _save_menu_config(config, menus):
    config.menu_data = _serialize_menu_data(menus)
    config.updated_at = datetime.utcnow()
    db.session.add(config)
    db.session.commit()


def _find_node(node_id, items):
    for item in items:
        if item.get('id') == node_id:
            return item
        children = item.get('children') or []
        found = _find_node(node_id, children)
        if found:
            return found
    return None


def _remove_node(node_id, items):
    for index, item in enumerate(items):
        if item.get('id') == node_id:
            items.pop(index)
            return True
        children = item.get('children') or []
        if _remove_node(node_id, children):
            return True
    return False


def _disable_descendants(node):
    for child in node.get('children') or []:
        child['status'] = 0
        _disable_descendants(child)


def _next_menu_id(items):
    max_id = 0
    for item in items:
        max_id = max(max_id, int(item.get('id', 0) or 0))
        children = item.get('children') or []
        if children:
            max_id = max(max_id, _next_menu_id(children))
    return max_id + 1


def _to_route_records(items, inherited_hidden=False):
    routes = []
    for item in items:
        if item.get('type') == 'button':
            continue

        hidden = inherited_hidden or item.get('status', 1) == 0
        route = {
            'component': item.get('component') or 'BasicLayout',
            'name': item.get('name') or item.get('path') or str(item.get('id')),
            'path': item.get('path') or '',
            'meta': {
                'hideInMenu': hidden,
                'icon': item.get('icon'),
                'title': item.get('title'),
            },
        }
        if item.get('redirect'):
            route['redirect'] = item['redirect']
        children = item.get('children') or []
        if children:
            route['children'] = _to_route_records(children, hidden)
        routes.append(route)
    return routes


def _normalize_menu_payload(payload, partial=False):
    normalized = {}
    field_names = ['pid', 'type', 'title', 'name', 'path', 'component', 'icon', 'redirect', 'status']

    for field_name in field_names:
        if partial and field_name not in payload:
            continue
        if field_name == 'status':
            value = payload.get(field_name, 1)
            normalized[field_name] = 1 if int(value or 1) == 1 else 0
            continue
        normalized[field_name] = payload.get(field_name)

    if not partial:
        normalized.setdefault('type', 'menu')
        normalized.setdefault('title', '')
        normalized.setdefault('status', 1)

    return normalized


@bp.route('/menu/all', methods=['GET'])
def get_all_menus():
    user, error_response = _decode_request_user()
    if error_response:
        return error_response

    _, menus = _get_or_create_menu_config(user.id)
    return jsonify({'code': 0, 'data': _to_route_records(menus), 'message': 'success'})


@bp.route('/system/menu/list', methods=['GET'])
def list_menus():
    user, error_response = _decode_request_user()
    if error_response:
        return error_response

    _, menus = _get_or_create_menu_config(user.id)
    return jsonify({
        'code': 0,
        'data': {
            'menus': menus,
            'total': len(menus),
        },
        'message': 'success',
    })


@bp.route('/system/menu/create', methods=['POST'])
def create_menu():
    user, error_response = _decode_request_user()
    if error_response:
        return error_response

    config, menus = _get_or_create_menu_config(user.id)
    payload = _normalize_menu_payload(request.get_json(silent=True) or {})
    if not payload['title']:
        return jsonify({'code': 400, 'message': 'title required'}), 400

    new_item = {
        **payload,
        'id': _next_menu_id(menus),
    }
    if new_item['type'] == 'catalog':
        new_item['children'] = new_item.get('children') or []

    parent_id = new_item.get('pid')
    if parent_id:
        parent = _find_node(parent_id, menus)
        if not parent:
            return jsonify({'code': 404, 'message': 'parent menu not found'}), 404
        parent.setdefault('children', []).append(new_item)
    else:
        menus.append(new_item)

    _save_menu_config(config, menus)
    return jsonify({'code': 0, 'data': {'menu': new_item}, 'message': 'success'}), 201


@bp.route('/system/menu/<int:menu_id>', methods=['PUT'])
def update_menu(menu_id):
    user, error_response = _decode_request_user()
    if error_response:
        return error_response

    config, menus = _get_or_create_menu_config(user.id)
    node = _find_node(menu_id, menus)
    if not node:
        return jsonify({'code': 404, 'message': 'menu not found'}), 404

    payload = _normalize_menu_payload(request.get_json(silent=True) or {}, partial=True)
    if 'title' in payload and payload['title']:
        node['title'] = payload['title']

    for key in ['pid', 'type', 'name', 'path', 'component', 'icon', 'redirect', 'status']:
        if key in payload:
            node[key] = payload[key]

    if node.get('pid') is None and node.get('type') == 'catalog' and node.get('status') == 0:
        _disable_descendants(node)

    _save_menu_config(config, menus)
    return jsonify({'code': 0, 'data': {'menu': node}, 'message': 'success'})


@bp.route('/system/menu/<int:menu_id>', methods=['DELETE'])
def delete_menu(menu_id):
    user, error_response = _decode_request_user()
    if error_response:
        return error_response

    config, menus = _get_or_create_menu_config(user.id)
    if not _remove_node(menu_id, menus):
        return jsonify({'code': 404, 'message': 'menu not found'}), 404

    _save_menu_config(config, menus)
    return jsonify({'code': 0, 'data': True, 'message': 'success'})


@bp.route('/system/menu/<int:menu_id>/toggle', methods=['POST'])
def toggle_menu_status(menu_id):
    user, error_response = _decode_request_user()
    if error_response:
        return error_response

    config, menus = _get_or_create_menu_config(user.id)
    node = _find_node(menu_id, menus)
    if not node:
        return jsonify({'code': 404, 'message': 'menu not found'}), 404

    node['status'] = 0 if int(node.get('status', 1) or 1) == 1 else 1
    if node.get('pid') is None and node.get('type') == 'catalog' and node.get('status') == 0:
        _disable_descendants(node)

    _save_menu_config(config, menus)
    return jsonify({'code': 0, 'data': {'menu': node, 'status': node['status']}, 'message': 'success'})