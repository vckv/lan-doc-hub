"""认证服务层 —— 登录验证、账号锁定"""

from datetime import datetime, timedelta

import bcrypt

from models import db, User


MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=30)


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
    now = datetime.utcnow()
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds() // 60)
        errors['error_type'] = 'locked'
        errors['message'] = f'账号已锁定，请在 {remaining} 分钟后重试'
        return {'success': False, 'user': None, 'errors': errors}

    # ── 4. 密码验证 ──
    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + LOCK_DURATION
            user.failed_attempts = 0
            errors['error_type'] = 'locked_out'
            errors['message'] = '密码错误次数过多，账号已锁定 30 分钟'
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
