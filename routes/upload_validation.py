"""上传校验路由蓝图 —— 跨项目拦截 API"""

from flask import Blueprint, jsonify, request, session, abort

from services.upload_validation_service import (
    validate_folder_project,
    ensure_project_folder,
    create_shortcut_record,
)

upload_validation_bp = Blueprint('upload_validation', __name__, url_prefix='/api')


def _require_login():
    if 'user_id' not in session:
        abort(401, '请先登录')


@upload_validation_bp.route('/validate-upload', methods=['POST'])
def api_validate_upload():
    """POST /api/validate-upload → 校验文件归属与文件夹项目是否一致

    JSON body: {"folder_id": N, "project_id": N}
    """
    _require_login()

    data = request.get_json(silent=True) or {}
    folder_id = data.get('folder_id')
    project_id = data.get('project_id')

    if folder_id is None or project_id is None:
        return jsonify({
            'success': False,
            'errors': {'params': ['缺少 folder_id 或 project_id']},
        }), 400

    result = validate_folder_project(int(folder_id), int(project_id))

    if result.get('errors'):
        return jsonify({'success': False, 'errors': result['errors']}), 400

    return jsonify({
        'success': True,
        'match': result['match'],
        'folder_project': result['folder_project'],
        'declared_project': result['declared_project'],
        'folder_name': result['folder_name'],
    })


@upload_validation_bp.route('/projects/<int:project_id>/ensure-folder', methods=['POST'])
def api_ensure_project_folder(project_id):
    """POST /api/projects/<id>/ensure-folder → 确保项目有根文件夹

    Returns:
        {'success': True, 'folder_id': N, 'folder_name': str, 'created': bool}
    """
    _require_login()

    result = ensure_project_folder(project_id, created_by=int(session['user_id']))

    if not result['success']:
        return jsonify({'success': False, 'errors': result['errors']}), 400

    return jsonify({
        'success': True,
        'folder_id': result['folder_id'],
        'folder_name': result['folder_name'],
        'created': result['created'],
    })


@upload_validation_bp.route('/shortcuts', methods=['POST'])
def api_create_shortcut():
    """POST /api/shortcuts → 创建快捷方式引用记录

    JSON body: {"file_id": N, "folder_id": N, "project_id": N}
    """
    _require_login()

    data = request.get_json(silent=True) or {}
    file_id = data.get('file_id')
    folder_id = data.get('folder_id')
    project_id = data.get('project_id')

    if file_id is None or folder_id is None or project_id is None:
        return jsonify({
            'success': False,
            'errors': {'params': ['缺少 file_id / folder_id / project_id']},
        }), 400

    result = create_shortcut_record(
        file_id=int(file_id),
        current_folder_id=int(folder_id),
        declared_project_id=int(project_id),
        user_id=int(session['user_id']),
    )

    if not result['success']:
        return jsonify({'success': False, 'errors': result['errors']}), 400

    return jsonify({
        'success': True,
        'shortcut': result['shortcut'],
    }), 201
