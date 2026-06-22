"""文件夹路由蓝图 —— JSON API：树形查询、创建、重命名、删除"""

from flask import Blueprint, jsonify, request, session, abort

from services.folder_service import (
    get_tree,
    create_folder,
    rename_folder,
    delete_folder,
    get_ancestors,
)
from utils.decorators import api_login_required, api_admin_required

folders_bp = Blueprint('folders', __name__, url_prefix='/api/folders')


@folders_bp.route('/tree')
@api_login_required
def api_get_tree():
    """GET /api/folders/tree → 返回完整文件夹树 JSON"""
    tree = get_tree()
    return jsonify({'success': True, 'tree': tree})


@folders_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_folder():
    """POST /api/folders → 创建子文件夹

    JSON body: {"name": "...", "parent_id": N}
    """
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    parent_id = data.get('parent_id')

    if parent_id is None:
        return jsonify({'success': False, 'errors': {'parent_id': ['缺少父文件夹 ID']}}), 400

    result = create_folder(
        name=name,
        parent_id=int(parent_id),
        user_id=int(session['user_id']),
    )

    if not result['success']:
        return jsonify({'success': False, 'errors': result['errors']}), 400

    f = result['folder']
    return jsonify({
        'success': True,
        'folder': {
            'id': f.id,
            'name': f.name,
            'is_project_root': f.is_project_root,
            'project_id': f.project_id,
            'parent_id': f.parent_id,
        },
    }), 201


@folders_bp.route('/<int:folder_id>', methods=['PUT'])
@api_login_required
@api_admin_required
def api_rename_folder(folder_id):
    """PUT /api/folders/<id> → 重命名文件夹

    JSON body: {"name": "新名称"}
    """
    data = request.get_json(silent=True) or {}
    new_name = data.get('name', '')

    result = rename_folder(folder_id, new_name)

    if not result['success']:
        status = 403 if '项目根文件夹' in str(result['errors']) else 400
        return jsonify({'success': False, 'errors': result['errors']}), status

    f = result['folder']
    return jsonify({
        'success': True,
        'folder': {
            'id': f.id,
            'name': f.name,
            'is_project_root': f.is_project_root,
        },
    })


@folders_bp.route('/<int:folder_id>', methods=['DELETE'])
@api_login_required
@api_admin_required
def api_delete_folder(folder_id):
    """DELETE /api/folders/<id> → 递归删除文件夹"""
    result = delete_folder(folder_id)

    if not result['success']:
        status = 403 if '项目根文件夹' in str(result['errors']) else 404
        return jsonify({'success': False, 'errors': result['errors']}), status

    return jsonify({'success': True})


@folders_bp.route('/<int:folder_id>/ancestors')
@api_login_required
def api_get_ancestors(folder_id):
    """GET /api/folders/<id>/ancestors → 返回祖先链（从根到自身）"""
    ancestors = get_ancestors(folder_id)

    if not ancestors:
        return jsonify({'success': False, 'errors': {'folder_id': ['文件夹不存在']}}), 404

    return jsonify({'success': True, 'ancestors': ancestors})
