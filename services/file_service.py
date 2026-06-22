"""文件服务层 —— 编号生成、磁盘存储、记录创建、文件列表查询"""

import os
import uuid
from datetime import datetime, timezone

from werkzeug.utils import secure_filename

from models import db, File, Folder, Project


def generate_file_number():
    """生成文件编号 F-YYYYMMDD-NNN（每日3位原子自增序号）

    策略：查询当日最大序号 + 1，SET NOT NULL 兜底。
    """
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    prefix = f'F-{today}-'

    latest = (
        File.query
        .filter(File.file_number.like(f'{prefix}%'))
        .order_by(File.file_number.desc())
        .first()
    )
    if latest and latest.file_number.startswith(prefix):
        try:
            seq = int(latest.file_number[-3:]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    return f'{prefix}{seq:03d}'


def get_files_by_folder(folder_id):
    """获取某文件夹下的文件列表（含快捷方式标注）

    Args:
        folder_id: 文件夹 ID

    Returns:
        list[dict]
    """
    files = (
        db.session.query(File, Project.model)
        .join(Project, File.project_id == Project.id)
        .filter(File.folder_id == folder_id, File.is_current == True)
        .order_by(File.created_at.desc())
        .all()
    )
    result = []
    for f, model in files:
        result.append({
            'id': f.id,
            'original_filename': f.original_filename,
            'file_number': f.file_number,
            'file_type': f.file_type,
            'file_size': f.file_size,
            'version_number': f.version_number,
            'version_note': f.version_note,
            'project_model': model,
            'is_shortcut': f.is_shortcut,
            'shortcut_target_id': f.shortcut_target_id,
            'uploader_name': f.uploader.display_name if f.uploader else '',
            'uploaded_at': f.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return result


def save_uploaded_file(file_storage, project_id, folder_id, uploader_id,
                       version_number='I', version_note=None):
    """保存上传文件到磁盘并创建 DB 记录

    磁盘路径：uploads/<YYYY>/<MM>/<project_model>_<project_name>/<uuid8>_<safe_name>

    Args:
        file_storage: Flask request.files['file'] (FileStorage 对象)
        project_id:   目标项目 ID
        folder_id:    目标文件夹 ID
        uploader_id:  上传者用户 ID

    Returns:
        {'success': bool, 'file': dict|None, 'errors': dict}
    """
    errors = {}

    # ── 获取项目信息（用于路径） ──
    project = db.session.get(Project, project_id)
    if project is None:
        errors['project_id'] = ['项目不存在']
        return {'success': False, 'file': None, 'errors': errors}

    # ── 文件类型校验 ──
    from flask import current_app
    allowed_ext = current_app.config.get('ALLOWED_EXTENSIONS', set())
    original_name = file_storage.filename or 'unknown'
    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''

    if ext not in allowed_ext:
        errors['file'] = [f'不支持的文件类型 .{ext}']
        return {'success': False, 'file': None, 'errors': errors}

    # ── 文件大小校验（压缩包不限） ──
    archive_exts = current_app.config.get('ARCHIVE_EXTENSIONS', set())
    if ext not in archive_exts:
        max_size = current_app.config.get('SINGLE_FILE_MAX_SIZE', 500 * 1024 * 1024)
        try:
            file_storage.stream.seek(0, 2)
            file_size_bytes = file_storage.stream.tell()
            file_storage.stream.seek(0)
        except (OSError, AttributeError):
            file_size_bytes = 0
        if file_size_bytes > max_size:
            errors['file'] = [
                f'文件大小 {file_size_bytes // (1024*1024)}MB 超过 '
                f'{max_size // (1024*1024)}MB 限制'
            ]
            return {'success': False, 'file': None, 'errors': errors}

    # ── 构建存储路径 ──
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    upload_dir = current_app.config['UPLOAD_FOLDER']
    project_dir_name = f'{project.model}_{project.name}'
    date_path = os.path.join(
        upload_dir, str(now.year),
        f'{now.month:02d}', project_dir_name,
    )
    os.makedirs(date_path, exist_ok=True)

    # ── 磁盘文件名：uuid8前缀防覆盖 ──
    safe_name = secure_filename(original_name)
    uuid_prefix = uuid.uuid4().hex[:8]
    disk_name = f'{uuid_prefix}_{safe_name}'

    disk_path = os.path.join(date_path, disk_name)
    file_storage.save(disk_path)

    # ── 相对路径（相对于 UPLOAD_FOLDER） ──
    rel_path = os.path.relpath(disk_path, upload_dir)

    # ── 文件大小 ──
    file_size = os.path.getsize(disk_path)

    # ── 文件类型分类 ──
    file_type = _classify_file_type(ext, mime=file_storage.mimetype)

    # ── 标记同名同项目旧版本为非当前 ──
    old_files = (
        File.query
        .filter_by(
            original_filename=original_name,
            project_id=project_id,
            is_current=True,
        )
        .all()
    )
    for old in old_files:
        old.is_current = False

    # ── 生成文件编号 ──
    file_number = generate_file_number()

    # ── 原始文件名截断至 64 字符 ──
    max_len = current_app.config.get('FILE_ORIGINAL_NAME_MAX_LENGTH', 64)
    if len(original_name) > max_len:
        name_part, ext_part = os.path.splitext(original_name)
        original_name = name_part[:59] + '...' + ext_part

    # ── 创建 DB 记录 ──
    file_record = File(
        filename=disk_name,
        original_filename=original_name,
        file_path=rel_path,
        file_number=file_number,
        folder_id=folder_id,
        uploader_id=uploader_id,
        project_id=project_id,
        version_number=version_number,
        version_note=version_note,
        file_type=file_type,
        file_size=file_size,
        is_current=True,
        storage_path=rel_path,
    )
    db.session.add(file_record)
    db.session.commit()

    return {
        'success': True,
        'file': {
            'id': file_record.id,
            'original_filename': file_record.original_filename,
            'file_number': file_record.file_number,
            'file_type': file_record.file_type,
            'file_size': file_record.file_size,
            'version_number': 'I',
            'is_shortcut': False,
            'uploader_name': file_record.uploader.display_name if file_record.uploader else '',
            'uploaded_at': file_record.created_at.strftime('%Y-%m-%d %H:%M'),
        },
        'errors': {},
    }


def _classify_file_type(ext, mime=None):
    """根据扩展名 + MIME 类型返回文件类型分类

    ext  文件扩展名（小写，不含点）
    mime MIME 类型字符串（可选）
    """
    mapping = {
        'pdf': 'PDF',
        'doc': 'Word', 'docx': 'Word',
        'xls': 'Excel', 'xlsx': 'Excel', 'xlsm': 'Excel',
        'ppt': 'PowerPoint', 'pptx': 'PowerPoint',
        'txt': 'TXT', 'csv': 'CSV',
        'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image',
        'gif': 'Image', 'bmp': 'Image', 'webp': 'Image',
        'zip': 'Archive', 'rar': 'Archive', '7z': 'Archive',
        'dwg': 'CAD', 'dxf': 'CAD',
    }
    result = mapping.get(ext)
    if result:
        return result

    # MIME 降级判断
    if mime:
        if mime.startswith('image/'):
            return 'Image'
        if mime.startswith('video/'):
            return 'Video'
        if mime.startswith('audio/'):
            return 'Audio'
        if mime.startswith('text/'):
            return 'TXT'

    return 'Other'


# 罗马数字映射（支持 I~X）
_ROMAN_TO_INT = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
                 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10}
_INT_TO_ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V',
                 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X'}


def next_version_number(original_filename, project_id):
    """返回同名文件的下一个版本号（罗马数字）

    检索同一 project 下 original_filename 相同且 is_current=True 的文件的
    最大 version_number，迭代+1。如果没有历史文件，返回 'I'。

    Args:
        original_filename: 原始文件名
        project_id: 项目 ID

    Returns:
        str: 下一个版本号，例如 'IV'
    """
    max_file = (
        File.query
        .filter_by(original_filename=original_filename, project_id=project_id, is_current=True)
        .order_by(File.created_at.desc())
        .first()
    )
    if max_file is None:
        return 'I'

    current_int = _ROMAN_TO_INT.get(max_file.version_number, 1)
    next_int = current_int + 1
    if next_int > 10:
        return 'X'
    return _INT_TO_ROMAN.get(next_int, 'I')


def get_file_version_history(file_id):
    """获取文件的完整版本历史（含当前版本）

    通过 file_id 定位文件，然后用 original_filename + project_id
    查找所有同名同项目文件（包括非当前版本），按时间倒序。

    Returns:
        dict: {current_file: dict, history: list[dict]} 或 None
    """
    current_file = db.session.get(File, file_id)
    if current_file is None:
        return None

    project = db.session.get(Project, current_file.project_id)

    all_versions = (
        File.query
        .filter_by(
            original_filename=current_file.original_filename,
            project_id=current_file.project_id,
        )
        .order_by(File.created_at.desc())
        .all()
    )

    history = []
    for v in all_versions:
        history.append({
            'id': v.id,
            'version_number': v.version_number,
            'version_note': v.version_note or '',
            'file_number': v.file_number,
            'file_size': v.file_size,
            'file_type': v.file_type,
            'is_current': v.is_current,
            'uploader_name': v.uploader.display_name if v.uploader else '',
            'uploaded_at': v.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return {
        'current_file': {
            'id': file_id,
            'original_filename': current_file.original_filename,
            'file_number': current_file.file_number,
            'project_model': project.model if project else '',
            'project_name': project.name if project else '',
        },
        'history': history,
    }
