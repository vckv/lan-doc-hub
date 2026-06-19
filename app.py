import os
import secrets
import logging

from flask import Flask, render_template, request, session, abort

from models import db

logger = logging.getLogger('lan_doc_hub')


def create_app(config_overrides=None):
    """创建并配置 Flask 应用

    Args:
        config_overrides: 可选的配置覆盖字典，在 db.create_all() 之前生效
    """
    app = Flask(__name__)
    app.config.from_object('config.Config')
    if config_overrides:
        app.config.update(config_overrides)

    # 初始化数据库
    db.init_app(app)

    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 创建所有数据库表（首次运行自动建表，已存在则跳过）
    with app.app_context():
        db.create_all()

    # ── CSRF 防护（F1-B 新增）──
    @app.before_request
    def csrf_protect():
        """对 POST/PUT/DELETE 请求校验 CSRF Token"""
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return
        token = session.get('csrf_token')
        submitted = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not token or not secrets.compare_digest(token, submitted):
            abort(400, 'CSRF 校验失败，请刷新页面后重试')

    @app.context_processor
    def inject_csrf():
        """向所有模板注入 CSRF Token"""
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        return {'csrf_token': session['csrf_token']}

    @app.context_processor
    def inject_user():
        """向所有模板注入当前登录用户信息"""
        from models import User
        user = None
        if 'user_id' in session:
            try:
                user = db.session.get(User, int(session['user_id']))
            except Exception:
                session.clear()
        return {'current_user': user}

    # ── 全局错误处理器（F1-B 新增）──
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def handle_error(e):
        logger.error('%s %s → %s %s', request.method, request.path, e.code, str(e))
        return render_template('error.html', code=e.code, message=str(e)), e.code

    # ── 注册蓝图 ──
    from routes.bootstrap import bootstrap_bp
    app.register_blueprint(bootstrap_bp)

    from routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    # 注册路由
    register_routes(app)

    return app


def register_routes(app):
    """注册应用路由"""

    @app.route('/')
    def index():
        return render_template('index.html')


if __name__ == '__main__':
    app = create_app()
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
