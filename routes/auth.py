"""认证路由蓝图 —— 登录 / 登出"""

import traceback

from flask import Blueprint, render_template, request, session, redirect, url_for

from services.auth_service import authenticate_user, LoginContext
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
                                   username=username,
                                   error='请输入用户名和密码')

        # ── 从 session 恢复或新建登录上下文 ──
        ctx = LoginContext(
            last_username=session.get('login_last_username', ''),
            last_password=session.get('login_last_password', ''),
            same_count=session.get('login_same_count', 0),
        )
        hint_case = ctx.track(username, password)
        session['login_last_username'] = ctx.last_username
        session['login_last_password'] = ctx.last_password
        session['login_same_count'] = ctx.same_count

        try:
            result = authenticate_user(
                username=username,
                password=password,
                ip_address=request.remote_addr or '127.0.0.1',
            )
        except Exception as exc:
            from flask import current_app
            current_app.logger.error(
                'authenticate_user 异常 — %s: %s\n%s',
                type(exc).__name__, str(exc), traceback.format_exc()
            )
            return render_template(
                'login.html',
                username=username,
                error=f'系统错误：{type(exc).__name__} — {exc}。请查看控制台获取详细信息。',
            )

        if result['success']:
            user = result['user']
            # ── 登录成功，清理追踪数据 ──
            session.pop('login_last_username', None)
            session.pop('login_last_password', None)
            session.pop('login_same_count', None)
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.display_name
            session['user_role'] = user.role
            return redirect(url_for('index'))

        # ── 构造错误消息 ──
        error_type = result['errors'].get('error_type', '')
        message = result['errors'].get('message', '用户名或密码错误')

        if error_type == 'wrong_password' and hint_case:
            message = '密码错误，请确认大小写后输入'

        return render_template('login.html', username=username, error=message)

    return render_template('login.html',
                           username=request.args.get('username', ''))


@auth_bp.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('auth.login'))
