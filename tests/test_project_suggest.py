"""F4-2 测试：项目建议接口（suggest）"""

import os
import tempfile
import json

import pytest
import bcrypt

from models import db as _db, Project, User


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    db_uri = 'sqlite:///' + db_path

    key_fd, key_path = tempfile.mkstemp(suffix='.setup_key')
    with open(key_path, 'w', encoding='utf-8') as kf:
        kf.write('test-key')

    from app import create_app
    app = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': db_uri,
        'TESTING': True,
        'SETUP_KEY_FILE': key_path,
    })

    yield app

    with app.app_context():
        _db.session.remove()
        _db.engine.dispose()
    os.close(db_fd)
    os.close(key_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass
    try:
        os.unlink(key_path)
    except PermissionError:
        pass


def _login_as_admin(app):
    """创建并登录 admin"""
    with app.app_context():
        pw_hash = bcrypt.hashpw('Admin@Pass1'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin = User(
            username='admin', display_name='Admin',
            password_hash=pw_hash, role='admin', is_active=True,
            created_ip='127.0.0.1',
        )
        _db.session.add(admin)
        _db.session.commit()

    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        token = sess.get('csrf_token')
    client.post('/login', data={
        'csrf_token': token, 'username': 'admin', 'password': 'Admin@Pass1',
    })
    return client


def _seed_projects(app):
    """创建测试项目"""
    with app.app_context():
        _db.session.add_all([
            Project(model='PRJ001', name='桥梁检测平台'),
            Project(model='PRJ002', name='隧道监测系统'),
            Project(model='BRG001', name='桥梁设计工具'),
            Project(model='MON001', name='环境监控系统'),
        ])
        _db.session.commit()


class TestProjectSuggest:

    def test_suggest_by_model_prefix(self, app):
        """按型号前缀模糊搜索"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=PRJ')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert len(data['projects']) == 2
        assert data['projects'][0]['display'] == 'PRJ001 - 桥梁检测平台'

    def test_suggest_by_name_keyword(self, app):
        """按名称关键字模糊搜索"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=检测')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['projects']) == 1
        assert data['projects'][0]['model'] == 'PRJ001'

    def test_suggest_case_insensitive(self, app):
        """型号搜索大小写不敏感"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=prj')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['projects']) == 2

    def test_suggest_no_match_returns_empty(self, app):
        """无匹配返回空列表"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=ZZZ999')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert data['projects'] == []

    def test_suggest_empty_query_returns_empty(self, app):
        """空查询返回空列表"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['projects'] == []

    def test_suggest_missing_q_param(self, app):
        """缺少 q 参数返回空列表"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['projects'] == []

    def test_suggest_partial_match_model_and_name(self, app):
        """同时匹配 model 和 name，验证 display 格式"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=BRG')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['projects']) == 1
        assert data['projects'][0]['display'] == 'BRG001 - 桥梁设计工具'
        assert data['projects'][0]['model'] == 'BRG001'
        assert data['projects'][0]['name'] == '桥梁设计工具'

    def test_suggest_requires_login(self, app):
        """未登录拒绝"""
        with app.app_context():
            _db.create_all()

        client = app.test_client()
        resp = client.get('/api/projects/suggest?q=PRJ')
        assert resp.status_code in (302, 401, 400)
