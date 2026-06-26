# F6-2 预览改为新标签页 实施计划

> **For agentic workers:** 按任务顺序逐步执行，每步含精确代码和命令。使用 checkbox (`- [ ]`) 跟踪进度。

**Goal:** 将文件预览从 Bootstrap 模态框改为打开新浏览器标签页（独立页面）。

**Architecture:** 在 `app.py` 的 `register_routes()` 中新增 `GET /preview/<file_id>` 页面路由（`@login_required`），创建独立 `templates/preview.html` 模板，服务端调用 `get_preview_data()` 获取数据并直接在模板中渲染对应 HTML（图片/PDF 用 `<iframe>` 加载 stream、文本用 `<pre>`、CSV/Office 用服务端生成的 HTML）。前端 `file_view.js` 和 `version_history_modal.js` 将 `PreviewModal.open(fileId)` 替换为 `window.open('/preview/' + fileId, '_blank')`。废弃 `preview_modal.js` 及 `base.html` 中的引用，保留后端 `/api/files/<id>/preview` 和 `/api/files/<id>/stream` 路由（以备将来 API 调用）。

**Tech Stack:** Python 3.12+ / Flask 3.1 / Jinja2 / jQuery 3.x

---

## 当前状态分析

### 现有预览流程（模态框模式）

```
用户点击"预览" → PreviewModal.open(fileId)
  → AJAX GET /api/files/<id>/preview → JSON {type, content/stream_url}
  → JS 根据 type 动态构建 DOM（iframe/pre/table）
  → 注入 Bootstrap 模态框显示
```

### 目标预览流程（新标签页模式）

```
用户点击"预览" → window.open('/preview/' + fileId, '_blank')
  → 服务端 GET /preview/<file_id>
  → 调用 get_preview_data(file_id)
  → Jinja2 渲染 preview.html（根据 type 输出对应 HTML）
  → 浏览器新标签页展示
```

### 涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app.py` | 修改 | `register_routes()` 新增 `/preview/<file_id>` 页面路由 |
| `templates/preview.html` | 新建 | 独立预览页面模板 |
| `static/js/file_view.js` | 修改 | 替换 `PreviewModal.open()` → `window.open()` |
| `static/js/version_history_modal.js` | 修改 | 替换 `PreviewModal.open()` → `window.open()` |
| `templates/base.html` | 修改 | 移除 `preview_modal.js` 脚本引用 |
| `static/js/preview_modal.js` | 删除 | 不再需要 |
| `static/css/app.css` | 修改 | 移除 F6-2 模态框专属样式，新增新标签页样式 |
| `tests/test_preview.py` | 修改 | 新增页面路由测试 |

---

## Task 1: 后端 — 新增 `/preview/<file_id>` 页面路由

**Files:**
- Modify: `app.py`（`register_routes()` 函数内新增路由）

- [ ] **Step 1: 添加预览页面路由**

在 `app.py` 第 211-217 行（`file_version_page` 路由之后）插入新路由，同时需要导入 `get_preview_data`：

```python
    @app.route('/files/<int:file_id>/versions')
    @login_required
    def file_version_page(file_id):
        from services.file_service import get_file_version_history
        data = get_file_version_history(file_id)
        if data is None:
            abort(404)
        return render_template('file_versions.html', **data)


    @app.route('/preview/<int:file_id>')
    @login_required
    def preview_page(file_id):
        """GET /preview/<id> → 文件预览页面（新标签页）"""
        from services.file_service import get_preview_data
        data = get_preview_data(file_id)
        if not data.get('success'):
            abort(404)
        return render_template('preview.html', **data)
```

- [ ] **Step 2: 提交**

```powershell
git add app.py
git commit -m "feat: add preview page route for F6-2 new-tab preview"
```

---

## Task 2: 前端 — 创建 `preview.html` 独立页面模板

**Files:**
- Create: `templates/preview.html`

- [ ] **Step 1: 创建模板**

`preview.html` 是独立页面（不继承 `base.html`），服务端已获取预览数据，直接渲染：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件预览 - LAN Doc Hub</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/bootstrap.min.css') }}">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f6fa; }

        .preview-header {
            background: #fff;
            border-bottom: 1px solid #dee2e6;
            padding: 10px 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .preview-header h6 { margin: 0; font-size: 14px; color: #333; }
        .preview-header .badge { font-size: 11px; }

        .preview-body {
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }

        .preview-text {
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 20px;
            font-size: 14px;
            line-height: 1.7;
            white-space: pre-wrap;
            word-wrap: break-word;
            color: #333;
        }

        .preview-stream {
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 85vh;
        }
        .preview-stream iframe {
            width: 100%;
            height: 90vh;
            border: none;
            border-radius: 6px;
        }

        .preview-table-wrap {
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            overflow-x: auto;
            padding: 12px;
        }
        .preview-table-wrap table {
            font-size: 13px;
            width: auto !important;
            margin: 0;
        }
        .preview-table-wrap th {
            white-space: nowrap;
            background: #f0f0f0;
            font-weight: 600;
        }
        .preview-table-wrap td {
            max-width: 220px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .preview-html {
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 16px 24px;
            font-size: 14px;
            line-height: 1.7;
            color: #333;
        }
        .preview-html h1,.preview-html h2,.preview-html h3,.preview-html h4,.preview-html h5 { color: #1a1a1a; margin-top: 20px; }
        .preview-html p { margin: 6px 0; }
        .preview-html table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 12px 0; }
        .preview-html th { background: #f5f5f5; font-weight: 600; }
        .preview-html th,.preview-html td { border: 1px solid #ddd; padding: 5px 10px; text-align: left; }
        .preview-html .preview-sheet h5 { margin-top: 20px; }
        .preview-html .preview-slide { border: 1px solid #e0e0e0; border-radius: 4px; padding: 12px 16px; margin-bottom: 12px; }
        .preview-html .preview-slide h5 { margin: 0 0 8px; font-size: 13px; color: #666; }
        .preview-html .preview-unsupported { text-align: center; padding: 60px 20px; color: #999; font-size: 15px; }

        .preview-error {
            text-align: center;
            padding: 80px 20px;
            color: #999;
        }
        .preview-error .icon { font-size: 48px; margin-bottom: 16px; }
    </style>
</head>
<body>

<div class="preview-header">
    <strong>&#128269; 文件预览</strong>
    {% if stream_url %}
        <span class="badge badge-secondary">图片 / PDF</span>
    {% elif type == 'text' %}
        <span class="badge badge-secondary">纯文本 ({{ encoding }})</span>
    {% elif type == 'csv' %}
        <span class="badge badge-secondary">CSV</span>
    {% elif type == 'html' %}
        <span class="badge badge-secondary">Office 文档</span>
    {% endif %}
</div>

<div class="preview-body">

{% if stream_url %}
    <div class="preview-stream">
        <iframe src="{{ stream_url }}" frameborder="0"></iframe>
    </div>

{% elif type == 'text' %}
    <pre class="preview-text">{{ content }}</pre>

{% elif type == 'csv' %}
    <div class="preview-table-wrap">
        <table class="table table-sm table-bordered mb-0">
            <thead><tr>
            {% for h in headers %}
                <th>{{ h }}</th>
            {% endfor %}
            </tr></thead>
            <tbody>
            {% for row in rows %}
                <tr>
                {% for cell in row %}
                    <td>{{ cell }}</td>
                {% endfor %}
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

{% elif type == 'html' %}
    <div class="preview-html">
        {{ content|safe }}
    </div>

{% else %}
    <div class="preview-error">
        <div class="icon">&#9888;</div>
        <p>不支持该文件类型的预览</p>
    </div>
{% endif %}

</div>

</body>
</html>
```

- [ ] **Step 2: 提交**

```powershell
git add templates/preview.html
git commit -m "feat: create preview page template for F6-2 new-tab preview"
```

---

## Task 3: 前端 — 替换 JS 调用方为 `window.open()`

**Files:**
- Modify: `static/js/file_view.js`（预览按钮事件）
- Modify: `static/js/version_history_modal.js`（版本历史预览按钮事件）

- [ ] **Step 3.1: 替换 `file_view.js`**

修改第 340-346 行：

```javascript
    // F6-1: 操作列 — 预览按钮
    $(document).on('click', '.btn-preview-file', function () {
        var fileId = $(this).data('file-id');
        if (fileId) {
            window.open('/preview/' + fileId, '_blank');
        }
    });
```

- [ ] **Step 3.2: 替换 `version_history_modal.js`**

修改第 44-49 行：

```javascript
        $('#vhVersionList').on('click', '.vh-btn-preview', function () {
            var fileId = $(this).data('file-id');
            if (fileId) {
                window.open('/preview/' + fileId, '_blank');
            }
        });
```

- [ ] **Step 3: 提交**

```powershell
git add static/js/file_view.js static/js/version_history_modal.js
git commit -m "feat: switch preview to new-tab via window.open() for F6-2"
```

---

## Task 4: 清理 — 移除废弃的 `preview_modal.js`

**Files:**
- Modify: `templates/base.html`（移除脚本引用）
- Delete: `static/js/preview_modal.js`

- [ ] **Step 4.1: 移除 `base.html` 中的引用**

删除第 180 行：

```diff
- <script src="{{ url_for('static', filename='js/preview_modal.js') }}"></script>
```

- [ ] **Step 4.2: 删除 `preview_modal.js` 文件**

```powershell
git rm static/js/preview_modal.js
```

- [ ] **Step 5: 提交**

```powershell
git add templates/base.html static/js/preview_modal.js
git commit -m "chore: remove deprecated PreviewModal for F6-2 new-tab migration"
```

---

## Task 5: CSS — 清理模态框预览样式

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 5.1: 移除 F6-2 模态框样式块**

删除 `static/css/app.css` 中 `/* ── F6-2 在线预览 ── */` 整块（第 727-790 行），保留其他样式不变。

- [ ] **Step 5.2: 提交**

```powershell
git add static/css/app.css
git commit -m "style: remove deprecated preview modal CSS for F6-2 new-tab"
```

---

## Task 6: 测试 — 新增预览页面路由测试

**Files:**
- Modify: `tests/test_preview.py`

- [ ] **Step 6.1: 新增 `TestPreviewPage` 类**

在 `test_preview.py` 末尾追加：

```python
class TestPreviewPage:
    """预览页面路由测试（新标签页模式）"""

    def test_preview_page_text(self, app):
        """TXT 文件预览页面返回 200 并包含文本内容"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, 'Hello World'.encode('utf-8'), 'readme.txt', proj_id, folder_id)
        file_id = _get_file_id(app, 'readme.txt')

        resp = client.get(f'/preview/{file_id}')
        assert resp.status_code == 200
        assert 'Hello World' in resp.data.decode('utf-8')
        assert '纯文本' in resp.data.decode('utf-8')

    def test_preview_page_image(self, app):
        """图片文件预览页面返回 iframe 加载 stream"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        png_data = (
            b'\x89PNG\r\n\x1a\n' + b'\x00' * 4 +
            b'IHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
            + b'\x00' * 4 + b'IDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
            + b'\x00' * 4 + b'IEND\xaeB`\x82'
        )
        _upload_file(client, png_data, 'img.png', proj_id, folder_id)
        file_id = _get_file_id(app, 'img.png')

        resp = client.get(f'/preview/{file_id}')
        assert resp.status_code == 200
        html = resp.data.decode('utf-8')
        assert 'preview-stream' in html
        assert f'/api/files/{file_id}/stream' in html

    def test_preview_page_nonexistent_returns_404(self, app):
        """不存在的文件预览页面返回 404"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.get('/preview/99999')
        assert resp.status_code == 404

    def test_preview_page_requires_login(self, app):
        """未登录用户访问预览页面重定向到登录页"""
        client = app.test_client()
        resp = client.get('/preview/1', follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_preview_page_docx(self, app):
        """Word (.docx) 文件预览页面返回 HTML"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        from docx import Document
        import tempfile as tf
        doc = Document()
        doc.add_heading('测试', level=1)
        doc.add_paragraph('内容')
        tmp = tf.NamedTemporaryFile(suffix='.docx', delete=False)
        doc.save(tmp.name)
        tmp.close()

        with open(tmp.name, 'rb') as fh:
            content = fh.read()
        os.unlink(tmp.name)

        _upload_file(client, content, 'doc.docx', proj_id, folder_id)
        file_id = _get_file_id(app, 'doc.docx')

        resp = client.get(f'/preview/{file_id}')
        assert resp.status_code == 200
        html = resp.data.decode('utf-8')
        assert '测试' in html
        assert '内容' in html
        assert 'Office 文档' in html
```

- [ ] **Step 6.2: 运行预览测试**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/test_preview.py -v --tb=short 2>&1 | Select-Object -Last 25
```

预期：全部通过（原有 8 个 + 新增 5 个 = 13 个测试）。

- [ ] **Step 6.3: 提交**

```powershell
git add tests/test_preview.py
git commit -m "test: add preview page route tests for F6-2 new-tab"
```

---

## Task 7: 验证 — 运行全部测试确认通过

- [ ] **Step 1: 运行完整测试套件**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 8
```

预期：全部测试通过（新增 5 个 + 原有 168 个 = 约 173 个测试）。

- [ ] **Step 2: 编译检查**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m py_compile app.py 2>&1
```

预期：无输出（编译通过）。

- [ ] **Step 3: 最终提交**

```powershell
git add -A
git commit -m "feat: migrate F6-2 preview from modal to new tab"
```

---

## 假设与决策

1. **预览页面为独立模板**：`preview.html` 不继承 `base.html`，与 `file_versions.html` 模式一致。页面自带 header（文件名 + 类型 badge）和 body，样式内联以确保隔离。
2. **服务端渲染**：Jinja2 根据 `get_preview_data()` 返回的 `type` 字段分支渲染 HTML，避免前端 AJAX + 动态 DOM 构建。
3. **保留后端 API 路由**：`/api/files/<id>/preview` 和 `/api/files/<id>/stream` 保持不变，stream 端点仍被新页面中的 `<iframe>` 引用。
4. **CSV/Office 的 HTML 由服务端生成**：`get_preview_data()` 返回的 `content` 字段已是 HTML 字符串，模板用 `{{ content|safe }}` 直接输出。
5. **不渲染文件名**：`get_preview_data()` 当前不返回文件名，预览 header 仅显示类型 badge。如需文件名可后续扩展。
6. **新标签页无 JS 依赖**：`preview.html` 仅含 HTML + CSS，无 JavaScript，页面完全由服务端渲染。

## 验证步骤

1. 运行 `pytest tests/ -v` 确认全部测试通过（预计 ~173 个测试）
2. 手动验证场景：
   - 上传图片 → 点击"预览" → 新标签页展示图片
   - 上传 PDF → 点击"预览" → 新标签页展示 PDF（浏览器原生查看器）
   - 上传 TXT → 点击"预览" → 新标签页展示文本内容
   - 上传 CSV → 点击"预览" → 新标签页展示表格
   - 上传 docx → 点击"预览" → 新标签页展示文档内容
   - 版本历史面板中 → 点击预览按钮 → 新标签页预览
   - 未登录 → 访问 /preview/1 → 重定向到登录页
   - 不存在的文件 → 访问 /preview/99999 → 404
