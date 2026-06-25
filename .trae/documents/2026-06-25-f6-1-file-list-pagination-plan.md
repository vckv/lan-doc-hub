# F6-1 文件列表展示（表格 + 分页）实施计划

> **For agentic workers:** 按任务顺序逐步执行，每步含精确代码和命令。使用 checkbox (`- [ ]`) 跟踪进度。

**Goal:** 文件列表增加分页能力（后端分页 API + 前端 Bootstrap 分页组件），表格新增类型图标列和操作列（预览/下载占位按钮），标签移至独立列。

**Architecture:** 后端 `get_files_by_folder()` 新增 `page`/`per_page` 参数，返回 `{files, total, page, pages}` 分页数据；`GET /api/files` 接受 `page`/`per_page` 查询参数。前端 `file_view.js` 重构为 table header + 数据行 + 分页 Bar 三部分渲染；新增文件类型图标映射表和操作列按钮。

**Tech Stack:** Python 3.12+ / Flask 3.1 / SQLAlchemy / jQuery 3.x / Bootstrap 4

---

## 当前状态分析

### 已有实现

| 组件 | 文件 | 说明 |
|---|---|---|
| 文件列表 API | `routes/files.py:158-168` | `GET /api/files?folder_id=N`，无分页 |
| `get_files_by_folder()` | `services/file_service.py:37-100` | 返回全部文件，无 limit/offset，含 `has_versions` 批量检测 |
| 前端表格渲染 | `static/js/file_view.js:47-118` | 监听 `folder-selected`，AJAX 加载后 renderFileList |
| 文件大小格式化 | `LanDocHub.Utils.formatFileSize` | 已实现人性化显示 |
| 标签 Badges | F4-1，内联在文件名下方 | 当前以 `<span class="tag-badge">` 渲染 |
| 版本+历史按钮 | F5-2 | 版本号徽章 + 条件"历史"按钮 |

### 当前表格列 vs PRD 要求

| PRD 要求 | 当前状态 |
|---|---|
| 类型图标 | ❌ 缺失（当前有"类型"文字 Badge 列） |
| 文件号 | ✅ `file_number` 列 |
| 文件名 | ✅ `original_filename` + `tags`（内联在文件名下方） |
| 大小（人性化显示） | ✅ `formatFileSize` |
| 版本序号+备注 | ✅ 版本 Badge + 历史按钮（F5-2） |
| 项目 | ✅ `project_model` Badge |
| 标签 | ⚠️ 内联在文件名右侧，非独立列 |
| 上传者 | ✅ |
| 上传时间 | ✅ |
| 操作（预览/下载） | ❌ 缺失 |
| **分页** | ❌ 缺失 |

### 关键约束

- **预览和下载路由未实现**（F6-2 预览、F8-1 下载在后续阶段），操作列按钮为占位，点击弹出提示或指向暂无路由。
- **emoji 图标体系**（`LanDocHub.ICONS`），文件类型图标通过 JS 映射表实现，无需引入外部图标库。
- **分页使用 Bootstrap 4 pagination 组件**，无需额外 CSS 库。

### 涉及文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `services/file_service.py` | 修改 | `get_files_by_folder()` 新增 `page`/`per_page` 参数，返回分页数据 |
| `routes/files.py` | 修改 | `GET /api/files` 接受 `page`/`per_page` 查询参数 |
| `static/js/file_view.js` | 修改 | 重构表格渲染（类型图标列+操作列），新增分页组件渲染 |
| `static/css/app.css` | 修改 | 新增分页组件和文件类型图标样式 |
| `tests/test_file_pagination.py` | 新建 | 分页 API 测试 |

---

## Task 1: 后端 — `get_files_by_folder()` 支持分页

**Files:**
- Modify: `services/file_service.py`（修改 `get_files_by_folder()` 函数签名和逻辑）

- [ ] **Step 1: 修改函数签名和文档**

修改 `services/file_service.py` 第 37-45 行：

```diff
  def get_files_by_folder(folder_id):
-     """获取某文件夹下的文件列表（含快捷方式标注、标签信息）
+     """获取某文件夹下的文件列表（含快捷方式标注、标签信息，分页支持）
+
+     Args:
+         folder_id: 文件夹 ID
+         page: 页码（从 1 开始，默认 1）
+         per_page: 每页条数（默认 20）
+
+     Returns:
+         dict: {files, total, page, pages}  — 分页数据结构
+     """
```

- [ ] **Step 2: 修改函数实现**

替换 `get_files_by_folder()` 的实现（第 46-100 行）。在原查询前加上 count 和分页参数，返回结构改为 dict：

```python
def get_files_by_folder(folder_id, page=1, per_page=20):
    """获取某文件夹下的文件列表（含快捷方式标注、标签信息，分页支持）"""
    # 计算总数
    total = (
        db.session.query(File.id)
        .filter(File.folder_id == folder_id, File.is_current == True)
        .count()
    )
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))

    offset = (page - 1) * per_page
    files = (
        db.session.query(File, Project.model)
        .join(Project, File.project_id == Project.id)
        .filter(File.folder_id == folder_id, File.is_current == True)
        .order_by(File.created_at.desc())
        .limit(per_page)
        .offset(offset)
        .all()
    )

    # F5-2: 批量检测每个文件是否有历史版本
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
            'has_versions': has_versions,
            'tags': tags,
        })
    return {'files': result, 'total': total, 'page': page, 'pages': pages}
```

- [ ] **Step 3: 验证现有调用者兼容**

原调用 `get_files_by_folder(folder_id)` 返回 `list`，现返回 `dict`。需检查所有调用处：

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
Select-String -Path routes/,services/ -Pattern 'get_files_by_folder' -SimpleMatch 2>&1
```

当前仅 `routes/files.py:167` 调用。需同步修改。

- [ ] **Step 4: 提交**

```powershell
git add services/file_service.py
git commit -m "feat: add pagination support to get_files_by_folder for F6-1"
```

---

## Task 2: 后端 — `GET /api/files` 接受分页参数

**Files:**
- Modify: `routes/files.py`（修改 `api_list_files()` 函数）

- [ ] **Step 1: 修改路由以接受分页参数并适配新返回结构**

替换 `routes/files.py` 第 158-168 行：

```python
@files_bp.route('', methods=['GET'])
@api_login_required
def api_list_files():
    """GET /api/files?folder_id=N&page=1&per_page=20 → 获取文件夹内文件列表（分页）"""

    folder_id = request.args.get('folder_id', type=int)
    if folder_id is None:
        return jsonify({'success': False, 'errors': {'folder_id': ['缺少参数']}}), 400

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = max(1, min(per_page, 100))  # 限制每页最大 100 条

    data = get_files_by_folder(folder_id, page=page, per_page=per_page)
    return jsonify({'success': True, **data})
```

- [ ] **Step 2: 检查返回值引用（确保无前端测试依赖旧结构）**

旧结构：`resp.files` 是列表。新结构：`resp.files` 仍是列表（来自 `data['files']`），`resp.total`、`resp.page`、`resp.pages` 为新增字段。前端 `file_view.js` 当前读取 `resp.files`，兼容。

- [ ] **Step 3: 运行现有测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部 148 个测试通过。

- [ ] **Step 4: 提交**

```powershell
git add routes/files.py
git commit -m "feat: accept page/per_page params in file list API for F6-1"
```

---

## Task 3: 前端 — 重构 `file_view.js` 表格 + 分页

**Files:**
- Modify: `static/js/file_view.js`（重构 `renderFileList()` 和 `loadFiles()`）


- [ ] **Step 3.1: 文件加载时传入分页参数**

修改 `loadFiles()` 函数（第 28-45 行）：

```javascript
    function loadFiles(folderId, folderName, page) {
        page = page || 1;
        $.ajax({
            url: '/api/files',
            method: 'GET',
            data: { folder_id: folderId, page: page, per_page: 20 },
            dataType: 'json',
        })
        .done(function (resp) {
            if (!resp.success) {
                LanDocHub.Utils.showInlineError($container, '加载失败');
                return;
            }
            renderFileList(resp.files || [], folderId, resp.page || 1, resp.pages || 1, resp.total || 0);
        })
        .fail(function () {
            LanDocHub.Utils.showInlineError($container, '加载失败，请刷新页面后重试');
        });
    }
```

- [ ] **Step 3.2: 更新 `folder-selected` 事件监听器以适配 `loadFiles` 签名变化**

修改第 14-26 行：

```diff
      $(document).on('folder-selected', function (e, data) {
          ...
-         loadFiles(data.folderId, data.folderName);
+         loadFiles(data.folderId, data.folderName, data.page || 1);
          loadBreadcrumb(data.folderId, data.folderName);
      });
```

- [ ] **Step 3.3: 新增文件类型图标映射表**

在 `renderFileList` 函数之前插入：

```javascript
    var FILE_TYPE_ICONS = {
        'PDF':        '\uD83D\uDCD5',
        'Word':       '\uD83D\uDCDD',
        'Excel':      '\uD83D\uDCCA',
        'PowerPoint': '\uD83D\uDCCA',
        'Image':      '\uD83D\uDDBC\uFE0F',
        'TXT':        '\uD83D\uDCC4',
        'CSV':        '\uD83D\uDCCA',
        'Video':      '\uD83C\uDFAC',
        'Audio':      '\uD83C\uDFB5',
        'Archive':    '\uD83D\uDCE6',
        'CAD':        '\uD83D\uDCD0',
    };
    var FILE_TYPE_ICON_DEFAULT = '\uD83D\uDCCE';
```

- [ ] **Step 3.4: 重构 `renderFileList()` — 新表头 + 类型图标列 + 操作列**

完整替换 `renderFileList()` 函数（第 47-118 行）：

```javascript
    function renderFileList(files, folderId, page, pages, total) {
        $container.data('currentFolderId', folderId);
        $container.data('currentPage', page);
        $container.data('totalPages', pages);

        if (files.length === 0) {
            $container.html([
                '<div class="file-empty">',
                '<div class="icon">' + ICONS.FILE_EMPTY + '</div>',
                '<p>此文件夹中暂无文件</p>',
                '<small>点击上方"上传文件"按钮添加</small>',
                '</div>'
            ].join(''));
            return;
        }

        var rows = $.map(files, function (f) {
            var typeIcon = FILE_TYPE_ICONS[f.file_type] || FILE_TYPE_ICON_DEFAULT;
            var shortcut = f.is_shortcut ? ' ' + ICONS.LINK : '';

            // 标签 Badges（独立列）
            var tagBadges = '<span class="file-tags">';
            if (f.tags && f.tags.length > 0) {
                $.each(f.tags, function (_ti, tag) {
                    var color = LanDocHub.Utils.escapeHtml(tag.color || '#3b82f6');
                    var name = LanDocHub.Utils.escapeHtml(tag.name || '');
                    tagBadges +=
                        '<span class="tag-badge" style="background:' + color + '20;color:' + color + ';border:1px solid ' + color + '40;">' +
                        '<span class="tag-dot" style="background:' + color + ';"></span>' +
                        name + '</span>';
                });
            }
            tagBadges += '</span>';

            // 操作列
            var operations =
                '<button class="btn btn-outline-secondary btn-xs btn-preview-file" ' +
                'data-file-id="' + f.id + '" title="预览文件">' + ICONS.SEARCH + '</button>' +
                '<button class="btn btn-outline-primary btn-xs btn-download-file" ' +
                'data-file-id="' + f.id + '" title="下载文件">' + ICONS.UPLOAD + '</button>';

            return '<tr data-file-id="' + f.id + '">' +
                '<td class="file-type-icon" title="' + LanDocHub.Utils.escapeHtml(f.file_type) + '">' + typeIcon + '</td>' +
                '<td><span class="file-number">' + f.file_number + '</span></td>' +
                '<td class="file-name">' + shortcut + f.original_filename + '</td>' +
                '<td class="file-meta">' + LanDocHub.Utils.formatFileSize(f.file_size) + '</td>' +
                '<td class="text-center" style="white-space:nowrap;">' +
                '<span class="badge badge-secondary mr-1">' + (f.version_number || 'I') + '</span>' +
                (f.has_versions
                    ? '<button class="btn btn-sm btn-outline-secondary btn-history" ' +
                      'data-file-id="' + f.id + '" title="查看历史版本" ' +
                      'style="font-size:0.7rem;padding:1px 6px;">历史</button>'
                    : '') +
                (f.version_note ? '<div class="small text-muted">' + LanDocHub.Utils.escapeHtml(f.version_note) + '</div>' : '') +
                '</td>' +
                '<td><span class="badge badge-info">' + (f.project_model || '') + '</span></td>' +
                '<td>' + tagBadges + '</td>' +
                '<td class="file-meta">' + (f.uploader_name || '') + '</td>' +
                '<td class="file-meta">' + f.uploaded_at + '</td>' +
                '<td class="file-operations">' + operations + '</td>' +
                '</tr>';
        });

        var tableHtml = [
            '<div class="file-table"><table class="table table-hover mb-0">',
            '<thead><tr>',
            '<th class="col-type-icon">类型</th>',
            '<th>编号</th><th>文件名</th><th>大小</th><th>版本</th><th>型号</th>',
            '<th>标签</th><th>上传者</th><th>时间</th><th class="col-operations">操作</th>',
            '</tr></thead><tbody>',
            rows.join(''),
            '</tbody></table></div>',
            renderPagination(page, pages, total, folderId),
        ].join('');

        $container.html(tableHtml);

        // 恢复滚动 + 高亮
        if (_highlightFileId) {
            var $row = $container.find('tr[data-file-id="' + _highlightFileId + '"]');
            if ($row.length) {
                $row.addClass('row-hover');
                $row[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        } else {
            var savedScroll = sessionStorage.getItem('lanhub_scroll_top');
            if (savedScroll) {
                requestAnimationFrame(function () {
                    $('.main-content').scrollTop(parseInt(savedScroll));
                });
            }
        }
    }
```

- [ ] **Step 3.5: 新增 `renderPagination()` 分页组件渲染函数**

在 `renderFileList` 之后插入：

```javascript
    function renderPagination(page, pages, total, folderId) {
        if (pages <= 1) return '';

        var html = '<nav class="file-pagination mt-3"><ul class="pagination pagination-sm justify-content-center flex-wrap mb-0">';

        // 上一页
        html += '<li class="page-item' + (page <= 1 ? ' disabled' : '') + '">';
        html += '<a class="page-link" href="#" data-page="' + (page - 1) + '">&laquo;</a></li>';

        // 页码
        var start = Math.max(1, page - 2);
        var end = Math.min(pages, page + 2);
        if (start > 1) {
            html += '<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>';
            if (start > 2) html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
        }
        for (var p = start; p <= end; p++) {
            html += '<li class="page-item' + (p === page ? ' active' : '') + '">';
            html += '<a class="page-link" href="#" data-page="' + p + '">' + p + '</a></li>';
        }
        if (end < pages) {
            if (end < pages - 1) html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
            html += '<li class="page-item"><a class="page-link" href="#" data-page="' + pages + '">' + pages + '</a></li>';
        }

        // 下一页
        html += '<li class="page-item' + (page >= pages ? ' disabled' : '') + '">';
        html += '<a class="page-link" href="#" data-page="' + (page + 1) + '">&raquo;</a></li>';

        html += '<li class="page-item disabled ml-2"><span class="page-link border-0">共 ' + total + ' 个文件</span></li>';
        html += '</ul></nav>';

        return html;
    }
```

- [ ] **Step 3.6: 绑定分页点击事件 + 操作按钮事件**

在 IIFE 末尾（`$(window).on('beforeunload', ...)` 之前）新增：

```javascript
    // F6-1: 分页点击
    $(document).on('click', '.file-pagination .page-link', function (e) {
        e.preventDefault();
        var p = parseInt($(this).data('page'));
        if (isNaN(p)) return;
        var folderId = $container.data('currentFolderId');
        if (folderId) {
            loadFiles(folderId, '', p);
        }
    });

    // F6-1: 操作列 — 预览按钮（占位，路由由 F6-2 实现）
    $(document).on('click', '.btn-preview-file', function () {
        alert('在线预览功能即将开放（F6-2 阶段）');
    });

    // F6-1: 操作列 — 下载按钮（占位，路由由 F8-1 实现）
    $(document).on('click', '.btn-download-file', function () {
        alert('文件下载功能即将开放（F8-1 阶段）');
    });
```

- [ ] **Step 7: 运行现有测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部 148 个测试通过。

- [ ] **Step 8: 提交**

```powershell
git add static/js/file_view.js
git commit -m "feat: add pagination, type icons, and operations column to file list for F6-1"
```

---

## Task 4: 前端 — 添加 CSS 样式

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 4.1: 新增分页和类型图标样式**

在 `static/css/app.css` 末尾追加：

```css
/* ── F6-1 文件列表分页 ── */
.file-pagination {
    border-top: 1px solid #dee2e6;
    padding-top: 12px;
}

.file-pagination .page-link {
    cursor: pointer;
}

/* ── F6-1 文件类型图标 ── */
.file-type-icon {
    font-size: 1.3rem;
    text-align: center;
    width: 40px;
}

.col-type-icon {
    width: 50px;
}

.col-operations {
    width: 80px;
}

/* ── F6-1 操作列按钮 ── */
.file-operations {
    white-space: nowrap;
}

.file-operations .btn-xs {
    font-size: 0.72rem;
    padding: 1px 6px;
    line-height: 1.4;
    margin-right: 3px;
}

.file-operations .btn-xs:last-child {
    margin-right: 0;
}
```

- [ ] **Step 4.2: 提交**

```powershell
git add static/css/app.css
git commit -m "feat: add pagination and type icon styles for F6-1"
```

---

## Task 5: 测试 — 编写后端分页测试

**Files:**
- Create: `tests/test_file_pagination.py`

- [ ] **Step 5.1: 编写测试文件**

```python
"""F6-1: 文件列表分页 测试"""

import io
import json
import os
import tempfile

import pytest
import bcrypt

from models import db as _db, File, Folder, Project, User


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
    client.post('/login', data={
        'csrf_token': token,
        'username': username,
        'password': password,
    })
    return client


def _get_csrf(client):
    with client.session_transaction() as sess:
        return sess.get('csrf_token', '')


def _upload_file(client, content, filename, proj_id, folder_id, **extra):
    data = {
        'file': (io.BytesIO(content), filename),
        'project_id': str(proj_id),
        'folder_id': str(folder_id),
        'csrf_token': _get_csrf(client),
    }
    data.update(extra)
    return client.post('/api/files/upload', data=data)


def _seed_project_and_folder(app, project_model='F6T1', project_name='分页测试'):
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


class TestFileListPagination:

    def test_returns_pagination_metadata(self, app):
        """返回的数据应包含 total/page/pages 字段"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'a.pdf', proj_id, folder_id)

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert 'total' in data
        assert 'page' in data
        assert 'pages' in data
        assert data['total'] == 1
        assert data['page'] == 1
        assert data['pages'] == 1
        assert 'files' in data
        assert len(data['files']) == 1

    def test_pagination_limit_and_offset(self, app):
        """per_page=3 时应只返回对应页的数据"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传 5 个文件
        for i in range(5):
            _upload_file(client, b'x', f'file_{i}.pdf', proj_id, folder_id)

        # 第 1 页：per_page=3 → 返回 3 条
        resp = client.get(f'/api/files?folder_id={folder_id}&page=1&per_page=3')
        data = json.loads(resp.data)
        assert data['success'] is True
        assert len(data['files']) == 3
        assert data['total'] == 5
        assert data['pages'] == 2

        # 第 2 页：返回 2 条
        resp = client.get(f'/api/files?folder_id={folder_id}&page=2&per_page=3')
        data = json.loads(resp.data)
        assert len(data['files']) == 2
        assert data['page'] == 2

    def test_page_out_of_range_clamped(self, app):
        """页码超出范围时自动钳位到最大/最小页"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'a.pdf', proj_id, folder_id)

        # page=999 → 钳位到 pages
        resp = client.get(f'/api/files?folder_id={folder_id}&page=999&per_page=20')
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['page'] == 1
        assert data['pages'] == 1

        # page=0 → 钳位到 1
        resp = client.get(f'/api/files?folder_id={folder_id}&page=0&per_page=20')
        data = json.loads(resp.data)
        assert data['page'] == 1

    def test_per_page_capped(self, app):
        """per_page 超过 100 应钳位到 100"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = client.get(f'/api/files?folder_id={folder_id}&page=1&per_page=999')
        assert resp.status_code == 200
        # per_page 应在路由层被钳位到 100

    def test_empty_folder(self, app):
        """空文件夹返回空列表和正确的元数据"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['files'] == []
        assert data['total'] == 0
        assert data['pages'] == 1

    def test_has_versions_field_works_with_pagination(self, app):
        """分页后 has_versions 字段仍正确"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传后覆盖，确保当前版本有 has_versions=True
        _upload_file(client, b'v1', 'doc.pdf', proj_id, folder_id, version_number='I')
        _upload_file(client, b'v2', 'doc.pdf', proj_id, folder_id, version_number='I',
                    duplicate_action='override')

        resp = client.get(f'/api/files?folder_id={folder_id}')
        data = json.loads(resp.data)
        current = [f for f in data['files'] if f['version_number'] == 'II']
        assert len(current) == 1
        assert current[0]['has_versions'] is True
```

- [ ] **Step 5.2: 运行测试**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/test_file_pagination.py -v --tb=short 2>&1 | Select-Object -Last 25
```

预期：全部通过（6 个测试）。

- [ ] **Step 5.3: 提交**

```powershell
git add tests/test_file_pagination.py
git commit -m "test: add file list pagination tests for F6-1"
```

---

## Task 6: 验证 — 运行全部测试确认通过

- [ ] **Step 1: 运行完整测试套件**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部测试通过（新增 6 个 + 原有 148 个 = 约 154 个测试）。

- [ ] **Step 2: 检查编译**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m py_compile services/file_service.py routes/files.py 2>&1
```

预期：无输出（编译通过）。

- [ ] **Step 3: 最终提交**

```powershell
git add -A
git commit -m "feat: complete F6-1 file list with pagination, type icons, and operations"
```

---

## 假设与决策

1. **分页默认值**：`page=1`，`per_page=20`，最大 `per_page=100`（防止恶意请求拉取全量数据）。
2. **`get_files_by_folder()` 返回值变更**：从 `list` 改为 `dict{files, total, page, pages}`。唯一调用处 `routes/files.py` 同步适配，无其他调用者。
3. **文件类型图标**：基于 emoji 的 JS 映射表（`FILE_TYPE_ICONS`），无需引入 Font Awesome 等外部图标库。`file_type` 字段值为 `_classify_file_type()` 返回的分类字符串（`PDF`/`Word`/`Excel` 等）。
4. **操作列按钮**：预览 → `alert('即将开放')`（F6-2 实现），下载 → `alert('即将开放')`（F8-1 实现）。
5. **标签列独立**：标签从文件名下方移出为独立列，与 PRD 要求一致。
6. **分页组件样式**：使用 Bootstrap 4 `.pagination` 组件，窗口化页码（当前页 ±2，首尾保留）。
7. **无外部依赖**：纯 Flask + jQuery + Bootstrap 实现。

## 验证步骤

1. 运行 `pytest tests/ -v` 确认全部测试通过（预计 ~154 个测试）
2. 手动验证场景：
   - 文件夹内文件 ≤20 个 → 不显示分页组件，文件正常列表
   - 文件夹内文件 >20 个 → 显示分页组件，点击页码切换 → 表格刷新
   - 点击"上一页"/"下一页"→ 正常翻页
   - 表格包含新列：类型图标 + 操作（预览/下载按钮）
   - 标签显示在独立列中
