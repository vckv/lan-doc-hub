"""首次初始化引导端点 —— 创建首个管理员账号"""

from flask import Blueprint, render_template, request, abort

from models import User
from services.user_service import create_user

bootstrap_bp = Blueprint('bootstrap', __name__)


@bootstrap_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """首次初始化引导页 —— 仅在 User 表为空时可访问"""
    if User.query.first() is not None:
        abort(404)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        display_name = request.form.get('display_name', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # 前端二次确认密码一致性
        if password != password_confirm:
            return render_template('setup.html',
                                   error='两次输入的密码不一致，请重新输入')

        result = create_user(
            username=username,
            display_name=display_name,
            password=password,
            role='admin',
            created_by_id=None,
            created_ip=request.remote_addr or '127.0.0.1',
        )

        if result['success']:
            return render_template('setup.html',
                                   success='管理员账号创建成功！请重启应用后使用新账号登录。')

        # 取第一个非空错误信息
        error = ''
        for field_msgs in result['errors'].values():
            if field_msgs:
                error = field_msgs[0]
                break
        return render_template('setup.html', error=error)

    return render_template('setup.html')
