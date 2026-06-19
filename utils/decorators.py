"""权限装饰器：login_required、admin_required"""

from functools import wraps

from flask import session, redirect, url_for, abort


def login_required(f):
    """要求用户已登录，未登录则重定向到 /login

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
    """要求当前用户为 admin 角色

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
