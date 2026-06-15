"""数据库模型定义 —— v1 核心表 + v2 预留表"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ═══════════════════════════════════════════
# v1 核心表
# ═══════════════════════════════════════════

class User(db.Model):
    """用户表"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False, default='member')  # admin / member
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    download_path = db.Column(db.String(512), nullable=True)

    # v2 预留字段
    is_approver = db.Column(db.Boolean, nullable=False, default=False)
    approval_level = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # 关系
    uploaded_files = db.relationship('File', backref='uploader', lazy=True,
                                     foreign_keys='File.uploader_id')
    uploaded_versions = db.relationship('FileVersion', backref='uploader', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'


class Project(db.Model):
    """项目表"""
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(20), unique=True, nullable=False)   # 项目型号：英文+数字
    name = db.Column(db.String(30), unique=True, nullable=False)    # 项目名称：中文
    description = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # 关系
    files = db.relationship('File', backref='project', lazy=True)
    root_folder = db.relationship('Folder', backref='project_ref', lazy=True,
                                  foreign_keys='Folder.project_id')

    def __repr__(self):
        return f'<Project {self.model}_{self.name}>'


class Folder(db.Model):
    """文件夹表"""
    __tablename__ = 'folders'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    is_project_root = db.Column(db.Boolean, nullable=False, default=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # 自引用关系
    children = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]), lazy=True)
    files = db.relationship('File', backref='folder', lazy=True)

    def __repr__(self):
        return f'<Folder {self.name}>'


class Tag(db.Model):
    """标签表"""
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=True, default='#3b82f6')  # hex color
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Tag {self.name}>'


class File(db.Model):
    """文件表"""
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(128), nullable=False)           # 磁盘存储名（UUID前缀+原名）
    original_filename = db.Column(db.String(64), nullable=False)   # 原始文件名（最长64字符）
    file_path = db.Column(db.String(512), nullable=False)          # 磁盘相对路径
    file_number = db.Column(db.String(20), unique=True, nullable=False, index=True)  # F-YYYYMMDD-NNN
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    version_number = db.Column(db.String(8), nullable=False, default='I')    # 罗马数字
    version_note = db.Column(db.String(200), nullable=True)                   # 版本备注（可编辑）
    storage_path = db.Column(db.String(512), nullable=True)                   # 自定义存储路径
    file_type = db.Column(db.String(32), nullable=False)                      # 文件类型分类
    file_size = db.Column(db.BigInteger, nullable=False, default=0)           # 字节
    is_current = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_shortcut = db.Column(db.Boolean, nullable=False, default=False)
    shortcut_target_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # 关系
    tags = db.relationship('Tag', secondary='file_tags', backref='files', lazy=True)
    versions = db.relationship('FileVersion', backref='file', lazy=True,
                               order_by='FileVersion.uploaded_at.desc()')

    def __repr__(self):
        return f'<File {self.original_filename}>'


class FileTag(db.Model):
    """文件-标签关联表（多对多）"""
    __tablename__ = 'file_tags'

    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), primary_key=True)


class FileVersion(db.Model):
    """文件历史版本表"""
    __tablename__ = 'file_versions'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False, index=True)
    version_number = db.Column(db.String(8), nullable=False)       # 罗马数字
    version_note = db.Column(db.String(200), nullable=True)
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<FileVersion {self.file_id} v{self.version_number}>'


# ═══════════════════════════════════════════
# v2 预留表（建表但不写业务代码）
# ═══════════════════════════════════════════

class Role(db.Model):
    """自定义角色表（v2 预留）"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    description = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Role {self.name}>'


class Permission(db.Model):
    """操作权限点定义表（v2 预留）"""
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    code = db.Column(db.String(64), unique=True, nullable=False)  # 如 file:upload, file:delete
    description = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Permission {self.code}>'


class RolePermission(db.Model):
    """角色-权限关联表（v2 预留）"""
    __tablename__ = 'role_permissions'

    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), primary_key=True)


class FolderPermission(db.Model):
    """文件夹级访问控制表（v2 预留）"""
    __tablename__ = 'folder_permissions'

    id = db.Column(db.Integer, primary_key=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    can_view = db.Column(db.Boolean, nullable=False, default=True)
    can_upload = db.Column(db.Boolean, nullable=False, default=False)
    can_delete = db.Column(db.Boolean, nullable=False, default=False)
    can_manage = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f'<FolderPermission folder={self.folder_id} role={self.role_id}>'


class ApprovalWorkflow(db.Model):
    """审批工作流定义表（v2 预留）"""
    __tablename__ = 'approval_workflows'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256), nullable=True)
    total_steps = db.Column(db.Integer, nullable=False, default=1)  # 总审批级数（8-10级）
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<ApprovalWorkflow {self.name}>'


class ApprovalStep(db.Model):
    """审批步骤定义表（v2 预留）"""
    __tablename__ = 'approval_steps'

    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('approval_workflows.id'), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)                      # 第几级审批（1-based）
    approver_role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    approver_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f'<ApprovalStep workflow={self.workflow_id} step={self.step_order}>'


class ApprovalRecord(db.Model):
    """审批记录表（v2 预留）"""
    __tablename__ = 'approval_records'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    workflow_id = db.Column(db.Integer, db.ForeignKey('approval_workflows.id'), nullable=False)
    current_step = db.Column(db.Integer, nullable=False, default=1)         # 当前审批到第几级
    status = db.Column(db.String(16), nullable=False, default='pending')    # pending/approved/rejected
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<ApprovalRecord file={self.file_id} status={self.status}>'


class ApprovalLog(db.Model):
    """审批操作日志表（v2 预留）"""
    __tablename__ = 'approval_logs'

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('approval_records.id'), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(16), nullable=False)    # approve / reject
    comment = db.Column(db.String(512), nullable=True)
    acted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<ApprovalLog record={self.record_id} step={self.step_order} {self.action}>'
