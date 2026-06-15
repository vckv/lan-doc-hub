import os


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
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB 默认上传上限

    # 会话
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 86400  # 24 小时
