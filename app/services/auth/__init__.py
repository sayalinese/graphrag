from datetime import datetime, timedelta
import uuid
import jwt
from flask import Blueprint, request, jsonify, current_app
from ...extensions import db
from ...models import User, UserSession

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _gen_token(user_id: int):
    """生成 JWT，将 sub 规范为字符串，避免 InvalidSubjectError"""
    exp_seconds = current_app.config.get('JWT_EXPIRES_SECONDS', 7200)
    payload = {
        'sub': str(user_id),  # 规范为字符串
        'exp': datetime.utcnow() + timedelta(seconds=exp_seconds)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def _decode_token(token):
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        sub = data.get('sub')
        if isinstance(sub, str) and sub.isdigit():
            return int(sub)
        return None
    except Exception as e:
        print(f"[AUTH] decode token failed: {e.__class__.__name__}: {e}")
        return None


def _user_dict(u: User):
    # 后端写的super案底吗，前端是super，映射同一一下
    role = u.role
    # 保持输出 super，前端已使用 super；数据库内部 superadmin 也映射为 super 输出
    if role == 'superadmin':
        role = 'super'
    admin_like = ('admin', 'super')
    home_path = '/workspace' if role in admin_like else '/analytics'
    return {
        'id': u.id,
        'username': u.username,
        'realName': u.username,
        'roles': [role],
        'homePath': home_path,
        'avatar': u.avatar,
    }


@bp.post('/register')
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username') or ''
    password = data.get('password') or ''
    email = data.get('email')
    avatar = data.get('avatar')
    role = (data.get('role') or 'user').strip()
    # 输入既可 super / superadmin；内部统一保存 superadmin；输出再映射成 super
    if role in ('super', 'superadmin'):
        role = 'superadmin'
    elif role not in ('user', 'admin'):
        role = 'user'
    if not username or not password:
        return jsonify({'code': 400, 'message': 'username & password required'}), 400
    if email and User.query.filter_by(email=email).first():
        return jsonify({'code': 409, 'message': 'email exists'}), 409
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 409, 'message': 'username exists'}), 409
    u = User(username=username, email=email, avatar=avatar, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    sid = str(uuid.uuid4())
    s = UserSession(id=sid, user_id=u.id)
    db.session.add(s)
    db.session.commit()
    token = _gen_token(u.id)
    return jsonify({'code': 0, 'data': {'accessToken': token, 'session_id': sid, 'user': _user_dict(u)}}), 201


@bp.post('/login')
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    username = data.get('username')
    password = data.get('password') or ''
    q = None
    if email:
        q = User.query.filter_by(email=email).first()
    elif username:
        q = User.query.filter_by(username=username).first()
    # 临时调试输出
    print(f"[AUTH] login attempt username={username} email={email} found_user={'yes' if q else 'no'}")
    if not q:
        print("[AUTH] reason: user not found")
        return jsonify({'code': 401, 'message': 'invalid credentials'}), 401
    if not q.check_password(password):
        print("[AUTH] reason: password mismatch")
        return jsonify({'code': 401, 'message': 'invalid credentials'}), 401
    q.touch_login()
    db.session.commit()
    sid = str(uuid.uuid4())
    s = UserSession(id=sid, user_id=q.id)
    db.session.add(s)
    db.session.commit()
    token = _gen_token(q.id)
    return jsonify({'code': 0, 'data': {'accessToken': token, 'session_id': sid, 'user': _user_dict(q)}})


@bp.get('/codes')
def access_codes():
    """返回当前用户权限码列表。需要登录。"""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'code': 401, 'message': 'missing bearer token'}), 401
    token = auth.split(' ', 1)[1]
    uid = _decode_token(token)
    if not uid:
        return jsonify({'code': 401, 'message': 'invalid token'}), 401
    user = User.query.get(uid)
    if not user:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    # 简化：以角色字符串作为唯一权限码
    eff_role = user.role
    # 输出权限码仍与前端保持 super 形式
    if eff_role == 'superadmin':
        eff_role = 'super'
    codes = [f'ROLE_{eff_role.upper()}']
    return jsonify({'code': 0, 'data': codes})


# 注销
@bp.post('/logout')
def logout():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1]
        uid = _decode_token(token)
        if uid:
            UserSession.query.filter_by(user_id=uid, is_active=True).update({'is_active': False})
            db.session.commit()
    return jsonify({'code': 0, 'data': True})

# 刷新 token
@bp.post('/refresh')
def refresh():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'code': 401, 'message': 'missing bearer token'}), 401
    token = auth.split(' ', 1)[1]
    uid = _decode_token(token)
    if not uid:
        return jsonify({'code': 401, 'message': 'invalid token'}), 401
    new_token = _gen_token(uid)
    return jsonify({'code': 0, 'data': new_token})


@bp.get('/me')
def me():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1]
        uid = _decode_token(token)
        if uid:
            u = User.query.get(uid)
            if u and u.is_active:
                return jsonify({'code': 0, 'data': {'user': _user_dict(u)}})
    return jsonify({'code': 401, 'message': 'unauthorized'}), 401


@bp.get('/users')
def auth_users_list():
    users = User.query.order_by(User.id.desc()).all()
    items = []
    for u in users:
        role = u.role
        if role == 'superadmin':
            role = 'super'
        items.append({
            'id': u.id,
            'username': u.username,
            'avatar': u.avatar,
            'email': u.email,
            'permissions': [role] if role else [],  # 前端使用数组渲染标签
            'createTime': u.created_at.isoformat() if u.created_at else None,
            'lastVisitTime': u.last_login_at.isoformat() if u.last_login_at else None,
            'status': 1 if u.is_active else 0,
        })
    return jsonify({'code': 0, 'data': {'items': items, 'total': len(items)}})



@bp.post('/users')
def users_create():
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
    eff_role = 'super' if u.role == 'superadmin' else u.role
    item = {
        'id': u.id,
        'username': u.username,
        'avatar': u.avatar,
        'email': u.email,
        'permissions': [eff_role],
        'createTime': u.created_at.isoformat() if u.created_at else None,
        'lastVisitTime': u.last_login_at.isoformat() if u.last_login_at else None,
        'status': 1 if u.is_active else 0,
    }
    return jsonify({'code': 0, 'data': {'user': item, 'rawPassword': password}}), 201


@bp.patch('/users/<int:user_id>')
def users_update(user_id: int):
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
    eff_role = 'super' if u.role == 'superadmin' else u.role
    item = {
        'id': u.id,
        'username': u.username,
        'avatar': u.avatar,
        'email': u.email,
        'permissions': [eff_role],
        'createTime': u.created_at.isoformat() if u.created_at else None,
        'lastVisitTime': u.last_login_at.isoformat() if u.last_login_at else None,
        'status': 1 if u.is_active else 0,
    }
    return jsonify({'code': 0, 'data': {'user': item}})


@bp.post('/users/<int:user_id>/toggle')
def users_toggle(user_id: int):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    u.is_active = not u.is_active
    db.session.commit()
    return jsonify({'code': 0, 'data': {'status': 1 if u.is_active else 0}})


@bp.delete('/users/<int:user_id>')
def users_delete(user_id: int):
    u = User.query.get(user_id)
    if not u:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    db.session.delete(u)
    db.session.commit()
    return jsonify({'code': 0, 'data': True})
