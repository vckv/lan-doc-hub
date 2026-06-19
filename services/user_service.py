"""用户服务层 —— PasswordPolicy、UsernamePolicy、create_user 统一入口"""

import re

import bcrypt
from sqlalchemy.exc import IntegrityError

from models import db, User


# ═══════════════════════════════════════════
# 密码策略 —— CLI 与 Web 共享的唯一真相来源
# ═══════════════════════════════════════════

class PasswordPolicy:
    """密码复杂度策略
    
    要求：8-20 位，大写/小写/数字/特殊符号四类中至少三类
    """
    MIN_LENGTH = 8
    MAX_LENGTH = 20

    RE_UPPER   = re.compile(r'[A-Z]')
    RE_LOWER   = re.compile(r'[a-z]')
    RE_DIGIT   = re.compile(r'[0-9]')
    RE_SPECIAL = re.compile(r'[!@#$%^&*(),.?":{}|<>~`\[\]_+=/;-]')

    @classmethod
    def validate(cls, password):
        """验证密码复杂度
        
        Args:
            password: 待验证的密码字符串
        
        Returns:
            {'valid': bool, 'errors': list}
        """
        errors = []

        length = len(password)
        if length < cls.MIN_LENGTH:
            errors.append(f'密码至少 {cls.MIN_LENGTH} 位')
        elif length > cls.MAX_LENGTH:
            errors.append(f'密码最多 {cls.MAX_LENGTH} 位')

        categories = sum([
            bool(cls.RE_UPPER.search(password)),
            bool(cls.RE_LOWER.search(password)),
            bool(cls.RE_DIGIT.search(password)),
            bool(cls.RE_SPECIAL.search(password)),
        ])
        if categories < 3:
            errors.append('密码需包含大写字母、小写字母、数字、特殊符号中的至少三类')

        return {'valid': len(errors) == 0, 'errors': errors}


# ═══════════════════════════════════════════
# 用户名策略
# ═══════════════════════════════════════════

class UsernamePolicy:
    """用户名策略
    
    要求：4-32 位，仅允许字母、数字和下划线
    """
    PATTERN = re.compile(r'^[a-zA-Z0-9_]{4,32}$')

    @classmethod
    def validate(cls, username):
        """验证用户名合法性
        
        Args:
            username: 待验证的用户名字符串
        
        Returns:
            {'valid': bool, 'errors': list}
        """
        errors = []
        if not cls.PATTERN.match(username):
            errors.append('用户名需为 4-32 位，仅允许字母、数字和下划线')
        return {'valid': len(errors) == 0, 'errors': errors}


# ═══════════════════════════════════════════
# 统一用户创建入口
# ═══════════════════════════════════════════

def create_user(username, display_name, password, role,
                created_by_id=None, created_ip='127.0.0.1'):
    """统一的用户创建入口 —— CLI 和 Web 路由共享
    
    执行完整的校验 -> 哈希 -> 入库流程，包含 flush-backfill 自引用回填
    
    Args:
        username:      用户名
        display_name:  显示名称
        password:      明文密码
        role:          角色（admin / member）
        created_by_id: 创建者 ID，None 时回填为自身（自引用场景）
        created_ip:    创建来源 IP
    
    Returns:
        {'success': bool, 'errors': dict, 'user': User|None}
        errors 格式: {'password': [...], 'username': [...], ...}
    """
    errors = {}

    # 1. 密码校验
    pw_result = PasswordPolicy.validate(password)
    if not pw_result['valid']:
        errors['password'] = pw_result['errors']

    # 2. 用户名校验
    un_result = UsernamePolicy.validate(username)
    if not un_result['valid']:
        errors['username'] = un_result['errors']

    # 3. 显示名称校验
    if not display_name or len(display_name) < 2 or len(display_name) > 20:
        errors['display_name'] = ['显示名称需为 2-20 个字符']

    # 4. 角色校验
    if role not in ('admin', 'member'):
        errors['role'] = ['角色必须为 admin 或 member']

    # 5. 有错误则提前返回
    if errors:
        return {'success': False, 'errors': errors, 'user': None}

    # ── bcrypt 72 字节硬限制检查 ──
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        errors['password'] = ['密码过长（bcrypt 限制 72 字节），请减少中文字符或特殊符号']
        return {'success': False, 'errors': errors, 'user': None}

    # 6. 密码哈希（bcrypt 原生）
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

    # 7. 构建对象并入库
    user = User(
        username=username,
        display_name=display_name,
        password_hash=password_hash,
        role=role,
        is_active=True,
        created_by_id=None,        # 先设为 None，flush 后回填
        created_ip=created_ip,
    )

    try:
        db.session.add(user)
        db.session.flush()  # 触发 INSERT，获取 user.id

        # 8. flush-backfill 自引用回填
        user.created_by_id = created_by_id or user.id
        db.session.commit()

        return {'success': True, 'errors': {}, 'user': user}

    except IntegrityError:
        db.session.rollback()
        return {
            'success': False,
            'errors': {'username': ['用户名已被占用，请更换后重试']},
            'user': None,
        }
