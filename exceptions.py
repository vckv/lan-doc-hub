"""LAN Doc Hub 统一异常体系"""


class AppError(Exception):
    """应用异常基类"""
    status_code = 500
    error_type = 'internal_error'

    def __init__(self, message: str = '', errors: dict = None, status_code: int = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}
        if status_code is not None:
            self.status_code = status_code


class ValidationError(AppError):
    """请求参数校验失败"""
    status_code = 400
    error_type = 'validation_error'


class AuthenticationError(AppError):
    """认证失败"""
    status_code = 401
    error_type = 'authentication_error'


class AuthorizationError(AppError):
    """权限不足"""
    status_code = 403
    error_type = 'authorization_error'


class NotFoundError(AppError):
    """资源不存在"""
    status_code = 404
    error_type = 'not_found'


class ConflictError(AppError):
    """资源冲突（如唯一性约束）"""
    status_code = 409
    error_type = 'conflict'


class FileTooLargeError(AppError):
    """文件大小超限"""
    status_code = 413
    error_type = 'file_too_large'
