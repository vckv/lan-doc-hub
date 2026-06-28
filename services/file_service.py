"""文件服务层 —— 编号生成、磁盘存储、记录创建、文件列表查询"""

import os
import uuid
from datetime import datetime, timezone

from werkzeug.utils import secure_filename

from models import db, File, FileVersion, Folder, Project, FileTag, Tag, User


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


# 排序白名单映射: 前端 sort_by 值 → SQLAlchemy 列对象
_SORT_COLUMNS = {
    'created_at': File.created_at,
    'file_type': File.file_type,
    'original_filename': File.original_filename,
    'file_size': File.file_size,
    'version_number': File.version_number,
    'model': Project.model,
    'uploader_name': User.display_name,
}


def get_files_by_folder(folder_id, page=1, per_page=20, sort_by='created_at', sort_order='asc'):
    """获取某文件夹下的文件列表（含快捷方式标注、标签信息，分页+排序支持）

    Args:
        folder_id: 文件夹 ID
        page: 页码（从 1 开始，默认 1）
        per_page: 每页条数（默认 20）
        sort_by: 排序字段（默认 created_at）
        sort_order: 排序方向（asc/desc，默认 asc）

    Returns:
        dict: {files, total, page, pages, sort_by, sort_order}
    """
    # 计算总数
    total = (
        db.session.query(File.id)
        .filter(File.folder_id == folder_id, File.is_current == True)
        .count()
    )
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))

    # 映射排序字段，非法值回退到默认
    sort_column = _SORT_COLUMNS.get(sort_by, File.created_at)
    sort_order_val = sort_order.lower() if sort_order.lower() in ('asc', 'desc') else 'asc'

    offset = (page - 1) * per_page

    # 构建查询
    query = (
        db.session.query(File, Project.model)
        .join(Project, File.project_id == Project.id)
    )

    # 按上传者排序时需要 JOIN User 表
    if sort_by == 'uploader_name':
        query = query.outerjoin(User, File.uploader_id == User.id)

    query = query.filter(File.folder_id == folder_id, File.is_current == True)
    query = query.order_by(sort_column.asc() if sort_order_val == 'asc' else sort_column.desc())
    files = query.limit(per_page).offset(offset).all()

    # F5-2: 批量检测每个文件是否有历史版本
    file_keys = list({(f.original_filename, f.project_id) for f, _ in files})
    has_history_set = set()
    if file_keys:
        from sqlalchemy import and_, or_
        conditions = [
            and_(
                File.original_filename == fn,
                File.project_id == pid,
                File.is_current == False,
            )
            for fn, pid in file_keys
        ]
        if conditions:
            non_current = (
                db.session.query(File.original_filename, File.project_id)
                .filter(or_(*conditions))
                .all()
            )
            has_history_set = {(fn, pid) for fn, pid in non_current}

    result = []
    for f, model in files:
        tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in f.tags]
        has_versions = (f.original_filename, f.project_id) in has_history_set
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
            'has_versions': has_versions,  # F5-2
            'tags': tags,
        })
    return {'files': result, 'total': total, 'page': page, 'pages': pages,
            'sort_by': sort_by, 'sort_order': sort_order_val}


def _archive_existing_file(original_filename, project_id, uploader_id):
    """F5-1: 将同名同项目当前版本归档到 file_versions 表。

    对每个 original_filename + project_id 匹配且 is_current=True 的文件：
    1. 创建 FileVersion 记录（保留版本号、备注、路径、大小）
    2. 将 is_current 标记为 False

    注意：此函数不执行 commit，由外层 save_uploaded_file 统一提交。
    """
    old_files = (
        File.query
        .filter_by(
            original_filename=original_filename,
            project_id=project_id,
            is_current=True,
        )
        .all()
    )

    for old in old_files:
        version = FileVersion(
            file_id=old.id,
            version_number=old.version_number,
            version_note=old.version_note,
            file_path=old.file_path,
            file_size=old.file_size,
            uploaded_by=uploader_id,
        )
        db.session.add(version)
        old.is_current = False


def save_uploaded_file(file_storage, project_id, folder_id, uploader_id,
                       version_number='I', version_note=None, tag_ids=None,
                       duplicate_action=None, new_filename=None):
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

    # ── F5-1: 同名文件处理（须在磁盘保存前执行）──
    if duplicate_action == 'override':
        version_number = next_version_number(original_name, project_id)
        _archive_existing_file(original_name, project_id, uploader_id)

    if duplicate_action == 'save_as_new' and new_filename:
        original_name = new_filename

    file_storage.save(disk_path)

    # ── 相对路径（相对于 UPLOAD_FOLDER） ──
    rel_path = os.path.relpath(disk_path, upload_dir)

    # ── 文件大小 ──
    file_size = os.path.getsize(disk_path)

    # ── 文件类型分类 ──
    file_type = _classify_file_type(ext, mime=file_storage.mimetype)

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

    # ── 绑定标签（仅绑定真实存在的 tag_id）──
    if tag_ids:
        existing_ids = {t.id for t in Tag.query.filter(Tag.id.in_(tag_ids)).all()}
        for tid in tag_ids:
            if tid in existing_ids:
                db.session.add(FileTag(file_id=file_record.id, tag_id=tid))

    db.session.commit()

    return {
        'success': True,
        'file': {
            'id': file_record.id,
            'original_filename': file_record.original_filename,
            'file_number': file_record.file_number,
            'file_type': file_record.file_type,
            'file_size': file_record.file_size,
            'version_number': version_number,
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
        'txt': 'TXT', 'csv': 'CSV', 'md': 'Markdown',
        'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image',
        'gif': 'Image', 'bmp': 'Image', 'webp': 'Image', 'svg': 'Image',
        'mp4': 'Video', 'avi': 'Video', 'mov': 'Video', 'webm': 'Video',
        'mp3': 'Audio', 'wav': 'Audio', 'flac': 'Audio',
        'zip': 'Archive', 'rar': 'Archive', '7z': 'Archive',
        'tar': 'Archive', 'gz': 'Archive', 'bz2': 'Archive',
        'dwg': 'CAD', 'dxf': 'CAD',
        'py': 'Code', 'js': 'Code', 'ts': 'Code', 'html': 'Code',
        'css': 'Code', 'java': 'Code', 'cpp': 'Code', 'c': 'Code',
        'go': 'Code', 'rs': 'Code', 'sql': 'Code', 'sh': 'Code',
        'yaml': 'Code', 'yml': 'Code', 'json': 'Code', 'xml': 'Code',
        'ini': 'Code', 'cfg': 'Code', 'toml': 'Code',
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


# ── F6-2 在线预览 ──


def _format_file_size(size_bytes):
    if size_bytes is None or size_bytes < 0:
        return '0 B'
    if size_bytes < 1024:
        return f'{size_bytes} B'
    if size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.1f} KB'
    if size_bytes < 1024 * 1024 * 1024:
        return f'{size_bytes / (1024 * 1024):.1f} MB'
    return f'{size_bytes / (1024 * 1024 * 1024):.2f} GB'


def get_preview_data(file_id):
    """获取文件预览数据（缓存包装器）

    Image/PDF 直接返回（无需解析），其他类型委托给 _compute_preview_data（LRU 缓存）。

    Args:
        file_id: 文件 ID

    Returns:
        dict: {'success': bool, 'filename': str, ...}
    """
    from flask import current_app
    from sqlalchemy.orm import selectinload

    file_record = db.session.execute(
        db.select(File)
        .options(
            selectinload(File.tags),
            selectinload(File.uploader),
            selectinload(File.project),
        )
        .where(File.id == file_id)
    ).scalar_one_or_none()
    if file_record is None:
        return {'success': False, 'errors': {'file_id': ['文件不存在']}}

    disk_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_record.file_path)
    if not os.path.isfile(disk_path):
        return {'success': False, 'errors': {'file': ['磁盘文件丢失']}}

    ft = file_record.file_type
    filename = file_record.original_filename

    tags_data = [{'name': t.name, 'color': t.color} for t in file_record.tags]
    metadata = {
        'file_size': _format_file_size(file_record.file_size),
        'file_type': ft,
        'file_number': file_record.file_number,
        'version_number': file_record.version_number,
        'version_note': file_record.version_note or '',
        'created_at': file_record.created_at.strftime('%Y-%m-%d %H:%M') if file_record.created_at else '',
        'uploader_name': file_record.uploader.display_name if file_record.uploader else '',
        'project_model': file_record.project.model if file_record.project else '',
        'project_name': file_record.project.name if file_record.project else '',
        'tags': tags_data,
    }

    if ft == 'Image':
        return {
            'success': True, 'type': 'image',
            'image_url': f'/api/files/{file_id}/stream',
            'filename': filename, **metadata,
        }

    if ft == 'PDF':
        return {
            'success': True, 'type': 'stream',
            'stream_url': f'/api/files/{file_id}/stream',
            'filename': filename, **metadata,
        }

    result = _compute_preview_data(file_id, file_record.file_path, ft, filename, disk_path)
    if result is None:
        return {'success': False, 'errors': {'file': ['不支持该文件类型的预览']}}
    result['success'] = True
    result['filename'] = filename
    result['file_type'] = ft
    result.update(metadata)
    return result


from functools import lru_cache


@lru_cache(maxsize=128)
def _compute_preview_data(file_id, file_path, ft, filename, disk_path):
    """实际的预览数据计算，受 LRU 缓存保护。
    (file_id, file_path) 构成缓存 key — 文件版本更新时 file_path 变化，缓存自动失效。
    """
    import csv as csv_module

    if ft == 'TXT' or ft == 'Code' or ft == 'Markdown':
        content = None
        encoding = 'utf-8'
        for enc in ('utf-8', 'gbk', 'latin-1'):
            try:
                with open(disk_path, 'r', encoding=enc) as fh:
                    content = fh.read()
                encoding = enc
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if content is None:
            with open(disk_path, 'r', encoding='utf-8', errors='replace') as fh:
                content = fh.read()
            encoding = 'utf-8 (fallback)'
        max_chars = 50000
        if len(content) > max_chars:
            content = content[:max_chars] + '\n\n... (内容过长，已截断)'
        return {'type': 'text', 'content': content, 'encoding': encoding}

    if ft == 'CSV':
        try:
            with open(disk_path, 'r', encoding='utf-8-sig', errors='replace') as fh:
                reader = csv_module.reader(fh)
                rows = list(reader)
            if not rows:
                return {'type': 'csv', 'headers': [], 'rows': []}
            headers = rows[0]
            data_rows = rows[1:]
            headers = headers[:50]
            data_rows = [row[:50] for row in data_rows[:500]]
            return {'type': 'csv', 'headers': headers, 'rows': data_rows}
        except Exception:
            return {'type': 'text', 'content': '(无法解析 CSV 文件)', 'encoding': 'utf-8'}

    if ft == 'Word':
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.doc':
            return {
                'type': 'html',
                'content': '<div class="preview-unsupported"><p>.doc 格式暂不支持在线预览</p><p>请下载后使用 Word 打开</p></div>',
            }
        try:
            from docx import Document
            doc = Document(disk_path)

            body = doc.element.body
            elements = []
            for child in body:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag == 'p':
                    elements.append(('para', child))
                elif tag == 'tbl':
                    elements.append(('table', child))

            element_to_para = {}
            for p in doc.paragraphs:
                element_to_para[p._element] = p

            html_parts = []
            para_count = 0
            table_count = 0
            max_paras = 500
            max_tables = 50

            for el_type, el in elements:
                if el_type == 'para':
                    if para_count >= max_paras:
                        continue
                    para_count += 1
                    para = element_to_para.get(el)
                    if para is None:
                        continue
                    runs_html = []
                    for run in para.runs:
                        text = run.text
                        if not text:
                            continue
                        text = _html_escape(text)
                        if run.font.bold and run.font.italic:
                            text = f'<strong><em>{text}</em></strong>'
                        elif run.font.bold:
                            text = f'<strong>{text}</strong>'
                        elif run.font.italic:
                            text = f'<em>{text}</em>'
                        runs_html.append(text)
                    full_text = ''.join(runs_html)
                    if not full_text:
                        html_parts.append('<p>&nbsp;</p>')
                    elif para.style and para.style.name and para.style.name.startswith('Heading'):
                        level = para.style.name.split()[-1]
                        try:
                            lv = int(level)
                            tag = f'h{min(lv, 6)}'
                        except ValueError:
                            tag = 'p'
                        html_parts.append(f'<{tag}>{full_text}</{tag}>')
                    else:
                        html_parts.append(f'<p>{full_text}</p>')

                elif el_type == 'table':
                    if table_count >= max_tables:
                        continue
                    table_count += 1
                    from docx.oxml.ns import qn
                    tbl = ['<table class="preview-csv-table"><tbody>']
                    for row_el in el.findall(qn('w:tr')):
                        tbl.append('<tr>')
                        for cell_el in row_el.findall(qn('w:tc')):
                            cell_text = ''
                            for p_el in cell_el.findall(qn('w:p')):
                                for t_el in p_el.iter(qn('w:t')):
                                    if t_el.text:
                                        cell_text += t_el.text
                            cell_text = _html_escape(cell_text.strip())
                            tbl.append(f'<td>{cell_text or "&nbsp;"}</td>')
                        tbl.append('</tr>')
                    tbl.append('</tbody></table>')
                    html_parts.append(''.join(tbl))

            if para_count >= max_paras or table_count >= max_tables:
                html_parts.append('<p class="preview-unsupported">预览内容已截断，仅显示部分内容。完整内容请下载后查看。</p>')

            content = '<div class="preview-word">' + ''.join(html_parts) + '</div>'
            return {'type': 'html', 'content': content}
        except Exception:
            return {'type': 'text', 'content': '(无法解析 Word 文档，请下载后查看)', 'encoding': 'utf-8'}

    if ft == 'Excel':
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext == '.xls':
                import xlrd
                wb = xlrd.open_workbook(disk_path)
                sheet_names = wb.sheet_names()
                sheets_html = []
                for idx, name in enumerate(sheet_names):
                    if idx >= 20:
                        break
                    sh = wb.sheet_by_index(idx)
                    nrows = min(sh.nrows, 200)
                    ncols = min(sh.ncols, 50)
                    tbl = ['<table class="preview-csv-table"><thead><tr>']
                    for c in range(ncols):
                        val = str(sh.cell_value(0, c) if nrows > 0 else '')
                        tbl.append(f'<th>{_html_escape(val)}</th>')
                    tbl.append('</tr></thead><tbody>')
                    for r in range(1, nrows):
                        tbl.append('<tr>')
                        for c in range(ncols):
                            val = str(sh.cell_value(r, c))
                            tbl.append(f'<td>{_html_escape(val)}</td>')
                        tbl.append('</tr>')
                    tbl.append('</tbody></table>')
                    sheets_html.append(
                        f'<div class="preview-sheet"><h5>Sheet: {_html_escape(name)}</h5>{"".join(tbl)}</div>'
                    )
                content = '<div class="preview-excel">' + ''.join(sheets_html) + '</div>'
            else:
                import openpyxl
                wb = openpyxl.load_workbook(disk_path, read_only=True, data_only=True)
                sheets_html = []
                for idx, name in enumerate(wb.sheetnames):
                    if idx >= 20:
                        break
                    sh = wb[name]
                    rows_list = list(sh.iter_rows(max_row=200, max_col=50, values_only=True))
                    if not rows_list:
                        continue
                    tbl = ['<table class="preview-csv-table"><thead><tr>']
                    for cell in rows_list[0]:
                        val = str(cell) if cell is not None else ''
                        tbl.append(f'<th>{_html_escape(val)}</th>')
                    tbl.append('</tr></thead><tbody>')
                    for row in rows_list[1:]:
                        tbl.append('<tr>')
                        for cell in row:
                            val = str(cell) if cell is not None else ''
                            tbl.append(f'<td>{_html_escape(val)}</td>')
                        tbl.append('</tr>')
                    tbl.append('</tbody></table>')
                    sheets_html.append(
                        f'<div class="preview-sheet"><h5>Sheet: {_html_escape(name)}</h5>{"".join(tbl)}</div>'
                    )
                content = '<div class="preview-excel">' + ''.join(sheets_html) + '</div>'
                wb.close()
            return {'type': 'html', 'content': content}
        except Exception:
            return {'type': 'text', 'content': '(无法解析 Excel 文档，请下载后查看)', 'encoding': 'utf-8'}

    if ft == 'PowerPoint':
        try:
            from pptx import Presentation
            prs = Presentation(disk_path)
            slides_html = []
            for idx, slide in enumerate(prs.slides):
                if idx >= 30:
                    break
                texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            t = para.text.strip()
                            if t:
                                texts.append(f'<p>{_html_escape(t)}</p>')
                slides_html.append(
                    f'<div class="preview-slide"><h5>第 {idx + 1} 页</h5>{"".join(texts)}</div>'
                )
            content = '<div class="preview-pptx">' + ''.join(slides_html) + '</div>'
            return {'type': 'html', 'content': content}
        except Exception:
            return {'type': 'text', 'content': '(无法解析 PPT 文档，请下载后查看)', 'encoding': 'utf-8'}

    return None


def _html_escape(text):
    """HTML 转义辅助函数"""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
