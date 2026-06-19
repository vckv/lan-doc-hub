"""首次登录修复测试：密钥、错误消息、本机跳转、导航栏按钮"""

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

    # 为测试创建临时 setup 密钥文件
    key_fd, key_path = tempfile.mkstemp(suffix='.setup_key')
    with open(key_path, 'w', encoding='utf-8') as kf:
        kf.write('test-setup-key')

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
    """辅助函数：获取有效 CSRF Token（直接访问 /setup，避免 /login 重定向）"""
    client.get('/setup')
    with client.session_transaction() as sess:
        return sess.get('csrf_token')


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
# 本机空库自动跳转测试（需求 1）
# ═══════════════════════════════════════════

class TestAutoSetupRedirect:

    def test_local_root_with_empty_db_redirects_to_setup(self, client):
        """本机访问首页 + 空库 → 302 跳转 /setup"""
        resp = client.get('/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/setup' in resp.location

    def test_root_with_users_shows_index(self, app, client):
        """数据库有用户时访问首页 → 正常显示，不跳转"""
        _create_test_user(app)
        resp = client.get('/', follow_redirects=False)
        assert resp.status_code == 200

    def test_root_redirect_preserves_setup_page_accessibility(self, client):
        """跳转后的 /setup 页面可正常访问"""
        resp = client.get('/')
        assert resp.status_code == 302
        resp2 = client.get(resp.location)
        assert resp2.status_code == 200


# ═══════════════════════════════════════════
# 密钥校验测试（需求 1 的 setup 密钥）
# ═══════════════════════════════════════════

class TestSetupKey:

    def test_setup_with_wrong_key_shows_error(self, client):
        """错误的密钥 → 返回错误页面"""
        from routes.bootstrap import _get_setup_key
        token = _get_csrf_token(client)

        resp = client.post('/setup', data={
            'csrf_token': token,
            'setup_key': 'wrong-key',
            'username': 'admin1',
            'display_name': 'Admin',
            'password': 'Admin@Pass1',
            'password_confirm': 'Admin@Pass1',
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '密钥错误' in html

    def test_setup_with_correct_key_creates_admin(self, client):
        """正确的密钥 → 创建管理员成功"""
        token = _get_csrf_token(client)

        resp = client.post('/setup', data=_post_setup_data(client, token, {
            'username': 'admin1',
            'display_name': 'Admin',
            'password': 'Admin@Pass1',
            'password_confirm': 'Admin@Pass1',
        }))
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '创建成功' in html
        assert '去登录' in html  # 验证"去登录"按钮存在


# ═══════════════════════════════════════════
# 登录错误消息测试（需求 3）
# ═══════════════════════════════════════════

class TestLoginErrorMessages:

    def test_nonexistent_user_message(self, app, client):
        """用户不存在 → 返回明确提示"""
        _create_test_user(app)
        token = _get_csrf_token(client)

        resp = client.post('/login', data={
            'csrf_token': token,
            'username': 'nobody',
            'password': 'AnyPass1!',
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '该用户名不存在，请确认后重新输入' in html

    def test_wrong_password_first_attempt_message(self, app, client):
        """第一次密码错误 → 返回"密码错误，请确认后输入" """
        _create_test_user(app)
        token = _get_csrf_token(client)

        resp = client.post('/login', data={
            'csrf_token': token,
            'username': 'testuser',
            'password': 'WrongPass1!',
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '密码错误，请确认后输入' in html

    def test_repeated_same_wrong_password_shows_caps_hint(self, app, client):
        """相同错误密码提交 ≥3 次 → 提示大小写"""
        _create_test_user(app)

        # 第 1 次
        token1 = _get_csrf_token(client)
        client.post('/login', data={
            'csrf_token': token1,
            'username': 'testuser',
            'password': 'WrongPass1!',
        })

        # 第 2 次（相同密码，same_count → 1）
        token2 = _get_csrf_token(client)
        client.post('/login', data={
            'csrf_token': token2,
            'username': 'testuser',
            'password': 'WrongPass1!',
        })

        # 第 3 次（相同密码，same_count → 2 → 触发大小写提示）
        token3 = _get_csrf_token(client)
        resp = client.post('/login', data={
            'csrf_token': token3,
            'username': 'testuser',
            'password': 'WrongPass1!',
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '确认大小写后输入' in html

    def test_different_wrong_passwords_no_caps_hint(self, app, client):
        """不同密码每次错误 → 不提示大小写"""
        _create_test_user(app)

        token1 = _get_csrf_token(client)
        client.post('/login', data={
            'csrf_token': token1,
            'username': 'testuser',
            'password': 'WrongPass1!',
        })

        token2 = _get_csrf_token(client)
        resp = client.post('/login', data={
            'csrf_token': token2,
            'username': 'testuser',
            'password': 'DifferentPass2!',
        })
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '确认大小写后输入' not in html
        assert '密码错误，请确认后输入' in html


# ═══════════════════════════════════════════
# 导航栏按钮测试（需求 2）
# ═══════════════════════════════════════════

class TestNavbarButton:

    def test_navbar_shows_login_button_when_not_logged_in(self, app, client):
        """未登录时导航栏显示"点击登录"按钮"""
        _create_test_user(app)
        resp = client.get('/')
        html = resp.get_data(as_text=True)
        assert '点击登录' in html
        assert '未登录' not in html

    def test_navbar_button_links_to_login(self, app, client):
        """点击登录按钮链接到 /login"""
        _create_test_user(app)
        resp = client.get('/login')
        html = resp.get_data(as_text=True)
        assert '/login' in html


# ═══════════════════════════════════════════
# authenticate_user 返回结构测试
# ═══════════════════════════════════════════

class TestAuthServiceErrors:

    def test_authenticate_user_not_found_error_type(self, app):
        with app.app_context():
            result = authenticate_user('nobody', 'AnyPass1!')
            assert not result['success']
            assert result['errors']['error_type'] == 'user_not_found'

    def test_authenticate_wrong_password_error_type(self, app):
        _create_test_user(app)
        with app.app_context():
            result = authenticate_user('testuser', 'WrongPass1!')
            assert not result['success']
            assert result['errors']['error_type'] == 'wrong_password'

    def test_authenticate_inactive_error_type(self, app):
        _create_test_user(app, is_active=True)
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            user.is_active = False
            _db.session.commit()
            result = authenticate_user('testuser', 'Test@Pass1')
            assert not result['success']
            assert result['errors']['error_type'] == 'inactive'
