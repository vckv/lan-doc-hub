# LAN Doc Hub 代码优化方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对已完成 F3-1 阶段的 LAN Doc Hub 代码库进行系统性优化，消除重复代码，提升可读性、简洁性和优雅性。

**Architecture:** 采用"配置驱动 + 装饰器统一 + Service 层下沉"策略。后端按基础设施→结构优化→业务纠正三步走；前端按提取共享→Unicode还原→清理死代码顺序执行。

**Tech Stack:** Python 3.12+ / Flask 3.x / SQLAlchemy / bcrypt / jQuery / Bootstrap 4

---

## 一、代码审查总览

经完整阅读 30+ 源文件（路由层 6 文件、服务层 6 文件、前端 JS 4 文件、模板 7 文件、配置/模型/工具/测试 7 文件），共发现 **12 项可优化问题**，按严重程度和影响范围分为后端 9 项、前端 3 项。

### 代码优点
- 模型层 F1→F2→F3 分阶段建设，注释清晰，v1/v2 表分离明确
- Service 层已建立 `PasswordPolicy` / `UsernamePolicy` 类，设计模式正确
- 测试覆盖全面（F3-1 上传 / F2-2 跨项目校验均有专门测试文件）
- `upload_intercept_modal.js` 使用 IIFE 模块模式，封装良好
- 加载顺序合理（folder_tree → upload_intercept → upload_handler → file_view）

### 待优化项一览

| # | 类别 | 问题 | 严重度 |
|---|------|------|--------|
| 1 | 重复代码 | `_require_login()` / `_require_admin()` 在 4 个路由文件中重复定义 | 高 |
| 2 | 硬编码 | 锁定时间 30min 硬编码，与 PRD 要求的 15min 不符 | 高 |
| 3 | 兼容性 | `datetime.utcnow()` 在 Python 3.12+ 已废弃（13 处） | 中 |
| 4 | 配置混乱 | `MAX_CONTENT_LENGTH` config.py=500MB vs app.py=50MB 硬编码覆盖 | 高 |
| 5 | 架构违规 | 登录追踪逻辑写在路由层而非 Service 层 | 中 |
| 6 | 架构缺失 | `projects.py` 路由直接操作 DB，无对应 Service | 中 |
| 7 | 代码异味 | `import traceback` 写在函数体内部（3 处） | 低 |
| 8 | 错误处理 | 全项目 `{'success': False, ...}` 字典模式，无统一异常类型 | 中 |
| 9 | 硬编码分散 | 多处 magic number 未配置化 | 低 |
| 10 | 可读性 | JS 中文字符串全部用 `\uXXXX` 转义，完全不可读 | 高 |
| 11 | 重复代码 | `flattenTree()` 在两个 JS 文件中完全重复 | 中 |
| 12 | 死代码 | `templates/partials/` 下 HTML 文件标注"备用方案"但从未引用 | 低 |

---

## 二、后端优化（9 项）

---

### Task 1: 消除 `_require_login()` / `_require_admin()` 重复定义

**Files:**
- Modify: `utils/decorators.py` — 新增 `api_login_required` 和 `api_admin_required` 装饰器
- Modify: `routes/files.py` — 删除 `_require_login()`，用 `@api_login_required` 替代
- Modify: `routes/folders.py` — 删除 `_require_login()` 和 `_require_admin()`，用装饰器替代
- Modify: `routes/upload_validation.py` — 删除 `_require_login()`，用 `@api_login_required` 替代
- Modify: `routes/projects.py` — 删除 `_require_admin()`，用 `@api_admin_required` 替代

- [ ] **Step 1: 在 `utils/decorators.py` 新增 JSON API 专用装饰器**

```python
"""权限装饰器：login_required、admin_required（页面视图用）、api_login_required、api_admin_required（JSON API 用）"""

from functools import wraps

from flask import session, redirect, url_for, abort


def login_required(f):
    """要求用户已登录，未登录则重定向到 /login（页面视图用）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """要求当前用户为 admin 角色（页面视图用）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            abort(403, '需要管理员权限')
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    """JSON API 用：未登录返回 401"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            abort(401, '请先登录')
        return f(*args, **kwargs)
    return decorated


def api_admin_required(f):
    """JSON API 用：非管理员返回 403"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            abort(403, '需要管理员权限')
        return f(*args, **kwargs)
    return decorated
```

- [ ] **Step 2: 修改 `routes/files.py` — 删除 `_require_login()`，用装饰器替代**

删除第 14-16 行的 `_require_login()` 函数。将三个路由函数改为：

```python
"""文件路由蓝图 —— 上传、列表、编号预生成"""

from flask import Blueprint, jsonify, request, session, abort, current_app

from services.file_service import (
    generate_file_number,
    save_uploaded_file,
    get_files_by_folder,
)
from utils.decorators import api_login_required

files_bp = Blueprint('files', __name__, url_prefix='/api/files')


@files_bp.route('/pre-number', methods=['POST'])
@api_login_required
def api_pre_number():
    """POST /api/files/pre-number → 预生成文件编号（供前端弹窗预览）"""
    return jsonify({'success': True, 'file_number': generate_file_number()})


@files_bp.route('/upload', methods=['POST'])
@api_login_required
def api_upload_file():
    """POST /api/files/upload → 接收文件并存储"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'errors': {'file': ['未选择文件']}}), 400
    # ... 其余代码不变


@files_bp.route('', methods=['GET'])
@api_login_required
def api_list_files():
    """GET /api/files?folder_id=N → 获取文件夹内文件列表"""
    # ... 其余代码不变
```

- [ ] **Step 3: 修改 `routes/folders.py` — 用装饰器替代两处内联函数**

删除第 16-25 行的 `_require_login()` 和 `_require_admin()`。顶部新增 import：

```python
from utils.decorators import api_login_required, api_admin_required
```

所有路由改为装饰器形式：

```python
@folders_bp.route('/tree')
@api_login_required
def api_get_tree():
    ...

@folders_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_folder():
    ...

@folders_bp.route('/<int:folder_id>', methods=['PUT'])
@api_login_required
@api_admin_required
def api_rename_folder(folder_id):
    ...

@folders_bp.route('/<int:folder_id>', methods=['DELETE'])
@api_login_required
@api_admin_required
def api_delete_folder(folder_id):
    ...

@folders_bp.route('/<int:folder_id>/ancestors')
@api_login_required
def api_get_ancestors(folder_id):
    ...
```

- [ ] **Step 4: 修改 `routes/upload_validation.py` — 用装饰器替代 `_require_login()`**

删除第 14-16 行的 `_require_login()`。顶部新增 import `from utils.decorators import api_login_required`。三个路由函数均加 `@api_login_required`。

- [ ] **Step 5: 修改 `routes/projects.py` — 用装饰器替代 `_require_admin()`**

删除第 10-12 行的 `_require_admin()`。顶部新增 import。路由改为：

```python
@projects_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_project():
    ...
```

- [ ] **Step 6: 运行测试确认零回归**

```bash
pytest tests/test_auth.py tests/test_upload.py tests/test_upload_validation.py tests/test_folders.py -v
```

Expected: 全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add utils/decorators.py routes/files.py routes/folders.py routes/upload_validation.py routes/projects.py
git commit -m "refactor: extract api_login_required/api_admin_required decorators, remove duplicated helpers"
```

---

### Task 2: 锁定时间从硬编码迁移到 config.py

**Files:**
- Modify: `config.py` — 新增 `LOGIN_MAX_FAILED_ATTEMPTS` 和 `LOGIN_LOCK_MINUTES`
- Modify: `services/auth_service.py` — 从配置读取锁定参数

- [ ] **Step 1: 在 `config.py` 新增两个配置项**

在 `# 密码策略` 区域下方新增：

```python
    # ── 登录安全 ──
    LOGIN_MAX_FAILED_ATTEMPTS = 5
    LOGIN_LOCK_MINUTES = 15          # PRD 要求 15 分钟
```

- [ ] **Step 2: 修改 `services/auth_service.py` — 从 current_app.config 读取**

将第 10-11 行的模块级常量改为从配置读取的辅助函数：

```python
"""认证服务层 —— 登录验证、账号锁定"""

from datetime import datetime, timedelta, timezone

import bcrypt
from flask import current_app

from models import db, User


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
    """验证用户凭证"""
    errors = {}
    user = User.query.filter_by(username=username).first()

    if user is None:
        errors['error_type'] = 'user_not_found'
        errors['message'] = '该用户名不存在，请确认后重新输入'
        return {'success': False, 'user': None, 'errors': errors}

    if not user.is_active:
        errors['error_type'] = 'inactive'
        errors['message'] = '账号已被禁用，请联系管理员'
        return {'success': False, 'user': None, 'errors': errors}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds() // 60)
        errors['error_type'] = 'locked'
        errors['message'] = f'账号已锁定，请在 {remaining} 分钟后重试'
        return {'success': False, 'user': None, 'errors': errors}

    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        max_attempts = _get_max_failed_attempts()
        user.failed_attempts += 1
        if user.failed_attempts >= max_attempts:
            user.locked_until = now + _get_lock_duration()
            user.failed_attempts = 0
            errors['error_type'] = 'locked_out'
            errors['message'] = f'密码错误次数过多，账号已锁定 {_get_lock_duration().total_seconds() // 60:.0f} 分钟'
        else:
            errors['error_type'] = 'wrong_password'
            errors['message'] = '密码错误，请确认后输入'
        db.session.commit()
        return {'success': False, 'user': None, 'errors': errors}

    user.failed_attempts = 0
    user.locked_until = None
    user.created_ip = ip_address
    db.session.commit()

    return {'success': True, 'user': user, 'errors': {}}
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_auth.py -v
```

Expected: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add config.py services/auth_service.py
git commit -m "fix: lock duration now reads from config (15min per PRD), remove hardcoded 30min"
```

---

### Task 3: `datetime.utcnow` 升级为 Python 3.12+ 兼容写法

**Files:**
- Modify: `models.py` — 所有 `default=datetime.utcnow` → `default=utcnow`
- Modify: `services/file_service.py` — 2 处 `.utcnow()` → `.now(timezone.utc)`
- Modify: `services/auth_service.py` — 1 处（已在 Task 2 中一并修改）

- [ ] **Step 1: 在 `models.py` 顶部新增 `utcnow` 辅助函数**

```python
"""数据库模型定义 —— v1 核心表 + v2 预留表"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


def utcnow():
    """Python 3.12+ 兼容的 UTC 当前时间（naive datetime，与 SQLite 对齐）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

- [ ] **Step 2: 替换 `models.py` 中所有 `default=datetime.utcnow`**

将 `models.py` 中所有 `default=datetime.utcnow` 替换为 `default=utcnow`（共约 8 处：Project、Folder、Tag、File、FileVersion、Role、Permission、ApprovalWorkflow 等）。

注意：`User.created_at` 已使用 `func.now()`，`User.updated_at` 已使用 `func.now()` + `onupdate`，这两处是 SQLAlchemy 层函数，不需要改。

- [ ] **Step 3: 替换 `services/file_service.py` 中的 `.utcnow()`**

第 17 行：
```python
# 旧
today = datetime.utcnow().strftime('%Y%m%d')
# 新
today = datetime.now(timezone.utc).strftime('%Y%m%d')
```

第 102 行：
```python
# 旧
now = datetime.utcnow()
# 新
now = datetime.now(timezone.utc).replace(tzinfo=None)
```

- [ ] **Step 4: 运行全量测试**

```bash
pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add models.py services/file_service.py services/auth_service.py
git commit -m "refactor: replace deprecated datetime.utcnow with timezone-aware UTC"
```

---

### Task 4: 统一上传限制配置，消除 app.py 硬编码

**Files:**
- Modify: `config.py` — 明确三项上传限制配置
- Modify: `app.py` — 删除第 173 行硬编码
- Modify: `services/file_service.py` — 增加按文件类型大小校验

- [ ] **Step 1: 修改 `config.py`**

将原来的：
```python
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB 默认上传上限（路由层覆写为 50MB）
```

改为：

```python
    # ── 文件上传限制 ──
    # Flask 全局限制设为 None，由上传路由按文件类型分别校验
    MAX_CONTENT_LENGTH = None
    SINGLE_FILE_MAX_SIZE = 500 * 1024 * 1024   # 单文件 500MB
    ARCHIVE_EXTENSIONS = {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'tgz'}
    FILE_ORIGINAL_NAME_MAX_LENGTH = 64
```

- [ ] **Step 2: 删除 `app.py` 第 173 行硬编码**

删除：
```python
    # 设置上传限制（F3-1）
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
```

改为注释：
```python
    # 上传限制已统一在 config.py 中配置，Flask 全局限制为 None，
    # 具体限制由 services/file_service.py 按文件类型校验
```

- [ ] **Step 3: 在 `services/file_service.py` 的 `save_uploaded_file` 中增加大小校验**

在 `# ── 文件类型校验 ──` 之后新增大小校验：

```python
    # ── 文件大小校验 ──
    archive_exts = current_app.config.get('ARCHIVE_EXTENSIONS', set())
    if ext not in archive_exts:
        max_size = current_app.config.get('SINGLE_FILE_MAX_SIZE', 500 * 1024 * 1024)
        # 读取文件大小（seek 到末尾再回来）
        file_storage.seek(0, 2)
        file_size_check = file_storage.tell()
        file_storage.seek(0)
        if file_size_check > max_size:
            errors['file'] = [f'文件大小 {file_size_check // (1024*1024)}MB 超过 {max_size // (1024*1024)}MB 限制']
            return {'success': False, 'file': None, 'errors': errors}
```

同时将截断 64 字符处的硬编码 `64` 替换为 `current_app.config.get('FILE_ORIGINAL_NAME_MAX_LENGTH', 64)`。

- [ ] **Step 4: 修改前端 `upload_handler.js` 错误提示**

将第 251 行的：
```javascript
msg = '\u6587\u4EF6\u592A\u5927\uFF0C\u8D85\u8FC7 50 MB \u9650\u5236';
```
替换为（配合后续前端优化 1 统一改为中文）：
```javascript
msg = '文件太大，超过 500 MB 限制';
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_upload.py -v
```

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add config.py app.py services/file_service.py static/js/upload_handler.js
git commit -m "fix: unify upload size limit config, remove hardcoded 50MB override"
```

---

### Task 5: 将 `auth.py` 中的登录追踪逻辑下沉到 Service 层

**Files:**
- Modify: `services/auth_service.py` — 新增 `LoginContext` 数据类
- Modify: `routes/auth.py` — 简化为参数提取 + Service 调用 + 结果渲染

- [ ] **Step 1: 在 `services/auth_service.py` 中新增 `LoginContext`**

```python
from dataclasses import dataclass

@dataclass
class LoginContext:
    """登录上下文，承载会话级追踪数据"""
    last_username: str = ''
    last_password: str = ''
    same_count: int = 0

    def track(self, username: str, password: str) -> bool:
        """记录本次尝试，返回是否需要大小写提示（≥3 次）"""
        if username == self.last_username and password == self.last_password:
            self.same_count += 1
        else:
            self.same_count = 1
        self.last_username = username
        self.last_password = password
        return self.same_count >= 3
```

- [ ] **Step 2: 重构 `routes/auth.py` 的 login 函数**

将原来嵌入路由的 session 操作提取出来：

```python
"""认证路由蓝图 —— 登录 / 登出"""

from flask import Blueprint, render_template, request, session, redirect, url_for, current_app

from services.auth_service import authenticate_user, LoginContext
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if 'user_id' in session:
        return redirect(url_for('index'))

    if User.query.first() is None:
        return redirect(url_for('bootstrap.setup'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('login.html',
                                   username=username,
                                   error='请输入用户名和密码')

        # ── 从 session 恢复或新建登录上下文 ──
        ctx = LoginContext(
            last_username=session.get('login_last_username', ''),
            last_password=session.get('login_last_password', ''),
            same_count=session.get('login_same_count', 0),
        )
        hint_case = ctx.track(username, password)
        session['login_last_username'] = ctx.last_username
        session['login_last_password'] = ctx.last_password
        session['login_same_count'] = ctx.same_count

        try:
            result = authenticate_user(
                username=username,
                password=password,
                ip_address=request.remote_addr or '127.0.0.1',
            )
        except Exception as exc:
            import traceback
            current_app.logger.error(
                'authenticate_user 异常 — %s: %s\n%s',
                type(exc).__name__, str(exc), traceback.format_exc()
            )
            return render_template(
                'login.html',
                username=username,
                error=f'系统错误：{type(exc).__name__} — {exc}。请查看控制台获取详细信息。',
            )

        if result['success']:
            user = result['user']
            # 登录成功，清理追踪数据
            for key in ('login_last_username', 'login_last_password', 'login_same_count'):
                session.pop(key, None)
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.display_name
            session['user_role'] = user.role
            return redirect(url_for('index'))

        # 构造错误消息
        error_type = result['errors'].get('error_type', '')
        message = result['errors'].get('message', '用户名或密码错误')

        if error_type == 'wrong_password' and hint_case:
            message = '密码错误，请确认大小写后输入'

        return render_template('login.html', username=username, error=message)

    return render_template('login.html',
                           username=request.args.get('username', ''))


@auth_bp.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('auth.login'))
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_auth.py -v
```

Expected: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add services/auth_service.py routes/auth.py
git commit -m "refactor: move login tracking logic into LoginContext dataclass in service layer"
```

---

### Task 6: 为 `projects.py` 创建 Service 层

**Files:**
- Create: `services/project_service.py`
- Modify: `routes/projects.py` — 简化为参数提取 + 调用 Service

- [ ] **Step 1: 新建 `services/project_service.py`**

```python
"""项目服务层 —— 创建项目（含根文件夹）"""

from models import db, Project, Folder


def create_project_with_root(model: str, name: str, created_by: int):
    """创建项目并同步创建根文件夹

    Args:
        model: 项目型号（如 PRJ001），最长 20 字符
        name:  项目名称，最长 30 字符
        created_by: 创建者用户 ID

    Returns:
        {'success': bool, 'project': dict|None, 'folder': dict|None, 'errors': dict}
    """
    errors = {}
    model = (model or '').strip().upper()
    name = (name or '').strip()

    if not model:
        errors['model'] = ['项目型号不能为空']
    elif len(model) > 20:
        errors['model'] = ['项目型号最多 20 个字符']

    if not name:
        errors['name'] = ['项目名称不能为空']
    elif len(name) > 30:
        errors['name'] = ['项目名称最多 30 个字符']

    if not errors:
        if Project.query.filter_by(model=model).first():
            errors['model'] = [f'项目型号 {model} 已存在']
        if Project.query.filter_by(name=name).first():
            errors['name'] = [f'项目名称 {name} 已存在']

    if errors:
        return {'success': False, 'project': None, 'folder': None, 'errors': errors}

    try:
        proj = Project(model=model, name=name)
        db.session.add(proj)
        db.session.flush()

        folder = Folder(
            name=f'{model}_{name}',
            is_project_root=True,
            project_id=proj.id,
            parent_id=None,
            created_by=created_by,
        )
        db.session.add(folder)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {
            'success': False,
            'project': None, 'folder': None,
            'errors': {'_system': ['创建项目失败，请重试']},
        }

    return {
        'success': True,
        'project': {'id': proj.id, 'model': proj.model, 'name': proj.name},
        'folder': {'id': folder.id, 'name': folder.name,
                   'is_project_root': True, 'project_id': folder.project_id},
        'errors': {},
    }
```

- [ ] **Step 2: 修改 `routes/projects.py`**

```python
"""项目管理路由蓝图 —— 创建项目（同时创建根文件夹）"""

from flask import Blueprint, jsonify, request, session

from services.project_service import create_project_with_root
from utils.decorators import api_login_required, api_admin_required

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')


@projects_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_project():
    """POST /api/projects → 创建项目 + 对应根文件夹"""
    data = request.get_json(silent=True) or {}
    result = create_project_with_root(
        model=data.get('model', ''),
        name=data.get('name', ''),
        created_by=int(session['user_id']),
    )

    if not result['success']:
        err_msg = str(result['errors'])
        status = 409 if '已存在' in err_msg else 400
        return jsonify({'success': False, 'errors': result['errors']}), status

    return jsonify({
        'success': True,
        'project': result['project'],
        'folder': result['folder'],
    }), 201
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_upload_validation.py -v
```

Expected: 调用 projects API 的用例全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add services/project_service.py routes/projects.py
git commit -m "refactor: extract project creation logic into project_service"
```

---

### Task 7: `import traceback` 移到文件顶部

**Files:**
- Modify: `app.py` — 顶部加 `import traceback`
- Modify: `routes/auth.py` — 顶部加 `import traceback`
- Modify: `routes/bootstrap.py` — 顶部加 `import traceback`

- [ ] **Step 1: 逐个文件修改**

`app.py` 第 4 行后添加：
```python
import traceback
```
删除第 147 行函数体内的 `import traceback`。

`routes/auth.py` 第 1 行后添加：
```python
import traceback
```
删除第 48 行函数体内的 `import traceback`。

`routes/bootstrap.py` 第 1 行后添加：
```python
import traceback
```
删除第 68 行函数体内的 `import traceback`。

- [ ] **Step 2: 提交**

```bash
git add app.py routes/auth.py routes/bootstrap.py
git commit -m "style: move import traceback to top of file"
```

---

### Task 8: 建立统一异常处理体系

**Files:**
- Create: `exceptions.py`
- Modify: `app.py` — 注册全局异常处理器

- [ ] **Step 1: 新建 `exceptions.py`**

```python
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
```

- [ ] **Step 2: 在 `app.py` 注册全局异常处理器**

在 `create_app` 函数中，蓝图注册之前添加：

```python
    from exceptions import AppError

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        """统一处理应用层异常，返回 JSON 或 HTML"""
        logger.warning('%s %s → %s %s', request.method, request.path,
                       e.status_code, e.message or e.error_type)
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error_type': e.error_type,
                'message': e.message,
                'errors': e.errors,
            }), e.status_code
        return render_template('error.html', code=e.status_code,
                               message=e.message or '请求错误'), e.status_code
```

> **注：** 本次仅搭建框架，不修改现有 Service 层的 `{'success': False, ...}` 返回模式。后续 F4/F5 阶段可逐步将 Service 改为抛异常。

- [ ] **Step 3: 提交**

```bash
git add exceptions.py app.py
git commit -m "feat: add unified exception hierarchy (AppError and subclasses)"
```

---

### Task 9: 硬编码值集中化到 `config.py`

**Files:**
- Modify: `config.py` — 新增配置项汇总
- Modify: `services/file_service.py` — 使用 `FILE_ORIGINAL_NAME_MAX_LENGTH`
- Modify: `services/folder_service.py` — 使用 `FOLDER_NAME_MAX_LENGTH`

- [ ] **Step 1: 在 `config.py` 中汇总所有配置项**

在现有配置基础上，确保以下配置项均已存在：

```python
    # ── 文件上传限制 ──
    MAX_CONTENT_LENGTH = None
    SINGLE_FILE_MAX_SIZE = 500 * 1024 * 1024
    ARCHIVE_EXTENSIONS = {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'tgz'}
    FILE_ORIGINAL_NAME_MAX_LENGTH = 64

    # ── 文件夹 ──
    FOLDER_NAME_MAX_LENGTH = 32

    # ── 登录安全 ──
    LOGIN_MAX_FAILED_ATTEMPTS = 5
    LOGIN_LOCK_MINUTES = 15
```

- [ ] **Step 2: 更新 `services/file_service.py` 中的硬编码**

将第 132 行的 `if len(original_name) > 64:` 改为：
```python
    max_len = current_app.config.get('FILE_ORIGINAL_NAME_MAX_LENGTH', 64)
    if len(original_name) > max_len:
```

- [ ] **Step 3: 更新 `services/folder_service.py` 中的硬编码**

将第 65 行和第 127 行的 `if len(name) > 32:` 改为：
```python
    max_len = current_app.config.get('FOLDER_NAME_MAX_LENGTH', 32)
    if len(name) > max_len:
```

注意：`create_folder` 和 `rename_folder` 两处都需要改。同时更新对应的错误消息。

- [ ] **Step 4: 提交**

```bash
git add config.py services/file_service.py services/folder_service.py
git commit -m "refactor: centralize all magic numbers into config.py"
```

---

## 三、前端优化（3 项）

---

### Task 10: 提取共享 `flattenTree()` 函数

**Files:**
- Modify: `static/js/folder_tree.js` — 将 `flattenTree` 挂载到全局命名空间
- Modify: `static/js/upload_handler.js` — 删除本地定义，使用共享版本

- [ ] **Step 1: 在 `folder_tree.js` 中将 `flattenTree` 暴露为全局**

在 `folder_tree.js` 末尾添加：

```javascript
// ── 共享工具：文件夹树扁平化（供 upload_handler.js 等复用）──
window.LanDocHub = window.LanDocHub || {};
window.LanDocHub.flattenTree = function flattenTree(nodes, depth) {
    depth = depth || 0;
    var flat = [];
    $.each(nodes, function (i, node) {
        flat.push({
            id: node.id,
            name: node.name,
            project_id: node.project_id,
            is_project_root: node.is_project_root,
            depth: depth,
        });
        if (node.children && node.children.length > 0) {
            flat = flat.concat(flattenTree(node.children, depth + 1));
        }
    });
    return flat;
};
```

将 `folder_tree.js` 内部的 `flattenTree` 调用（`loadParentPicker` 中）改为 `LanDocHub.flattenTree(...)`。

- [ ] **Step 2: 删除 `upload_handler.js` 中的本地 `flattenTree`**

删除第 265-281 行的 `flattenTree` 函数。将所有调用 `flattenTree(...)` 替换为 `LanDocHub.flattenTree(...)`（共 2 处：`showFolderPickerModal` 内部）。

- [ ] **Step 3: Commit**

```bash
git add static/js/folder_tree.js static/js/upload_handler.js
git commit -m "refactor: extract shared flattenTree into LanDocHub namespace"
```

---

### Task 11: JavaScript Unicode 转义替换为可读中文字符

**Files:**
- Modify: `static/js/upload_handler.js` — ~30 处 `\uXXXX` → 中文
- Modify: `static/js/upload_intercept_modal.js` — ~15 处
- Modify: `static/js/folder_tree.js` — ~25 处
- Modify: `static/js/file_view.js` — ~12 处

- [ ] **Step 1: 编写转换脚本并执行**

创建 `c:\Users\EnnaLowei\.trae-cn\work\6a39225e98a9a560bb0ba3ad\convert_unicode.py`（中间产物，用完删除）：

```python
import re
import os

JS_DIR = r'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub\static\js'

for filename in os.listdir(JS_DIR):
    if not filename.endswith('.js'):
        continue
    filepath = os.path.join(JS_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    def replace_unicode(m):
        return chr(int(m.group(1), 16))

    new_content = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Converted: {filename}')
    else:
        print(f'Skipped (no change): {filename}')

print('Done.')
```

运行：
```bash
python convert_unicode.py
```

- [ ] **Step 2: 人工抽查关键文件**

打开每个改动的 JS 文件，确认：
- 弹窗标题、按钮文案、错误提示等均为可读中文
- 没有因转义导致语法错误（如字符串未闭合）

- [ ] **Step 3: 前端冒烟测试**

启动应用，手动验证：
- 点击上传按钮 → 弹窗文案正确
- 跨项目上传 → 拦截弹窗文案正确
- 新建项目/文件夹 → 对话框文案正确
- 文件列表面包屑 → 文案正确

- [ ] **Step 4: Commit**

```bash
git add static/js/
git commit -m "style: replace JS unicode escapes with readable Chinese characters"
```

---

### Task 12: 清理无效的 HTML partial 文件

**Files:**
- Delete: `templates/partials/upload_modal.html`
- Delete: `templates/partials/upload_intercept_modal.html`

- [ ] **Step 1: 全局搜索确认零引用**

```bash
grep -r "upload_modal" templates/ --include="*.html"
grep -r "upload_intercept_modal" templates/ --include="*.html"
```

Expected: 只有在 `partials/` 自身文件中出现，无外部 `include` 引用。

- [ ] **Step 2: 确认 JS 动态注入覆盖所有功能**

`upload_handler.js` 的 `showUploadModal()` 和 `upload_intercept_modal.js` 的 `init()` 均完整构建 DOM，不依赖 HTML partial。

- [ ] **Step 3: 删除文件**

```bash
git rm templates/partials/upload_modal.html
git rm templates/partials/upload_intercept_modal.html
```

- [ ] **Step 4: 检查 `folder_tree.html` partial**

```bash
grep -r "folder_tree.html" templates/ --include="*.html"
```

如果也无外部引用，一并删除。

- [ ] **Step 5: 若 `templates/partials/` 目录为空，删除目录**

```bash
rmdir templates\partials
```

- [ ] **Step 6: Commit**

```bash
git add templates/
git commit -m "chore: remove unused HTML partials (JS handles all modal rendering)"
```

---

## 四、执行顺序

| 步骤 | Task # | 内容 | 依赖 | 风险 |
|------|--------|------|------|------|
| 1 | 7 | `import traceback` 移到文件顶部 | 无 | 极低 |
| 2 | 8 | 创建 `exceptions.py`（仅新建文件） | 无 | 极低 |
| 3 | 3 | `datetime.utcnow` 升级 | 无 | 低 |
| 4 | 9 | 硬编码值集中化 `config.py` | 无 | 低 |
| 5 | 1 | 消除 `_require_login`/`_require_admin` 重复 | 无 | 中（装饰器改为函数） |
| 6 | 2 | 锁定时间配置化 | Task 9 | 低 |
| 7 | 4 | 上传限制配置统一 | Task 9 | 中（涉及大小校验逻辑） |
| 8 | 6 | projects service 层提取 | Task 1 | 低 |
| 9 | 5 | 登录追踪逻辑下沉 | Task 1, Task 2 | 中（涉及 session 操作） |
| 10 | 10 | 提取共享 `flattenTree` | 无 | 低 |
| 11 | 11 | JS Unicode 转义替换 | Task 10 | 低（纯文本替换） |
| 12 | 12 | 删除 dead HTML partials | 无 | 极低 |

每完成一个大步骤（1-4、5-9、10-12）后运行一次全量测试：

```bash
pytest tests/ -v
```

---

## 五、验证步骤

### 自动化验证
完成所有优化后，运行全量测试：
```bash
pytest tests/ -v
```
Expected: 全部 PASS。

### 手动冒烟测试清单
1. 启动应用 → 首页加载正常
2. 文件夹树加载 → 展开/收起 → 选中高亮正常
3. 点击上传 → 弹窗出现 → 选择文件 → 文件列表刷新
4. 跨项目文件上传 → 拦截弹窗触发 → "保存到正确项目"和"快捷方式"均可选
5. 新建项目 → 项目创建 + 根文件夹同步生成
6. 新建子文件夹 → 树刷新
7. 登录 → 锁定测试（连续 5 次失败 → 15 分钟锁定）
8. 面包屑导航 → 点击跳转正常

---

## 六、假设与决策

1. **FC3-1 之后尚未实现的功能（版本管理、标签、搜索等）不在本次优化范围**，本次仅优化已有代码。
2. **`datetime.utcnow` 替换方案**采用 `.replace(tzinfo=None)`保持 naive datetime，确保与 SQLite 存储一致。
3. **异常体系仅搭建框架**，不修改现有 Service 层的 `{'success': False, ...}` 返回模式，避免大面积重构风险。
4. **Flask `MAX_CONTENT_LENGTH = None`** 关闭全局限制，依赖 Service 层按文件类型校验大小。生产环境建议在 nginx 层配置兜底限制。
5. **JS 模板字符串拼接**当前方案（jQuery + 字符串拼接 DOM）保持不变，仅清理 Unicode 转义。后续 F15（UI 重构）阶段再考虑迁移到现代框架。
