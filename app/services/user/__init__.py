from flask import Blueprint, jsonify, request
from ...models import User
from ...extensions import db
from ..auth import _decode_token  

bp = Blueprint('user', __name__, url_prefix='/api/user')


def _public_user(u: User):
    role = u.role
    if role == 'superadmin':
        role = 'super'
    return {
        'id': u.id,
        'username': u.username,
        'realName': u.username,
        'avatar': u.avatar,
        'email': u.email,
        'permissions': [role] if role else [],
        'createTime': u.created_at.isoformat() if u.created_at else None,
        'lastVisitTime': u.last_login_at.isoformat() if u.last_login_at else None,
        'status': 1 if u.is_active else 0,
    }

@bp.get('/info')
def info():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'code': 401, 'message': 'missing bearer token'}), 401
    token = auth.split(' ', 1)[1]
    uid = _decode_token(token)
    if not uid:
        return jsonify({'code': 401, 'message': 'invalid token'}), 401
    u = User.query.get(uid)
    if not u or not u.is_active:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    return jsonify({'code': 0, 'data': {'user': _public_user(u)}})

@bp.get('/list')
def list_users():
    try:
        page = int(request.args.get('page', '1'))
        page_size = int(request.args.get('page_size', '10'))
    except ValueError:
        return jsonify({'code': 400, 'message': 'page & page_size must be integers'}), 400
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    search = (request.args.get('search') or '').strip()

    query = User.query
    if search:
        like = f"%{search}%"
        query = query.filter(User.username.ilike(like))
    total = query.count()
    items = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data_items = [_public_user(u) for u in items]
    return jsonify({'code': 0, 'data': {'items': data_items, 'total': total, 'page': page, 'page_size': page_size, 'search': search}})

@bp.post('/create')
def create():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip() or None
    avatar = (data.get('avatar') or '').strip() or None
    permissions = data.get('permissions') or []
    role = data.get('role') or (permissions[0] if permissions else 'user')
    password = data.get('password') or '123456'
    if not username:
        return jsonify({'code': 400, 'message': 'username required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 409, 'message': 'username exists'}), 409
    if email and User.query.filter_by(email=email).first():
        return jsonify({'code': 409, 'message': 'email exists'}), 409
    if role in ('super', 'superadmin'):
        role_store = 'superadmin'
    elif role not in ('admin', 'user'):
        role_store = 'user'
    else:
        role_store = role
    u = User(username=username, email=email, avatar=avatar, role=role_store)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return jsonify({'code': 0, 'data': {'user': _public_user(u), 'rawPassword': password}}), 201

@bp.patch('/update/<int:user_id>')
def update(user_id: int):
    data = request.get_json(silent=True) or {}
    u = User.query.get(user_id)
    if not u:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    username = data.get('username')
    email = data.get('email')
    avatar = data.get('avatar')
    permissions = data.get('permissions') or []
    role = data.get('role') or (permissions[0] if permissions else None)
    status = data.get('status')
    password = data.get('password')

    if username and username != u.username:
        if User.query.filter_by(username=username).first():
            return jsonify({'code': 409, 'message': 'username exists'}), 409
        u.username = username
    if email and email != u.email:
        if User.query.filter_by(email=email).first():
            return jsonify({'code': 409, 'message': 'email exists'}), 409
        u.email = email
    if avatar is not None:
        u.avatar = avatar
    if role:
        if role in ('super', 'superadmin'):
            u.role = 'superadmin'
        elif role in ('admin', 'user'):
            u.role = role
    if status is not None:
        u.is_active = bool(status)
    if password:
        u.set_password(password)
    db.session.commit()
    return jsonify({'code': 0, 'data': {'user': _public_user(u)}})

@bp.post('/toggle/<int:user_id>')
def toggle(user_id: int):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    u.is_active = not u.is_active
    db.session.commit()
    return jsonify({'code': 0, 'data': {'status': 1 if u.is_active else 0}})

@bp.delete('/delete/<int:user_id>')
def delete(user_id: int):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    db.session.delete(u)
    db.session.commit()
    return jsonify({'code': 0, 'data': True})
