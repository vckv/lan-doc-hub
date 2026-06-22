"""权限装饰器：login_required、admin_required（页面视图用）、api_login_required、api_admin_required（JSON API 用）"""

from functools import wraps

from flask import session, redirect, url_for, abort


def login_required(f):
    """要求用户已登录，未登录则重定向到 /login（页面视图用）

    用法:
        @app.route('/protected')
        @login_required
        def protected():
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """要求当前用户为 admin 角色（页面视图用）

    用法:
        @app.route('/admin/users')
        @login_required
        @admin_required
        def admin_users():
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            abort(403, '需要管理员权限')
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    """JSON API 用：未登录返回 401"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            abort(401, '请先登录')
        return f(*args, **kwargs)
    return decorated


def api_admin_required(f):
    """JSON API 用：非管理员返回 403"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            abort(403, '需要管理员权限')
        return f(*args, **kwargs)
    return decorated
