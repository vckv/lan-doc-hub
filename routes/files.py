"""文件路由蓝图 —— 上传、列表、编号预生成"""

from flask import Blueprint, jsonify, request, session, abort, current_app

from services.file_service import (
    generate_file_number,
    save_uploaded_file,
    get_files_by_folder,
)
from utils.decorators import api_login_required

files_bp = Blueprint('files', __name__, url_prefix='/api/files')


@files_bp.route('/pre-number', methods=['POST'])
@api_login_required
def api_pre_number():
    """POST /api/files/pre-number → 预生成文件编号（供前端弹窗预览）"""
    return jsonify({'success': True, 'file_number': generate_file_number()})


@files_bp.route('/next-version')
@api_login_required
def api_next_version():
    """GET /api/files/next-version?filename=xxx&project_id=yyy → 返回下一个版本号"""
    filename = request.args.get('filename', '').strip()
    project_id = request.args.get('project_id', type=int)

    if not filename or not project_id:
        return jsonify({'success': False, 'errors': {'params': ['缺少 filename 或 project_id']}}), 400

    from services.file_service import next_version_number
    version = next_version_number(filename, project_id)
    return jsonify({'success': True, 'version_number': version})


@files_bp.route('/upload', methods=['POST'])
@api_login_required
def api_upload_file():
    """POST /api/files/upload → 接收文件并存储

    multipart/form-data 字段：
        file       : 文件二进制
        project_id : 归属项目 ID
        folder_id  : 目标文件夹 ID
    """

    if 'file' not in request.files:
        return jsonify({'success': False, 'errors': {'file': ['未选择文件']}}), 400

    file_storage = request.files['file']
    if not file_storage.filename:
        return jsonify({'success': False, 'errors': {'file': ['未选择文件']}}), 400

    project_id = request.form.get('project_id', type=int)
    folder_id = request.form.get('folder_id', type=int)
    version_number = request.form.get('version_number', 'I').strip() or 'I'
    version_note = request.form.get('version_note', '').strip() or None

    # ── F4-1: 标签 ID 列表（逗号分隔）──
    tag_ids_raw = request.form.get('tag_ids', '')
    tag_ids = []
    if tag_ids_raw:
        try:
            tag_ids = [int(x.strip()) for x in tag_ids_raw.split(',') if x.strip()]
        except (ValueError, TypeError):
            pass

    if not project_id or not folder_id:
        return jsonify({
            'success': False,
            'errors': {'params': ['缺少 project_id 或 folder_id']},
        }), 400

    if version_note and len(version_note) > 200:
        version_note = version_note[:200]

    result = save_uploaded_file(
        file_storage=file_storage,
        project_id=project_id,
        folder_id=folder_id,
        uploader_id=int(session['user_id']),
        version_number=version_number,
        version_note=version_note,
        tag_ids=tag_ids,
    )

    if not result['success']:
        return jsonify({'success': False, 'errors': result['errors']}), 400

    return jsonify({'success': True, 'file': result['file']}), 201


@files_bp.route('', methods=['GET'])
@api_login_required
def api_list_files():
    """GET /api/files?folder_id=N → 获取文件夹内文件列表"""

    folder_id = request.args.get('folder_id', type=int)
    if folder_id is None:
        return jsonify({'success': False, 'errors': {'folder_id': ['缺少参数']}}), 400

    files = get_files_by_folder(folder_id)
    return jsonify({'success': True, 'files': files, 'folder_id': folder_id})


@files_bp.route('/<int:file_id>/versions')
@api_login_required
def api_file_versions(file_id):
    """GET /api/files/<id>/versions → 返回文件的所有历史版本"""
    from services.file_service import get_file_version_history
    result = get_file_version_history(file_id)
    if result is None:
        return jsonify({'success': False, 'errors': {'file_id': ['文件不存在']}}), 404
    return jsonify({'success': True, **result})
