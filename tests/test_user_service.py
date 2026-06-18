"""F1-A 单元测试：PasswordPolicy、UsernamePolicy、create_user"""

import pytest

from models import User
from services.user_service import (
    PasswordPolicy,
    UsernamePolicy,
    create_user,
    pwd_context,
)


# ═══════════════════════════════════════════
# PasswordPolicy 测试
# ═══════════════════════════════════════════

class TestPasswordPolicy:

    @pytest.mark.parametrize('password', [
        'Admin@2024',    # 四类全有（大写+小写+数字+特殊）
        'abcdefG1',      # 小写+大写+数字（三类）
        'ABCDEf!1',      # 大写+小写+特殊+数字（四类）
    ])
    def test_strong_passwords_pass(self, password):
        """强密码（>=3 类字符）应通过校验"""
        result = PasswordPolicy.validate(password)
        assert result['valid'], f'密码应通过: {password}, 错误: {result["errors"]}'

    @pytest.mark.parametrize('password', [
        '123456',       # 仅数字（一类）
        'abcdefgh',     # 仅小写（一类）
        'ABCDEFGH',     # 仅大写（一类）
        '!@#$%^&*',     # 仅特殊（一类）
        'abc',          # 太短（3 位）
        'Ab1!',         # 太短（4 位，虽类别够但长度不够）
    ])
    def test_weak_passwords_rejected(self, password):
        """弱密码应被拦截"""
        result = PasswordPolicy.validate(password)
        assert not result['valid'], f'弱密码应被拦截: {password}'

    def test_too_short_error_message(self):
        """密码长度不足 8 位时错误信息包含'至少 8 位'"""
        result = PasswordPolicy.validate('Ab1!')
        assert not result['valid']
        assert any('至少 8 位' in e for e in result['errors'])

    def test_too_long_error_message(self):
        """密码长度超过 20 位时错误信息包含'最多 20 位'"""
        result = PasswordPolicy.validate('A' * 21)
        assert not result['valid']
        assert any('最多 20 位' in e for e in result['errors'])

    def test_only_two_categories_rejected(self):
        """仅有两类字符应报错（大写+数字，缺小写和特殊）"""
        result = PasswordPolicy.validate('ABCD1234')
        assert not result['valid']
        assert any('至少三类' in e for e in result['errors'])


# ═══════════════════════════════════════════
# UsernamePolicy 测试
# ═══════════════════════════════════════════

class TestUsernamePolicy:

    @pytest.mark.parametrize('username', [
        'admin',
        'user_123',
        'testUser',
        'a_b_c',
        'a' * 4,      # 最小长度（4 位）
        'a' * 32,     # 最大长度（32 位）
    ])
    def test_valid_usernames_pass(self, username):
        """合法用户名应通过校验"""
        result = UsernamePolicy.validate(username)
        assert result['valid'], f'用户名应通过: {username}'

    @pytest.mark.parametrize('username', [
        'ab',           # 太短（2 位）
        'a' * 33,       # 太长（33 位）
        'user name',    # 含空格
        'user-name',    # 含连字符
        'user@name',    # 含特殊字符
    ])
    def test_invalid_usernames_rejected(self, username):
        """非法用户名应被拦截"""
        result = UsernamePolicy.validate(username)
        assert not result['valid'], f'用户名应被拦截: {username}'


# ═══════════════════════════════════════════
# create_user 集成测试
# ═══════════════════════════════════════════

class TestCreateUser:

    def test_create_user_success(self, app):
        """正常创建用户成功，密码为 passlib bcrypt 哈希"""
        with app.app_context():
            result = create_user(
                username='testuser',
                display_name='Test User',
                password='StrongP@ss1',
                role='member',
                created_by_id=None,
                created_ip='192.168.1.1',
            )

            assert result['success']
            assert result['user'] is not None
            assert result['user'].username == 'testuser'
            assert result['user'].role == 'member'
            assert result['user'].created_ip == '192.168.1.1'

            # 密码为 passlib bcrypt 哈希（以 $2b$ 开头）
            assert result['user'].password_hash.startswith('$2b$')

            # created_by_id 已通过 flush-backfill 回填为自身
            assert result['user'].created_by_id == result['user'].id

    def test_create_user_with_specified_creator(self, app):
        """由管理员创建新用户时 created_by_id 为管理员 ID"""
        with app.app_context():
            admin_result = create_user(
                username='admin',
                display_name='Admin',
                password='Admin@Pass1',
                role='admin',
                created_by_id=None,
            )
            admin_id = admin_result['user'].id

            member_result = create_user(
                username='member1',
                display_name='Member One',
                password='Member@Pass1',
                role='member',
                created_by_id=admin_id,
            )

            assert member_result['success']
            assert member_result['user'].created_by_id == admin_id

    def test_duplicate_username_returns_error_not_crash(self, app):
        """重复用户名返回错误而非 500 崩溃"""
        with app.app_context():
            create_user(
                username='dupe',
                display_name='First',
                password='Dupe@Pass1',
                role='member',
            )

            result = create_user(
                username='dupe',
                display_name='Second',
                password='Dupe@Pass2',
                role='member',
            )

            assert not result['success']
            assert 'username' in result['errors']
            assert '已被占用' in result['errors']['username'][0]
            assert result['user'] is None

    def test_weak_password_rejected_not_written_to_db(self, app):
        """弱密码被拦截，数据库中无记录"""
        with app.app_context():
            result = create_user(
                username='gooduser',
                display_name='Good User',
                password='123456',
                role='member',
            )

            assert not result['success']
            assert 'password' in result['errors']

            user = User.query.filter_by(username='gooduser').first()
            assert user is None

    def test_invalid_username_rejected(self, app):
        """非法用户名被拦截"""
        with app.app_context():
            result = create_user(
                username='ab',
                display_name='Short',
                password='Valid@Pass1',
                role='member',
            )

            assert not result['success']
            assert 'username' in result['errors']

    def test_invalid_role_rejected(self, app):
        """非法角色被拦截"""
        with app.app_context():
            result = create_user(
                username='roleuser',
                display_name='Role Test',
                password='Valid@Pass1',
                role='superadmin',
            )

            assert not result['success']
            assert 'role' in result['errors']

    def test_empty_display_name_rejected(self, app):
        """空显示名称被拦截"""
        with app.app_context():
            result = create_user(
                username='nodisplay',
                display_name='',
                password='Valid@Pass1',
                role='member',
            )

            assert not result['success']
            assert 'display_name' in result['errors']

    def test_password_hash_verifiable_by_passlib(self, app):
        """创建的密码哈希可通过 passlib verify 验证"""
        with app.app_context():
            result = create_user(
                username='verify',
                display_name='Verify Test',
                password='MySecret@123',
                role='member',
            )

            assert result['success']
            user = result['user']

            assert pwd_context.verify('MySecret@123', user.password_hash)
            assert not pwd_context.verify('WrongPassword', user.password_hash)
