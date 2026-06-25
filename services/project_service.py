"""项目服务层 —— 创建项目（含根文件夹）"""

from models import db, Project, Folder


def create_project_with_root(model: str, name: str, created_by: int):
    """创建项目并同步创建根文件夹

    Args:
        model: 项目型号（如 PRJ001），最长 20 字符
        name:  项目名称，最长 30 字符
        created_by: 创建者用户 ID

    Returns:
        {'success': bool, 'project': dict|None, 'folder': dict|None, 'errors': dict}
    """
    errors = {}
    model = (model or '').strip().upper()
    name = (name or '').strip()

    if not model:
        errors['model'] = ['项目型号不能为空']
    elif len(model) > 20:
        errors['model'] = ['项目型号最多 20 个字符']

    if not name:
        errors['name'] = ['项目名称不能为空']
    elif len(name) > 30:
        errors['name'] = ['项目名称最多 30 个字符']

    if not errors:
        if Project.query.filter_by(model=model).first():
            errors['model'] = [f'项目型号 {model} 已存在']
        if Project.query.filter_by(name=name).first():
            errors['name'] = [f'项目名称 {name} 已存在']

    if errors:
        return {'success': False, 'project': None, 'folder': None, 'errors': errors}

    try:
        proj = Project(model=model, name=name)
        db.session.add(proj)
        db.session.flush()

        folder = Folder(
            name=f'{model}_{name}',
            is_project_root=True,
            project_id=proj.id,
            parent_id=None,
            created_by=created_by,
        )
        db.session.add(folder)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {
            'success': False,
            'project': None, 'folder': None,
            'errors': {'_system': ['创建项目失败，请重试']},
        }

    return {
        'success': True,
        'project': {'id': proj.id, 'model': proj.model, 'name': proj.name},
        'folder': {'id': folder.id, 'name': folder.name,
                   'is_project_root': True, 'project_id': folder.project_id},
        'errors': {},
    }


def suggest_projects(query: str, limit: int = 10):
    """按项目型号或名称模糊匹配

    Args:
        query: 用户输入的关键字（型号或名称，大小写不敏感）
        limit: 最多返回条数，默认 10

    Returns:
        list[dict]: [{id, model, name, display}, ...]
        display 格式为 "model - name"
    """
    q = (query or '').strip()
    if not q:
        return []

    pattern = f'%{q}%'
    results = (
        Project.query
        .filter(
            db.or_(
                Project.model.ilike(pattern),
                Project.name.ilike(pattern),
            )
        )
        .order_by(Project.model)
        .limit(limit)
        .all()
    )
    return [
        {
            'id': p.id,
            'model': p.model,
            'name': p.name,
            'display': f'{p.model} - {p.name}',
        }
        for p in results
    ]
