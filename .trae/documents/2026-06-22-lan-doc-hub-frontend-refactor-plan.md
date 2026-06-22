# LAN Doc Hub 前端代码重构方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对已完成后端重构的 LAN Doc Hub 前端代码进行系统性优化，消除重复代码、修复运行时 Bug、统一错误处理与图标管理，使所有 JS 模块可读、可维护。

**Architecture:** 采用"配置层 → 工具层 → 业务模块层"三层架构。新建 `app_config.js`（全局常量）和 `app_utils.js`（共享工具函数），作为所有业务 JS 模块的共同基础。业务模块按加载顺序依次重构，每步改动量可控，全程保持行为不变。

**Tech Stack:** jQuery 3.x / Bootstrap 4 / Flask Jinja2 模板 / 纯 JavaScript（ES5 兼容）

---

## 一、现状分析

### 1.1 文件结构与加载顺序

```
base.html 按顺序加载:
  jquery.min.js                      (vendor)
  bootstrap.bundle.min.js            (vendor)
  folder_tree.js          (425 行)   树加载 + 新建模态框
  upload_intercept_modal.js (110 行) 跨项目拦截 IIFE
  upload_handler.js       (437 行)   上传全流程
  file_view.js            (129 行)   文件列表 + 面包屑
```

### 1.2 问题清单

| # | 严重度 | 文件 | 问题 |
|---|--------|------|------|
| ① | **致命** | `upload_handler.js` → `folder_tree.js` | `upload_handler.js:317,392` 调用 `LanDocHub.flattenTree()`，但 `folder_tree.js` 的 `flattenTree` 是局部闭包函数、未导出到全局。运行时 `LanDocHub` 为 `undefined`，文件夹选择器加载会静默失败 |
| ② | 高 | 全部 JS | 所有中文字符串均用 `\uXXXX` Unicode 转义，代码不可读 |
| ③ | 高 | `file_view.js:76-80` / `upload_handler.js:258-262` | `formatFileSize()` 在两个文件中完全重复 |
| ④ | 中 | `upload_handler.js:63` | `$('#navbarUserDisplay').text()` — 该元素在 `base.html` 中不存在，始终回退到 `'当前用户'` |
| ⑤ | 中 | `upload_handler.js:252` | 413 错误提示 "超过 50 MB 限制"，PRD 要求 500MB |
| ⑥ | 低 | `upload_intercept_modal.js:34-35` | 按钮文本使用代理对 `\uD83D\uDCC1`，上次 Unicode 转换因代理对错误被跳过 |
| ⑦ | 中 | 全部 JS | HTML 构建全用 `+` 字符串拼接，嵌套层级多、难以追踪 |
| ⑧ | 低 | 多处 | 错误处理不一致：`alert()` vs 内联 HTML |
| ⑨ | 低 | `upload_handler.js:14-16` | `getCurrentFolderId()` 读取隐藏 DOM data 属性 — 隐式耦合 |
| ⑩ | 低 | `upload_handler.js:164` | `loadProjectOptions()` 直接遍历 DOM 树节点获取项目列表 |

### 1.3 重构目标架构

```
base.html 新加载顺序:
  jquery.min.js
  bootstrap.bundle.min.js
  app_config.js        [NEW]  ← 全局配置常量
  app_utils.js         [NEW]  ← 共享工具函数
  folder_tree.js       [REFACTOR]
  upload_intercept_modal.js [REFACTOR]
  upload_handler.js    [REFACTOR]
  file_view.js         [REFACTOR]
```

---

## 二、实施步骤

---

### Task 1: 创建 `app_config.js` — 全局配置常量

**Files:**
- Create: `static/js/app_config.js`

- [ ] **Step 1: 创建文件**

```javascript
/**
 * LAN Doc Hub — 全局应用配置
 * 所有硬编码常量集中管理，业务模块从此处引用。
 */
window.LanDocHub = window.LanDocHub || {};

LanDocHub.CONFIG = {
    // ── 上传限制 ──
    MAX_FILE_SIZE_MB: 500,
    MAX_FILE_SIZE_BYTES: 500 * 1024 * 1024,
    ACCEPTED_FILE_TYPES: '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.jpg,.jpeg,.png,.gif,.bmp,.webp',

    // ── 输入长度限制 ──
    FOLDER_NAME_MAX_LENGTH: 32,
    PROJECT_MODEL_MAX_LENGTH: 20,
    PROJECT_NAME_MAX_LENGTH: 30,
};

LanDocHub.ICONS = {
    FOLDER_OPEN:   '\u{1F4C2}',   // 📂
    FOLDER_CLOSED: '\u{1F4C1}',   // 📁
    FILE_EMPTY:    '\u{1F4C4}',   // 📄
    UPLOAD:        '\u{1F4E4}',   // 📤
    LINK:          '\u{1F517}',   // 🔗
    PAGE:          '\u{1F4D6}',   // 📖
    SEARCH:        '\u{1F50D}',   // 🔍
    CHECK:         '\u2714',      // ✔
    WARNING:       '\u26A0',      // ⚠
    ARROW_RIGHT:   '\u25B6',      // ▶
    ARROW_DOWN:    '\u25BC',      // ▼
    DOT:           '\u00B7',      // ·
};
```

- [ ] **Step 2: 验证文件可被正确加载**

在 `base.html` 中临时添加 `<script>console.log('CONFIG:', LanDocHub.CONFIG.MAX_FILE_SIZE_MB);</script>` 检查控制台输出 `CONFIG: 500`。

- [ ] **Step 3: Commit**

```bash
git add static/js/app_config.js
git commit -m "feat: add app_config.js — centralized frontend constants and icons"
```

---

### Task 2: 创建 `app_utils.js` — 共享工具函数

**Files:**
- Create: `static/js/app_utils.js`

- [ ] **Step 1: 创建文件**

```javascript
/**
 * LAN Doc Hub — 共享工具函数
 * 所有业务模块共用的纯逻辑函数，不依赖 DOM / 全局状态。
 */
window.LanDocHub = window.LanDocHub || {};

LanDocHub.Utils = {

    // ── 文件大小格式化（合并 file_view + upload_handler 中的重复实现）──
    formatFileSize: function (bytes) {
        if (bytes === null || bytes === undefined) return '--';
        bytes = parseInt(bytes, 10);
        if (isNaN(bytes)) return '--';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    },

    // ── 文件夹树扁平化（原本在 folder_tree.js 和 upload_handler.js 中各有一份）──
    flattenTree: function (nodes, depth) {
        depth = depth || 0;
        var flat = [];
        if (!nodes || !nodes.length) return flat;
        $.each(nodes, function (i, node) {
            flat.push({
                id: node.id,
                name: node.name,
                project_id: node.project_id,
                is_project_root: node.is_project_root,
                depth: depth,
            });
            if (node.children && node.children.length > 0) {
                flat = flat.concat(LanDocHub.Utils.flattenTree(node.children, depth + 1));
            }
        });
        return flat;
    },

    // ── CSRF Token（统一从 meta 标签读取）──
    getCsrfToken: function () {
        return $('meta[name="csrf-token"]').attr('content') || '';
    },

    // ── 统一错误提示（替代各处 alert()）──
    showInlineError: function ($container, msg) {
        $container.html(
            '<div class="file-empty"><p class="text-danger">' + msg + '</p></div>'
        );
    },

    // ── 获取当前登录用户显示名 ──
    getUserDisplayName: function () {
        return $('.sidebar').data('user-display-name') || '当前用户';
    },
};
```

- [ ] **Step 2: 验证 `flattenTree` 函数正确性**

```bash
# 在浏览器控制台手动测试：
LanDocHub.Utils.flattenTree([{id:1, name:'A', children:[{id:2, name:'B'}]}])
# 预期输出: [{id:1, name:'A', depth:0}, {id:2, name:'B', depth:1}]
```

- [ ] **Step 3: Commit**

```bash
git add static/js/app_utils.js
git commit -m "feat: add app_utils.js — shared utilities (formatFileSize, flattenTree, error handling)"
```

---

### Task 3: 修改 `base.html` — 调整加载顺序 + 注入用户数据

**Files:**
- Modify: `templates/base.html` — 三处改动

- [ ] **Step 1: 在侧边栏注入用户数据（修复 ④）**

将第 61 行：
```html
<aside class="sidebar" data-is-admin="{{ 'true' if session.get('user_role') == 'admin' else 'false' }}">
```
改为：
```html
<aside class="sidebar"
       data-is-admin="{{ 'true' if session.get('user_role') == 'admin' else 'false' }}"
       data-user-display-name="{{ session.get('display_name', session.get('username', '')) }}">
```

- [ ] **Step 2: 调整 JS 加载顺序**

在第 101-112 行的 `<script>` 区域，在 `jquery.min.js` 和 `bootstrap.bundle.min.js` 之后、`folder_tree.js` 之前，新增两行：

```html
<!-- 应用配置（全局常量） -->
<script src="{{ url_for('static', filename='js/app_config.js') }}"></script>
<!-- 共享工具函数 -->
<script src="{{ url_for('static', filename='js/app_utils.js') }}"></script>
<!-- 文件夹树 JS -->
...
```

完整的 script 区域变为：

```html
<!-- jQuery -->
<script src="{{ url_for('static', filename='js/jquery.min.js') }}"></script>
<!-- Bootstrap 4 JS -->
<script src="{{ url_for('static', filename='js/bootstrap.bundle.min.js') }}"></script>

<!-- 应用配置（全局常量、图标） -->
<script src="{{ url_for('static', filename='js/app_config.js') }}"></script>
<!-- 共享工具函数 -->
<script src="{{ url_for('static', filename='js/app_utils.js') }}"></script>

<!-- 文件夹树 JS -->
<script src="{{ url_for('static', filename='js/folder_tree.js') }}"></script>
<!-- 跨项目上传拦截模态框 JS -->
<script src="{{ url_for('static', filename='js/upload_intercept_modal.js') }}"></script>
<!-- 上传流程 JS -->
<script src="{{ url_for('static', filename='js/upload_handler.js') }}"></script>
<!-- 文件视图 JS -->
<script src="{{ url_for('static', filename='js/file_view.js') }}"></script>
```

- [ ] **Step 3: HTML Entity → Unicode 字符**

| 位置 | 当前 | 改为 |
|------|------|------|
| 63 行 | `&#128193;` | `📁` |
| 71 行 | `&#128193;` | `📁` |
| 83 行 | `&#128193;` | `📁` |
| 84 行 | `&#128206;` | `📎` |

- [ ] **Step 4: Commit**

```bash
git add templates/base.html
git commit -m "refactor: add config/utils scripts, inject user data via data-attr, unify icons"
```

---

### Task 4: 重构 `file_view.js` — 消除重复 + Unicode 可读化 + 图标统一

**Files:**
- Modify: `static/js/file_view.js` — 全面改动

- [ ] **Step 1: 删除 `formatFileSize()` 和 `showError()` 本地定义**

删除第 76-84 行的两个函数。

- [ ] **Step 2: 重写 `renderFileList()` 和 `loadBreadcrumb()` — Unicode 可读化**

```javascript
/**
 * F3-1 文件视图 —— 监听文件夹选中事件，AJAX 加载文件列表
 */
$(function () {
    'use strict';

    var ICONS = LanDocHub.ICONS;
    var $container = $('#fileListContainer');
    var $breadcrumb = $('#breadcrumbFolder');

    $(document).on('folder-selected', function (e, data) {
        loadFiles(data.folderId, data.folderName);
        loadBreadcrumb(data.folderId, data.folderName);
    });

    function loadFiles(folderId, folderName) {
        $.ajax({
            url: '/api/files',
            method: 'GET',
            data: { folder_id: folderId },
            dataType: 'json',
        })
        .done(function (resp) {
            if (!resp.success) {
                LanDocHub.Utils.showInlineError($container, '加载失败');
                return;
            }
            renderFileList(resp.files || [], folderId);
        })
        .fail(function () {
            LanDocHub.Utils.showInlineError($container, '加载失败，请刷新页面后重试');
        });
    }

    function renderFileList(files, folderId) {
        $container.data('currentFolderId', folderId);

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
            var shortcut = f.is_shortcut ? ' ' + ICONS.LINK : '';
            return '<tr>' +
                '<td class="file-name">' + f.original_filename + shortcut + '</td>' +
                '<td><span class="file-number">' + f.file_number + '</span></td>' +
                '<td><span class="badge badge-light badge-type">' + f.file_type + '</span></td>' +
                '<td class="file-meta">' + LanDocHub.Utils.formatFileSize(f.file_size) + '</td>' +
                '<td class="file-meta">' + (f.uploader_name || '') + '</td>' +
                '<td class="file-meta">' + f.uploaded_at + '</td>' +
                '</tr>';
        });

        $container.html([
            '<div class="file-table"><table class="table table-hover mb-0">',
            '<thead><tr>',
            '<th>文件名称</th><th>编号</th><th>类型</th><th>大小</th><th>上传者</th><th>时间</th>',
            '</tr></thead><tbody>',
            rows.join(''),
            '</tbody></table></div>'
        ].join(''));
    }

    // ── 面包屑导航 ──
    function loadBreadcrumb(folderId, fallbackName) {
        $.ajax({
            url: '/api/folders/' + folderId + '/ancestors',
            method: 'GET',
            dataType: 'json',
        })
        .done(function (resp) {
            if (!resp.success || !resp.ancestors || resp.ancestors.length === 0) {
                $breadcrumb.html(ICONS.FOLDER_OPEN + ' ' + fallbackName);
                return;
            }
            var parts = [];
            var lastIdx = resp.ancestors.length - 1;
            $.each(resp.ancestors, function (i, a) {
                if (i === lastIdx) {
                    parts.push('<span class="breadcrumb-current">' + a.name + '</span>');
                } else {
                    parts.push(
                        '<a href="#" class="breadcrumb-link" data-folder-id="' + a.id + '" ' +
                        'data-folder-name="' + a.name + '">' + a.name + '</a>'
                    );
                }
            });
            $breadcrumb.html(ICONS.FOLDER_OPEN + ' ' + parts.join(' <span class="breadcrumb-sep">/</span> '));
        })
        .fail(function () {
            $breadcrumb.html(ICONS.FOLDER_OPEN + ' ' + fallbackName);
        });
    }

    // 点击面包屑链接 → 导航到对应文件夹
    $(document).on('click', '.breadcrumb-link', function (e) {
        e.preventDefault();
        var folderId = $(this).data('folder-id');
        var folderName = $(this).data('folder-name');

        $('.tree-node.active').removeClass('active');
        $('.tree-node[data-folder-id="' + folderId + '"]').addClass('active');

        loadFiles(folderId, folderName);
        loadBreadcrumb(folderId, folderName);
    });
});
```

- [ ] **Step 3: Commit**

```bash
git add static/js/file_view.js
git commit -m "refactor: file_view — remove duplicate formatFileSize, unicode readability, icon unification"
```

---

### Task 5: 重构 `folder_tree.js` — Unicode 可读化 + 导出 flattenTree + 图标统一

**Files:**
- Modify: `static/js/folder_tree.js` — 全面改动（~200 行语义等价替换）

- [ ] **Step 1: 替换所有 Unicode 转义 + 使用 `LanDocHub.ICONS`**

对 `folder_tree.js` 进行全局替换。用 Python 脚本批量处理 Unicode 转义（完成后删除脚本）：

```python
import re, os

path = r'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub\static\js\folder_tree.js'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Unicode 转义 → 实际字符
def replace_unicode(m):
    code = int(m.group(1), 16)
    if 0xD800 <= code <= 0xDFFF:
        return m.group(0)
    return chr(code)

new_content = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'Converted {len(content)} → {len(new_content)} chars')
```

- [ ] **Step 2: 替换魔法字符串为 `LanDocHub.ICONS` 常量**

所有出现以下字符串的位置，替换为对应常量引用：

| 原始 | 替换为 |
|------|--------|
| `'\uD83D\uDCC2'` | `LanDocHub.ICONS.FOLDER_OPEN` |
| `'\uD83D\uDCC1'` | `LanDocHub.ICONS.FOLDER_CLOSED` |
| `'\u25B6'` | `LanDocHub.ICONS.ARROW_RIGHT` |
| `'\u25BC'` | `LanDocHub.ICONS.ARROW_DOWN` |
| `'\u00B7'` | `LanDocHub.ICONS.DOT` |

注意：`folder_tree.js` 需要在函数顶部声明 `var ICONS = LanDocHub.ICONS;` 以简化引用。

- [ ] **Step 3: 删除本地 `flattenTree` 定义，改为调用 `LanDocHub.Utils.flattenTree`**

删除第 264-280 行的 `flattenTree` 函数。将第 250 行的 `flattenTree(resp.tree)` 改为 `LanDocHub.Utils.flattenTree(resp.tree)`。

- [ ] **Step 4: 统一错误处理 — `alert()` → 内联错误**

| 行号 | 当前 | 改为 |
|------|------|------|
| 360 | `alert('创建失败，请刷新页面后重试')` | 在模态框内显示 Bootstrap alert |
| 376 | `alert('未找到可用的父文件夹')` | 在模态框内显示 |
| 415 | `alert('创建失败，请刷新页面后重试')` | 在模态框内显示 |

- [ ] **Step 5: Commit**

```bash
git add static/js/folder_tree.js
git commit -m "refactor: folder_tree — unicode readability, use LanDocHub.Utils.flattenTree, icon unification"
```

---

### Task 6: 重构 `upload_handler.js` — 修复 Bug + 消除重复 + 规范化

**Files:**
- Modify: `static/js/upload_handler.js` — 全面改动

- [ ] **Step 1: 修复 ④ — 用户显示名获取**

第 63 行：
```javascript
// 旧
var uploaderName = ($('#navbarUserDisplay').text() || '').trim() || '当前用户';
// 新
var uploaderName = LanDocHub.Utils.getUserDisplayName();
```

- [ ] **Step 2: 修复 ⑤ — 413 错误提示改为配置驱动**

第 249-254 行：
```javascript
// 旧
if (jqXHR.status === 413) {
    msg = '文件太大，超过 50 MB 限制';
}
// 新
if (jqXHR.status === 413) {
    msg = '文件太大，超过 ' + LanDocHub.CONFIG.MAX_FILE_SIZE_MB + ' MB 限制';
}
```

- [ ] **Step 3: 修复 ① — `LanDocHub.flattenTree` → `LanDocHub.Utils.flattenTree`**

第 317 行和第 392 行：
```javascript
// 旧
var flat = LanDocHub.flattenTree(resp.tree);
// 新
var flat = LanDocHub.Utils.flattenTree(resp.tree);
```

另外第 277 行（flattenTree 函数内部的递归调用）已随函数删除一并移除。

- [ ] **Step 4: 删除 `formatUploadSize()` — 使用共享工具函数**

删除第 258-262 行。将第 63、278 行引用改为 `LanDocHub.Utils.formatFileSize(...)`。

- [ ] **Step 5: 统一输入 accept 属性**

第 22 行：
```javascript
// 旧
'accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.jpg,.jpeg,.png,.gif,.bmp,.webp">'
// 新
'accept="' + LanDocHub.CONFIG.ACCEPTED_FILE_TYPES + '">'
```

- [ ] **Step 6: 统一错误处理**

| 行号 | 改动 |
|------|------|
| 54 | `alert('文件编号生成失败...')` → 在 `#fileListContainer` 中调用 `LanDocHub.Utils.showInlineError` |
| 128 | `alert('请选择所属项目')` → 在模态框内用 Bootstrap `.invalid-feedback` 提示 |
| 239 | `alert(msg)` → 在 `#fileListContainer` 中显示 |

- [ ] **Step 7: Commit**

```bash
git add static/js/upload_handler.js
git commit -m "refactor: upload_handler — fix LanDocHub ref, 500MB limit, user name, DRY utils"
```

---

### Task 7: 重构 `upload_intercept_modal.js` — 代理对修复 + 图标统一

**Files:**
- Modify: `static/js/upload_intercept_modal.js`

- [ ] **Step 1: 替换代理对为 `LanDocHub.ICONS`**

```javascript
// 第 34 行 — 旧
'<button type="button" class="btn btn-warning" id="btnSaveToCorrect">\uD83D\uDCC1 保存到正确项目文件夹</button>' +
// 新
'<button type="button" class="btn btn-warning" id="btnSaveToCorrect">' + LanDocHub.ICONS.FOLDER_CLOSED + ' 保存到正确项目文件夹</button>' +

// 第 35 行 — 旧
'<button type="button" class="btn btn-info" id="btnSaveWithShortcut">\uD83D\uDCC1 保存到正确项目，并在此创建快捷方式</button>' +
// 新
'<button type="button" class="btn btn-info" id="btnSaveWithShortcut">' + LanDocHub.ICONS.FOLDER_CLOSED + ' 保存到正确项目，并在此创建快捷方式</button>' +
```

- [ ] **Step 2: Commit**

```bash
git add static/js/upload_intercept_modal.js
git commit -m "refactor: upload_intercept_modal — fix surrogate emoji, use LanDocHub.ICONS"
```

---

### Task 8: 重构 `templates/index.html` — 图标统一

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: HTML Entity → Unicode 字符**

将第 7 行：
```html
    <div class="icon">&#128214;</div>
```
改为：
```html
    <div class="icon">📖</div>
```

- [ ] **Step 2: Commit**

```bash
git add templates/index.html
git commit -m "style: index.html — replace HTML entity with unicode emoji"
```

---

## 三、执行顺序

| 顺序 | Task | 内容 | 依赖 |
|------|------|------|------|
| 1 | Task 1 | 创建 `app_config.js` | 无 |
| 2 | Task 2 | 创建 `app_utils.js` | Task 1 |
| 3 | Task 3 | 修改 `base.html` | Task 1, Task 2 |
| 4 | Task 4 | 重构 `file_view.js` | Task 3 |
| 5 | Task 5 | 重构 `folder_tree.js` | Task 3 |
| 6 | Task 6 | 重构 `upload_handler.js` | Task 3, Task 5 |
| 7 | Task 7 | 重构 `upload_intercept_modal.js` | Task 3 |
| 8 | Task 8 | 重构 `index.html` | 无 |

---

## 四、验证步骤

### 手动冒烟测试清单

完成全部重构后，启动应用并验证：

1. **首页加载** → 文件夹树正常渲染，无 JS 报错
2. **点击树节点** → 文件列表加载、面包屑更新
3. **空文件夹** → 显示空状态占位 "此文件夹中暂无文件"
4. **上传流程（已选中文件夹）** → 弹窗出现 → 项目下拉正常 → 确认上传 → 文件列表刷新
5. **上传流程（未选中文件夹）** → 文件夹选择器弹窗 → 列表正常加载 → 选中后进入上传弹窗
6. **跨项目拦截** → 选择不同项目 → 拦截弹窗出现 → 两个按钮均可正常回调
7. **文件夹选择器中新建文件夹** → 创建成功 → 列表自动刷新 → 新文件夹自动选中
8. **新建项目** → 模态框切换 Tab → 表单提交 → 页面刷新
9. **新建文件夹** → 选择父文件夹 → 提交 → 树局部刷新
10. **面包屑导航** → 点击祖先节点跳转正常
11. **控制台** → 0 error, 0 warning
12. **后端测试** → `pytest tests/ -v` 全部通过（111/111）

---

## 五、假设与决策

1. **`loadProjectOptions()` 保留 DOM 遍历方案** — 暂不改用后端 API（需后端新增 `/api/projects` GET 接口），但添加 `TODO` 注释标记为技术债。
2. **ES5 兼容** — 所有 JS 代码保持 ES5 语法（`function` 声明、`var`、`$.each`），与项目现有风格一致，不引入 ES6+ 特性。
3. **不引入模板引擎** — 当前 HTML 构建由 jQuery 字符串拼接完成，改为数组 `.join()` 模式即可大幅提升可读性，不增加额外依赖。
4. **错误处理渐进改善** — `showInlineError()` 覆盖文件列表区域的错误；模态框内表单错误继续使用 Bootstrap `.invalid-feedback` 机制。
5. **图标集中管理但不在 `base.html` 模板中动态注入** — `base.html` 中直接写 Unicode 字符，JS 中使用 `LanDocHub.ICONS` 常量，保持各自领域内的一致性。
