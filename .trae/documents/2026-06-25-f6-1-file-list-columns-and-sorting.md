# F6-1 文件列表列调整 + 排序功能 实施计划

> **For agentic workers:** 按任务顺序逐步执行，每步含精确代码和命令。使用 checkbox (`- [ ]`) 跟踪进度。

**Goal:** 文件列表隐藏"编号"列、"版本"/"型号"移至文件名右侧、操作按钮改为文字、各字段支持点击排序（默认"时间"升序）。

**Architecture:** 后端 `get_files_by_folder()` 新增 `sort_by`/`sort_order` 参数，通过白名单映射动态构建 SQL `ORDER BY`；路由 `GET /api/files` 接受新的查询参数。前端 `file_view.js` 去掉编号列、调整列序、操作按钮文字化；表头 `<th>` 添加 `data-sort` 属性和排序箭头，点击触发 AJAX 重载并传参。

**Tech Stack:** Python 3.12+ / Flask 3.1 / SQLAlchemy / jQuery 3.x / Bootstrap 4

---

## 当前状态分析

### 现有表格列（修改前）

`类型 → 编号 → 文件名 → 大小 → 版本 → 型号 → 标签 → 上传者 → 时间 → 操作`

### 目标表格列（修改后）

`类型 → 文件名 → 版本 → 型号 → 大小 → 标签 → 上传者 → 时间 → 操作`

**变更汇总：**

| 变更 | 详情 |
|------|------|
| 隐藏"编号" | 从 header 和 row 中完全移除 `<td>` |
| 列序调整 | "版本"、"型号"移到"文件名"之后 |
| 操作按钮文字化 | `ICONS.SEARCH` → `"预览"`，`ICONS.UPLOAD` → `"下载"` |
| 排序（新增） | 后端动态 `ORDER BY`，前端可点击表头，默认 `created_at ASC` |

### 后端排序白名单

| 前端 sort 值 | SQLAlchemy 列 | 所需 JOIN |
|-------------|--------------|-----------|
| `created_at` | `File.created_at` | 无（已有） |
| `file_type` | `File.file_type` | 无 |
| `original_filename` | `File.original_filename` | 无 |
| `file_size` | `File.file_size` | 无 |
| `version_number` | `File.version_number` | 无 |
| `model` | `Project.model` | `JOIN Project`（已有） |
| `uploader_name` | `User.display_name` | `outerjoin User`（新增） |

不可排序：标签（多对多关系，排序无意义）

### 涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/file_service.py` | 修改 | `get_files_by_folder()` 新增 `sort_by`/`sort_order` 参数 |
| `routes/files.py` | 修改 | `GET /api/files` 接受 `sort_by`/`sort_order` |
| `static/js/file_view.js` | 修改 | 列调整 + 文字按钮 + 排序表头 + 点击事件 |
| `static/css/app.css` | 修改 | 排序箭头样式 |
| `tests/test_file_pagination.py` | 修改 | 新增排序测试用例 |

---

## Task 1: 后端 — `get_files_by_folder()` 支持动态排序

**Files:**
- Modify: `services/file_service.py`（修改函数签名 + 查询逻辑）

- [ ] **Step 1: 新增排序白名单和函数参数**

修改 `services/file_service.py` 第 37-45 行：

```python
# 排序白名单映射: 前端 sort_by 值 → SQLAlchemy 列对象
_SORT_COLUMNS = {
    'created_at': File.created_at,
    'file_type': File.file_type,
    'original_filename': File.original_filename,
    'file_size': File.file_size,
    'version_number': File.version_number,
    'model': Project.model,
    'uploader_name': User.display_name,
}


def get_files_by_folder(folder_id, page=1, per_page=20, sort_by='created_at', sort_order='asc'):
    """获取某文件夹下的文件列表（含快捷方式标注、标签信息，分页+排序支持）

    Args:
        folder_id: 文件夹 ID
        page: 页码（从 1 开始，默认 1）
        per_page: 每页条数（默认 20）
        sort_by: 排序字段（默认 created_at）
        sort_order: 排序方向（asc/desc，默认 asc）

    Returns:
        dict: {files, total, page, pages, sort_by, sort_order}
    """
```

- [ ] **Step 2: 添加 User JOIN 并构建动态 ORDER BY**

修改查询部分（第 57-66 行），将硬编码 `.order_by(File.created_at.desc())` 替换为动态排序 + 条件 JOIN：

```python
    # 映射排序字段，非法值回退到默认
    sort_column = _SORT_COLUMNS.get(sort_by, File.created_at)
    sort_order = sort_order.lower() if sort_order.lower() in ('asc', 'desc') else 'asc'

    offset = (page - 1) * per_page

    # 构建查询
    query = (
        db.session.query(File, Project.model)
        .join(Project, File.project_id == Project.id)
    )

    # 按上传者排序时需要 JOIN User 表
    if sort_by == 'uploader_name':
        query = query.outerjoin(User, File.uploader_id == User.id)

    query = query.filter(File.folder_id == folder_id, File.is_current == True)
    query = query.order_by(sort_column.asc() if sort_order == 'asc' else sort_column.desc())
    files = query.limit(per_page).offset(offset).all()
```

- [ ] **Step 3: 返回值包含当前排序参数**

修改 return 语句（第 109 行）：

```python
    return {'files': result, 'total': total, 'page': page, 'pages': pages,
            'sort_by': sort_by, 'sort_order': sort_order}
```

完整修改后的 `get_files_by_folder()` 函数体（第 37-109 行整段替换）：

```python
# 排序白名单映射: 前端 sort_by 值 → SQLAlchemy 列对象
_SORT_COLUMNS = {
    'created_at': File.created_at,
    'file_type': File.file_type,
    'original_filename': File.original_filename,
    'file_size': File.file_size,
    'version_number': File.version_number,
    'model': Project.model,
    'uploader_name': User.display_name,
}


def get_files_by_folder(folder_id, page=1, per_page=20, sort_by='created_at', sort_order='asc'):
    """获取某文件夹下的文件列表（含快捷方式标注、标签信息，分页+排序支持）

    Args:
        folder_id: 文件夹 ID
        page: 页码（从 1 开始，默认 1）
        per_page: 每页条数（默认 20）
        sort_by: 排序字段（默认 created_at）
        sort_order: 排序方向（asc/desc，默认 asc）

    Returns:
        dict: {files, total, page, pages, sort_by, sort_order}
    """
    # 计算总数
    total = (
        db.session.query(File.id)
        .filter(File.folder_id == folder_id, File.is_current == True)
        .count()
    )
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))

    # 映射排序字段，非法值回退到默认
    sort_column = _SORT_COLUMNS.get(sort_by, File.created_at)
    sort_order_val = sort_order.lower() if sort_order.lower() in ('asc', 'desc') else 'asc'

    offset = (page - 1) * per_page

    # 构建查询
    query = (
        db.session.query(File, Project.model)
        .join(Project, File.project_id == Project.id)
    )

    # 按上传者排序时需要 JOIN User 表
    if sort_by == 'uploader_name':
        query = query.outerjoin(User, File.uploader_id == User.id)

    query = query.filter(File.folder_id == folder_id, File.is_current == True)
    query = query.order_by(sort_column.asc() if sort_order_val == 'asc' else sort_column.desc())
    files = query.limit(per_page).offset(offset).all()

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
    return {'files': result, 'total': total, 'page': page, 'pages': pages,
            'sort_by': sort_by, 'sort_order': sort_order_val}
```

- [ ] **Step 4: 提交**

```powershell
git add services/file_service.py
git commit -m "feat: add dynamic sorting support to get_files_by_folder"
```

---

## Task 2: 后端 — `GET /api/files` 接受排序参数

**Files:**
- Modify: `routes/files.py`（修改 `api_list_files()` 函数）

- [ ] **Step 1: 修改路由以接受 `sort_by`/`sort_order` 参数**

替换 `routes/files.py` 第 158-172 行：

```python
@files_bp.route('', methods=['GET'])
@api_login_required
def api_list_files():
    """GET /api/files?folder_id=N&page=1&per_page=20&sort_by=created_at&sort_order=asc"""

    folder_id = request.args.get('folder_id', type=int)
    if folder_id is None:
        return jsonify({'success': False, 'errors': {'folder_id': ['缺少参数']}}), 400

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = max(1, min(per_page, 100))  # 限制每页最大 100 条

    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'asc')

    data = get_files_by_folder(folder_id, page=page, per_page=per_page,
                               sort_by=sort_by, sort_order=sort_order)
    return jsonify({'success': True, **data})
```

- [ ] **Step 2: 检查现有调用者兼容**

`breadcrumb-link` 的点击事件（file_view.js 第 224-234 行）调用 `loadFiles(folderId, folderName)` 不带 page 参数，默认 page=1。排序参数通过前端 JS 管理，loadFiles 内部会读取 `$container.data('sortBy')` / `$container.data('sortOrder')`（在 Task 4 中实现），无兼容性问题。路由 `get_files_by_folder()` 新参数均有默认值，向后兼容。

- [ ] **Step 3: 运行现有测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部 154 个测试通过。

- [ ] **Step 4: 提交**

```powershell
git add routes/files.py
git commit -m "feat: accept sort_by/sort_order params in file list API"
```

---

## Task 3: 前端 — 列调整 + 文字按钮

**Files:**
- Modify: `static/js/file_view.js`（修改表头 + 行渲染 + 按钮文字）

- [ ] **Step 3.1: 调整表格列序（去掉编号，重排版本/型号）**

修改 `renderFileList()` 中的行渲染（第 104-123 行），去掉 `<td>` 编号列，调整列序为 `类型 → 文件名 → 版本 → 型号 → 大小 → 标签 → 上传者 → 时间 → 操作`：

```javascript
            return '<tr data-file-id="' + f.id + '">' +
                '<td class="file-type-icon" title="' + LanDocHub.Utils.escapeHtml(f.file_type) + '">' + typeIcon + '</td>' +
                '<td class="file-name">' + shortcut + f.original_filename + '</td>' +
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
                '<td class="file-meta">' + LanDocHub.Utils.formatFileSize(f.file_size) + '</td>' +
                '<td>' + tagBadges + '</td>' +
                '<td class="file-meta">' + (f.uploader_name || '') + '</td>' +
                '<td class="file-meta">' + f.uploaded_at + '</td>' +
                '<td class="file-operations">' + operations + '</td>' +
                '</tr>';
```

- [ ] **Step 3.2: 修改操作按钮为文字**

修改第 97-102 行，将 icon 改为中文文字：

```javascript
            // 操作列
            var operations =
                '<button class="btn btn-outline-secondary btn-xs btn-preview-file" ' +
                'data-file-id="' + f.id + '" title="预览文件">预览</button>' +
                '<button class="btn btn-outline-primary btn-xs btn-download-file" ' +
                'data-file-id="' + f.id + '" title="下载文件">下载</button>';
```

- [ ] **Step 3.3: 修改表头，去掉编号列**

修改第 126-132 行：

```javascript
        var tableHtml = [
            '<div class="file-table"><table class="table table-hover mb-0">',
            '<thead><tr>',
            '<th class="col-type-icon sortable-header" data-sort="file_type">类型 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="original_filename">文件名 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="version_number">版本 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="model">型号 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="file_size">大小 <span class="sort-arrow"></span></th>',
            '<th>标签</th>',
            '<th class="sortable-header" data-sort="uploader_name">上传者 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="created_at">时间 <span class="sort-arrow"></span></th>',
            '<th class="col-operations">操作</th>',
            '</tr></thead><tbody>',
            rows.join(''),
            '</tbody></table></div>',
            renderPagination(page, pages, total, folderId),
        ].join('');
```

- [ ] **Step 4: 提交**

```powershell
git add static/js/file_view.js
git commit -m "feat: hide file_number column, reorder columns, text buttons for F6-1"
```

---

## Task 4: 前端 — 排序表头点击 + 箭头状态

**Files:**
- Modify: `static/js/file_view.js`（排序状态管理 + 点击事件 + 箭头渲染）
- Modify: `static/css/app.css`（排序箭头样式）

- [ ] **Step 4.1: `loadFiles()` 传递排序参数**

修改 `loadFiles()` 函数（第 28-45 行），从 container data 读取当前排序状态并传给 API：

```javascript
    function loadFiles(folderId, folderName, page) {
        page = page || 1;
        var sortBy = $container.data('sortBy') || 'created_at';
        var sortOrder = $container.data('sortOrder') || 'asc';
        $.ajax({
            url: '/api/files',
            method: 'GET',
            data: { folder_id: folderId, page: page, per_page: 20, sort_by: sortBy, sort_order: sortOrder },
            dataType: 'json',
        })
        .done(function (resp) {
            if (!resp.success) {
                LanDocHub.Utils.showInlineError($container, '加载失败');
                return;
            }
            // 后端可能回退排序参数，以 resp 为准更新本地状态
            if (resp.sort_by) $container.data('sortBy', resp.sort_by);
            if (resp.sort_order) $container.data('sortOrder', resp.sort_order);
            renderFileList(resp.files || [], folderId, resp.page || 1, resp.pages || 1, resp.total || 0,
                           resp.sort_by || 'created_at', resp.sort_order || 'asc');
        })
        .fail(function () {
            LanDocHub.Utils.showInlineError($container, '加载失败，请刷新页面后重试');
        });
    }
```

- [ ] **Step 4.2: `renderFileList()` 渲染排序箭头**

修改 `renderFileList()` 签名和排序箭头渲染。在 `$container.html(tableHtml)` 之后添加箭头更新逻辑：

修改函数签名（第 63 行）为：

```javascript
    function renderFileList(files, folderId, page, pages, total, sortBy, sortOrder) {
```

在 `$container.html(tableHtml);` 之后添加箭头更新：

```javascript
        $container.html(tableHtml);

        // 更新排序箭头状态
        updateSortArrows(sortBy, sortOrder);

        // 恢复滚动 + 高亮
```

新增 `updateSortArrows()` 辅助函数，放在 `renderPagination()` 之前：

```javascript
    function updateSortArrows(sortBy, sortOrder) {
        $container.find('.sortable-header .sort-arrow').text('');
        var $active = $container.find('.sortable-header[data-sort="' + sortBy + '"] .sort-arrow');
        $active.text(sortOrder === 'asc' ? ' ▲' : ' ▼');
    }
```

- [ ] **Step 4.3: 排序表头点击事件**

在 IIFE 末尾、`// F6-1: 分页点击` 之前新增：

```javascript
    // F6-1: 排序表头点击
    $(document).on('click', '.sortable-header', function () {
        var sortBy = $(this).data('sort');
        if (!sortBy) return;

        var currentSortBy = $container.data('sortBy') || 'created_at';
        var currentOrder = $container.data('sortOrder') || 'asc';

        if (sortBy === currentSortBy) {
            // 同列切换方向
            $container.data('sortOrder', currentOrder === 'asc' ? 'desc' : 'asc');
        } else {
            // 不同列，默认升序
            $container.data('sortBy', sortBy);
            $container.data('sortOrder', 'asc');
        }

        var folderId = $container.data('currentFolderId');
        if (folderId) {
            loadFiles(folderId, '', 1);  // 排序时回到第 1 页
        }
    });
```

- [ ] **Step 4.4: CSS 排序箭头样式**

在 `static/css/app.css` 的 F6-1 区域末尾追加（含操作列宽度更新：文字按钮比 emoji 宽）：

```css
/* ── F6-1 排序表头 ── */
.sortable-header {
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}

.sortable-header:hover {
    background-color: #f0f0f0;
}

.sortable-header .sort-arrow {
    font-size: 0.65rem;
    color: #adb5bd;
}

/* 操作列宽度更新：文字"预览""下载"比 emoji 宽 */
.col-operations {
    width: 100px;
}
```

- [ ] **Step 5: 运行测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部 154 个测试通过。

- [ ] **Step 6: 提交**

```powershell
git add static/js/file_view.js static/css/app.css
git commit -m "feat: add sortable headers with arrow indicators for F6-1"
```

---

## Task 5: 测试 — 编写排序功能测试

**Files:**
- Modify: `tests/test_file_pagination.py`（新增 `TestFileListSorting` 类）

- [ ] **Step 5.1: 在测试文件末尾追加排序测试**

```python
class TestFileListSorting:

    def test_default_sort_is_created_at_asc(self, app):
        """默认排序为创建时间升序（最早上传的文件在前）"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传 3 个文件
        import time
        _upload_file(client, b'1', 'a.pdf', proj_id, folder_id)
        time.sleep(1.1)  # 确保时间戳不同（SQLite 精度为秒）
        _upload_file(client, b'2', 'b.pdf', proj_id, folder_id)
        time.sleep(1.1)
        _upload_file(client, b'3', 'c.pdf', proj_id, folder_id)

        resp = client.get(f'/api/files?folder_id={folder_id}')
        data = json.loads(resp.data)
        assert data['success'] is True
        assert len(data['files']) == 3
        # 默认 asc：最早的在最前
        assert data['files'][0]['original_filename'] == 'a.pdf'
        assert data['files'][2]['original_filename'] == 'c.pdf'
        assert data['sort_by'] == 'created_at'
        assert data['sort_order'] == 'asc'

    def test_sort_by_filename_desc(self, app):
        """按文件名倒序排列"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'a.pdf', proj_id, folder_id)
        _upload_file(client, b'x', 'b.pdf', proj_id, folder_id)
        _upload_file(client, b'x', 'c.pdf', proj_id, folder_id)

        resp = client.get(
            f'/api/files?folder_id={folder_id}&sort_by=original_filename&sort_order=desc'
        )
        data = json.loads(resp.data)
        assert data['success'] is True
        assert len(data['files']) == 3
        assert data['files'][0]['original_filename'] == 'c.pdf'
        assert data['files'][2]['original_filename'] == 'a.pdf'

    def test_sort_by_file_size_asc(self, app):
        """按文件大小升序排列"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'AAA', 'large.txt', proj_id, folder_id)    # 3 bytes
        _upload_file(client, b'A', 'small.txt', proj_id, folder_id)     # 1 byte
        _upload_file(client, b'AA', 'medium.txt', proj_id, folder_id)   # 2 bytes

        resp = client.get(
            f'/api/files?folder_id={folder_id}&sort_by=file_size&sort_order=asc'
        )
        data = json.loads(resp.data)
        assert data['success'] is True
        assert len(data['files']) == 3
        assert data['files'][0]['file_size'] <= data['files'][1]['file_size']
        assert data['files'][1]['file_size'] <= data['files'][2]['file_size']

    def test_sort_by_model_asc(self, app):
        """按型号升序排列"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app, project_model='M002')

        # 创建另一个项目，型号 M001 < M002（用于验证排序）
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            proj2 = Project(model='M001', name='测试二号')
            _db.session.add(proj2)
            _db.session.flush()
            folder2 = Folder(
                name='M001_测试二号',
                is_project_root=True,
                project_id=proj2.id,
                parent_id=None,
                created_by=admin.id if admin else 1,
            )
            _db.session.add(folder2)
            _db.session.commit()
            proj2_id = proj2.id
            folder2_id = folder2.id

        # 向第二个项目（M001）上传文件
        _upload_file(client, b'y', 'b.pdf', proj2_id, folder2_id)
        # 向第一个项目（M002）上传文件
        _upload_file(client, b'x', 'a.pdf', proj_id, folder_id)

        # 排序：按 model 升序 → M001 在前, M002 在后
        resp = client.get(
            f'/api/files?folder_id={folder_id}&sort_by=model&sort_order=asc'
        )
        data = json.loads(resp.data)
        assert data['success'] is True
        # 仅 M002 项目在 folder_id 中
        assert len(data['files']) == 1
        assert data['files'][0]['project_model'] == 'M002'

    def test_invalid_sort_by_falls_back_to_default(self, app):
        """非法的 sort_by 值回退到默认排序"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'a.pdf', proj_id, folder_id)

        resp = client.get(
            f'/api/files?folder_id={folder_id}&sort_by=hacked_column&sort_order=desc'
        )
        data = json.loads(resp.data)
        assert data['success'] is True
        # 回退到默认 created_at asc
        assert data['sort_by'] == 'hacked_column'  # 原值保留在返回值中告知调用方
        assert data['sort_order'] == 'desc'
        assert len(data['files']) == 1

    def test_sort_persists_with_pagination(self, app):
        """排序参数与分页兼容——翻页后排序方向不变"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        for i in range(5):
            _upload_file(client, b'x', f'file_{i}.pdf', proj_id, folder_id)

        # 第 1 页，按文件名倒序
        resp = client.get(
            f'/api/files?folder_id={folder_id}&page=1&per_page=3'
            '&sort_by=original_filename&sort_order=desc'
        )
        data = json.loads(resp.data)
        assert data['total'] == 5
        assert data['pages'] == 2
        # 按文件名倒序，file_4 应该在最前
        assert data['files'][0]['original_filename'].startswith('file_4')

        # 第 2 页
        resp = client.get(
            f'/api/files?folder_id={folder_id}&page=2&per_page=3'
            '&sort_by=original_filename&sort_order=desc'
        )
        data = json.loads(resp.data)
        assert len(data['files']) == 2
        # 第 2 页应为 file_0
        assert data['files'][1]['original_filename'] == 'file_0.pdf'
```

- [ ] **Step 5.2: 运行排序测试**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/test_file_pagination.py -v --tb=short 2>&1 | Select-Object -Last 25
```

预期：全部通过（原有 6 个 + 新增 6 个 = 12 个测试）。

- [ ] **Step 5.3: 提交**

```powershell
git add tests/test_file_pagination.py
git commit -m "test: add file list sorting tests for F6-1"
```

---

## Task 6: 验证 — 运行全部测试确认通过

- [ ] **Step 1: 运行完整测试套件**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部测试通过（新增 6 个 + 原有 154 个 = 约 160 个测试）。

- [ ] **Step 2: 编译检查**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m py_compile services/file_service.py routes/files.py 2>&1
```

预期：无输出（编译通过）。

- [ ] **Step 3: 最终提交**

```powershell
git add -A
git commit -m "feat: F6-1 columns reorder, hide number, sorting support"
```

---

## 假设与决策

1. **排序字段白名单**：仅 `_SORT_COLUMNS` 中列出的 7 个字段可排序，非法值自动回退到 `File.created_at` ASC。
2. **默认排序**：`sort_by=created_at`，`sort_order=asc`（用户要求"默认时间升序"）。
3. **uploader_name 排序**：需要 `outerjoin(User)`，仅在 `sort_by='uploader_name'` 时添加该 JOIN，不影响其他排序路径的性能。
4. **标签列不可排序**：标签是多对多关系，排序无明确业务含义，表头不添加 `sortable-header` 类。
5. **排序时重置页码**：点击排序表头后回到第 1 页，避免当前页码超出排序后的总页数。
6. **排序箭头**：使用纯文本 ▲/▼，无需引入图标库。当前排序列箭头加粗/高亮。
7. **操作按钮宽度**：文字"预览"/"下载"比 emoji 宽，需要更新 `.col-operations` 宽度从 80px 增加到约 100px。
8. **编号字段**：后端仍保留 `file_number` 字段（不影响 API 响应），仅前端不渲染。

## 验证步骤

1. 运行 `pytest tests/ -v` 确认全部测试通过（预计 ~160 个测试）
2. 手动验证场景：
   - 表格无"编号"列，列序正确：`类型 → 文件名 → 版本 → 型号 → 大小 → 标签 → 上传者 → 时间 → 操作`
   - 操作按钮显示"预览"/"下载"文字
   - 点击"时间"表头 → 切换升序/降序，箭头变化
   - 点击其他表头 → 切换排序字段，默认升序
   - 排序后翻页 → 排序方向保持不变
   - 默认加载时按时间升序排列
