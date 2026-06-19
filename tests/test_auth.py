"""F1-C 测试：登录 / 登出 / 权限装饰器 / 账号锁定"""

import os
import tempfile

import pytest

from models import db as _db, User
from services.auth_service import authenticate_user
from services.user_service import create_user


@pytest.fixture
def app():
    """使用真实 create_app，通过 config_overrides 注入临时数据库"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    db_uri = 'sqlite:///' + db_path

    from app import create_app
    app = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': db_uri,
        'TESTING': True,
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


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


def _create_test_user(app, username='testuser', password='Test@Pass1',
                      role='member', is_active=True):
    """辅助函数：在应用上下文中创建测试用户"""
    with app.app_context():
        return create_user(
            username=username,
            display_name=username.title(),
            password=password,
            role=role,
            created_ip='127.0.0.1',
        )


def _get_csrf_token(client):
    """辅助函数：获取有效 CSRF Token"""
    client.get('/login')
    with client.session_transaction() as sess:
        return sess.get('csrf_token')


# ═══════════════════════════════════════════
# authenticate_user 单元测试
# ═══════════════════════════════════════════

class TestAuthenticateUser:

    def test_valid_credentials_return_success(self, app):
        _create_test_user(app)
        with app.app_context():
            result = authenticate_user('testuser', 'Test@Pass1')
            assert result['success']
            assert result['user'] is not None
            assert result['user'].username == 'testuser'

    def test_wrong_password_returns_error(self, app):
        _create_test_user(app)
        with app.app_context():
            result = authenticate_user('testuser', 'WrongPass1!')
            assert not result['success']
            assert 'password' in result['errors']

    def test_nonexistent_user_returns_error(self, app):
        with app.app_context():
            result = authenticate_user('nobody', 'AnyPass1!')
            assert not result['success']
            assert 'username' in result['errors']

    def test_inactive_user_rejected(self, app):
        _create_test_user(app, is_active=True)
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            user.is_active = False
            from models import db
            db.session.commit()

            result = authenticate_user('testuser', 'Test@Pass1')
            assert not result['success']
            assert '禁用' in str(result['errors'])

    def test_failed_attempts_increment_on_wrong_password(self, app):
        _create_test_user(app)
        with app.app_context():
            authenticate_user('testuser', 'wrong1')
            user = User.query.filter_by(username='testuser').first()
            assert user.failed_attempts == 1

    def test_failed_attempts_reset_on_success(self, app):
        _create_test_user(app)
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            user.failed_attempts = 3
            from models import db
            db.session.commit()

            result = authenticate_user('testuser', 'Test@Pass1')
            assert result['success']
            assert user.failed_attempts == 0


# ═══════════════════════════════════════════
# 登录 / 登出 路由测试
# ═══════════════════════════════════════════

class TestLoginRoute:

    def test_get_login_page_returns_200(self, app, client):
        _create_test_user(app)
        resp = client.get('/login')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '登录' in html
        assert 'name="username"' in html
        assert 'name="password"' in html

    def test_login_page_contains_csrf_hidden_field(self, app, client):
        _create_test_user(app)
        resp = client.get('/login')
        html = resp.get_data(as_text=True)
        assert 'name="csrf_token"' in html

    def test_successful_login_redirects_to_index(self, app, client):
        _create_test_user(app, username='admin1', password='Admin@Pass1')
        token = _get_csrf_token(client)

        resp = client.post('/login', data={
            'csrf_token': token,
            'username': 'admin1',
            'password': 'Admin@Pass1',
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.location == '/'

    def test_successful_login_sets_session(self, app, client):
        _create_test_user(app, username='admin1', password='Admin@Pass1')
        token = _get_csrf_token(client)

        client.post('/login', data={
            'csrf_token': token,
            'username': 'admin1',
            'password': 'Admin@Pass1',
        })

        with client.session_transaction() as sess:
            assert sess.get('user_id') is not None
            assert sess.get('username') == 'admin1'
            assert sess.get('user_role') == 'member'

    def test_wrong_password_shows_error(self, app, client):
        _create_test_user(app)
        token = _get_csrf_token(client)

        resp = client.post('/login', data={
            'csrf_token': token,
            'username': 'testuser',
            'password': 'WrongPass1!',
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '错误' in html

    def test_empty_credentials_shows_error(self, app, client):
        _create_test_user(app)
        token = _get_csrf_token(client)
        resp = client.post('/login', data={
            'csrf_token': token,
            'username': '',
            'password': '',
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '请输入' in html


class TestLogoutRoute:

    def test_logout_clears_session(self, app, client):
        _create_test_user(app, username='admin1', password='Admin@Pass1')
        token = _get_csrf_token(client)
        client.post('/login', data={
            'csrf_token': token,
            'username': 'admin1',
            'password': 'Admin@Pass1',
        })

        resp = client.get('/logout', follow_redirects=False)
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            assert sess.get('user_id') is None

    def test_logout_redirects_to_login(self, client):
        resp = client.get('/logout', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.location


# ═══════════════════════════════════════════
# 导航栏状态感知测试
# ═══════════════════════════════════════════

class TestNavbarState:

    def test_navbar_shows_login_link_when_not_logged_in(self, client):
        resp = client.get('/')
        html = resp.get_data(as_text=True)
        assert '未登录' in html
        assert '/login' in html

    def test_navbar_shows_display_name_when_logged_in(self, app, client):
        _create_test_user(app, username='admin1', password='Admin@Pass1')
        token = _get_csrf_token(client)
        client.post('/login', data={
            'csrf_token': token,
            'username': 'admin1',
            'password': 'Admin@Pass1',
        })

        resp = client.get('/')
        html = resp.get_data(as_text=True)
        assert 'Admin1' in html
        assert '/logout' in html
        assert '未登录' not in html
