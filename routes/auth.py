"""认证路由蓝图 —— 登录 / 登出"""

from flask import Blueprint, render_template, request, session, redirect, url_for

from services.auth_service import authenticate_user
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    # ── 已登录用户直接跳转首页 ──
    if 'user_id' in session:
        return redirect(url_for('index'))

    # ── 自动检测是否需要初始化 ──
    if User.query.first() is None:
        return redirect(url_for('bootstrap.setup'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('login.html',
                                   error='请输入用户名和密码')

        result = authenticate_user(
            username=username,
            password=password,
            ip_address=request.remote_addr or '127.0.0.1',
        )

        if result['success']:
            user = result['user']
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.display_name
            session['user_role'] = user.role
            return redirect(url_for('index'))

        # 取第一个错误信息
        error = ''
        for field_msgs in result['errors'].values():
            if field_msgs:
                error = field_msgs[0]
                break
        return render_template('login.html', error=error)

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('auth.login'))
