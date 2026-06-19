"""项目管理路由蓝图 —— 创建项目（同时创建根文件夹）"""

from flask import Blueprint, jsonify, request, session, abort

from models import db, Project, Folder

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')


def _require_admin():
    if session.get('user_role') != 'admin':
        abort(403, '需要管理员权限')


@projects_bp.route('', methods=['POST'])
def api_create_project():
    """POST /api/projects → 创建项目 + 对应根文件夹

    JSON body: {"model": "PRJ", "name": "项目名称"}
    """
    if 'user_id' not in session:
        abort(401, '请先登录')
    _require_admin()

    data = request.get_json(silent=True) or {}
    model = (data.get('model', '') or '').strip().upper()
    name = (data.get('name', '') or '').strip()

    errors = {}
    if not model:
        errors['model'] = ['项目型号不能为空']
    elif len(model) > 20:
        errors['model'] = ['项目型号最多 20 个字符']
    if not name:
        errors['name'] = ['项目名称不能为空']
    elif len(name) > 30:
        errors['name'] = ['项目名称最多 30 个字符']
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    # 型号和名称唯一性检查
    if Project.query.filter_by(model=model).first():
        errors['model'] = [f'项目型号 {model} 已存在']
    if Project.query.filter_by(name=name).first():
        errors['name'] = [f'项目名称 {name} 已存在']
    if errors:
        return jsonify({'success': False, 'errors': errors}), 409

    try:
        proj = Project(model=model, name=name)
        db.session.add(proj)
        db.session.flush()

        folder = Folder(
            name=f'{model}_{name}',
            is_project_root=True,
            project_id=proj.id,
            parent_id=None,
            created_by=int(session['user_id']),
        )
        db.session.add(folder)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            'success': False,
            'errors': {'_system': ['创建项目失败，请重试']},
        }), 500

    return jsonify({
        'success': True,
        'project': {
            'id': proj.id,
            'model': proj.model,
            'name': proj.name,
        },
        'folder': {
            'id': folder.id,
            'name': folder.name,
            'is_project_root': True,
            'project_id': folder.project_id,
        },
    }), 201
