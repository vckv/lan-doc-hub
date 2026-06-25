# F5-2 历史版本面板 实施计划

> **For agentic workers:** 按任务顺序逐步执行，每步含精确代码和命令。使用 checkbox (`- [ ]`) 跟踪进度。

**Goal:** 文件列表每行"历史版本"按钮改为 AJAX 模态面板，以时间线展示该文件全部历史版本（版本序号、备注、上传者、时间、大小），预留下载/预览/删除按钮。

**Architecture:** 后端 `get_files_by_folder()` 新增 `has_versions` 布尔字段；前端新建 `version_history_modal.js`（IIFE 模态框，AJAX 加载 `/api/files/<id>/versions` 数据）；`file_view.js` 中替换 `<a href>` 链接为按钮 + 条件显示逻辑；新增 CSS 样式。

**Tech Stack:** Python 3.12+ / Flask 3.1 / SQLAlchemy / jQuery 3.x / Bootstrap 4

---

## 当前状态分析

### 已有实现（需替换）

`static/js/file_view.js:82-86` — "历史"按钮始终显示，以 `<a href>` 在新窗口打开服务器渲染页面 `file_versions.html`：

```javascript
'<a href="/files/' + f.id + '/versions?from=' + folderId + '&file=' + f.id +
'" class="badge badge-pill small" target="_blank" ' +
'style="border:1px solid #6c757d;color:#6c757d;font-size:0.7rem;text-decoration:none;" ' +
'title="历史版次">历史</a>' +
```

### 已有实现（保留并复用）

| 组件 | 文件 | 说明 |
|---|---|---|
| `GET /api/files/<id>/versions` | `routes/files.py:171-179` | 返回 `{current_file, history[]}` JSON，完全满足 F5-2 数据需求 |
| `get_file_version_history()` | `services/file_service.py:317-365` | 按 `original_filename + project_id` 查找所有版本（含当前和非当前），按时间倒序 |
| `file_versions.html` | `templates/file_versions.html` | 服务器渲染独立页面，F5-2 完成后可删除 |

### 关键发现

- **`FileVersion` 表与 `files.is_current=False` 共存**：F5-1 的 `_archive_existing_file()` 同时创建 `FileVersion` 记录和标记 `is_current=False`。`get_file_version_history()` 查询 `files` 表（按 `original_filename + project_id`），能正确覆盖所有历史版本。
- **检测"是否有历史版本"**：统计同名同项目且 `id != 当前文件id` 的文件数量。若大于 0，则有历史 → 显示按钮。
- **F6 预览和 F8-1 下载未实现**：模态框中预留按钮，点击时用 `alert('即将开放')` 占位。
- **F11-1 删除版本未实现**：同理预留按钮占位。

### 涉及文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `services/file_service.py` | 修改 | `get_files_by_folder()` 新增 `has_versions` 字段 |
| `static/js/version_history_modal.js` | 新建 | 历史版本模态框（~120 行，IIFE 模式） |
| `static/js/file_view.js` | 修改 | 替换 `<a href>` 为按钮 + 条件显示逻辑 |
| `static/css/app.css` | 修改 | 新增模态框和时间线条目样式 |
| `templates/base.html` | 修改 | 注册 `version_history_modal.js` |
| `tests/test_version_history.py` | 新建 | 历史版本面板相关的后端测试 |

> 注：`file_versions.html` 在 F5-2 完成后可删除（功能已被模态面板取代）。

---

## Task 1: 后端 — `get_files_by_folder()` 新增 `has_versions` 字段

**Files:**
- Modify: `services/file_service.py`（修改 `get_files_by_folder()` 函数）

- [ ] **Step 1: 在文件列表查询中添加 `has_versions` 判断**

修改 `services/file_service.py` 中 `get_files_by_folder()` 的返回构建逻辑（约第 52-71 行）。在构建每个文件条目时，查询是否存在同名同项目的历史文件。

当前代码（第 46-71 行）：

```python
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

替换为：

```python
    # F5-2: 批量检测每个文件是否有历史版本
    # 收集所有 (original_filename, project_id) 对
    file_keys = list({(f.original_filename, f.project_id) for f, _ in files})
    has_history_set = set()
    if file_keys:
        from sqlalchemy import and_, or_
        conditions = [
            and_(
                File.original_filename == fn,
                File.project_id == pid,
                File.is_current == False,
            )
            for fn, pid in file_keys
        ]
        if conditions:
            non_current = (
                db.session.query(File.original_filename, File.project_id)
                .filter(or_(*conditions))
                .all()
            )
            has_history_set = {(fn, pid) for fn, pid in non_current}

    result = []
    for f, model in files:
        tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in f.tags]
        has_versions = (f.original_filename, f.project_id) in has_history_set
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
            'has_versions': has_versions,  # F5-2
            'tags': tags,
        })
    return result
```

**设计说明：** 使用批量查询（一次 `SELECT` 而非 N 次），筛选 `is_current=False` 的同名同项目文件。如果存在，说明有历史版本。

- [ ] **Step 2: 验证现有测试通过**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部 142 个测试通过。

- [ ] **Step 3: 提交**

```powershell
git add services/file_service.py
git commit -m "feat: add has_versions field to file list API for F5-2"
```

---

## Task 2: 前端 — 创建 `version_history_modal.js` 模态框

**Files:**
- Create: `static/js/version_history_modal.js`

- [ ] **Step 1: 创建模态框文件**

```javascript
/**
 * F5-2 历史版本面板
 *
 * 用法：
 *   VersionHistoryModal.show(fileId)
 *
 * 加载 GET /api/files/<fileId>/versions，弹出 Bootstrap Modal
 * 展示版本时间线列表：版本序号、备注、上传者、时间、大小
 */
var VersionHistoryModal = (function () {
    'use strict';

    var $modal = null;
    var _fileId = null;

    function init() {
        if ($modal) return;
        var html =
            '<div class="modal fade" id="versionHistoryModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered modal-lg" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-primary text-white">' +
            '<h5 class="modal-title">' + LanDocHub.ICONS.FILE_EMPTY + ' <span id="vhTitle">版本历史</span></h5>' +
            '<button type="button" class="close text-white" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body" style="max-height:500px;overflow-y:auto;">' +
            '<div id="vhFileInfo" class="small text-muted mb-3"></div>' +
            '<div id="vhLoading" class="text-center py-4 text-muted">加载中...</div>' +
            '<div id="vhVersionList" style="display:none;"></div>' +
            '<div id="vhEmpty" style="display:none;" class="text-center py-4 text-muted">暂无历史版本</div>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">关闭</button>' +
            '</div>' +
            '</div></div></div>';
        $('body').append(html);
        $modal = $('#versionHistoryModal');

        $modal.on('hidden.bs.modal', function () {
            _fileId = null;
        });
    }

    /**
     * 显示历史版本面板
     * @param {number} fileId 文件 ID
     */
    function show(fileId) {
        init();
        _fileId = fileId;

        $('#vhTitle').text('版本历史');
        $('#vhFileInfo').text('');
        $('#vhVersionList').hide().empty();
        $('#vhEmpty').hide();
        $('#vhLoading').show();

        $modal.modal('show');

        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
        $.ajax({
            url: '/api/files/' + fileId + '/versions',
            method: 'GET',
            headers: { 'X-CSRF-Token': csrfToken },
            dataType: 'json',
        }).done(function (resp) {
            $('#vhLoading').hide();
            if (!resp.success) {
                $('#vhEmpty').text('加载失败').show();
                return;
            }
            var cur = resp.current_file || {};
            $('#vhTitle').text(LanDocHub.Utils.escapeHtml(cur.original_filename || '版本历史'));
            $('#vhFileInfo').html(
                '编号：' + LanDocHub.Utils.escapeHtml(cur.file_number || '-') +
                ' &nbsp;|&nbsp; 项目：' + LanDocHub.Utils.escapeHtml(cur.project_model || '') +
                ' ' + LanDocHub.Utils.escapeHtml(cur.project_name || '')
            );

            var history = resp.history || [];
            if (history.length === 0) {
                $('#vhEmpty').show();
                return;
            }

            var html = '<div class="vh-timeline">';
            $.each(history, function (i, v) {
                var isCurrent = v.is_current;
                var versionLabel = isCurrent
                    ? '<span class="badge badge-success">当前</span>'
                    : '';
                html +=
                    '<div class="vh-item' + (isCurrent ? ' vh-item-current' : '') + '">' +
                    '<div class="vh-item-header">' +
                    '<span class="vh-version-badge">' +
                    LanDocHub.Utils.escapeHtml(v.version_number || '-') +
                    '</span>' +
                    versionLabel +
                    '<span class="small text-muted ml-2">' +
                    LanDocHub.Utils.escapeHtml(v.version_note || '') +
                    '</span>' +
                    '<span class="float-right small text-muted">' +
                    LanDocHub.Utils.escapeHtml(v.uploaded_at || '') +
                    '</span>' +
                    '</div>' +
                    '<div class="vh-item-body">' +
                    '<span class="small text-muted">' +
                    LanDocHub.Utils.formatFileSize(v.file_size || 0) +
                    ' &nbsp;|&nbsp; ' + LanDocHub.Utils.escapeHtml(v.uploader_name || '') +
                    '</span>' +
                    '</div>' +
                    '<div class="vh-item-actions">' +
                    '<button class="btn btn-outline-secondary btn-xs vh-btn-preview" ' +
                    'data-file-id="' + v.id + '" title="在线预览（即将开放）">' +
                    LanDocHub.ICONS.FILE_EMPTY + ' 预览</button>' +
                    '<button class="btn btn-outline-primary btn-xs vh-btn-download" ' +
                    'data-file-id="' + v.id + '" title="下载该版本（即将开放）">' +
                    LanDocHub.ICONS.UPLOAD + ' 下载</button>' +
                    '<button class="btn btn-outline-danger btn-xs vh-btn-delete" ' +
                    'data-file-id="' + v.id + '" title="删除该版本（即将开放）">🗑 删除</button>' +
                    '</div>' +
                    '</div>';
            });
            html += '</div>';
            $('#vhVersionList').html(html).show();

            // 绑定按钮事件（预览/下载/删除均为占位）
            $('#vhVersionList').on('click', '.vh-btn-preview', function () {
                alert('在线预览功能即将开放（F6 阶段）');
            });
            $('#vhVersionList').on('click', '.vh-btn-download', function () {
                alert('单文件下载功能即将开放（F8-1 阶段）');
            });
            $('#vhVersionList').on('click', '.vh-btn-delete', function () {
                alert('版本删除功能即将开放（F11-1 阶段）');
            });
        }).fail(function () {
            $('#vhLoading').hide();
            $('#vhEmpty').text('加载失败，请稍后重试').show();
        });
    }

    return { show: show };
})();
```

- [ ] **Step 2: 提交**

```powershell
git add static/js/version_history_modal.js
git commit -m "feat: add VersionHistoryModal for F5-2 version panel"
```

---

## Task 3: 前端 — 修改 `file_view.js` 替换历史按钮

**Files:**
- Modify: `static/js/file_view.js`（修改第 82-85 行）

- [ ] **Step 1: 替换 `<a href>` 为条件按钮**

修改 `static/js/file_view.js` 第 82-85 行：

```diff
-             '<a href="/files/' + f.id + '/versions?from=' + folderId + '&file=' + f.id + '" class="badge badge-pill small" target="_blank" ' +
-             'style="border:1px solid #6c757d;color:#6c757d;font-size:0.7rem;text-decoration:none;" ' +
-             'title="历史版次">历史</a>' +
+             (f.has_versions
+                 ? '<button class="btn btn-sm btn-outline-secondary btn-history" ' +
+                   'data-file-id="' + f.id + '" title="查看历史版本" ' +
+                   'style="font-size:0.7rem;padding:1px 6px;">历史</button>'
+                 : '') +
```

- [ ] **Step 2: 绑定按钮点击事件**

在 `file_view.js` 的 `_setup()` 或 `fileView` 初始化中（文件末尾附近），新增事件委托：

找到 `$(document).on('click', ...)` 区域或 IIFE 初始化块，新增：

```javascript
    // F5-2: 历史版本按钮点击
    $(document).on('click', '.btn-history', function () {
        var fileId = $(this).data('file-id');
        if (fileId) {
            VersionHistoryModal.show(fileId);
        }
    });
```

插入位置：在 `$('body').on('folder-selected', ...)` 之后（约第 27 行之后）或 IIFE 的 `$(document).ready(...)` 块中。

实际文件末尾处查看当前事件绑定位置：

```powershell
Select-String -Path 'static/js/file_view.js' -Pattern '\$\(document\)\.on|ready|folder-selected' 2>&1
```

找到合适位置插入。

- [ ] **Step 3: 验证 `has_versions` 字段在现有测试中不破坏兼容性**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部 142 个测试通过。

- [ ] **Step 4: 提交**

```powershell
git add static/js/file_view.js
git commit -m "feat: replace history link with modal trigger button for F5-2"
```

---

## Task 4: 前端 — 注册 JS + 添加 CSS 样式

**Files:**
- Modify: `templates/base.html`
- Modify: `static/css/app.css`

- [ ] **Step 1: 在 `base.html` 中注册 `version_history_modal.js`**

在 `templates/base.html` 中，找到 `duplicate_check_modal.js` 的 `<script>` 标签行，在其**之后**、`file_view.js` 之前插入：

```html
<!-- F5-2 历史版本面板 JS -->
<script src="{{ url_for('static', filename='js/version_history_modal.js') }}"></script>
```

先定位 `file_view.js` 的加载位置：

```powershell
Select-String -Path 'templates/base.html' -Pattern 'file_view\.js|duplicate_check_modal' 2>&1
```

然后插入新脚本标签。

- [ ] **Step 2: 在 `app.css` 中添加样式**

```css
/* ── F5-2 历史版本面板 ── */
.vh-timeline {
    position: relative;
    padding-left: 24px;
}

.vh-timeline::before {
    content: '';
    position: absolute;
    left: 8px;
    top: 8px;
    bottom: 8px;
    width: 2px;
    background: #dee2e6;
}

.vh-item {
    position: relative;
    padding: 10px 14px;
    margin-bottom: 8px;
    background: #f8f9fa;
    border-radius: 6px;
    border-left: 3px solid #e2e8f0;
}

.vh-item-current {
    background: #e8f5e9;
    border-left-color: #28a745;
}

.vh-item-header {
    margin-bottom: 4px;
}

.vh-version-badge {
    display: inline-block;
    min-width: 28px;
    text-align: center;
    background: #6c757d;
    color: #fff;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 6px;
}

.vh-item-body {
    margin-bottom: 6px;
}

.vh-item-actions {
    display: flex;
    gap: 6px;
}

.vh-item-actions .btn-xs {
    font-size: 0.72rem;
    padding: 1px 8px;
    line-height: 1.4;
}

.btn-history {
    cursor: pointer;
}
```

- [ ] **Step 3: 提交**

```powershell
git add templates/base.html static/css/app.css
git commit -m "feat: register version_history_modal.js and add CSS for F5-2"
```

---

## Task 5: 测试 — 编写后端测试

**Files:**
- Create: `tests/test_version_history.py`

- [ ] **Step 1: 编写测试文件**

```python
"""F5-2: 历史版本面板 测试"""

import io
import json
import os
import tempfile

import pytest
import bcrypt

from models import db as _db, File, FileVersion, Folder, Project, User


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


def _get_csrf(client):
    """从 session 中提取 CSRF Token"""
    with client.session_transaction() as sess:
        return sess.get('csrf_token', '')


def _upload_file(client, content, filename, proj_id, folder_id, **extra):
    """上传文件辅助函数"""
    data = {
        'file': (io.BytesIO(content), filename),
        'project_id': str(proj_id),
        'folder_id': str(folder_id),
        'csrf_token': _get_csrf(client),
    }
    data.update(extra)
    return client.post('/api/files/upload', data=data)


def _seed_project_and_folder(app, project_model='F5T2', project_name='测试项目'):
    """创建测试用的项目和根文件夹"""
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        proj = Project(model=project_model, name=project_name)
        _db.session.add(proj)
        _db.session.flush()

        root = Folder(
            name=f'{project_model}_{project_name}',
            is_project_root=True,
            project_id=proj.id,
            parent_id=None,
            created_by=admin.id if admin else 1,
        )
        _db.session.add(root)
        _db.session.commit()
        return proj.id, root.id


# ===========================================
# 版本历史 API 测试
# ===========================================

class TestVersionHistoryAPI:

    def test_versions_endpoint_returns_data(self, app):
        """GET /api/files/<id>/versions 返回正确结构"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传一个文件
        resp = _upload_file(client, b'hello', 'doc.pdf', proj_id, folder_id,
                           version_number='I')
        assert resp.status_code == 201
        file_id = json.loads(resp.data)['file']['id']

        # 查询版本
        resp = client.get(f'/api/files/{file_id}/versions')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert 'current_file' in data
        assert 'history' in data
        assert data['current_file']['original_filename'] == 'doc.pdf'
        assert len(data['history']) == 1  # 仅当前版本
        assert data['history'][0]['is_current'] is True
        assert data['history'][0]['version_number'] == 'I'

    def test_versions_endpoint_returns_404_for_nonexistent(self, app):
        """不存在的文件返回 404"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.get('/api/files/9999/versions')
        assert resp.status_code == 404

    def test_versions_includes_replaced_files(self, app):
        """被覆盖替换的旧文件也应出现在 history 中"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传 v1，然后覆盖为 v2
        r1 = _upload_file(client, b'v1', 'report.pdf', proj_id, folder_id,
                         version_number='I')
        assert r1.status_code == 201
        file_id_v1 = json.loads(r1.data)['file']['id']

        r2 = _upload_file(client, b'v2', 'report.pdf', proj_id, folder_id,
                         version_number='I', duplicate_action='override')
        assert r2.status_code == 201

        # 查询版本历史（用 v2 的 ID）
        file_id_v2 = json.loads(r2.data)['file']['id']
        resp = client.get(f'/api/files/{file_id_v2}/versions')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        history = data['history']
        assert len(history) == 2  # v1 + v2

        versions = [v['version_number'] for v in history]
        assert 'I' in versions
        assert 'II' in versions

    def test_unrelated_file_not_in_history(self, app):
        """不同项目或不同文件名的版本不应出现在历史中"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传两个不同名称的文件
        _upload_file(client, b'a', 'alpha.pdf', proj_id, folder_id)
        r2 = _upload_file(client, b'b', 'beta.pdf', proj_id, folder_id)
        assert r2.status_code == 201
        file_id = json.loads(r2.data)['file']['id']

        resp = client.get(f'/api/files/{file_id}/versions')
        data = json.loads(resp.data)
        assert len(data['history']) == 1  # 仅 beta.pdf 自身


# ===========================================
# has_versions 字段测试
# ===========================================

class TestHasVersionsField:

    def test_new_file_has_versions_false(self, app):
        """新上传文件（无历史）的 has_versions 为 False"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'new.pdf', proj_id, folder_id)

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        files = json.loads(resp.data)['files']
        assert len(files) == 1
        assert files[0]['has_versions'] is False

    def test_replaced_file_has_versions_true(self, app):
        """被覆盖过的文件（存在旧版本）的 has_versions 为 True"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传然后覆盖
        _upload_file(client, b'v1', 'doc.pdf', proj_id, folder_id, version_number='I')
        _upload_file(client, b'v2', 'doc.pdf', proj_id, folder_id, version_number='I',
                    duplicate_action='override')

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        files = json.loads(resp.data)['files']
        # 当前版本 is_current=True，有旧版本 is_current=False
        current_files = [f for f in files if f['version_number'] != 'I' or True]
        # 找到当前版本（version_number='II'）
        current = [f for f in files if f['version_number'] == 'II']
        assert len(current) == 1
        assert current[0]['has_versions'] is True
```

- [ ] **Step 2: 运行测试**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/test_version_history.py -v --tb=short 2>&1 | Select-Object -Last 30
```

预期：全部通过。

- [ ] **Step 3: 提交**

```powershell
git add tests/test_version_history.py
git commit -m "test: add version history panel tests for F5-2"
```

---

## Task 6: 验证 — 运行全部测试确认通过

- [ ] **Step 1: 运行完整测试套件**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部测试通过（新增 6 个 + 原有 142 个 = 约 148 个测试）。

- [ ] **Step 2: 检查编译**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m py_compile services/file_service.py routes/files.py 2>&1
```

预期：无输出（编译通过）。

- [ ] **Step 3: 最终提交**

```powershell
git add -A
git commit -m "feat: complete F5-2 version history panel with modal UI"
```

---

## 假设与决策

1. **`has_versions` 检测方式**：批量查询 `files` 表中 `is_current=False` 的同名同项目文件。一次查询覆盖当前页所有文件，性能优于逐条 N+1 查询。
2. **"历史版本"按钮条件显示**：仅当 `has_versions=True` 时渲染按钮，符合 PRD 要求。
3. **预览/下载/删除按钮**：全部占位，点击弹出 `alert('即将开放')`。实际功能分别由 F6、F8-1、F11-1 实现。
4. **版本数据来源**：复用现有 `GET /api/files/<id>/versions` 端点和 `get_file_version_history()` 函数，无需新建后端逻辑。
5. **现有 `file_versions.html` 保留**：F5-2 完成后可删除，但为安全起见，暂不删除，待确认模态面板功能正常后再处理。
6. **无外部依赖**：纯 Flask + jQuery + Bootstrap 实现。
7. **时间线样式**：用 CSS 伪元素 `::before` 绘制竖线，通过 `.vh-item` 卡片展示每一条版本记录。

## 验证步骤

1. 运行 `pytest tests/ -v` 确认全部测试通过（预计 ~148 个测试）
2. 手动验证场景：
   - 新文件无历史 → 不显示"历史"按钮
   - 覆盖上传后 → 当前文件行显示"历史"按钮
   - 点击"历史" → 弹出模态面板 → 显示版本时间线（含当前 + 旧版本）
   - 点击预览/下载/删除 → 弹出"即将开放"提示
3. 检查旧版 `file_versions.html` 页面不再被引用后可安全删除
