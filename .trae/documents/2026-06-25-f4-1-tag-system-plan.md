# F4-1 标签系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现标签系统的完整功能：管理员创建/编辑/删除标签，上传时选择标签，文件列表展示标签 Badge，普通成员 7 天内可修改自己上传文件的标签。

**Architecture:** 新增 `services/tag_service.py` 和 `routes/tags.py`（蓝图），改造 `services/file_service.py` 在上传时支持绑定标签、在列表查询中返回标签，修改上传弹窗、批量上传弹窗、文件列表前端三个 JS 文件来展示和选择标签。所有 API 遵循现有 `{'success': bool, ...errors: dict}` 返回模式，权限通过 `@api_admin_required` 和 Service 层手动权限检查。

**Tech Stack:** Python 3.12+ / Flask 3.1 / SQLAlchemy / SQLite / jQuery + Bootstrap 4

**数据模型（已建表，无需迁移）：**
- `Tag`: id, name(unique), color(#hex), created_at — 标签定义
- `FileTag`: file_id(FK) + tag_id(FK) 复合主键 — 多对多关联
- `File.tags`: 通过 `secondary='file_tags'` 已配置 relationship

---

### 文件结构总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `services/tag_service.py` | **新建** | 标签 CRUD + 文件标签绑定/解绑 + 7 天权限校验 |
| `services/file_service.py` | 修改 | `save_uploaded_file()` 接受 `tag_ids`；`get_files_by_folder()` 返回 `tags` 字段 |
| `routes/tags.py` | **新建** | Blueprint：标签管理 API + 文件标签 API |
| `routes/files.py` | 修改 | 上传端点解析 `tag_ids` 参数 |
| `app.py` | 修改 | 注册 `tags_bp` 蓝图 |
| `static/css/app.css` | 追加 | 标签 Badge、管理页、多选组件样式 |
| `static/js/upload_handler.js` | 修改 | 上传弹窗 + 批量弹窗添加标签多选；上传时附带 `tag_ids` |
| `static/js/file_view.js` | 修改 | `renderFileList()` 渲染标签 Badge |
| `static/js/tag_management.js` | **新建** | Admin 端标签管理弹窗（CRUD 交互） |
| `templates/base.html` | 修改 | 侧边栏添加"标签管理"按钮（admin only），加载 `tag_management.js` |
| `tests/test_tags.py` | **新建** | 标签 CRUD + 文件标签权限测试 |

---

### Task 1: 创建标签服务层 `services/tag_service.py`

**Files:**
- Create: `services/tag_service.py`
- Create: `tests/test_tags.py`（见 Task 6）

- [ ] **Step 1: 创建 `services/tag_service.py`**

```python
"""标签服务层 —— 标签 CRUD、文件标签关联、7 天可编辑权限"""
from datetime import datetime, timezone

from models import db, Tag, FileTag, File


def _now():
    """当前 UTC naive datetime"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── 标签 CRUD ──

def create_tag(name, color='#3b82f6'):
    """创建标签（仅 admin 调用）

    Args:
        name: 标签名（1-32 字符，不可重复）
        color: Hex 颜色（可选，默认 #3b82f6）

    Returns:
        {'success': bool, 'tag': dict|None, 'errors': dict}
    """
    errors = {}
    name = (name or '').strip()
    if not name:
        errors['name'] = ['标签名不能为空']
    elif len(name) > 32:
        errors['name'] = ['标签名最多 32 个字符']

    color = (color or '').strip() or '#3b82f6'
    # 校验 hex 颜色格式：#RRGGBB 或 #RGB
    if not color.startswith('#') or len(color) not in (4, 7):
        errors['color'] = ['颜色格式不正确，应为 #RRGGBB 或 #RGB']

    if errors:
        return {'success': False, 'tag': None, 'errors': errors}

    existing = Tag.query.filter_by(name=name).first()
    if existing:
        return {
            'success': False, 'tag': None,
            'errors': {'name': [f'标签 "{name}" 已存在']},
        }

    tag = Tag(name=name, color=color.lower())
    db.session.add(tag)
    db.session.commit()

    return {
        'success': True,
        'tag': {'id': tag.id, 'name': tag.name, 'color': tag.color},
        'errors': {},
    }


def update_tag(tag_id, name=None, color=None):
    """编辑标签（仅 admin 调用）

    Args:
        tag_id: 标签 ID
        name: 新名称（可选，None 表示不修改）
        color: 新颜色（可选，None 表示不修改）

    Returns:
        {'success': bool, 'tag': dict|None, 'errors': dict}
    """
    errors = {}
    tag = db.session.get(Tag, tag_id)
    if tag is None:
        return {'success': False, 'tag': None, 'errors': {'tag_id': ['标签不存在']}}

    if name is not None:
        name = name.strip()
        if not name:
            errors['name'] = ['标签名不能为空']
        elif len(name) > 32:
            errors['name'] = ['标签名最多 32 个字符']
        else:
            dup = Tag.query.filter(Tag.name == name, Tag.id != tag_id).first()
            if dup:
                errors['name'] = [f'标签 "{name}" 已存在']

    if color is not None:
        color = color.strip()
        if not color.startswith('#') or len(color) not in (4, 7):
            errors['color'] = ['颜色格式不正确，应为 #RRGGBB 或 #RGB']

    if errors:
        return {'success': False, 'tag': None, 'errors': errors}

    if name is not None:
        tag.name = name
    if color is not None:
        tag.color = color.lower()
    db.session.commit()

    return {
        'success': True,
        'tag': {'id': tag.id, 'name': tag.name, 'color': tag.color},
        'errors': {},
    }


def delete_tag(tag_id):
    """删除标签，同时清理 file_tags 关联（仅 admin 调用）

    Args:
        tag_id: 标签 ID

    Returns:
        {'success': bool, 'errors': dict}
    """
    tag = db.session.get(Tag, tag_id)
    if tag is None:
        return {'success': False, 'errors': {'tag_id': ['标签不存在']}}

    FileTag.query.filter_by(tag_id=tag_id).delete()
    db.session.delete(tag)
    db.session.commit()

    return {'success': True, 'errors': {}}


def get_all_tags():
    """获取所有标签列表（所有登录用户可调用）

    Returns:
        list[dict]: [{id, name, color}, ...]
    """
    tags = Tag.query.order_by(Tag.name).all()
    return [{'id': t.id, 'name': t.name, 'color': t.color} for t in tags]


# ── 文件-标签关联 ──

def set_file_tags(file_id, user_id, tag_ids, user_role='member'):
    """设置文件的标签（替换式：先清空再重新写入）

    权限规则：
    - admin 可编辑所有文件的标签
    - 普通成员只能编辑自己上传 + 7 天内的标签

    Args:
        file_id:   文件 ID
        user_id:   操作用户 ID
        tag_ids:   标签 ID 列表（空列表 = 清空所有标签）
        user_role: 用户角色（'admin' 或 'member'）

    Returns:
        {'success': bool, 'tags': list|None, 'errors': dict}
    """
    errors = {}
    f = db.session.get(File, file_id)
    if f is None:
        return {'success': False, 'tags': None, 'errors': {'file_id': ['文件不存在']}}

    # ── 权限校验 ──
    if user_role != 'admin':
        if f.uploader_id != user_id:
            errors['permission'] = ['只能编辑自己上传的文件']
        else:
            delta = _now() - f.created_at
            if delta.days > 7:
                errors['permission'] = ['上传超过 7 天的文件不可修改标签']

    if errors:
        return {'success': False, 'tags': None, 'errors': errors}

    # ── 校验 tag_ids 均存在 ──
    if tag_ids:
        existing_ids = {t.id for t in Tag.query.filter(Tag.id.in_(tag_ids)).all()}
        invalid = set(tag_ids) - existing_ids
        if invalid:
            return {
                'success': False, 'tags': None,
                'errors': {'tag_ids': [f'标签 ID 不存在: {", ".join(map(str, invalid))}']},
            }

    # ── 替换式写入 ──
    FileTag.query.filter_by(file_id=file_id).delete()
    for tid in tag_ids:
        db.session.add(FileTag(file_id=file_id, tag_id=tid))
    db.session.commit()

    # 返回更新后的标签列表
    f_updated = db.session.get(File, file_id)
    tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in f_updated.tags]
    return {'success': True, 'tags': tags, 'errors': {}}


def get_file_tags(file_id):
    """获取某文件的标签列表

    Returns:
        list[dict]: [{id, name, color}, ...]
    """
    f = db.session.get(File, file_id)
    if f is None:
        return []
    return [{'id': t.id, 'name': t.name, 'color': t.color} for t in f.tags]


def can_edit_file_tags(file_id, user_id, user_role='member'):
    """判断用户是否有权编辑某文件的标签

    Returns:
        {'can_edit': bool, 'reason': str|None}
    """
    if user_role == 'admin':
        return {'can_edit': True, 'reason': None}

    f = db.session.get(File, file_id)
    if f is None:
        return {'can_edit': False, 'reason': '文件不存在'}
    if f.uploader_id != user_id:
        return {'can_edit': False, 'reason': '只能编辑自己上传的文件'}
    delta = _now() - f.created_at
    if delta.days > 7:
        return {'can_edit': False, 'reason': '上传超过 7 天的文件不可修改标签'}
    return {'can_edit': True, 'reason': None}
```

- [ ] **Step 2: 运行测试确保无导入错误**

```powershell
python -c "from services.tag_service import create_tag, get_all_tags; print('OK')"
```

Expected: 输出 `OK`（需在虚拟环境且有 Flask app context 下测试）

- [ ] **Step 3: Commit**

```bash
git add services/tag_service.py
git commit -m "feat: add tag service layer with CRUD, file-tag binding, 7-day permission check"
```

---

### Task 2: 修改文件服务层 `services/file_service.py`

**Files:**
- Modify: `services/file_service.py` (lines 3, 72-73, 37-69, 172-186)

- [ ] **Step 1: 修改 `save_uploaded_file()` 签名，新增 `tag_ids` 参数**

将 `services/file_service.py` 第 3 行的导入改为（新增 `FileTag`）：

```python
from models import db, File, Folder, Project, FileTag
```

将第 72-73 行函数签名改为：

```python
def save_uploaded_file(file_storage, project_id, folder_id, uploader_id,
                       version_number='I', version_note=None, tag_ids=None):
```

在第 186 行（`db.session.add(file_record)`）之后、`db.session.commit()` 之前，添加标签绑定逻辑：

```python
    # ── 绑定标签 ──
    if tag_ids:
        for tid in tag_ids:
            db.session.add(FileTag(file_id=file_record.id, tag_id=tid))
```

- [ ] **Step 2: 修改 `get_files_by_folder()` 返回标签信息**

将 `services/file_service.py` 第 37-69 行的 `get_files_by_folder` 改为：

```python
def get_files_by_folder(folder_id):
    """获取某文件夹下的文件列表（含快捷方式标注、标签信息）

    Args:
        folder_id: 文件夹 ID

    Returns:
        list[dict]
    """
    files = (
        db.session.query(File, Project.model)
        .join(Project, File.project_id == Project.id)
        .filter(File.folder_id == folder_id, File.is_current == True)
        .order_by(File.created_at.desc())
        .all()
    )
    result = []
    for f, model in files:
        tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in f.tags]
        result.append({
            'id': f.id,
            'original_filename': f.original_filename,
            'file_number': f.file_number,
            'file_type': f.file_type,
            'file_size': f.file_size,
            'version_number': f.version_number,
            'version_note': f.version_note,
            'project_model': model,
            'is_shortcut': f.is_shortcut,
            'shortcut_target_id': f.shortcut_target_id,
            'uploader_name': f.uploader.display_name if f.uploader else '',
            'uploaded_at': f.created_at.strftime('%Y-%m-%d %H:%M'),
            'tags': tags,
        })
    return result
```

> **注意**: 查询仍使用 `File.id` 形式，无需 `joinedload` —— SQLAlchemy 的 lazy loading 会在访问 `f.tags` 时触发额外查询，对当前文件夹文件数量（通常几十个）而言性能完全可接受。若未来文件量大，可加 `.options(joinedload(File.tags))` 优化，但因查询返回 tuple，joinedload 需作用在 Query 而非 entity 上，在不改变现有返回结构的约束下保留 lazy loading。

- [ ] **Step 3: Commit**

```bash
git add services/file_service.py
git commit -m "feat: add tag_ids param to save_uploaded_file, return tags in get_files_by_folder"
```

---

### Task 3: 创建标签路由蓝图 `routes/tags.py`

**Files:**
- Create: `routes/tags.py`

- [ ] **Step 1: 创建 `routes/tags.py`**

```python
"""标签路由蓝图 —— 管理端 CRUD + 文件标签绑定"""

from flask import Blueprint, jsonify, request, session

from services.tag_service import (
    create_tag, update_tag, delete_tag, get_all_tags,
    set_file_tags, get_file_tags, can_edit_file_tags,
)
from utils.decorators import api_login_required, api_admin_required

tags_bp = Blueprint('tags', __name__, url_prefix='/api/tags')


# ── 管理端（admin only）──

@tags_bp.route('', methods=['GET'])
@api_login_required
def api_list_tags():
    """GET /api/tags → 获取所有标签"""
    tags = get_all_tags()
    return jsonify({'success': True, 'tags': tags})


@tags_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_tag():
    """POST /api/tags → 创建标签（admin）
    JSON: {"name": "紧急", "color": "#ff0000"}
    """
    data = request.get_json(silent=True) or {}
    result = create_tag(
        name=data.get('name', ''),
        color=data.get('color', '#3b82f6'),
    )
    if not result['success']:
        err_str = str(result['errors'])
        status = 409 if '已存在' in err_str else 400
        return jsonify({'success': False, 'errors': result['errors']}), status
    return jsonify({'success': True, 'tag': result['tag']}), 201


@tags_bp.route('/<int:tag_id>', methods=['PUT'])
@api_login_required
@api_admin_required
def api_update_tag(tag_id):
    """PUT /api/tags/<id> → 编辑标签（admin）
    JSON: {"name": "新名"}  或  {"color": "#00ff00"}  或两者皆有
    """
    data = request.get_json(silent=True) or {}
    result = update_tag(
        tag_id=tag_id,
        name=data.get('name'),
        color=data.get('color'),
    )
    if not result['success']:
        err_str = str(result['errors'])
        if '不存在' in err_str:
            status = 404
        elif '已存在' in err_str:
            status = 409
        else:
            status = 400
        return jsonify({'success': False, 'errors': result['errors']}), status
    return jsonify({'success': True, 'tag': result['tag']})


@tags_bp.route('/<int:tag_id>', methods=['DELETE'])
@api_login_required
@api_admin_required
def api_delete_tag(tag_id):
    """DELETE /api/tags/<id> → 删除标签（admin）"""
    result = delete_tag(tag_id)
    if not result['success']:
        return jsonify({'success': False, 'errors': result['errors']}), 404
    return jsonify({'success': True})


# ── 文件-标签绑定 ──

@tags_bp.route('/file/<int:file_id>', methods=['GET'])
@api_login_required
def api_get_file_tags(file_id):
    """GET /api/tags/file/<file_id> → 获取文件的标签 + 是否可编辑"""
    tags = get_file_tags(file_id)
    user_id = int(session['user_id'])
    user_role = session.get('user_role', 'member')
    perm = can_edit_file_tags(file_id, user_id, user_role)
    return jsonify({
        'success': True,
        'tags': tags,
        'can_edit': perm['can_edit'],
        'reason': perm.get('reason'),
    })


@tags_bp.route('/file/<int:file_id>', methods=['PUT'])
@api_login_required
def api_update_file_tags(file_id):
    """PUT /api/tags/file/<file_id> → 设置文件的标签（替换式）
    JSON: {"tag_ids": [1, 2, 3]}  或 {"tag_ids": []}
    """
    data = request.get_json(silent=True) or {}
    tag_ids = data.get('tag_ids', [])
    if not isinstance(tag_ids, list):
        return jsonify({
            'success': False,
            'errors': {'tag_ids': ['tag_ids 必须是数组']},
        }), 400

    user_id = int(session['user_id'])
    user_role = session.get('user_role', 'member')
    result = set_file_tags(
        file_id=file_id,
        user_id=user_id,
        tag_ids=tag_ids,
        user_role=user_role,
    )
    if not result['success']:
        status = 403 if 'permission' in result.get('errors', {}) else 400
        return jsonify({'success': False, 'errors': result['errors']}), status
    return jsonify({'success': True, 'tags': result['tags']})
```

- [ ] **Step 2: Commit**

```bash
git add routes/tags.py
git commit -m "feat: add tag API blueprint with admin CRUD and file-tag binding endpoints"
```

---

### Task 4: 修改 `routes/files.py` 接受 tag_ids

**Files:**
- Modify: `routes/files.py` (lines 57-76)

- [ ] **Step 1: 在 upload 端点解析 `tag_ids` 并传入 service**

在 `routes/files.py` 的 `api_upload_file()` 中，第 58 行 `version_note` 之后添加 `tag_ids` 解析：

```python
    version_note = request.form.get('version_note', '').strip() or None
    # ── F4-1: 标签 ID 列表（逗号分隔）──
    tag_ids_raw = request.form.get('tag_ids', '')
    tag_ids = []
    if tag_ids_raw:
        try:
            tag_ids = [int(x.strip()) for x in tag_ids_raw.split(',') if x.strip()]
        except (ValueError, TypeError):
            pass  # 无效格式静默忽略，上传本身不受影响
```

然后将第 69-76 行的 `save_uploaded_file` 调用改为传入 `tag_ids`：

```python
    result = save_uploaded_file(
        file_storage=file_storage,
        project_id=project_id,
        folder_id=folder_id,
        uploader_id=int(session['user_id']),
        version_number=version_number,
        version_note=version_note,
        tag_ids=tag_ids,
    )
```

- [ ] **Step 2: Commit**

```bash
git add routes/files.py
git commit -m "feat: accept tag_ids in file upload endpoint"
```

---

### Task 5: 在 `app.py` 注册标签蓝图

**Files:**
- Modify: `app.py` (after line 187)

- [ ] **Step 1: 注册 tags_bp**

在 `app.py` 中，于第 187 行 `projects_bp` 注册之后添加：

```python
    from routes.tags import tags_bp
    app.register_blueprint(tags_bp)
```

- [ ] **Step 2: Commit**

```bash
git add app.py
git commit -m "feat: register tags blueprint"
```

---

### Task 6: 创建测试文件 `tests/test_tags.py`

**Files:**
- Create: `tests/test_tags.py`

- [ ] **Step 1: 创建 `tests/test_tags.py`**

```python
"""F4-1 测试：标签 CRUD、文件-标签关联、7 天权限控制"""

import os
import tempfile
import json

import pytest
import bcrypt

from models import db as _db, Tag, FileTag, File, Folder, Project, User


@pytest.fixture
def app():
    """创建带临时数据库的应用实例"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    db_uri = 'sqlite:///' + db_path

    key_fd, key_path = tempfile.mkstemp(suffix='.setup_key')
    with open(key_path, 'w', encoding='utf-8') as kf:
        kf.write('test-key')

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
    os.close(key_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass
    try:
        os.unlink(key_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def _api_headers(client):
    """生成带 CSRF Token 的 JSON 请求头"""
    with client.session_transaction() as sess:
        token = sess.get('csrf_token', '')
    return {'X-CSRF-Token': token, 'Content-Type': 'application/json'}


def _login_as(app, username, password, role):
    """创建用户并登录，返回已认证的 test_client"""
    with app.app_context():
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = User(
            username=username,
            display_name=username.capitalize(),
            password_hash=pw_hash,
            role=role,
            is_active=True,
            created_ip='127.0.0.1',
        )
        _db.session.add(user)
        _db.session.commit()

    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        token = sess.get('csrf_token')
    resp = client.post('/login', data={
        'csrf_token': token,
        'username': username,
        'password': password,
    })
    return client


def _seed_projects_and_tags(app):
    """创建测试用的项目、根文件夹、两个标签"""
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        proj = Project(model='F4TEST', name='测试项目')
        _db.session.add(proj)
        _db.session.flush()

        root = Folder(
            name='F4TEST_测试项目', is_project_root=True,
            project_id=proj.id, parent_id=None, created_by=admin.id,
        )
        _db.session.add(root)
        _db.session.flush()

        tag1 = Tag(name='紧急', color='#ff0000')
        tag2 = Tag(name='待审核', color='#ffaa00')
        _db.session.add_all([tag1, tag2])
        _db.session.commit()

        return {
            'project_id': proj.id,
            'folder_id': root.id,
            'tag_ids': [tag1.id, tag2.id],
        }


# ═══════════════════════════════════════════
# 标签 CRUD 测试
# ═══════════════════════════════════════════

class TestTagCRUD:

    def test_create_tag_success(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': '紧急', 'color': '#ff0000'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['success']
        assert data['tag']['name'] == '紧急'
        assert data['tag']['color'] == '#ff0000'

    def test_create_duplicate_tag_returns_409(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        client.post('/api/tags', data=json.dumps({'name': '唯一', 'color': '#000'}), headers=hdrs)
        resp = client.post('/api/tags', data=json.dumps({'name': '唯一', 'color': '#000'}), headers=hdrs)
        assert resp.status_code == 409

    def test_create_tag_name_too_long(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': 'A' * 33, 'color': '#000000'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 400

    def test_create_tag_invalid_color(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': '测试', 'color': 'red'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 400

    def test_update_tag_success(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        r = client.post('/api/tags', data=json.dumps({'name': '旧名', 'color': '#ff0000'}), headers=hdrs)
        tag_id = json.loads(r.data)['tag']['id']

        resp = client.put(
            f'/api/tags/{tag_id}',
            data=json.dumps({'name': '新名', 'color': '#00ff00'}),
            headers=hdrs,
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['tag']['name'] == '新名'
        assert data['tag']['color'] == '#00ff00'

    def test_update_nonexistent_tag(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.put(
            '/api/tags/9999',
            data=json.dumps({'name': '新名'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 404

    def test_delete_tag_success(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        r = client.post('/api/tags', data=json.dumps({'name': '待删', 'color': '#000000'}), headers=hdrs)
        tag_id = json.loads(r.data)['tag']['id']

        resp = client.delete(f'/api/tags/{tag_id}', headers=hdrs)
        assert resp.status_code == 200

        # 验证已删除
        resp_list = client.get('/api/tags')
        tags = json.loads(resp_list.data)['tags']
        assert all(t['id'] != tag_id for t in tags)

    def test_list_tags(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        client.post('/api/tags', data=json.dumps({'name': 'A标签', 'color': '#aaa'}), headers=hdrs)
        client.post('/api/tags', data=json.dumps({'name': 'B标签', 'color': '#bbb'}), headers=hdrs)

        resp = client.get('/api/tags')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['tags']) == 2

    def test_member_cannot_create_tag(self, app):
        _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        client = _login_as(app, 'member1', 'Member@Pass1', 'member')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': '非法标签', 'color': '#ff0000'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════
# 文件-标签关联 + 7 天权限测试
# ═══════════════════════════════════════════

class TestFileTags:

    def test_member_can_set_own_file_tags(self, app):
        """上传者 7 天内可设置自己文件的标签"""
        _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        member_client = _login_as(app, 'member1', 'Member@Pass1', 'member')

        # 以 member 身份上传文件
        with app.app_context():
            member = User.query.filter_by(username='member1').first()
            f = File(
                filename='test.pdf', original_filename='test.pdf',
                file_path='2026/06/test.pdf', file_number='F-20260625-001',
                folder_id=info['folder_id'], uploader_id=member.id,
                project_id=info['project_id'], file_type='PDF', file_size=1024,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        resp = member_client.put(
            f'/api/tags/file/{file_id}',
            data=json.dumps({'tag_ids': info['tag_ids']}),
            headers=_api_headers(member_client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert len(data['tags']) == 2

    def test_cannot_edit_others_file_tags(self, app):
        """不能编辑他人上传的文件标签"""
        admin_client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        member_client = _login_as(app, 'member1', 'Member@Pass1', 'member')

        # admin 上传文件
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            f = File(
                filename='admin_doc.pdf', original_filename='admin_doc.pdf',
                file_path='2026/06/admin_doc.pdf', file_number='F-20260625-002',
                folder_id=info['folder_id'], uploader_id=admin.id,
                project_id=info['project_id'], file_type='PDF', file_size=2048,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        # member 尝试编辑 admin 的文件标签
        resp = member_client.put(
            f'/api/tags/file/{file_id}',
            data=json.dumps({'tag_ids': info['tag_ids']}),
            headers=_api_headers(member_client),
        )
        assert resp.status_code == 403

    def test_get_file_tags_with_can_edit_flag(self, app):
        """获取文件标签时应返回 can_edit 和 reason"""
        _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        member_client = _login_as(app, 'member1', 'Member@Pass1', 'member')

        with app.app_context():
            member = User.query.filter_by(username='member1').first()
            f = File(
                filename='member_doc.pdf', original_filename='member_doc.pdf',
                file_path='2026/06/member_doc.pdf', file_number='F-20260625-003',
                folder_id=info['folder_id'], uploader_id=member.id,
                project_id=info['project_id'], file_type='PDF', file_size=2048,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        resp = member_client.get(f'/api/tags/file/{file_id}')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert data['can_edit'] is True
        assert data['tags'] == []

    def test_admin_can_edit_all_tags(self, app):
        """admin 可编辑任意文件的标签"""
        admin_client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        _login_as(app, 'member1', 'Member@Pass1', 'member')

        # member 上传文件
        with app.app_context():
            member = User.query.filter_by(username='member1').first()
            f = File(
                filename='member_doc2.pdf', original_filename='member_doc2.pdf',
                file_path='2026/06/member_doc2.pdf', file_number='F-20260625-004',
                folder_id=info['folder_id'], uploader_id=member.id,
                project_id=info['project_id'], file_type='PDF', file_size=4096,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        # admin 设置标签
        resp = admin_client.put(
            f'/api/tags/file/{file_id}',
            data=json.dumps({'tag_ids': info['tag_ids']}),
            headers=_api_headers(admin_client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert len(data['tags']) == 2
```

- [ ] **Step 2: 运行测试**

```powershell
pytest tests/test_tags.py -v
```

Expected: 13 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_tags.py
git commit -m "test: add tag CRUD and file-tag permission tests (13 cases)"
```

---

### Task 7: 追加 CSS 样式 `static/css/app.css`

**Files:**
- Modify: `static/css/app.css` (末尾追加)

- [ ] **Step 1: 在 `static/css/app.css` 末尾追加标签样式**

```css
/* ═══════════════════════════════════════
   F4-1 标签系统样式
   ═══════════════════════════════════════ */

/* 文件列表行中的标签容器 */
.file-tags {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-left: 6px;
    vertical-align: middle;
}

/* 标签徽章 */
.tag-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 500;
    line-height: 1.4;
    white-space: nowrap;
}

.tag-badge .tag-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
    flex-shrink: 0;
}

/* ── 标签管理弹窗 ── */
.tag-mgmt-list {
    max-height: 300px;
    overflow-y: auto;
}

.tag-mgmt-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0.6rem;
    border-bottom: 1px solid #f0f0f0;
}

.tag-mgmt-item:last-child {
    border-bottom: none;
}

.tag-mgmt-info {
    display: flex;
    align-items: center;
    gap: 8px;
}

.tag-mgmt-actions .btn {
    font-size: 0.72rem;
    padding: 0.12rem 0.5rem;
    margin-left: 3px;
}

/* ── 上传弹窗标签多选 ── */
.tag-selector {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 4px 0;
}

.tag-selector .tag-check-label {
    display: inline-flex;
    align-items: center;
    cursor: pointer;
    padding: 3px 8px;
    border: 1px solid #dee2e6;
    border-radius: 12px;
    font-size: 0.75rem;
    transition: all 0.15s ease;
    user-select: none;
}

.tag-selector .tag-check-label:hover {
    border-color: #007bff;
}

.tag-selector .tag-check-label.selected {
    background: #007bff;
    color: #fff;
    border-color: #007bff;
}

.tag-selector .tag-check-label input[type="checkbox"] {
    display: none;
}

.tag-selector .tag-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/css/app.css
git commit -m "style: add tag badge, management, and selector CSS for F4-1"
```

---

### Task 8: 修改 `static/js/file_view.js` 渲染标签

**Files:**
- Modify: `static/js/file_view.js` (line 63)

- [ ] **Step 1: 在 `renderFileList()` 中渲染标签 Badge**

将 `static/js/file_view.js` 第 63 行：
```javascript
                '<td class="file-name">' + f.original_filename + shortcut + '</td>' +
```

替换为：
```javascript
                // F4-1: 渲染标签 Badges
                var tagBadges = '';
                if (f.tags && f.tags.length > 0) {
                    tagBadges = '<span class="file-tags">';
                    $.each(f.tags, function (_ti, tag) {
                        var color = LanDocHub.Utils.escapeHtml(tag.color || '#3b82f6');
                        var name = LanDocHub.Utils.escapeHtml(tag.name || '');
                        tagBadges +=
                            '<span class="tag-badge" style="background:' + color + '20;color:' + color + ';border:1px solid ' + color + '40;">' +
                            '<span class="tag-dot" style="background:' + color + ';"></span>' +
                            name +
                            '</span>';
                    });
                    tagBadges += '</span>';
                }
                '<td class="file-name">' + f.original_filename + shortcut + tagBadges + '</td>' +
```

完整替换后的 `renderFileList` 中 rows 构建部分应类似：

```javascript
        var rows = $.map(files, function (f) {
            var shortcut = f.is_shortcut ? ' ' + ICONS.LINK : '';
            // F4-1: 标签 Badges
            var tagBadges = '';
            if (f.tags && f.tags.length > 0) {
                tagBadges = '<span class="file-tags">';
                $.each(f.tags, function (_ti, tag) {
                    var color = LanDocHub.Utils.escapeHtml(tag.color || '#3b82f6');
                    var name = LanDocHub.Utils.escapeHtml(tag.name || '');
                    tagBadges +=
                        '<span class="tag-badge" style="background:' + color + '20;color:' + color + ';border:1px solid ' + color + '40;">' +
                        '<span class="tag-dot" style="background:' + color + ';"></span>' +
                        name + '</span>';
                });
                tagBadges += '</span>';
            }
            return '<tr data-file-id="' + f.id + '">' +
                '<td class="file-name">' + f.original_filename + shortcut + tagBadges + '</td>' +
                '<td><span class="file-number">' + f.file_number + '</span></td>' +
                '<td><span class="badge badge-info">' + (f.project_model || '') + '</span></td>' +
                '<td class="text-center" style="white-space:nowrap;">' +
                '<span class="badge badge-secondary mr-1">' + (f.version_number || 'I') + '</span>' +
                '<a href="/files/' + f.id + '/versions?from=' + folderId + '&file=' + f.id + '" class="badge badge-pill small" target="_blank" ' +
                'style="border:1px solid #6c757d;color:#6c757d;font-size:0.7rem;text-decoration:none;" ' +
                'title="历史版次">历史</a>' +
                '</td>' +
                '<td><span class="badge badge-light badge-type">' + f.file_type + '</span></td>' +
                '<td class="file-meta">' + LanDocHub.Utils.formatFileSize(f.file_size) + '</td>' +
                '<td class="file-meta">' + (f.uploader_name || '') + '</td>' +
                '<td class="file-meta">' + f.uploaded_at + '</td>' +
                '</tr>';
        });
```

- [ ] **Step 2: Commit**

```bash
git add static/js/file_view.js
git commit -m "feat: render file tags as colored badges in file list"
```

---

### Task 9: 修改 `static/js/upload_handler.js` — 上传弹窗 + 批量弹窗

**Files:**
- Modify: `static/js/upload_handler.js`

- [ ] **Step 1: 在 `showUploadModal()` 中添加标签多选区域（在第 263 行 `alertProjectMismatch` 之前）**

```javascript
            // F4-1: 标签选择
            '<div class="form-group">' +
            '<label>标签 <small class="text-muted">(可选，多选)</small></label>' +
            '<div class="tag-selector" id="uploadTagSelector">' +
            '<span class="text-muted small">加载中...</span>' +
            '</div>' +
            '</div>' +
```

然后在 `$modal` 声明行之后（原第 280 行），`$modal.modal('show')` 之前添加标签加载逻辑：

```javascript
        // F4-1: 加载标签选择器
        function loadTagSelector($container) {
            var csrfToken = LanDocHub.Utils.getCsrfToken();
            $.ajax({
                url: '/api/tags',
                method: 'GET',
                headers: { 'X-CSRF-Token': csrfToken },
                dataType: 'json',
            }).done(function (resp) {
                var $sel = $container || $('#uploadTagSelector');
                $sel.empty();
                if (!resp.success || !resp.tags || resp.tags.length === 0) {
                    $sel.html('<span class="text-muted small">暂无标签</span>');
                    return;
                }
                $.each(resp.tags, function (_i, tag) {
                    $sel.append(
                        '<label class="tag-check-label">' +
                        '<input type="checkbox" value="' + tag.id + '">' +
                        '<span class="tag-dot" style="background:' + LanDocHub.Utils.escapeHtml(tag.color) + ';"></span>' +
                        LanDocHub.Utils.escapeHtml(tag.name) +
                        '</label>'
                    );
                });
            });
        }
        loadTagSelector();

        // 标签多选点击切换（委托在 document 上）
        $(document).on('click', '#uploadTagSelector .tag-check-label', function (e) {
            e.preventDefault();
            var $label = $(this);
            var $cb = $label.find('input[type="checkbox"]');
            var checked = !$cb.prop('checked');
            $cb.prop('checked', checked);
            $label.toggleClass('selected', checked);
        });
```

- [ ] **Step 2: 在 `uploadFile()` 中添加 `tag_ids` 到 FormData（第 421 行 `version_note` 之后）**

```javascript
        // F4-1: 收集选中的标签 ID
        var tagIds = [];
        $('#uploadTagSelector input[type="checkbox"]:checked').each(function () {
            tagIds.push($(this).val());
        });
        if (tagIds.length > 0) {
            formData.append('tag_ids', tagIds.join(','));
        }
```

- [ ] **Step 3: 在 `showBatchUploadModal()` 批处理弹窗中添加标签多选**

在 `showBatchUploadModal` 的 `$list.html(rowsHtml)` 之后（原第 892 行），于恢复确认表单之前，添加批量标签选择：

```javascript
        // F4-1: 批量上传标签选择（所有文件共用）
        var tagSelectorHtml =
            '<div class="form-group mt-3" id="batchTagSelectorGroup">' +
            '<label>标签 <small class="text-muted">(可选，多选，所有文件共用)</small></label>' +
            '<div class="tag-selector" id="batchTagSelector">' +
            '<span class="text-muted small">加载中...</span>' +
            '</div>' +
            '</div>';

        // 在版本备注下方插入
        $('#inputBatchVersionNote').closest('.form-group').after(tagSelectorHtml);

        // 加载标签
        var csrfToken = LanDocHub.Utils.getCsrfToken();
        $.ajax({
            url: '/api/tags',
            method: 'GET',
            headers: { 'X-CSRF-Token': csrfToken },
            dataType: 'json',
        }).done(function (resp) {
            var $sel = $('#batchTagSelector').empty();
            if (!resp.success || !resp.tags || resp.tags.length === 0) {
                $sel.html('<span class="text-muted small">暂无标签</span>');
                return;
            }
            $.each(resp.tags, function (_i, tag) {
                $sel.append(
                    '<label class="tag-check-label">' +
                    '<input type="checkbox" value="' + tag.id + '">' +
                    '<span class="tag-dot" style="background:' + LanDocHub.Utils.escapeHtml(tag.color) + ';"></span>' +
                    LanDocHub.Utils.escapeHtml(tag.name) +
                    '</label>'
                );
            });
        });

        // 批量标签多选点击事件（委托）
        $(document).on('click', '#batchTagSelector .tag-check-label', function (e) {
            e.preventDefault();
            var $label = $(this);
            var $cb = $label.find('input[type="checkbox"]');
            var checked = !$cb.prop('checked');
            $cb.prop('checked', checked);
            $label.toggleClass('selected', checked);
        });
```

- [ ] **Step 4: 在 `uploadBatch()` 中添加 `tag_ids`（找到构建 FormData 并调用 `/api/files/upload` 的位置）**

在 `uploadBatch()` 函数中，搜索构建 `formData` 并调用 `/api/files/upload` 的地方（约第 920-960 行区域），在 `formData.append(...)` 之后添加：

```javascript
                // F4-1: 收集批量标签 ID
                var batchTagIds = [];
                $('#batchTagSelector input[type="checkbox"]:checked').each(function () {
                    batchTagIds.push($(this).val());
                });
                if (batchTagIds.length > 0) {
                    formData.append('tag_ids', batchTagIds.join(','));
                }
```

同时，在 `autoUpload()` 调用的 `uploadBatch(fileArray, projectId, folderId, 'I', '')` 中，批量标签选择器里的标签 ID 会在 `uploadBatch` 内部每个文件的 FormData 构建时被读取（上面添加的代码读取的是全局 `#batchTagSelector`，所以对所有文件生效）。

- [ ] **Step 5: Commit**

```bash
git add static/js/upload_handler.js
git commit -m "feat: add tag multi-select to upload modal and batch upload modal"
```

---

### Task 10: 修改 `templates/base.html` + 创建 `static/js/tag_management.js`

**Files:**
- Modify: `templates/base.html` (line 71-77)
- Create: `static/js/tag_management.js`

- [ ] **Step 1: 在 `base.html` 侧边栏 admin 操作区添加"标签管理"按钮**

将 `templates/base.html` 第 71-77 行改为：

```html
        {% if session.get('user_role') == 'admin' %}
        <div class="sidebar-footer">
            <button class="btn btn-outline-secondary btn-sm" id="btnCreate">
                📁 新增项目
            </button>
            <button class="btn btn-outline-secondary btn-sm ml-1" id="btnTagManage">
                🏷️ 标签管理
            </button>
        </div>
        {% endif %}
```

- [ ] **Step 2: 在 `base.html` 加载 `tag_management.js`（第 170 行 `file_view.js` 之后）**

```html
<!-- 标签管理 JS（F4-1） -->
<script src="{{ url_for('static', filename='js/tag_management.js') }}"></script>
```

- [ ] **Step 3: 创建 `static/js/tag_management.js`**

```javascript
/**
 * F4-1 标签管理 —— admin 端标签 CRUD 弹窗
 */
$(function () {
    'use strict';

    var $btnTagManage = $('#btnTagManage');
    if (!$btnTagManage.length) return;

    $btnTagManage.on('click', function () {
        openTagManagementModal();
    });

    function openTagManagementModal() {
        $('#tagManagementModal').remove();

        var html =
            '<div class="modal fade" id="tagManagementModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-primary text-white">' +
            '<h5 class="modal-title">🏷️ 标签管理</h5>' +
            '<button type="button" class="close text-white" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<div class="form-row mb-3">' +
            '<div class="col-6">' +
            '<input type="text" class="form-control form-control-sm" id="inputNewTagName" ' +
            'placeholder="新标签名，最多 32 字" maxlength="32">' +
            '</div>' +
            '<div class="col-3">' +
            '<input type="color" class="form-control form-control-sm" id="inputNewTagColor" ' +
            'value="#3b82f6" style="height:31px;padding:2px;">' +
            '</div>' +
            '<div class="col-3">' +
            '<button class="btn btn-success btn-sm btn-block" id="btnCreateTag">创建</button>' +
            '</div>' +
            '</div>' +
            '<div class="tag-mgmt-list" id="tagMgmtList">' +
            '<div class="text-center text-muted py-2 small">加载中...</div>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>';

        $('body').append(html);
        var $modal = $('#tagManagementModal');
        $modal.modal('show');
        $modal.on('hidden.bs.modal', function () { $modal.remove(); });

        loadTagMgmtList();

        // 创建标签
        $('#btnCreateTag').on('click', function () {
            var name = $('#inputNewTagName').val().trim();
            var color = $('#inputNewTagColor').val().trim() || '#3b82f6';
            if (!name) { alert('请输入标签名'); return; }

            $.ajax({
                url: '/api/tags',
                method: 'POST',
                contentType: 'application/json',
                headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
                data: JSON.stringify({ name: name, color: color }),
            }).done(function (resp) {
                if (resp.success) {
                    $('#inputNewTagName').val('');
                    $('#inputNewTagColor').val('#3b82f6');
                    loadTagMgmtList();
                } else {
                    var msg = Object.values(resp.errors || {}).flat().join('; ');
                    alert(msg || '创建失败');
                }
            }).fail(function () {
                alert('创建失败，请重试');
            });
        });

        // ── 编辑标签 ──
        $('#tagMgmtList').on('click', '.btn-edit-tag', function () {
            var $item = $(this).closest('.tag-mgmt-item');
            var tagId = $item.data('tag-id');
            var currentName = $item.data('tag-name');
            var currentColor = $item.data('tag-color');

            var newName = prompt('编辑标签名（留空不修改）：', currentName);
            if (newName === null) return;

            var payload = {};
            if (newName.trim() && newName.trim() !== currentName) {
                payload.name = newName.trim();
            }

            var newColor = prompt('编辑颜色（如 #ff0000，留空不修改）：', currentColor);
            if (newColor !== null && newColor.trim() && newColor.trim() !== currentColor) {
                payload.color = newColor.trim();
            }

            if ($.isEmptyObject(payload)) return;

            $.ajax({
                url: '/api/tags/' + tagId,
                method: 'PUT',
                contentType: 'application/json',
                headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
                data: JSON.stringify(payload),
            }).done(function (resp) {
                if (resp.success) {
                    loadTagMgmtList();
                } else {
                    var msg = Object.values(resp.errors || {}).flat().join('; ');
                    alert(msg || '编辑失败');
                }
            }).fail(function () {
                alert('编辑失败，请重试');
            });
        });

        // ── 删除标签 ──
        $('#tagMgmtList').on('click', '.btn-delete-tag', function () {
            var $item = $(this).closest('.tag-mgmt-item');
            var tagId = $item.data('tag-id');
            var tagName = $item.data('tag-name');
            if (!confirm('确定删除标签 "' + tagName + '"？\n删除后所有文件上该标签将被移除。')) return;

            $.ajax({
                url: '/api/tags/' + tagId,
                method: 'DELETE',
                headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
            }).done(function (resp) {
                if (resp.success) {
                    loadTagMgmtList();
                } else {
                    alert('删除失败');
                }
            }).fail(function () {
                alert('删除失败，请重试');
            });
        });
    }

    function loadTagMgmtList() {
        $.ajax({
            url: '/api/tags',
            method: 'GET',
            headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
            dataType: 'json',
        }).done(function (resp) {
            var $container = $('#tagMgmtList');
            if (!resp.success || !resp.tags) {
                $container.html('<div class="text-center text-muted py-3">加载失败</div>');
                return;
            }
            if (resp.tags.length === 0) {
                $container.html('<div class="text-center text-muted py-3">暂无标签，请在上方创建</div>');
                return;
            }
            var rows = $.map(resp.tags, function (tag) {
                var escName = LanDocHub.Utils.escapeHtml(tag.name);
                var escColor = LanDocHub.Utils.escapeHtml(tag.color);
                return '<div class="tag-mgmt-item" data-tag-id="' + tag.id +
                    '" data-tag-name="' + escName +
                    '" data-tag-color="' + escColor + '">' +
                    '<span class="tag-mgmt-info">' +
                    '<span class="tag-badge" style="background:' + escColor + '20;color:' + escColor + ';border:1px solid ' + escColor + '40;">' +
                    '<span class="tag-dot" style="background:' + escColor + ';"></span>' +
                    escName + '</span>' +
                    '<code class="small text-muted">' + escColor + '</code>' +
                    '</span>' +
                    '<span class="tag-mgmt-actions">' +
                    '<button class="btn btn-outline-secondary btn-sm btn-edit-tag">编辑</button>' +
                    '<button class="btn btn-outline-danger btn-sm btn-delete-tag">删除</button>' +
                    '</span>' +
                    '</div>';
            });
            $container.html(rows.join(''));
        });
    }
});
```

- [ ] **Step 4: Commit**

```bash
git add templates/base.html static/js/tag_management.js
git commit -m "feat: add tag management modal for admin, accessible from sidebar"
```

---

### Task 11: 端到端验证

- [ ] **Step 1: 运行全部测试确保无回归**

```powershell
pytest tests/ -v
```

Expected: 全部测试 PASS（含新增的 13+ 标签测试）

- [ ] **Step 2: 手工验证清单**
1. 以 admin 登录 → 侧边栏出现"标签管理"按钮 → 点击弹出管理弹窗
2. 创建标签"紧急"（红色）、"待审核"（橙色）→ 标签列表更新
3. 编辑标签"紧急" → 改名为"高优" → 更新成功
4. 删除标签 → 确认后标签移除
5. 上传文件 → 弹窗出现标签多选 → 勾选"紧急"+"待审核" → 上传成功
6. 文件列表显示标签 Badge（带颜色圆点）
7. 批量上传 → 弹窗出现标签多选 → 所有文件附带相同标签
8. 以 member 登录 → 侧边栏无"标签管理"按钮
9. member 上传文件 → 可正常选择标签

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: finalize F4-1 tag system implementation"
```

---

### 假设与决策

1. **标签在文件列表中的展示密度**：仅展示标签 Badge（带颜色圆点），不含文件上传者或 7 天编辑入口。标签编辑功能（成员端）留待 F10（标签管理）或后续迭代中实现 UI —— 后端 API 已就绪（`PUT /api/tags/file/<id>`）。
2. **批量上传标签**：所有文件共用同一组标签选择，简化交互。
3. **标签数量**：不设上限，前端通过 flex-wrap 自动换行显示。
4. **Service 层异常体系**：当前 Service 层仍使用 `{'success': bool, ...}` 字典返回模式（与现有代码一致），暂不迁移到 `exceptions.py` 异常体系 —— 这是两个优化计划文档中标注的后续改进项。
5. **`get_files_by_folder` 无 joinedload**：对单文件夹几十个文件用 lazy loading 加载标签完全可接受，避免改动现有查询结构。

### 验证步骤

1. `pytest tests/test_tags.py -v` — 13 个测试全部通过
2. `pytest tests/ -v` — 无回归
3. `python app.py` 启动 → 浏览器访问 → 按 Task 11 手工验证清单逐项确认
4. 检查浏览器 Console 无 JS 错误
5. 检查终端无 500 错误日志
