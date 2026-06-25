"""项目管理路由蓝图 —— 创建项目（同时创建根文件夹）+ suggest 自动补全"""

from flask import Blueprint, jsonify, request, session

from services.project_service import create_project_with_root, suggest_projects
from utils.decorators import api_login_required, api_admin_required

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')


@projects_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_project():
    """POST /api/projects → 创建项目 + 对应根文件夹

    JSON body: {"model": "PRJ", "name": "项目名称"}
    """
    data = request.get_json(silent=True) or {}
    result = create_project_with_root(
        model=data.get('model', ''),
        name=data.get('name', ''),
        created_by=int(session['user_id']),
    )

    if not result['success']:
        err_msg = str(result['errors'])
        status = 409 if '已存在' in err_msg else 400
        return jsonify({'success': False, 'errors': result['errors']}), status

    return jsonify({
        'success': True,
        'project': result['project'],
        'folder': result['folder'],
    }), 201


@projects_bp.route('/suggest', methods=['GET'])
@api_login_required
def api_suggest_projects():
    """GET /api/projects/suggest?q=xxx → 按型号/名称模糊搜索项目

    Query params:
        q: 搜索关键字（必填）
    """
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'success': True, 'projects': []})

    results = suggest_projects(q, limit=10)
    return jsonify({'success': True, 'projects': results})
