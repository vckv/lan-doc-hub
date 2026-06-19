"""F1-B 测试：CSRF 防护 + Bootstrap /setup 路由"""

import os
import tempfile

import pytest
from flask import session

from models import db as _db, User


@pytest.fixture
def app():
    """使用真实 create_app，通过 config_overrides 注入临时数据库"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    db_uri = 'sqlite:///' + db_path

    from app import create_app

    # 为测试创建临时 setup 密钥文件
    key_fd, key_path = tempfile.mkstemp(suffix='.setup_key')
    with open(key_path, 'w', encoding='utf-8') as kf:
        kf.write('test-setup-key')

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
    try:
        os.unlink(db_path)
    except PermissionError:
        pass
    os.close(key_fd)
    try:
        os.unlink(key_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    """测试客户端"""
    return app.test_client()


def _post_setup_data(client, token, extra_data=None):
    """辅助函数：构建带 setup_key 的标准 POST 数据"""
    data = {
        'setup_key': 'test-setup-key',
        'csrf_token': token,
        'username': 'admin_user',
        'display_name': 'Admin',
        'password': 'Admin@Pass1',
        'password_confirm': 'Admin@Pass1',
    }
    if extra_data:
        data.update(extra_data)
    return data


# ═══════════════════════════════════════════
# CSRF 防护测试
# ═══════════════════════════════════════════

class TestCSRF:

    def test_get_requests_pass_without_csrf(self, client):
        """GET 请求不校验 CSRF Token"""
        resp = client.get('/setup')
        assert resp.status_code == 200

    def test_post_without_csrf_token_rejected(self, client):
        """POST 请求不带 csrf_token 返回 400"""
        resp = client.post('/setup', data={
            'setup_key': 'test-setup-key',
            'username': 'admin',
            'display_name': 'Admin',
            'password': 'Admin@Pass1',
            'password_confirm': 'Admin@Pass1',
        })
        assert resp.status_code == 400

    def test_post_with_wrong_csrf_token_rejected(self, client):
        """POST 请求带错误的 csrf_token 返回 400"""
        resp = client.post('/setup', data={
            'csrf_token': 'wrongtoken',
            'setup_key': 'test-setup-key',
            'username': 'admin',
            'display_name': 'Admin',
            'password': 'Admin@Pass1',
            'password_confirm': 'Admin@Pass1',
        })
        assert resp.status_code == 400

    def test_post_with_valid_csrf_token_accepted(self, client):
        """POST 请求带有效的 csrf_token 返回 200 并创建成功"""
        resp_get = client.get('/setup')
        assert resp_get.status_code == 200

        with client.session_transaction() as sess:
            token = sess.get('csrf_token')

        assert token is not None

        resp_post = client.post('/setup', data=_post_setup_data(client, token, {
            'username': 'admin_csrf',
        }))
        assert resp_post.status_code == 200
        html = resp_post.get_data(as_text=True)
        assert '创建成功' in html


# ═══════════════════════════════════════════
# /setup 路由测试
# ═══════════════════════════════════════════

class TestSetupRoute:

    def _get_csrf_token(self, client):
        """辅助方法：获取有效 CSRF Token"""
        client.get('/setup')
        with client.session_transaction() as sess:
            return sess.get('csrf_token')

    def test_setup_accessible_when_no_users(self, client):
        """数据库无用户时 /setup 可访问"""
        resp = client.get('/setup')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '首次初始化' in html

    def test_setup_returns_404_when_users_exist(self, client):
        """数据库已有用户时 /setup 返回 404"""
        token = self._get_csrf_token(client)
        client.post('/setup', data=_post_setup_data(client, token, {
            'username': 'admin_first',
            'display_name': 'First Admin',
        }))

        resp = client.get('/setup')
        assert resp.status_code == 404

    def test_password_mismatch_shows_error(self, client):
        """两次密码不一致显示错误"""
        token = self._get_csrf_token(client)
        resp = client.post('/setup', data=_post_setup_data(client, token, {
            'username': 'testuser',
            'display_name': 'Test User',
            'password': 'Good@Pass1',
            'password_confirm': 'Wrong@Pass2',
        }))
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '不一致' in html

    def test_weak_password_shows_error(self, client):
        """弱密码被拦截，显示错误"""
        token = self._get_csrf_token(client)
        resp = client.post('/setup', data=_post_setup_data(client, token, {
            'username': 'gooduser',
            'display_name': 'Good User',
            'password': '123456',
            'password_confirm': '123456',
        }))
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert any(w in html for w in ('至少', '三类', '8 位'))

    def test_empty_username_shows_error(self, client):
        """空用户名被拦截"""
        token = self._get_csrf_token(client)
        resp = client.post('/setup', data=_post_setup_data(client, token, {
            'username': '',
            'display_name': 'Test',
        }))
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'class="alert' in html.lower()

    def test_create_admin_creates_admin_user(self, client):
        """创建管理员后返回成功提示"""
        token = self._get_csrf_token(client)
        resp = client.post('/setup', data=_post_setup_data(client, token, {
            'username': 'admin_user',
            'display_name': 'System Admin',
            'password': 'Admin@2024',
            'password_confirm': 'Admin@2024',
        }))
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '创建成功' in html

    def test_setup_form_contains_csrf_hidden_field(self, client):
        """/setup 表单包含 csrf_token 隐藏字段"""
        resp = client.get('/setup')
        html = resp.get_data(as_text=True)
        assert 'name="csrf_token"' in html


# ═══════════════════════════════════════════
# 错误处理器测试
# ═══════════════════════════════════════════

class TestErrorHandlers:

    def test_404_page_renders_error_template(self, client):
        """404 页面使用 error.html 模板"""
        resp = client.get('/nonexistent/page')
        assert resp.status_code == 404
        html = resp.get_data(as_text=True)
        assert '404' in html

    def test_400_page_on_csrf_failure(self, client):
        """CSRF 失败返回 400"""
        resp = client.post('/setup', data={'username': 'test'})
        assert resp.status_code == 400
