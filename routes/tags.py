"""标签路由蓝图 —— 管理端 CRUD + 文件标签绑定"""

from flask import Blueprint, jsonify, request, session

from services.tag_service import (
    create_tag, update_tag, delete_tag, get_all_tags,
    set_file_tags, get_file_tags, can_edit_file_tags,
)
from utils.decorators import api_login_required, api_admin_required

tags_bp = Blueprint('tags', __name__, url_prefix='/api/tags')


# ── 管理端（admin only）──

@tags_bp.route('', methods=['GET'])
@api_login_required
def api_list_tags():
    """GET /api/tags → 获取所有标签"""
    tags = get_all_tags()
    return jsonify({'success': True, 'tags': tags})


@tags_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_tag():
    """POST /api/tags → 创建标签（admin）
    JSON: {"name": "紧急", "color": "#ff0000"}
    """
    data = request.get_json(silent=True) or {}
    result = create_tag(
        name=data.get('name', ''),
        color=data.get('color', '#3b82f6'),
    )
    if not result['success']:
        err_str = str(result['errors'])
        status = 409 if '已存在' in err_str else 400
        return jsonify({'success': False, 'errors': result['errors']}), status
    return jsonify({'success': True, 'tag': result['tag']}), 201


@tags_bp.route('/<int:tag_id>', methods=['PUT'])
@api_login_required
@api_admin_required
def api_update_tag(tag_id):
    """PUT /api/tags/<id> → 编辑标签（admin）
    JSON: {"name": "新名"}  或  {"color": "#00ff00"}  或两者皆有
    """
    data = request.get_json(silent=True) or {}
    result = update_tag(
        tag_id=tag_id,
        name=data.get('name'),
        color=data.get('color'),
    )
    if not result['success']:
        err_str = str(result['errors'])
        if '不存在' in err_str:
            status = 404
        elif '已存在' in err_str:
            status = 409
        else:
            status = 400
        return jsonify({'success': False, 'errors': result['errors']}), status
    return jsonify({'success': True, 'tag': result['tag']})


@tags_bp.route('/<int:tag_id>', methods=['DELETE'])
@api_login_required
@api_admin_required
def api_delete_tag(tag_id):
    """DELETE /api/tags/<id> → 删除标签（admin）"""
    result = delete_tag(tag_id)
    if not result['success']:
        return jsonify({'success': False, 'errors': result['errors']}), 404
    return jsonify({'success': True})


# ── 文件-标签绑定 ──

@tags_bp.route('/file/<int:file_id>', methods=['GET'])
@api_login_required
def api_get_file_tags(file_id):
    """GET /api/tags/file/<file_id> → 获取文件的标签 + 是否可编辑"""
    tags = get_file_tags(file_id)
    user_id = int(session['user_id'])
    user_role = session.get('user_role', 'member')
    perm = can_edit_file_tags(file_id, user_id, user_role)
    return jsonify({
        'success': True,
        'tags': tags,
        'can_edit': perm['can_edit'],
        'reason': perm.get('reason'),
    })


@tags_bp.route('/file/<int:file_id>', methods=['PUT'])
@api_login_required
def api_update_file_tags(file_id):
    """PUT /api/tags/file/<file_id> → 设置文件的标签（替换式）
    JSON: {"tag_ids": [1, 2, 3]}  或 {"tag_ids": []}
    """
    data = request.get_json(silent=True) or {}
    tag_ids = data.get('tag_ids', [])
    if not isinstance(tag_ids, list):
        return jsonify({
            'success': False,
            'errors': {'tag_ids': ['tag_ids 必须是数组']},
        }), 400

    user_id = int(session['user_id'])
    user_role = session.get('user_role', 'member')
    result = set_file_tags(
        file_id=file_id,
        user_id=user_id,
        tag_ids=tag_ids,
        user_role=user_role,
    )
    if not result['success']:
        status = 403 if 'permission' in result.get('errors', {}) else 400
        return jsonify({'success': False, 'errors': result['errors']}), status
    return jsonify({'success': True, 'tags': result['tags']})
