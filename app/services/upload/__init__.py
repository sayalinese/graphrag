import os, time
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from ...extensions import db
from ...models import User
from ..auth import _decode_token

bp = Blueprint('upload', __name__, url_prefix='/api/upload')

ALLOWED_EXTS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_SIZE_MB = 2

def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

@bp.route('/avatar', methods=['POST', 'OPTIONS'])
def upload_avatar():
    # 处理预检请求
    if request.method == 'OPTIONS':
        return '', 200
    
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'code': 401, 'message': 'missing bearer token'}), 401
    token = auth.split(' ', 1)[1]
    uid = _decode_token(token)
    if not uid:
        return jsonify({'code': 401, 'message': 'invalid token'}), 401

    f = request.files.get('file')
    if not f:
        return jsonify({'code': 400, 'message': 'file required'}), 400
    filename = secure_filename(f.filename or '')
    if '.' not in filename:
        return jsonify({'code': 400, 'message': 'invalid filename'}), 400
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTS:
        return jsonify({'code': 400, 'message': 'invalid file type'}), 400

    # size check
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > MAX_SIZE_MB * 1024 * 1024:
        return jsonify({'code': 400, 'message': f'file too large (>{MAX_SIZE_MB}MB)'}), 400

    save_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    ensure_dir(save_dir)
    new_name = f'{uid}_{int(time.time())}.{ext}'
    path = os.path.join(save_dir, new_name)
    f.save(path)

    user = User.query.get(uid)
    if not user:
        return jsonify({'code': 404, 'message': 'user not found'}), 404
    user.avatar = f'/static/avatars/{new_name}'
    db.session.commit()

    # 构建绝对URL
    base = request.host_url.rstrip('/')
    url = base + user.avatar
    return jsonify({'code': 0, 'data': {'url': url}})
