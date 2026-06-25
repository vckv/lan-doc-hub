"""文件路由蓝图 —— 上传、列表、编号预生成"""

from flask import Blueprint, jsonify, request, session, abort, current_app

from models import File
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


@files_bp.route('/check-duplicate')
@api_login_required
def api_check_duplicate():
    """GET /api/files/check-duplicate?filename=xxx&project_id=yyy
    → 检测目标项目中是否存在同名当前版本文件"""
    filename = request.args.get('filename', '').strip()
    project_id = request.args.get('project_id', type=int)

    if not filename or not project_id:
        return jsonify({
            'success': False,
            'errors': {'params': ['缺少 filename 或 project_id']},
        }), 400

    existing = (
        File.query
        .filter_by(
            original_filename=filename,
            project_id=project_id,
            is_current=True,
        )
        .first()
    )

    if not existing:
        return jsonify({'success': True, 'exists': False})

    return jsonify({
        'success': True,
        'exists': True,
        'existing_file': {
            'id': existing.id,
            'original_filename': existing.original_filename,
            'file_number': existing.file_number,
            'version_number': existing.version_number,
            'file_size': existing.file_size,
            'file_type': existing.file_type,
            'folder_id': existing.folder_id,
            'uploader_name': existing.uploader.display_name if existing.uploader else '',
            'uploaded_at': existing.created_at.strftime('%Y-%m-%d %H:%M'),
        },
    })


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

    # ── F5-1: 同名文件处理参数 ──
    duplicate_action = request.form.get('duplicate_action', '').strip() or None
    new_filename = request.form.get('new_filename', '').strip() or None

    # 参数校验
    if duplicate_action and duplicate_action not in ('override', 'save_as_new'):
        return jsonify({
            'success': False,
            'errors': {'duplicate_action': ['无效的操作']},
        }), 400

    if duplicate_action == 'save_as_new' and not new_filename:
        return jsonify({
            'success': False,
            'errors': {'new_filename': ['缺少新文件名']},
        }), 400

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
        duplicate_action=duplicate_action,
        new_filename=new_filename,
    )

    if not result['success']:
        return jsonify({'success': False, 'errors': result['errors']}), 400

    return jsonify({'success': True, 'file': result['file']}), 201


@files_bp.route('', methods=['GET'])
@api_login_required
def api_list_files():
    """GET /api/files?folder_id=N&page=1&per_page=20&sort_by=created_at&sort_order=asc"""

    folder_id = request.args.get('folder_id', type=int)
    if folder_id is None:
        return jsonify({'success': False, 'errors': {'folder_id': ['缺少参数']}}), 400

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = max(1, min(per_page, 100))  # 限制每页最大 100 条

    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'asc')

    data = get_files_by_folder(folder_id, page=page, per_page=per_page,
                               sort_by=sort_by, sort_order=sort_order)
    return jsonify({'success': True, **data})


@files_bp.route('/<int:file_id>/versions')
@api_login_required
def api_file_versions(file_id):
    """GET /api/files/<id>/versions → 返回文件的所有历史版本"""
    from services.file_service import get_file_version_history
    result = get_file_version_history(file_id)
    if result is None:
        return jsonify({'success': False, 'errors': {'file_id': ['文件不存在']}}), 404
    return jsonify({'success': True, **result})
