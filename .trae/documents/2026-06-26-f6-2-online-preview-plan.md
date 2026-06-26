# F6-2 在线预览 实施计划

> **For agentic workers:** 按任务顺序逐步执行，每步含精确代码和命令。使用 checkbox (`- [ ]`) 跟踪进度。

**Goal:** 实现文件在线预览功能——支持图片、PDF、文本、CSV、Office 文档（Word/Excel/PowerPoint）的在线预览，替换 F6-1 和 F5-2 中的占位 alert。

**Architecture:** 后端新增 `GET /api/files/<id>/preview`（返回预览数据 JSON）和 `GET /api/files/<id>/stream`（流式传输原始文件）两个路由。依据 `file_type` 分类处理：图片/PDF 通过 stream 端点传文件、前端用 `<img>`/`<iframe>` 展示；文本/CSV 在后端读取内容返回 JSON、前端渲染 `<pre>`/`<table>`；Office 文档用 python-docx/openpyxl/python-pptx 提取内容并转 HTML。前端新建 `preview_modal.js` IIFE 模态框组件，替换 `file_view.js` 和 `version_history_modal.js` 中的 `alert()` 占位。

**Tech Stack:** Python 3.12+ / Flask 3.1 / python-docx 1.2 / openpyxl 3.1 / python-pptx 1.0 / xlrd 2.0 / jQuery 3.x / Bootstrap 4

---

## 当前状态分析

### 已有依赖（已安装，无需下载）

| 包 | 版本 | 用途 |
|---|---|---|
| `python-docx` | 1.2.0 | Word (.docx) 内容提取 |
| `openpyxl` | 3.1.5 | Excel (.xlsx) 内容提取 |
| `python-pptx` | 1.0.2 | PowerPoint (.pptx) 内容提取 |
| `xlrd` | 2.0.2 | 旧版 Excel (.xls) 内容提取 |
| `Pillow` | 12.2.0 | 图片处理 |
| `pypdf` | 3.17.4 | PDF 页数统计 |

### 当前占位代码位置

| 文件 | 行号 | 内容 |
|---|---|---|
| `static/js/file_view.js:340-343` | 预览按钮 → `alert('在线预览功能即将开放（F6-2 阶段）')` |
| `static/js/version_history_modal.js:44-46` | 版本历史预览按钮 → `alert('在线预览功能即将开放（F6 阶段）')` |

### 预览策略（按文件类型）

| file_type | 后端处理 | 前端渲染 |
|-----------|---------|---------|
| Image | stream 端点直接返回文件 | `<img src="/api/files/<id>/stream">` |
| PDF | stream 端点直接返回文件 | `<iframe src="/api/files/<id>/stream">` |
| TXT | 读取文本内容，JSON 返回 | `<pre>` 标签展示 |
| CSV | 读取 CSV，JSON 返回 headers+rows | `<table>` 标签展示 |
| Word | python-docx 提取段落文本，转 HTML | `<iframe srcdoc>` 展示 |
| Excel | openpyxl/xlrd 提取 sheet 数据，转 HTML table | `<iframe srcdoc>` 展示 |
| PowerPoint | python-pptx 提取 slide 文本，转 HTML | `<iframe srcdoc>` 展示 |

### 涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/file_service.py` | 修改 | 新增 `get_preview_data()` 函数 |
| `routes/files.py` | 修改 | 新增 `preview_file()` 和 `stream_file()` 路由 |
| `static/js/preview_modal.js` | 新建 | 预览模态框组件（IIFE） |
| `templates/base.html` | 修改 | 注册 `preview_modal.js` |
| `static/js/file_view.js` | 修改 | 替换 alert 为 PreviewModal.open() |
| `static/js/version_history_modal.js` | 修改 | 替换 alert 为 PreviewModal.open() |
| `static/css/app.css` | 修改 | 新增预览模态框样式 |
| `tests/test_preview.py` | 新建 | 预览 API 测试 |

---

## Task 1: 后端 — `get_preview_data()` 预览数据服务函数

**Files:**
- Modify: `services/file_service.py`（文件末尾新增函数）

- [ ] **Step 1: 新增 `get_preview_data()` 函数**

在 `services/file_service.py` 文件末尾追加：

```python
# ── F6-2 在线预览 ──

def get_preview_data(file_id):
    """获取文件预览数据

    根据文件类型返回不同的预览数据结构：
    - Image/PDF: {'type': 'stream', 'stream_url': '/api/files/<id>/stream'}
    - TXT: {'type': 'text', 'content': str, 'encoding': str}
    - CSV: {'type': 'csv', 'headers': [str], 'rows': [[str]]}
    - Word/Excel/PPT: {'type': 'html', 'content': str}

    Args:
        file_id: 文件 ID

    Returns:
        dict: {'success': bool, ...}  — 预览数据结构或错误信息
    """
    from flask import current_app, url_for
    import csv as csv_module
    import io

    file_record = db.session.get(File, file_id)
    if file_record is None:
        return {'success': False, 'errors': {'file_id': ['文件不存在']}}

    disk_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_record.file_path)
    if not os.path.isfile(disk_path):
        return {'success': False, 'errors': {'file': ['磁盘文件丢失']}}

    ft = file_record.file_type

    # ── 图片 / PDF：返回 stream 地址 ──
    if ft == 'Image' or ft == 'PDF':
        return {
            'success': True,
            'type': 'stream',
            'stream_url': f'/api/files/{file_id}/stream',
        }

    # ── 纯文本 ──
    if ft == 'TXT':
        # 尝试 UTF-8 → GBK 顺序检测编码
        content = None
        encoding = 'utf-8'
        for enc in ('utf-8', 'gbk', 'latin-1'):
            try:
                with open(disk_path, 'r', encoding=enc) as fh:
                    content = fh.read()
                encoding = enc
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if content is None:
            return {'success': False, 'errors': {'file': ['无法解码文件内容']}}
        return {
            'success': True,
            'type': 'text',
            'content': content,
            'encoding': encoding,
        }

    # ── CSV ──
    if ft == 'CSV':
        try:
            with open(disk_path, 'r', encoding='utf-8-sig', errors='replace') as fh:
                reader = csv_module.reader(fh)
                rows = list(reader)
            if not rows:
                return {'success': True, 'type': 'csv', 'headers': [], 'rows': []}
            headers = rows[0]
            data_rows = rows[1:]
            # 限制最多返回 500 行，每行最多 50 列
            headers = headers[:50]
            data_rows = [row[:50] for row in data_rows[:500]]
            return {
                'success': True,
                'type': 'csv',
                'headers': headers,
                'rows': data_rows,
            }
        except Exception as e:
            return {'success': False, 'errors': {'file': [f'CSV 解析失败: {str(e)}']}}

    # ── Word (.docx) ──
    if ft == 'Word':
        ext = os.path.splitext(file_record.original_filename)[1].lower()
        if ext == '.doc':
            return {
                'success': True,
                'type': 'html',
                'content': '<div class="preview-unsupported"><p>.doc 格式暂不支持在线预览</p><p>请下载后使用 Word 打开</p></div>',
            }
        try:
            from docx import Document
            doc = Document(disk_path)
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    paragraphs.append('<p>&nbsp;</p>')
                    continue
                # 简单 HTML 转义
                text = (text.replace('&', '&amp;').replace('<', '&lt;')
                            .replace('>', '&gt;').replace('"', '&quot;'))
                # 检测标题样式
                if para.style and para.style.name and para.style.name.startswith('Heading'):
                    level = para.style.name.split()[-1]
                    try:
                        lv = int(level)
                        tag = f'h{min(lv, 6)}'
                    except ValueError:
                        tag = 'p'
                    paragraphs.append(f'<{tag}>{text}</{tag}>')
                else:
                    paragraphs.append(f'<p>{text}</p>')
            content = '<div class="preview-word">' + ''.join(paragraphs) + '</div>'
            return {'success': True, 'type': 'html', 'content': content}
        except Exception as e:
            return {'success': False, 'errors': {'file': [f'Word 解析失败: {str(e)}']}}

    # ── Excel (.xlsx / .xls) ──
    if ft == 'Excel':
        ext = os.path.splitext(file_record.original_filename)[1].lower()
        try:
            if ext == '.xls':
                # 使用 xlrd 读取旧格式
                import xlrd
                wb = xlrd.open_workbook(disk_path)
                sheet_names = wb.sheet_names()
                sheets_html = []
                for idx, name in enumerate(sheet_names):
                    if idx >= 3:  # 最多展示 3 个 sheet
                        break
                    sh = wb.sheet_by_index(idx)
                    nrows = min(sh.nrows, 200)
                    ncols = min(sh.ncols, 50)
                    tbl = ['<table class="preview-csv-table"><thead><tr>']
                    for c in range(ncols):
                        val = str(sh.cell_value(0, c) if nrows > 0 else '')
                        tbl.append(f'<th>{_html_escape(val)}</th>')
                    tbl.append('</tr></thead><tbody>')
                    for r in range(1, nrows):
                        tbl.append('<tr>')
                        for c in range(ncols):
                            val = str(sh.cell_value(r, c))
                            tbl.append(f'<td>{_html_escape(val)}</td>')
                        tbl.append('</tr>')
                    tbl.append('</tbody></table>')
                    sheets_html.append(
                        f'<div class="preview-sheet"><h5>Sheet: {_html_escape(name)}</h5>{"".join(tbl)}</div>'
                    )
                content = '<div class="preview-excel">' + ''.join(sheets_html) + '</div>'
            else:
                # .xlsx 使用 openpyxl
                import openpyxl
                wb = openpyxl.load_workbook(disk_path, read_only=True, data_only=True)
                sheets_html = []
                for idx, name in enumerate(wb.sheetnames):
                    if idx >= 3:
                        break
                    sh = wb[name]
                    rows = list(sh.iter_rows(max_row=200, max_col=50, values_only=True))
                    if not rows:
                        continue
                    tbl = ['<table class="preview-csv-table"><thead><tr>']
                    for cell in rows[0]:
                        val = str(cell) if cell is not None else ''
                        tbl.append(f'<th>{_html_escape(val)}</th>')
                    tbl.append('</tr></thead><tbody>')
                    for row in rows[1:]:
                        tbl.append('<tr>')
                        for cell in row:
                            val = str(cell) if cell is not None else ''
                            tbl.append(f'<td>{_html_escape(val)}</td>')
                        tbl.append('</tr>')
                    tbl.append('</tbody></table>')
                    sheets_html.append(
                        f'<div class="preview-sheet"><h5>Sheet: {_html_escape(name)}</h5>{"".join(tbl)}</div>'
                    )
                content = '<div class="preview-excel">' + ''.join(sheets_html) + '</div>'
                wb.close()
            return {'success': True, 'type': 'html', 'content': content}
        except Exception as e:
            return {'success': False, 'errors': {'file': [f'Excel 解析失败: {str(e)}']}}

    # ── PowerPoint (.pptx) ──
    if ft == 'PowerPoint':
        try:
            from pptx import Presentation
            prs = Presentation(disk_path)
            slides_html = []
            for idx, slide in enumerate(prs.slides):
                if idx >= 30:  # 最多展示 30 张幻灯片
                    break
                texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            t = para.text.strip()
                            if t:
                                texts.append(f'<p>{_html_escape(t)}</p>')
                slides_html.append(
                    f'<div class="preview-slide"><h5>第 {idx + 1} 页</h5>{"".join(texts)}</div>'
                )
            content = '<div class="preview-pptx">' + ''.join(slides_html) + '</div>'
            return {'success': True, 'type': 'html', 'content': content}
        except Exception as e:
            return {'success': False, 'errors': {'file': [f'PPT 解析失败: {str(e)}']}}

    # ── 未知类型 ──
    return {'success': False, 'errors': {'file': ['不支持该文件类型的预览']}}


def _html_escape(text):
    """HTML 转义辅助函数"""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
```

- [ ] **Step 2: 提交**

```powershell
git add services/file_service.py
git commit -m "feat: add get_preview_data() for F6-2 online preview"
```

---

## Task 2: 后端 — 预览 + 流式传输路由

**Files:**
- Modify: `routes/files.py`（在文件末尾之前新增两个路由）

- [ ] **Step 1: 新增 `preview_file()` 和 `stream_file()` 路由**

在 `routes/files.py` 文件中，`api_version_history` 路由之后、文件结尾之前插入：

```python
# ── F6-2 在线预览 ──


@files_bp.route('/<int:file_id>/preview', methods=['GET'])
@api_login_required
def api_preview_file(file_id):
    """GET /api/files/<id>/preview → 获取文件预览数据

    根据文件类型返回不同结构：
    - Image/PDF: {'type': 'stream', 'stream_url': '...'}
    - TXT: {'type': 'text', 'content': '...'}
    - CSV: {'type': 'csv', 'headers': [...], 'rows': [[...]]}
    - Office: {'type': 'html', 'content': '<div>...</div>'}
    """

    from services.file_service import get_preview_data
    data = get_preview_data(file_id)
    if data.get('success'):
        return jsonify(data)
    return jsonify(data), 400


@files_bp.route('/<int:file_id>/stream', methods=['GET'])
@api_login_required
def api_stream_file(file_id):
    """GET /api/files/<id>/stream → 流式传输原始文件（图片/PDF 直接展示）"""

    from flask import send_file

    file_record = db.session.get(File, file_id)
    if file_record is None:
        return jsonify({'success': False, 'errors': {'file_id': ['文件不存在']}}), 404

    disk_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_record.file_path)
    if not os.path.isfile(disk_path):
        return jsonify({'success': False, 'errors': {'file': ['磁盘文件丢失']}}), 404

    # 构建 MIME 类型
    ext = os.path.splitext(file_record.original_filename)[1].lower()
    mime_map = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.bmp': 'image/bmp', '.webp': 'image/webp',
    }
    mimetype = mime_map.get(ext, 'application/octet-stream')

    # 中文文件名需要编码
    download_name = file_record.original_filename
    try:
        download_name.encode('ascii')
    except UnicodeEncodeError:
        download_name = file_record.original_filename.encode('utf-8')

    return send_file(
        disk_path,
        mimetype=mimetype,
        as_attachment=False,
        download_name=download_name,
    )
```

- [ ] **Step 2: 确认导入语句**

检查文件顶部已有 `import os`（第 5 行）和 `from flask import ... jsonify, request`（第 3 行），`current_app` 已导入。`send_file` 在路由函数内延迟导入以避免循环引用。

- [ ] **Step 3: 运行现有测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 8
```

预期：全部 160 个测试通过。

- [ ] **Step 4: 提交**

```powershell
git add routes/files.py
git commit -m "feat: add preview and stream routes for F6-2"
```

---

## Task 3: 前端 — 新建 `preview_modal.js` 预览模态框

**Files:**
- Create: `static/js/preview_modal.js`

- [ ] **Step 1: 创建 `preview_modal.js`**

```javascript
/**
 * F6-2: 在线预览模态框
 *
 * 使用方式:
 *   PreviewModal.open(fileId);
 *
 * 依赖: jQuery 3.x, Bootstrap 4, LanDocHub.ICONS
 */
(function () {
    'use strict';

    var ICONS = LanDocHub.ICONS;
    var $modal = null;

    /**
     * 初始化模态框 DOM（只执行一次）
     */
    function init() {
        if ($modal) return;

        $modal = $(['<div class="modal fade" id="previewModal" tabindex="-1">',
            '<div class="modal-dialog modal-xl modal-dialog-scrollable">',
            '<div class="modal-content">',
            '<div class="modal-header py-2">',
            '<h6 class="modal-title" id="previewModalTitle">' + ICONS.SEARCH + ' 文件预览</h6>',
            '<button type="button" class="close" data-dismiss="modal">&times;</button>',
            '</div>',
            '<div class="modal-body p-3" id="previewModalBody">',
            '<div class="text-center py-5">',
            '<div class="spinner-border text-primary" role="status"></div>',
            '<p class="mt-2 text-muted">加载中...</p>',
            '</div>',
            '</div>',
            '</div></div></div>',
        ].join(''));

        $('body').append($modal);
    }

    /**
     * 打开预览模态框
     * @param {number} fileId - 文件 ID
     */
    function open(fileId) {
        init();
        var $body = $modal.find('#previewModalBody');
        $body.html([
            '<div class="text-center py-5">',
            '<div class="spinner-border text-primary" role="status"></div>',
            '<p class="mt-2 text-muted">正在加载预览...</p>',
            '</div>',
        ].join(''));
        $modal.modal('show');

        $.ajax({
            url: '/api/files/' + fileId + '/preview',
            method: 'GET',
            dataType: 'json',
        })
        .done(function (resp) {
            if (!resp.success) {
                var errMsg = '预览加载失败';
                if (resp.errors && resp.errors.file) {
                    errMsg = resp.errors.file[0];
                }
                $body.html([
                    '<div class="text-center py-5">',
                    '<p class="text-muted mb-2">' + ICONS.WARNING + '</p>',
                    '<p class="text-danger">' + LanDocHub.Utils.escapeHtml(errMsg) + '</p>',
                    '</div>',
                ].join(''));
                return;
            }
            renderPreview(resp);
        })
        .fail(function () {
            $body.html([
                '<div class="text-center py-5">',
                '<p class="text-muted mb-2">' + ICONS.WARNING + '</p>',
                '<p class="text-danger">网络请求失败，请刷新页面后重试</p>',
                '</div>',
            ].join(''));
        });
    }

    /**
     * 根据数据类型渲染预览内容
     */
    function renderPreview(data) {
        var $body = $modal.find('#previewModalBody');

        switch (data.type) {

            case 'stream':
                // 图片：<img> 标签
                // 通过 HEAD 请求判断是图片还是 PDF（简单判断：根据 URL 扩展名）
                if (data.stream_url) {
                    $body.html([
                        '<div class="preview-stream-container">',
                        '<iframe src="' + data.stream_url + '" ',
                        'class="preview-iframe" ',
                        'style="width:100%;min-height:70vh;border:none;" ',
                        'frameborder="0"></iframe>',
                        '</div>',
                    ].join(''));
                }
                break;

            case 'text':
                $body.html([
                    '<pre class="preview-text">',
                    LanDocHub.Utils.escapeHtml(data.content || ''),
                    '</pre>',
                ].join(''));
                break;

            case 'csv':
                var tblHtml = buildCsvTable(data.headers, data.rows);
                $body.html('<div class="preview-csv">' + tblHtml + '</div>');
                break;

            case 'html':
                var content = data.content || '';
                // 注入基础样式使 Office 文档预览内容可读
                var styled = [
                    '<html><head><style>',
                    'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;',
                    'font-size:14px;line-height:1.6;padding:12px;color:#333;}',
                    'h1,h2,h3,h4,h5{color:#1a1a1a;margin-top:16px;}',
                    'p{margin:4px 0;}',
                    'table{border-collapse:collapse;width:100%;font-size:13px;}',
                    'th{background:#f5f5f5;font-weight:600;}',
                    'th,td{border:1px solid #ddd;padding:4px 8px;text-align:left;}',
                    '.preview-unsupported{text-align:center;padding:40px;color:#999;}',
                    '</style></head><body>',
                    content,
                    '</body></html>',
                ].join('');
                $body.html([
                    '<iframe srcdoc="' + styled.replace(/"/g, '&quot;') + '" ',
                    'class="preview-iframe" ',
                    'style="width:100%;min-height:70vh;border:none;" ',
                    'frameborder="0"></iframe>',
                ].join(''));
                break;

            default:
                $body.html([
                    '<div class="text-center py-5">',
                    '<p class="text-muted">不支持该文件类型的预览</p>',
                    '</div>',
                ].join(''));
        }
    }

    /**
     * 构建 CSV 表格 HTML
     */
    function buildCsvTable(headers, rows) {
        var h = headers || [];
        var r = rows || [];
        var html = '<table class="preview-csv-table table table-sm table-bordered"><thead><tr>';
        for (var i = 0; i < h.length; i++) {
            html += '<th>' + LanDocHub.Utils.escapeHtml(String(h[i])) + '</th>';
        }
        html += '</tr></thead><tbody>';
        for (var ri = 0; ri < r.length; ri++) {
            html += '<tr>';
            var row = r[ri];
            for (var ci = 0; ci < row.length; ci++) {
                html += '<td>' + LanDocHub.Utils.escapeHtml(String(row[ci])) + '</td>';
            }
            html += '</tr>';
        }
        html += '</tbody></table>';
        return html;
    }

    // 公开 API
    window.PreviewModal = { open: open };
})();
```

- [ ] **Step 2: 在 `base.html` 中注册脚本**

在 `templates/base.html` 中，`version_history_modal.js` 之后添加：

```html
<script src="{{ url_for('static', filename='js/preview_modal.js') }}"></script>
```

- [ ] **Step 3: 提交**

```powershell
git add static/js/preview_modal.js templates/base.html
git commit -m "feat: add PreviewModal component for F6-2 online preview"
```

---

## Task 4: 前端 — 替换 `file_view.js` 和 `version_history_modal.js` 中的占位

**Files:**
- Modify: `static/js/file_view.js`（替换预览按钮事件）
- Modify: `static/js/version_history_modal.js`（替换预览按钮事件）

- [ ] **Step 4.1: 替换 `file_view.js` 中的 alert**

修改第 340-343 行：

```javascript
    // F6-1: 操作列 — 预览按钮
    $(document).on('click', '.btn-preview-file', function () {
        var fileId = $(this).data('file-id');
        if (fileId) {
            PreviewModal.open(fileId);
        }
    });
```

- [ ] **Step 4.2: 替换 `version_history_modal.js` 中的 alert**

修改第 44-46 行：

```javascript
        $('#vhVersionList').on('click', '.vh-btn-preview', function () {
            var fileId = $(this).data('file-id');
            if (fileId) {
                PreviewModal.open(fileId);
            }
        });
```

- [ ] **Step 5: 运行测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 8
```

预期：全部 160 个测试通过。

- [ ] **Step 6: 提交**

```powershell
git add static/js/file_view.js static/js/version_history_modal.js
git commit -m "feat: replace preview alert with PreviewModal.open() for F6-2"
```

---

## Task 5: 前端 — CSS 预览模态框样式

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 5.1: 追加预览样式**

在 `static/css/app.css` 末尾追加：

```css
/* ── F6-2 在线预览 ── */
#previewModal .modal-xl {
    max-width: 95vw;
}

#previewModal .modal-body {
    min-height: 50vh;
    max-height: 80vh;
    overflow-y: auto;
}

.preview-text {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 16px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 70vh;
    overflow-y: auto;
    color: #333;
}

.preview-csv-table {
    font-size: 13px;
    width: auto !important;
}

.preview-csv-table th {
    white-space: nowrap;
    background: #f0f0f0;
}

.preview-csv-table td {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.preview-csv {
    overflow-x: auto;
}

.preview-iframe {
    width: 100%;
    min-height: 70vh;
    border: 1px solid #dee2e6;
    border-radius: 4px;
}

.preview-stream-container {
    display: flex;
    justify-content: center;
}

.preview-stream-container img {
    max-width: 100%;
    border: 1px solid #dee2e6;
    border-radius: 4px;
}
```

- [ ] **Step 5.2: 提交**

```powershell
git add static/css/app.css
git commit -m "style: add preview modal CSS for F6-2"
```

---

## Task 6: 测试 — 编写预览 API 测试

**Files:**
- Create: `tests/test_preview.py`

- [ ] **Step 6.1: 编写测试文件**

```python
"""F6-2: 在线预览 测试"""

import io
import json
import os
import tempfile

import pytest
import bcrypt

from models import db as _db, File, Folder, Project, User


@pytest.fixture
def app():
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


def _seed_project_and_folder(app, project_model='P6T1', project_name='预览测试'):
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


def _get_file_id(app, filename):
    with app.app_context():
        f = File.query.filter_by(original_filename=filename, is_current=True).first()
        return f.id if f else None


class TestPreviewAPI:

    def test_preview_nonexistent_file(self, app):
        """预览不存在的文件返回 400"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.get('/api/files/99999/preview')
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_preview_text_file(self, app):
        """TXT 文件返回文本内容"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, 'Hello\nWorld\n测试', 'note.txt', proj_id, folder_id)
        file_id = _get_file_id(app, 'note.txt')

        resp = client.get(f'/api/files/{file_id}/preview')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['type'] == 'text'
        assert 'Hello' in data['content']

    def test_preview_csv_file(self, app):
        """CSV 文件返回 headers 和 rows"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        csv_content = 'Name,Age,City\nAlice,30,Beijing\nBob,25,Shanghai'
        _upload_file(client, csv_content.encode('utf-8'), 'data.csv', proj_id, folder_id)
        file_id = _get_file_id(app, 'data.csv')

        resp = client.get(f'/api/files/{file_id}/preview')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['type'] == 'csv'
        assert data['headers'] == ['Name', 'Age', 'City']
        assert len(data['rows']) == 2

    def test_preview_image_returns_stream_url(self, app):
        """图片文件返回 stream 类型和 stream_url"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 最小的有效 PNG（1x1 像素）
        png_data = (
            b'\x89PNG\r\n\x1a\n' + b'\x00' * 4 +
            b'IHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
            + b'\x00' * 4 + b'IDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
            + b'\x00' * 4 + b'IEND\xaeB`\x82'
        )
        _upload_file(client, png_data, 'test.png', proj_id, folder_id)
        file_id = _get_file_id(app, 'test.png')

        resp = client.get(f'/api/files/{file_id}/preview')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['type'] == 'stream'
        assert f'/api/files/{file_id}/stream' in data['stream_url']

    def test_stream_image_returns_file(self, app):
        """stream 端点返回图片二进制数据"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'fake-png-data', 'photo.jpg', proj_id, folder_id)
        file_id = _get_file_id(app, 'photo.jpg')

        resp = client.get(f'/api/files/{file_id}/stream')
        assert resp.status_code == 200
        assert resp.content_type == 'image/jpeg'
        assert resp.data == b'fake-png-data'

    def test_preview_requires_login(self, app):
        """未登录用户无法访问预览 API"""
        client = app.test_client()
        resp = client.get('/api/files/1/preview')
        assert resp.status_code == 401

    def test_preview_docx_word_file(self, app):
        """Word (.docx) 文件返回 HTML 内容"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 创建一个最小的 .docx 文件
        from docx import Document
        import tempfile as tf
        doc = Document()
        doc.add_heading('测试标题', level=1)
        doc.add_paragraph('第一段内容')
        doc.add_paragraph('第二段内容')
        tmp = tf.NamedTemporaryFile(suffix='.docx', delete=False)
        doc.save(tmp.name)
        tmp.close()

        with open(tmp.name, 'rb') as fh:
            content = fh.read()
        os.unlink(tmp.name)

        _upload_file(client, content, 'report.docx', proj_id, folder_id)
        file_id = _get_file_id(app, 'report.docx')

        resp = client.get(f'/api/files/{file_id}/preview')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['type'] == 'html'
        assert '测试标题' in data['content']
        assert '第一段内容' in data['content']

    def test_preview_xlsx_excel_file(self, app):
        """Excel (.xlsx) 文件返回 HTML 内容"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        import openpyxl
        import tempfile as tf
        wb = openpyxl.Workbook()
        sh = wb.active
        sh.title = '数据'
        sh.append(['Name', 'Score'])
        sh.append(['Alice', '95'])
        sh.append(['Bob', '87'])
        tmp = tf.NamedTemporaryFile(suffix='.xlsx', delete=False)
        wb.save(tmp.name)
        wb.close()
        tmp.close()

        with open(tmp.name, 'rb') as fh:
            content = fh.read()
        os.unlink(tmp.name)

        _upload_file(client, content, 'scores.xlsx', proj_id, folder_id)
        file_id = _get_file_id(app, 'scores.xlsx')

        resp = client.get(f'/api/files/{file_id}/preview')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['type'] == 'html'
        assert 'Alice' in data['content']
        assert 'Score' in data['content']
```

- [ ] **Step 6.2: 运行预览测试**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/test_preview.py -v --tb=short 2>&1 | Select-Object -Last 30
```

预期：全部通过（8 个测试）。

- [ ] **Step 6.3: 提交**

```powershell
git add tests/test_preview.py
git commit -m "test: add online preview API tests for F6-2"
```

---

## Task 7: 验证 — 运行全部测试确认通过

- [ ] **Step 1: 运行完整测试套件**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 10
```

预期：全部测试通过（新增 8 个 + 原有 160 个 = 约 168 个测试）。

- [ ] **Step 2: 编译检查**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m py_compile services/file_service.py routes/files.py 2>&1
```

预期：无输出（编译通过）。

- [ ] **Step 3: 最终提交**

```powershell
git add -A
git commit -m "feat: complete F6-2 online file preview"
```

---

## 假设与决策

1. **预览策略分层**：图片/PDF 直接流式传输+浏览器原生渲染；文本/CSV 后端读取内容 JSON 返回；Office 文档用 python-docx/openpyxl/python-pptx 提取文本转 HTML。
2. **.doc 不支持**：`.doc`（旧格式）在 `_classify_file_type()` 中被分类为 `Word`，但 python-docx 无法解析 .doc 格式。对于 .doc 文件，返回"暂不支持在线预览"的友好提示。
3. **CSV 行数/列数限制**：最多 500 行 × 50 列，防止超大 CSV 导致前端渲染卡顿。
4. **Excel sheet 限制**：最多展示前 3 个 sheet，每个 sheet 最多 200 行 × 50 列。
5. **PPT slide 限制**：最多展示前 30 张幻灯片。
6. **iframe sandbox**：Office 预览 HTML 通过 `<iframe srcdoc>` 渲染，自动隔离样式，防止污染主页面。
7. **stream 端点仅用于图片/PDF**：其他文件类型的 stream 请求仍可工作，但前端不调用。
8. **权限控制**：stream 端点使用 `send_file`（不需要 CSRF），preview 端点返回 JSON（需要登录认证）。

## 验证步骤

1. 运行 `pytest tests/ -v` 确认全部测试通过（预计 ~168 个测试）
2. 手动验证场景：
   - 上传图片 → 点击"预览" → 模态框展示图片
   - 上传 PDF → 点击"预览" → 模态框展示 PDF（浏览器原生查看器）
   - 上传 TXT → 点击"预览" → 模态框展示文本内容
   - 上传 CSV → 点击"预览" → 模态框展示表格
   - 上传 docx → 点击"预览" → 模态框展示文档内容
   - 上传 xlsx → 点击"预览" → 模态框展示 Excel 表格
   - 上传 pptx → 点击"预览" → 模态框展示幻灯片文本
   - 版本历史面板中 → 点击预览按钮 → 同样可以预览
   - 未登录 → 访问 /api/files/1/preview → 401
