"""认证服务层 —— 登录验证、账号锁定"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from flask import current_app

from models import db, User


@dataclass
class LoginContext:
    """登录上下文，承载会话级追踪数据（相同密码提示大小写）"""
    last_username: str = ''
    last_password: str = ''
    same_count: int = 0

    def track(self, username: str, password: str) -> bool:
        """记录本次尝试，返回是否需要大小写提示（≥3 次相同密码）"""
        if username == self.last_username and password == self.last_password:
            self.same_count += 1
        else:
            self.same_count = 1
        self.last_username = username
        self.last_password = password
        return self.same_count >= 3


def _get_lock_duration():
    """从配置读取锁定时间（分钟），兜底 15 分钟"""
    try:
        minutes = current_app.config.get('LOGIN_LOCK_MINUTES', 15)
    except RuntimeError:
        minutes = 15
    return timedelta(minutes=minutes)


def _get_max_failed_attempts():
    """从配置读取最大失败次数，兜底 5 次"""
    try:
        return current_app.config.get('LOGIN_MAX_FAILED_ATTEMPTS', 5)
    except RuntimeError:
        return 5


def authenticate_user(username, password, ip_address='127.0.0.1'):
    """验证用户凭证

    Args:
        username:  用户名
        password:  明文密码
        ip_address: 登录来源 IP

    Returns:
        {
            'success': bool,
            'user': User|None,
            'errors': {
                'error_type': 'user_not_found'|'inactive'|'locked'|'wrong_password'|'locked_out',
                'message': str,
            }
        }
    """
    errors = {}
    user = User.query.filter_by(username=username).first()

    # ── 1. 用户存在性检查 ──
    if user is None:
        errors['error_type'] = 'user_not_found'
        errors['message'] = '该用户名不存在，请确认后重新输入'
        return {'success': False, 'user': None, 'errors': errors}

    # ── 2. 账号激活检查 ──
    if not user.is_active:
        errors['error_type'] = 'inactive'
        errors['message'] = '账号已被禁用，请联系管理员'
        return {'success': False, 'user': None, 'errors': errors}

    # ── 3. 账号锁定检查 ──
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds() // 60)
        errors['error_type'] = 'locked'
        errors['message'] = f'账号已锁定，请在 {remaining} 分钟后重试'
        return {'success': False, 'user': None, 'errors': errors}

    # ── 4. 密码验证 ──
    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        max_attempts = _get_max_failed_attempts()
        lock_duration = _get_lock_duration()
        user.failed_attempts += 1
        if user.failed_attempts >= max_attempts:
            user.locked_until = now + lock_duration
            user.failed_attempts = 0
            errors['error_type'] = 'locked_out'
            errors['message'] = f'密码错误次数过多，账号已锁定 {lock_duration.total_seconds() // 60:.0f} 分钟'
        else:
            errors['error_type'] = 'wrong_password'
            errors['message'] = '密码错误，请确认后输入'
        db.session.commit()
        return {'success': False, 'user': None, 'errors': errors}

    # ── 5. 登录成功 ──
    user.failed_attempts = 0
    user.locked_until = None
    user.created_ip = ip_address  # 更新最后登录 IP
    db.session.commit()

    return {'success': True, 'user': user, 'errors': {}}
