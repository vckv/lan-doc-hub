# F4-2 项目字段自动补全 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上传时项目输入框支持自动补全（按型号或名称模糊匹配），显示格式为 `model - name`，下拉底部提供"创建新项目"入口（双字段 model + name），创建后自动生成根文件夹。

**Architecture:** 后端新增 `GET /api/projects/suggest?q=xxx` 接口（`project_service.py` + `routes/projects.py`），前端开发一个轻量自定义 autocomplete 组件（~100 行 JS，不引入 jQuery UI 避免依赖膨胀），替换上传弹窗和批量上传弹窗中的 `<select>` 为 autocomplete `<input>`。

**Tech Stack:** Python 3.12+ / Flask 3.1 / SQLAlchemy / SQLite / jQuery + 自定义 Autocomplete

---

### 文件结构总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `services/project_service.py` | 修改 | 新增 `suggest_projects(query)` — 按 model/name 模糊查询 |
| `routes/projects.py` | 修改 | 新增 `GET /api/projects/suggest?q=xxx` |
| `static/js/autocomplete.js` | **新建** | 可复用的自定义 autocomplete 组件（jQuery 插件） |
| `static/css/autocomplete.css` | **新建** | autocomplete 下拉样式 |
| `static/js/upload_handler.js` | 修改 | 上传弹窗项目 `<select>` → autocomplete `<input>` + "创建新项目" |
| `templates/base.html` | 修改 | 批量上传弹窗 `<select>` → autocomplete `<input>`；加载 autocomplete.css/js |
| `tests/test_project_suggest.py` | **新建** | suggest 接口测试（模糊匹配、空结果、大小写等） |

---

### Task 1: 后端 — 新增 suggest 查询函数 `services/project_service.py`

**Files:**
- Modify: `services/project_service.py`

- [ ] **Step 1: 在 `project_service.py` 末尾追加 `suggest_projects()` 函数**

```python
def suggest_projects(query: str, limit: int = 10):
    """按项目型号或名称模糊匹配

    Args:
        query: 用户输入的关键字（型号或名称，大小写不敏感）
        limit: 最多返回条数，默认 10

    Returns:
        list[dict]: [{id, model, name, display}, ...]
        display 格式为 "model - name"
    """
    q = (query or '').strip()
    if not q:
        return []

    pattern = f'%{q}%'
    results = (
        Project.query
        .filter(
            db.or_(
                Project.model.ilike(pattern),
                Project.name.ilike(pattern),
            )
        )
        .order_by(Project.model)
        .limit(limit)
        .all()
    )
    return [
        {
            'id': p.id,
            'model': p.model,
            'name': p.name,
            'display': f'{p.model} - {p.name}',
        }
        for p in results
    ]
```

需要在文件顶部导入 `db`（如果尚未导入，检查第 3 行已有 `from models import db, Project, Folder`，无需改动）。

- [ ] **Step 2: 验证导入正确性**

```powershell
python -c "from services.project_service import suggest_projects; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/project_service.py
git commit -m "feat: add suggest_projects() for autocomplete fuzzy matching by model/name"
```

---

### Task 2: 后端 — 新增 suggest API 路由 `routes/projects.py`

**Files:**
- Modify: `routes/projects.py`

- [ ] **Step 1: 在 `routes/projects.py` 中新增 suggest 路由**

将第 5 行导入改为（追加 `suggest_projects`）：

```python
from services.project_service import create_project_with_root, suggest_projects
```

在文件末尾（`api_create_project` 之后）追加：

```python
@projects_bp.route('/suggest', methods=['GET'])
@api_login_required
def api_suggest_projects():
    """GET /api/projects/suggest?q=xxx → 按型号/名称模糊搜索项目

    Query params:
        q: 搜索关键字（必填）
    """
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'success': True, 'projects': []})

    results = suggest_projects(q, limit=10)
    return jsonify({'success': True, 'projects': results})
```

完整修改后的 `routes/projects.py`（仅 36 行）：

```python
"""项目管理路由蓝图 —— 创建项目（同时创建根文件夹）+ suggest 自动补全"""

from flask import Blueprint, jsonify, request, session

from services.project_service import create_project_with_root, suggest_projects
from utils.decorators import api_login_required, api_admin_required

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')


@projects_bp.route('', methods=['POST'])
@api_login_required
@api_admin_required
def api_create_project():
    """POST /api/projects → 创建项目 + 对应根文件夹

    JSON body: {"model": "PRJ", "name": "项目名称"}
    """
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


@projects_bp.route('/suggest', methods=['GET'])
@api_login_required
def api_suggest_projects():
    """GET /api/projects/suggest?q=xxx → 按型号/名称模糊搜索项目

    Query params:
        q: 搜索关键字（必填）
    """
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'success': True, 'projects': []})

    results = suggest_projects(q, limit=10)
    return jsonify({'success': True, 'projects': results})
```

- [ ] **Step 2: Commit**

```bash
git add routes/projects.py
git commit -m "feat: add GET /api/projects/suggest endpoint for autocomplete"
```

---

### Task 3: 前端 — 创建自定义 autocomplete 组件

**Files:**
- Create: `static/js/autocomplete.js`
- Create: `static/css/autocomplete.css`

- [ ] **Step 1: 创建 `static/css/autocomplete.css`**

```css
/* ═══════════════════════════════════════
   F4-2 自定义 Autocomplete 下拉样式
   ═══════════════════════════════════════ */

/* 下拉容器 */
.autocomplete-suggestions {
    position: absolute;
    z-index: 1060;
    max-height: 260px;
    overflow-y: auto;
    background: #fff;
    border: 1px solid #ced4da;
    border-top: none;
    border-radius: 0 0 6px 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    min-width: 100%;
    display: none;
}

/* 每条建议项 */
.autocomplete-item {
    padding: 8px 14px;
    cursor: pointer;
    font-size: 0.85rem;
    color: #333;
    transition: background 0.1s ease;
    border-bottom: 1px solid #f5f5f5;
}

.autocomplete-item:last-child {
    border-bottom: none;
    border-radius: 0 0 6px 6px;
}

.autocomplete-item:hover,
.autocomplete-item.active {
    background: #e8f0fe;
}

/* 高亮匹配文本 */
.autocomplete-item .ac-highlight {
    color: #007bff;
    font-weight: 600;
}

/* 项目显示格式：model - name */
.autocomplete-item .ac-display {
    display: flex;
    align-items: center;
    gap: 6px;
}

.autocomplete-item .ac-model {
    font-family: 'Courier New', monospace;
    font-weight: 600;
    color: #007bff;
}

.autocomplete-item .ac-separator {
    color: #999;
    font-size: 0.75rem;
}

.autocomplete-item .ac-name {
    color: #333;
}

/* 创建新项目入口（底部特殊项） */
.autocomplete-item.ac-create {
    background: #f8f9fa;
    color: #28a745;
    font-weight: 500;
    text-align: center;
    border-top: 1px solid #dee2e6;
}

.autocomplete-item.ac-create:hover {
    background: #e2f5e8;
}

/* 输入框组定位容器（供 autocomplete 使用 relative 定位） */
.ac-input-wrapper {
    position: relative;
}
```

- [ ] **Step 2: 创建 `static/js/autocomplete.js`**

```javascript
/**
 * F4-2 自定义 Autocomplete 组件
 * 
 * 用法：
 *   $('#myInput').lanAutocomplete({
 *       source: function (query, done) { ... },  // 异步数据源
 *       onSelect: function (item) { ... },        // 选中回调
 *       renderItem: function (item, query) { ... },// 可选：自定义渲染
 *       minLength: 1,                             // 最少输入字符数触发搜索
 *       placeholder: '请输入...',                 // placeholder
 *       onCreateNew: function (query, done) { ... },// 可选：创建新项目回调
 *       createLabel: '创建新项目',                 // 可选：底部创建入口文案
 *   });
 */
$(function () {
    'use strict';

    var pluginName = 'lanAutocomplete';
    var $doc = $(document);

    function Autocomplete(element, options) {
        this.$input = $(element);
        this.options = $.extend({}, Autocomplete.defaults, options);
        this._init();
    }

    Autocomplete.defaults = {
        source: null,           // function(query, done) — 返回 [{id, display, ...}]
        onSelect: null,         // function(item) — 选中回调
        renderItem: null,       // function(item, query) → html string
        minLength: 1,
        debounceMs: 200,
        placeholder: '',
        createLabel: null,      // 底部"创建新项目"入口文案
        onCreateNew: null,      // function(query, done) — 创建新项目回调
    };

    Autocomplete.prototype._init = function () {
        var self = this;

        // 包裹 input
        if (!this.$input.parent().hasClass('ac-input-wrapper')) {
            this.$input.wrap('<div class="ac-input-wrapper"></div>');
            this.$input.attr('autocomplete', 'off');
            if (this.options.placeholder) {
                this.$input.attr('placeholder', this.options.placeholder);
            }
        }
        this.$wrapper = this.$input.parent();

        // 创建下拉容器
        this.$dropdown = $('<div class="autocomplete-suggestions"></div>');
        this.$wrapper.append(this.$dropdown);

        // 防抖输入事件
        var debounceTimer = null;
        this.$input.on('input', function () {
            clearTimeout(debounceTimer);
            var q = self.$input.val().trim();
            if (q.length < self.options.minLength) {
                self._hide();
                return;
            }
            debounceTimer = setTimeout(function () {
                self._search(q);
            }, self.options.debounceMs);
        });

        // 键盘导航
        this.$input.on('keydown', function (e) {
            var $items = self.$dropdown.find('.autocomplete-item:not(.ac-create)');
            if (!$items.length) return;

            var $active = self.$dropdown.find('.autocomplete-item.active');

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (!$active.length) {
                    $items.first().addClass('active');
                } else {
                    var next = $active.next('.autocomplete-item:not(.ac-create)');
                    $active.removeClass('active');
                    if (next.length) next.addClass('active');
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if ($active.length) {
                    var prev = $active.prev('.autocomplete-item:not(.ac-create)');
                    $active.removeClass('active');
                    if (prev.length) prev.addClass('active');
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if ($active.length) {
                    self._select($active);
                }
            } else if (e.key === 'Escape') {
                self._hide();
            }
        });

        // 点击选中
        this.$dropdown.on('click', '.autocomplete-item', function () {
            self._select($(this));
        });

        // 点击外部关闭
        $doc.on('click.autocomplete', function (e) {
            if (!self.$wrapper.is(e.target) && self.$wrapper.has(e.target).length === 0) {
                self._hide();
            }
        });
    };

    Autocomplete.prototype._search = function (query) {
        var self = this;
        this.options.source(query, function (items) {
            self._render(query, items);
        });
    };

    Autocomplete.prototype._render = function (query, items) {
        if (!items || items.length === 0) {
            this._hide();
            return;
        }

        var self = this;
        var renderFn = this.options.renderItem || function (item, q) {
            var highlight = function (text) {
                if (!q) return LanDocHub.Utils.escapeHtml(text);
                var re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
                return LanDocHub.Utils.escapeHtml(text).replace(re, '<span class="ac-highlight">$1</span>');
            };
            return '<span class="ac-display">' +
                '<span class="ac-model">' + highlight(item.model) + '</span>' +
                '<span class="ac-separator">-</span>' +
                '<span class="ac-name">' + highlight(item.name) + '</span>' +
                '</span>';
        };

        var html = '';
        $.each(items, function (_i, item) {
            html += '<div class="autocomplete-item" data-value="' + item.id + '" data-display="' + LanDocHub.Utils.escapeHtml(item.display || '') + '">' +
                renderFn(item, query) + '</div>';
        });

        // 底部"创建新项目"入口
        if (this.options.createLabel && this.options.onCreateNew) {
            html += '<div class="autocomplete-item ac-create" data-action="create">' +
                '+ ' + this.options.createLabel + '</div>';
        }

        this.$dropdown.html(html).show();
    };

    Autocomplete.prototype._select = function ($item) {
        var action = $item.data('action');
        if (action === 'create') {
            this._hide();
            if (this.options.onCreateNew) {
                var currentQuery = this.$input.val().trim();
                var self = this;
                this.options.onCreateNew(currentQuery, function (newProject) {
                    if (newProject && self.options.onSelect) {
                        self.options.onSelect(newProject);
                    }
                });
            }
            return;
        }

        var item = {
            id: $item.data('value'),
            display: $item.data('display'),
        };
        this.$input.val(item.display || '');
        this._hide();
        if (this.options.onSelect) {
            this.options.onSelect(item);
        }
    };

    Autocomplete.prototype._hide = function () {
        this.$dropdown.empty().hide();
    };

    Autocomplete.prototype.destroy = function () {
        this.$input.off();
        this.$dropdown.remove();
        this.$input.unwrap();
        $doc.off('click.autocomplete');
    };

    // jQuery 插件注册
    $.fn[pluginName] = function (options) {
        return this.each(function () {
            var $this = $(this);
            var instance = $this.data(pluginName);
            if (instance) {
                instance.destroy();
            }
            $this.data(pluginName, new Autocomplete(this, options));
        });
    };
});
```

- [ ] **Step 3: Commit**

```bash
git add static/js/autocomplete.js static/css/autocomplete.css
git commit -m "feat: add custom autocomplete component (jQuery plugin)"
```

---

### Task 4: 前端 — 改造上传弹窗项目选择为 autocomplete

**Files:**
- Modify: `static/js/upload_handler.js` (lines 240-245, 396-434)

- [ ] **Step 1: 修改上传弹窗 HTML — 将 `<select>` 替换为 `<input>`**

将 `upload_handler.js` 第 240-245 行改为：

```javascript
            '<div class="form-group">' +
            '<label>所属项目 ' +
            '<small class="text-muted">(输入型号或名称搜索)</small></label>' +
            '<input type="text" class="form-control form-control-sm" id="inputProjectSearch" ' +
            'placeholder="搜索已有项目..." autocomplete="off">' +
            '<input type="hidden" id="inputProjectId">' +
            '</div>' +
```

- [ ] **Step 2: 修改 `loadProjectOptions()` 为 autocomplete 初始化函数**

将第 396-434 行的 `loadProjectOptions()` 替换为：

```javascript
    function initProjectAutocomplete() {
        var $acInput = $('#inputProjectSearch');
        var $hidden = $('#inputProjectId');
        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';

        // 获取当前文件夹默认项目
        var defaultProjectId = null;
        var defaultDisplay = '';
        var activeNode = $('.tree-node.active');
        if (activeNode.length) {
            var $root = activeNode.closest('.folder-tree').find('.tree-node[data-is-root="true"]').first();
            if ($root.length) {
                defaultProjectId = $root.data('project-id');
                defaultDisplay = $root.find('.tree-name').text().trim();
            } else if (activeNode.data('project-id')) {
                defaultProjectId = activeNode.data('project-id');
                var $node = $('.tree-node[data-project-id="' + defaultProjectId + '"][data-is-root="true"]').first();
                defaultDisplay = $node.find('.tree-name').text().trim();
            }
        }
        if (defaultProjectId) {
            $acInput.val(defaultDisplay);
            $hidden.val(defaultProjectId);
        }

        // 初始化 autocomplete
        $acInput.lanAutocomplete({
            minLength: 1,
            placeholder: '输入型号或名称搜索...',
            createLabel: '创建新项目（需填写型号 + 名称）',
            source: function (query, done) {
                $.ajax({
                    url: '/api/projects/suggest',
                    method: 'GET',
                    data: { q: query },
                    headers: { 'X-CSRF-Token': csrfToken },
                    dataType: 'json',
                }).done(function (resp) {
                    if (resp.success && resp.projects) {
                        done(resp.projects);
                    } else {
                        done([]);
                    }
                }).fail(function () {
                    done([]);
                });
            },
            onSelect: function (item) {
                $hidden.val(item.id);
                $acInput.val(item.display);
            },
            onCreateNew: function (query, onCreated) {
                showCreateProjectInline(query, function (newProject) {
                    onCreated(newProject);
                    $hidden.val(newProject.id);
                    $acInput.val(newProject.display);
                });
            },
        });
    }

    // 内联"创建新项目"弹窗
    function showCreateProjectInline(defaultModel, callback) {
        $('#createProjectModal').remove();
        var html =
            '<div class="modal fade" id="createProjectModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered modal-sm" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-success text-white">' +
            '<h6 class="modal-title">+ 创建新项目</h6>' +
            '<button type="button" class="close text-white" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<div class="form-group">' +
            '<label class="small">项目型号 <span class="text-danger">*</span></label>' +
            '<input type="text" class="form-control form-control-sm" id="inputNewModel" ' +
            'placeholder="英文+数字，如 PRJ001" maxlength="' + LanDocHub.CONFIG.PROJECT_MODEL_MAX_LENGTH + '" ' +
            'value="' + LanDocHub.Utils.escapeHtml(defaultModel) + '">' +
            '</div>' +
            '<div class="form-group">' +
            '<label class="small">项目名称 <span class="text-danger">*</span></label>' +
            '<input type="text" class="form-control form-control-sm" id="inputNewName" ' +
            'placeholder="中文名称，如 某研发项目" maxlength="' + LanDocHub.CONFIG.PROJECT_NAME_MAX_LENGTH + '">' +
            '</div>' +
            '</div>' +
            '<div class="modal-footer py-2">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">取消</button>' +
            '<button type="button" class="btn btn-success btn-sm" id="btnConfirmCreateProject">创建</button>' +
            '</div>' +
            '</div></div></div>';

        $('body').append(html);
        var $modal = $('#createProjectModal');
        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';

        $modal.modal('show');
        $modal.on('hidden.bs.modal', function () { $modal.remove(); });
        // 焦点默认到名称输入框方便直接输入
        $modal.on('shown.bs.modal', function () { $('#inputNewName').focus(); });

        $('#btnConfirmCreateProject').on('click', function () {
            var model = $('#inputNewModel').val().trim();
            var name = $('#inputNewName').val().trim();
            if (!model) { alert('请输入项目型号'); return; }
            if (!name) { alert('请输入项目名称'); return; }

            $.ajax({
                url: '/api/projects',
                method: 'POST',
                contentType: 'application/json',
                headers: { 'X-CSRF-Token': csrfToken },
                data: JSON.stringify({ model: model, name: name }),
            }).done(function (resp) {
                if (resp.success) {
                    $modal.modal('hide');
                    callback({
                        id: resp.project.id,
                        display: resp.project.model + ' - ' + resp.project.name,
                        model: resp.project.model,
                        name: resp.project.name,
                    });
                    // 刷新文件夹树以显示新项目根文件夹
                    if (typeof reloadFolderTree === 'function') {
                        reloadFolderTree();
                    }
                } else {
                    var msg = Object.values(resp.errors || {}).flat().join('; ');
                    alert(msg || '创建失败');
                }
            }).fail(function () {
                alert('创建失败，请重试');
            });
        });
    }
```

- [ ] **Step 3: 修改调用处 — `$modal` 声明后的初始化**

将第 280 行 `var $modal = $('#uploadInfoModal');` 后的：

```javascript
        // 加载项目下拉
        loadProjectOptions(function (selectedId) {
            $('#inputProjectId').val(selectedId);
        });
```

改为：

```javascript
        // F4-2: 初始化项目 autocomplete
        initProjectAutocomplete();
```

- [ ] **Step 4: 修改 `uploadFile()` 中项目 ID 读取方式**

`uploadFile()` 中（第 415-421 行区域）的 `projectId` 参数和 `inputProjectId` 读取方式保持不变，因为 autocomplete 选中的 ID 仍写入 `#inputProjectId`（hidden field），所以 `uploadFile` 代码无需修改。

- [ ] **Step 5: Commit**

```bash
git add static/js/upload_handler.js
git commit -m "feat: replace upload modal project <select> with autocomplete + inline create"
```

---

### Task 5: 前端 — 改造批量上传弹窗为 autocomplete

**Files:**
- Modify: `templates/base.html` (lines 139-142)
- Modify: `static/js/upload_handler.js` — `showBatchUploadModal()` 中的项目选择逻辑

- [ ] **Step 1: 修改 `base.html` 批量弹窗项目选择**

将第 139-142 行：

```html
        <div class="form-group">
          <label for="inputBatchProjectId">所属项目</label>
          <select class="form-control" id="inputBatchProjectId"></select>
        </div>
```

改为：

```html
        <div class="form-group">
          <label for="inputBatchProjectSearch">所属项目 <small class="text-muted">(输入型号或名称搜索)</small></label>
          <input type="text" class="form-control" id="inputBatchProjectSearch"
            placeholder="搜索已有项目..." autocomplete="off">
          <input type="hidden" id="inputBatchProjectId">
        </div>
```

- [ ] **Step 2: 修改 `upload_handler.js` 中 `showBatchUploadModal()` 的项目选择逻辑**

在 `showBatchUploadModal()` 中，找到原来的项目加载逻辑（约第 1001-1010 行），将其替换为 autocomplete 初始化：

```javascript
        // F4-2: 初始化批量上传项目 autocomplete
        var $batchAcInput = $('#inputBatchProjectSearch');
        var $batchHidden = $('#inputBatchProjectId');
        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';

        // 默认选中当前文件夹所属项目
        var defaultProjectId = $('.tree-node[data-folder-id="' + folderId + '"]').data('project-id');
        if (defaultProjectId) {
            var $node = $('.tree-node[data-project-id="' + defaultProjectId + '"][data-is-root="true"]').first();
            var defaultDisplay = $node.find('.tree-name').text().trim();
            $batchAcInput.val(defaultDisplay);
            $batchHidden.val(defaultProjectId);
        }

        $batchAcInput.lanAutocomplete({
            minLength: 1,
            placeholder: '输入型号或名称搜索...',
            createLabel: '创建新项目（需填写型号 + 名称）',
            source: function (query, done) {
                $.ajax({
                    url: '/api/projects/suggest',
                    method: 'GET',
                    data: { q: query },
                    headers: { 'X-CSRF-Token': csrfToken },
                    dataType: 'json',
                }).done(function (resp) {
                    if (resp.success && resp.projects) {
                        done(resp.projects);
                    } else {
                        done([]);
                    }
                }).fail(function () {
                    done([]);
                });
            },
            onSelect: function (item) {
                $batchHidden.val(item.id);
                $batchAcInput.val(item.display);
            },
            onCreateNew: function (query, onCreated) {
                showCreateProjectInline(query, function (newProject) {
                    onCreated(newProject);
                    $batchHidden.val(newProject.id);
                    $batchAcInput.val(newProject.display);
                });
            },
        });
```

同时需要删除原来的项目加载代码块（`$projectSelect` 相关的 `.empty()` / `.append()` / `off('change.batchVersion')` 逻辑），因为 autocomplete 不需要这些。

- [ ] **Step 3: 修改 `uploadBatch()` 中项目 ID 读取**

`uploadBatch()` 已经通过 `projectId` 参数传入，调用处 `showBatchUploadModal` 的确认按钮中读取 `$('#inputBatchProjectId').val()`，保持不变（hidden field 名不变）。

- [ ] **Step 4: Commit**

```bash
git add templates/base.html static/js/upload_handler.js
git commit -m "feat: replace batch upload project <select> with autocomplete"
```

---

### Task 6: 前端 — 加载 autocomplete 依赖

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1: 在 `base.html` 中加载 autocomplete CSS 和 JS**

在第 159 行 `bootstrap.bundle.min.js` 之后、`app_config.js` 之前：

```html
<!-- 自定义 Autocomplete 组件（F4-2） -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/autocomplete.css') }}">
<script src="{{ url_for('static', filename='js/autocomplete.js') }}"></script>
```

- [ ] **Step 2: Commit**

```bash
git add templates/base.html
git commit -m "feat: load autocomplete.css and autocomplete.js in base template"
```

---

### Task 7: 创建测试文件

**Files:**
- Create: `tests/test_project_suggest.py`

- [ ] **Step 1: 创建 `tests/test_project_suggest.py`**

```python
"""F4-2 测试：项目建议接口（suggest）"""

import os
import tempfile
import json

import pytest
import bcrypt

from models import db as _db, Project, User


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


def _login_as_admin(app):
    """创建并登录 admin"""
    with app.app_context():
        pw_hash = bcrypt.hashpw('Admin@Pass1'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin = User(
            username='admin', display_name='Admin',
            password_hash=pw_hash, role='admin', is_active=True,
            created_ip='127.0.0.1',
        )
        _db.session.add(admin)
        _db.session.commit()

    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        token = sess.get('csrf_token')
    client.post('/login', data={
        'csrf_token': token, 'username': 'admin', 'password': 'Admin@Pass1',
    })
    return client


def _seed_projects(app):
    """创建测试项目"""
    with app.app_context():
        _db.session.add_all([
            Project(model='PRJ001', name='桥梁检测平台'),
            Project(model='PRJ002', name='隧道监测系统'),
            Project(model='BRG001', name='桥梁设计工具'),
            Project(model='MON001', name='环境监控系统'),
        ])
        _db.session.commit()


class TestProjectSuggest:

    def test_suggest_by_model_prefix(self, app):
        """按型号前缀模糊搜索"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=PRJ')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert len(data['projects']) == 2
        assert data['projects'][0]['display'] == 'PRJ001 - 桥梁检测平台'

    def test_suggest_by_name_keyword(self, app):
        """按名称关键字模糊搜索"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=检测')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['projects']) == 1
        assert data['projects'][0]['model'] == 'PRJ001'

    def test_suggest_case_insensitive(self, app):
        """型号搜索大小写不敏感"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=prj')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['projects']) == 2

    def test_suggest_no_match_returns_empty(self, app):
        """无匹配返回空列表"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=ZZZ999')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert data['projects'] == []

    def test_suggest_empty_query_returns_empty(self, app):
        """空查询返回空列表"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['projects'] == []

    def test_suggest_missing_q_param(self, app):
        """缺少 q 参数返回空列表"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['projects'] == []

    def test_suggest_partial_match_model_and_name(self, app):
        """同时匹配 model 和 name"""
        client = _login_as_admin(app)
        _seed_projects(app)

        resp = client.get('/api/projects/suggest?q=BRG')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['projects']) == 1
        # 验证返回格式
        assert data['projects'][0]['display'] == 'BRG001 - 桥梁设计工具'

    def test_suggest_requires_login(self, app):
        """未登录拒绝"""
        with app.app_context():
            _db.create_all()

        client = app.test_client()
        resp = client.get('/api/projects/suggest?q=PRJ')
        assert resp.status_code in (302, 401, 400)
```

- [ ] **Step 2: 运行测试验证**

```powershell
python -m pytest tests/test_project_suggest.py -v
```

Expected: 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_project_suggest.py
git commit -m "test: add project suggest API tests (8 cases)"
```

---

### Task 8: 端到端验证

- [ ] **Step 1: 运行全量测试确保零回归**

```powershell
python -m pytest tests/ -v
```

Expected: 全部测试 PASS（原有 124 + 新增 8 = 132 tests）

- [ ] **Step 2: 手工验证清单**

1. admin 登录 → 点击上传 → 弹窗出现文本输入框（非下拉框）→ placeholder "搜索已有项目..."
2. 输入 "PRJ" → 下拉出现匹配项目 → 显示格式为 `PRJ001 - 桥梁检测平台`（型号蓝色等宽字体 + 灰色 `-` + 名称黑色）
3. 选中一项 → 输入框填充 `PRJ001 - 桥梁检测平台`
4. 输入不存在的关键字 → 出现"创建新项目"绿色入口
5. 点击"创建新项目" → 弹窗出现 model + name 双字段 → 填写 → 创建成功 → 自动填充
6. 批量上传 → 同上交互一致
7. 验证新创建的项目在文件夹树中出现（需刷新）
8. `<select>` 项目输入框确认已不存在于单文件上传和批量上传弹窗中

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "chore: finalize F4-2 project autocomplete implementation"
```

---

### 假设与决策

| # | 决策 | 理由 |
|---|------|------|
| 1 | **使用自定义 autocomplete 而非 jQuery UI** | jQuery UI 约 250KB，需下载 + 管理额外 vendor 文件；自定义组件 ~100 行，轻量、可控、项目自主维护。实现相同功能（防抖、键盘导航、高亮、创建入口），且不引入外部依赖 |
| 2 | **项目搜索对所有登录用户开放** | suggest 只是搜索列表，不涉及修改操作，无需 admin 限制 |
| 3 | **上传弹窗"创建新项目"仍保持 admin 权限** | 后端 `POST /api/projects` 保持 `@api_admin_required` 不变；非 admin 用户点击创建会被后端拒绝 |
| 4 | **autocomplete 防抖 200ms** | 平衡响应速度与请求频率 |
| 5 | **下拉最多 10 条** | 与 `suggest_projects()` 的 `limit=10` 参数一致 |

### 验证步骤

1. `python -m pytest tests/test_project_suggest.py -v` — 8 个测试 PASS
2. `python -m pytest tests/ -v` — 132 个测试 PASS，零回归
3. 手工验证（见 Task 8 清单）
4. 浏览器 Console 无 JS 错误
5. 检查 `<select>` 已完全被 `<input>` + autocomplete 替代
