import os

from flask import Flask, render_template
from models import db


def create_app():
    """创建并配置 Flask 应用"""
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # 初始化数据库
    db.init_app(app)

    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 创建所有数据库表（首次运行自动建表，已存在则跳过）
    with app.app_context():
        db.create_all()

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
