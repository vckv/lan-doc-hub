"""项目管理路由蓝图 —— 创建项目（同时创建根文件夹）"""

from flask import Blueprint, jsonify, request, session

from services.project_service import create_project_with_root
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
