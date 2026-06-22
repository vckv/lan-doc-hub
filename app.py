import os
import sys
import secrets
import logging
import traceback

from flask import Flask, render_template, request, session, abort, redirect, url_for, jsonify

from models import db as model_db

logger = logging.getLogger('lan_doc_hub')


def _ensure_setup_key(app):
    """读取或生成 setup 密钥（方案 B）

    逻辑：
    1. 如果 .setup_key 文件已存在 → 读取并打印到控制台
    2. 如果不存在 → 随机生成 32 字符 hex 密钥 → 写入文件 → 打印到控制台
    3. 读写失败时捕获异常，打印警告但不阻止应用启动
    """
    key_file = app.config.get('SETUP_KEY_FILE', '')
    if not key_file:
        return

    # ── 尝试读取已有密钥 ──
    try:
        if os.path.exists(key_file):
            with open(key_file, 'r', encoding='utf-8') as f:
                key = f.read().strip()
            print('\n' + '=' * 60, file=sys.stderr)
            print('  [Setup 密钥] 已从文件加载：', key, file=sys.stderr)
            print('  请妥善保管，创建管理员账号时需要此密钥。', file=sys.stderr)
            print('=' * 60 + '\n', file=sys.stderr)
            return
    except OSError as e:
        print('\n' + '=' * 60, file=sys.stderr)
        print('  [警告] 无法读取 .setup_key 文件：', str(e), file=sys.stderr)
        print('  将生成新密钥。', file=sys.stderr)
        print('=' * 60 + '\n', file=sys.stderr)

    # ── 生成新密钥 ──
    key = secrets.token_hex(16)

    try:
        with open(key_file, 'w', encoding='utf-8') as f:
            f.write(key)
        print('\n' + '=' * 60, file=sys.stderr)
        print('  [Setup 密钥] 已生成并保存到 .setup_key', file=sys.stderr)
        print('  密钥：', key, file=sys.stderr)
        print('  请复制此密钥，创建管理员账号时需要输入。', file=sys.stderr)
        print('=' * 60 + '\n', file=sys.stderr)
    except OSError as e:
        # 密钥无法持久化，仅在控制台显示（本次运行有效）
        print('\n' + '!' * 60, file=sys.stderr)
        print('  [错误] 无法保存 .setup_key 文件：', str(e), file=sys.stderr)
        print('  密钥仅本次运行有效，重启后将无法使用。', file=sys.stderr)
        print('  [Setup 密钥]：', key, file=sys.stderr)
        print('  请立即复制此密钥，创建管理员账号。', file=sys.stderr)
        print('!' * 60 + '\n', file=sys.stderr)


def _is_local_request():
    """判断当前请求是否来自本机"""
    remote_addr = request.remote_addr or ''
    return remote_addr in ('127.0.0.1', '::1', 'localhost')


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
    model_db.init_app(app)

    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 创建所有数据库表（首次运行自动建表，已存在则跳过）
    with app.app_context():
        model_db.create_all()

    # ── 生成/读取 setup 密钥（方案 B：控制台打印）──
    _ensure_setup_key(app)

    # ── 本机 + 空库 → 自动跳转 /setup（需求 1）──
    @app.before_request
    def auto_setup_redirect():
        """首页访问：若为本机请求且数据库无用户，自动跳转 /setup"""
        if request.method != 'GET':
            return
        if request.path != '/':
            return
        if not _is_local_request():
            return
        # 延迟导入避免循环引用
        from models import User
        if User.query.first() is None:
            return redirect(url_for('bootstrap.setup'))

    # ── CSRF 防护（F1-B）──
    @app.before_request
    def csrf_protect():
        """对 POST/PUT/DELETE 请求校验 CSRF Token"""
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return
        token = session.get('csrf_token')
        submitted = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token') or ''
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
                user = model_db.session.get(User, int(session['user_id']))
            except Exception:
                session.clear()
        return {'current_user': user}

    # ── 全局错误处理器（F1-B）──
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def handle_client_error(e):
        logger.warning('%s %s → %s %s', request.method, request.path, e.code, str(e))
        return render_template('error.html', code=e.code, message=str(e)), e.code

    @app.errorhandler(500)
    def handle_server_error(e):
        logger.error('500 at %s %s — full traceback follows:', request.method, request.path)
        logger.error(traceback.format_exc())
        return render_template('error.html', code=500,
                               message='服务器内部错误，请查看控制台获取详细信息。'), 500

    from exceptions import AppError

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        """统一处理应用层异常，返回 JSON 或 HTML"""
        logger.warning('%s %s → %s %s', request.method, request.path,
                       e.status_code, e.message or e.error_type)
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error_type': e.error_type,
                'message': e.message,
                'errors': e.errors,
            }), e.status_code
        return render_template('error.html', code=e.status_code,
                               message=e.message or '请求错误'), e.status_code

    # ── 注册蓝图 ──
    from routes.bootstrap import bootstrap_bp
    app.register_blueprint(bootstrap_bp)

    from routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from routes.folders import folders_bp
    app.register_blueprint(folders_bp)

    from routes.upload_validation import upload_validation_bp
    app.register_blueprint(upload_validation_bp)

    from routes.files import files_bp
    app.register_blueprint(files_bp)

    from routes.projects import projects_bp
    app.register_blueprint(projects_bp)

    # 上传限制已统一在 config.py 中配置，Flask 全局限制为 None，
    # 具体限制由 services/file_service.py 按文件类型校验

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
