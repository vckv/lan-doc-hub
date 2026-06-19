"""上传校验服务层 —— 跨项目归属检查、自动创建文件夹、快捷方式"""

from models import db, Folder, Project, File


def validate_folder_project(folder_id, declared_project_id):
    """检查文件夹归属项目是否与文件声明的项目一致

    优先直接读取 folder.project_id（create_folder 已逐层复制）。
    若为 None 则递归向上查找（兜底旧数据）。

    Args:
        folder_id:            当前用户选择的上传目标文件夹 ID
        declared_project_id:  文件所声明归属的项目 ID

    Returns:
        {
            'match': bool | None,
            'folder_project':   {'id', 'model', 'name'},
            'declared_project': {'id', 'model', 'name'},
            'folder_name': str,
            'target_folder_id': int | None,
            'errors'?: dict,
        }
    """
    folder = db.session.get(Folder, folder_id)
    if folder is None:
        return {'match': None, 'errors': {'folder_id': ['文件夹不存在']}}

    declared_project = db.session.get(Project, declared_project_id)
    if declared_project is None:
        return {'match': None, 'errors': {'project_id': ['项目不存在']}}

    # 优先直接取字段（O(1)），兜底递归
    folder_project_id = folder.project_id
    if folder_project_id is None:
        folder_project_id = _resolve_folder_project_id(folder)

    folder_project = db.session.get(Project, folder_project_id)

    match = (folder_project_id == declared_project_id)

    return {
        'match': match,
        'folder_project': {
            'id': folder_project.id, 'model': folder_project.model, 'name': folder_project.name,
        } if folder_project else None,
        'declared_project': {
            'id': declared_project.id, 'model': declared_project.model, 'name': declared_project.name,
        },
        'folder_name': folder.name,
        'target_folder_id': folder_id if match else None,
    }


def _resolve_folder_project_id(folder):
    """递归向上查找文件夹的项目归属（兜底旧数据）"""
    if folder.project_id is not None:
        return folder.project_id
    if folder.parent_id is not None:
        parent = db.session.get(Folder, folder.parent_id)
        if parent:
            return _resolve_folder_project_id(parent)
    return None


def ensure_project_folder(project_id, created_by=1):
    """确保项目存在根文件夹，没有则自动创建

    Args:
        project_id: 项目 ID
        created_by: 创建者用户 ID（路由层传入 session['user_id']）

    Returns:
        {'success': bool, 'folder_id': int, 'folder_name': str, 'created': bool, 'errors'?: dict}
    """
    project = db.session.get(Project, project_id)
    if project is None:
        return {'success': False, 'errors': {'project_id': ['项目不存在']}}

    existing = Folder.query.filter_by(project_id=project_id, is_project_root=True).first()
    if existing:
        return {
            'success': True,
            'folder_id': existing.id,
            'folder_name': existing.name,
            'created': False,
        }

    folder_name = f'{project.model}_{project.name}'
    root = Folder(
        name=folder_name,
        is_project_root=True,
        project_id=project_id,
        parent_id=None,
        created_by=created_by,
    )
    db.session.add(root)
    db.session.commit()

    return {
        'success': True,
        'folder_id': root.id,
        'folder_name': folder_name,
        'created': True,
    }


def create_shortcut_record(file_id, current_folder_id, declared_project_id, user_id):
    """在当前位置创建快捷方式引用记录

    快捷方式是一条 is_shortcut=True 的 File 记录，指向真实文件。
    original_filename 格式为 "[来自项目XX] 原文件名"。

    Args:
        file_id:               真实文件的 ID
        current_folder_id:     用户当前所在文件夹（快捷方式位置）
        declared_project_id:   文件声明归属的项目
        user_id:               操作者 ID

    Returns:
        {'success': bool, 'shortcut': dict, 'errors': dict}
    """
    real_file = db.session.get(File, file_id)
    if real_file is None:
        return {'success': False, 'errors': {'file_id': ['文件不存在']}}

    project = db.session.get(Project, declared_project_id)
    project_label = f'{project.model}_{project.name}' if project else f'项目{declared_project_id}'

    shortcut = File(
        filename=real_file.filename,
        original_filename=f'[来自项目{project_label}] {real_file.original_filename}',
        file_path=real_file.file_path,
        file_number=f'SHORTCUT-{real_file.file_number}',
        folder_id=current_folder_id,
        uploader_id=user_id,
        project_id=declared_project_id,
        version_number=real_file.version_number,
        file_type=real_file.file_type,
        file_size=real_file.file_size,
        is_current=True,
        is_shortcut=True,
        shortcut_target_id=file_id,
        storage_path=real_file.storage_path,
    )
    db.session.add(shortcut)
    db.session.commit()

    return {
        'success': True,
        'shortcut': {
            'id': shortcut.id,
            'original_filename': shortcut.original_filename,
            'folder_id': shortcut.folder_id,
            'shortcut_target_id': file_id,
        },
        'errors': {},
    }
