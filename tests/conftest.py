"""pytest 配置与共享 fixtures"""

import os
import tempfile

import pytest
from flask import Flask

from models import db as _db
from config import Config


class TestConfig(Config):
    """测试配置，覆盖数据库为临时文件"""
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    """创建测试用 Flask 应用，使用临时数据库"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    db_uri = 'sqlite:///' + db_path

    app = Flask('test_app')
    app.config.from_object(TestConfig)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

    _db.init_app(app)

    with app.app_context():
        _db.create_all()

    # 注册测试路由
    @app.route('/')
    def index():
        return 'test ok'

    yield app

    # 释放数据库连接后删除临时文件
    with app.app_context():
        _db.session.remove()
        _db.engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass  # Windows 下 SQLite 可能仍有锁，忽略


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


@pytest.fixture
def db(app):
    """数据库会话（应用上下文内）"""
    with app.app_context():
        yield _db
