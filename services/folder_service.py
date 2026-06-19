"""文件夹服务层 —— 树形查询、创建、重命名、删除"""

from models import db, Folder


def _build_children(parent_id):
    """递归构建子节点（不包含孙子，只返回直接子节点的 dict 列表）
    
    每个子节点内部再递归调用 _build_children 以构建完整树。
    """
    children = Folder.query.filter_by(parent_id=parent_id).order_by(Folder.name).all()
    result = []
    for child in children:
        result.append({
            'id': child.id,
            'name': child.name,
            'is_project_root': child.is_project_root,
            'project_id': child.project_id,
            'parent_id': child.parent_id,
            'children': _build_children(child.id),
        })
    return result


def get_tree():
    """获取完整文件夹树（顶层 = is_project_root 的文件夹，按名称排序）

    Returns:
        list[dict]: 树形结构，每个节点含 id/name/is_project_root/children
    """
    roots = Folder.query.filter_by(is_project_root=True).order_by(Folder.name).all()
    tree = []
    for root in roots:
        tree.append({
            'id': root.id,
            'name': root.name,
            'is_project_root': True,
            'project_id': root.project_id,
            'parent_id': root.parent_id,
            'children': _build_children(root.id),
        })
    return tree


def create_folder(name, parent_id, user_id):
    """在指定父文件夹下创建子文件夹

    校验：
    - 父文件夹必须存在
    - 名称不能为空
    - 同一父文件夹下不能重名

    Args:
        name:      文件夹名称（1-32 字符）
        parent_id: 父文件夹 ID
        user_id:   创建者 ID

    Returns:
        {'success': bool, 'folder': Folder|None, 'errors': dict}
    """
    errors = {}
    name = (name or '').strip()
    if not name:
        errors['name'] = ['文件夹名称不能为空']
    elif len(name) > 32:
        errors['name'] = ['文件夹名称最多 32 个字符']

    parent = db.session.get(Folder, parent_id)
    if parent is None:
        errors['parent_id'] = ['父文件夹不存在']

    if errors:
        return {'success': False, 'folder': None, 'errors': errors}

    # 同名检测
    existing = Folder.query.filter_by(parent_id=parent_id, name=name).first()
    if existing:
        return {
            'success': False,
            'folder': None,
            'errors': {'name': ['同一父文件夹下已存在同名文件夹']},
        }

    folder = Folder(
        name=name,
        is_project_root=False,
        project_id=parent.project_id,
        parent_id=parent_id,
        created_by=user_id,
    )
    db.session.add(folder)
    db.session.commit()

    return {'success': True, 'folder': folder, 'errors': {}}


def rename_folder(folder_id, new_name):
    """重命名文件夹（is_project_root 不可改名）

    Args:
        folder_id: 文件夹 ID
        new_name:  新名称

    Returns:
        {'success': bool, 'folder': Folder|None, 'errors': dict}
    """
    errors = {}
    folder = db.session.get(Folder, folder_id)
    if folder is None:
        return {
            'success': False,
            'folder': None,
            'errors': {'folder_id': ['文件夹不存在']},
        }

    if folder.is_project_root:
        return {
            'success': False,
            'folder': None,
            'errors': {'name': ['项目根文件夹不可重命名']},
        }

    new_name = (new_name or '').strip()
    if not new_name:
        errors['name'] = ['文件夹名称不能为空']
    elif len(new_name) > 32:
        errors['name'] = ['文件夹名称最多 32 个字符']

    if errors:
        return {'success': False, 'folder': None, 'errors': errors}

    # 同名检测（同一父目录下）
    existing = Folder.query.filter_by(
        parent_id=folder.parent_id, name=new_name
    ).first()
    if existing and existing.id != folder_id:
        return {
            'success': False,
            'folder': None,
            'errors': {'name': ['同一父文件夹下已存在同名文件夹']},
        }

    folder.name = new_name
    db.session.commit()

    return {'success': True, 'folder': folder, 'errors': {}}


def delete_folder(folder_id):
    """递归删除文件夹及其所有子孙（is_project_root 不可删除）

    校验：
    - 文件夹必须存在
    - 项目根文件夹不可删除
    - 所有子孙节点递归删除

    Args:
        folder_id: 文件夹 ID

    Returns:
        {'success': bool, 'errors': dict}
    """
    folder = db.session.get(Folder, folder_id)
    if folder is None:
        return {
            'success': False,
            'errors': {'folder_id': ['文件夹不存在']},
        }

    if folder.is_project_root:
        return {
            'success': False,
            'errors': {'name': ['项目根文件夹不可删除']},
        }

    # 递归收集所有子孙 ID，批量删除
    ids_to_delete = _collect_descendant_ids(folder_id)

    # 倒序删除（叶子先删）
    for fid in reversed(ids_to_delete):
        f = db.session.get(Folder, fid)
        if f:
            db.session.delete(f)
    db.session.commit()

    return {'success': True, 'errors': {}}


def _collect_descendant_ids(folder_id):
    """递归收集子孙文件夹 ID 列表（含自身）"""
    ids = [folder_id]
    children = Folder.query.filter_by(parent_id=folder_id).all()
    for child in children:
        ids.extend(_collect_descendant_ids(child.id))
    return ids


def get_ancestors(folder_id):
    """获取文件夹的祖先链（从根到自身，含自身）

    沿 parent_id 上溯至 is_project_root=True 的节点，
    然后反转数组得到从根到目标文件夹的顺序。

    Returns:
        list[dict]: [{id, name, is_project_root}, ...]，失败返回空列表
    """
    chain = []
    current = db.session.get(Folder, folder_id)
    if current is None:
        return chain

    chain.append({
        'id': current.id,
        'name': current.name,
        'is_project_root': current.is_project_root,
    })

    # 沿 parent_id 上溯
    while current.parent_id is not None:
        current = db.session.get(Folder, current.parent_id)
        if current is None:
            break
        chain.append({
            'id': current.id,
            'name': current.name,
            'is_project_root': current.is_project_root,
        })

    chain.reverse()  # 从根到目标
    return chain
