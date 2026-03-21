from flask import Blueprint, jsonify, request
from ..models import User
from ..services.auth import _decode_token, _user_dict  
from ..extensions import db

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.get('/ping')
def ping():
    return jsonify({'pong': 1})

# 导入API蓝图模块
from . import chat_api
from . import knowledge_base_api
from . import character_api
from . import menu_api



