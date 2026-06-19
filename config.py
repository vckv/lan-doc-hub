import os
from datetime import timedelta


class Config:
    """基础配置"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'lan-doc-hub-dev-secret-key-2026')

    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 文件上传
    UPLOAD_FOLDER = os.environ.get(
        'UPLOAD_FOLDER',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    )
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB 默认上传上限（路由层覆写为 50MB）

    # 会话安全（F1-B 硬化）
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # 内网 HTTP 环境，不上 HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # 密码策略（F1-B 新增，可配置回滚）
    # 回滚至简易策略（6-12 位，无复杂度要求）：
    #   将 MIN 改为 6、MAX 改为 12、REQUIRE_COMPLEXITY 改为 False
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 20
    PASSWORD_REQUIRE_COMPLEXITY = True

    # 管理员初始化密钥文件路径（方案 B：控制台打印随机密钥）
    SETUP_KEY_FILE = os.environ.get(
        'SETUP_KEY_FILE',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.setup_key')
    )

    # ── F3-1 文件类型白名单 ──
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'txt', 'csv', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',
    }
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain',
        'text/csv',
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
    }
