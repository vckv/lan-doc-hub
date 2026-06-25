# F5-1 同名文件检测 + 确认弹窗 实施计划

> **For agentic workers:** 按任务顺序逐步执行，每步含精确代码和命令。使用 checkbox (`- [ ]`) 跟踪进度。

**Goal:** 上传文件前检测目标项目中是否已存在同名文件，若存在则弹出确认弹窗，用户可选择"覆盖为新版本"（归档旧版到 file_versions、递增版本号）或"另存为新文件"（自动添加文件名后缀）。

**Architecture:** 后端新增 GET `/api/files/check-duplicate` 检测端点；前端在 `uploadFile()` 中插入 AJAX 预检步骤，命中同名文件时弹出 `DuplicateCheck` 模态框；`save_uploaded_file()` 接受 `duplicate_action` 和 `new_filename` 参数，在保存前执行归档/重命名逻辑。移除现有的静默 `is_current=False` 后置逻辑。

**Tech Stack:** Python 3.12+ / Flask 3.1 / SQLAlchemy / jQuery 3.x / Bootstrap 4

---

## 当前状态分析

### 已有行为（需移除）

`services/file_service.py:151-162` 在上传完成后 **静默标记** 同名同项目旧文件的 `is_current=False`：

```python
# 第 151-162 行 — 将在 F5-1 中移除
old_files = (
    File.query
    .filter_by(
        original_filename=original_name,
        project_id=project_id,
        is_current=True,
    )
    .all()
)
for old in old_files:
    old.is_current = False
```

**问题：**
- 无用户确认 — 直接覆盖无提示
- 无 `FileVersion` 归档 — 旧版本元数据丢失
- 无"另存为新文件"选项

### 关键发现

- `models.py:9` 当前 **未导入** `FileVersion`（需添加）
- `file_versions` 表存在但上传流程从未写入
- `routes/files.py` 已有 `GET /api/files/next-version` 端点（基于 `original_filename + project_id` 查询）
- `upload_intercept_modal.js` 提供了前端模态框的标准模式（`init()` + `show()` + 回调）

### 涉及文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `services/file_service.py` | 修改 | 删除第 151-162 行；新增 `_archive_existing_file()` 函数；`save_uploaded_file()` 签名新增 `duplicate_action`、`new_filename` 参数；在磁盘保存前插入归档/重命名逻辑 |
| `routes/files.py` | 修改 | 新增 `GET /api/files/check-duplicate` 端点；修改 `POST /api/files/upload` 提取新表单字段 |
| `static/js/duplicate_check_modal.js` | 新建 | 同名文件确认模态框（~80 行） |
| `static/js/upload_handler.js` | 修改 | 拆分 `uploadFile()` 为预检 + 实际上传两阶段；新增 `doUploadFile()`、`generateSuffixedName()`；修改 `uploadBatch()` 内 `uploadNext()` |
| `templates/base.html` | 修改 | 注册 `duplicate_check_modal.js` |
| `static/css/app.css` | 修改 | 新增 `#dupExistingInfo` 样式 |
| `tests/test_duplicate_detection.py` | 新建 | 同名检测和覆盖逻辑测试 |

---

## Task 1: 后端 — 新增 `_archive_existing_file()` 辅助函数

**Files:**
- Modify: `services/file_service.py`（在模块顶部或 `save_uploaded_file` 之前插入；同时在 import 行新增 `FileVersion`）

- [ ] **Step 1: 在 `models` import 行新增 `FileVersion`**

修改 `services/file_service.py` 第 9 行：

```diff
- from models import db, File, Folder, Project, FileTag, Tag
+ from models import db, File, Folder, Project, FileTag, Tag, FileVersion
```

- [ ] **Step 2: 新增 `_archive_existing_file()` 函数**

在 `services/file_service.py` 中，`save_uploaded_file()` 函数定义之前（约第 73 行之前）插入：

```python
def _archive_existing_file(original_filename, project_id, uploader_id):
    """F5-1: 将同名同项目当前版本归档到 file_versions 表。

    对每个 original_filename + project_id 匹配且 is_current=True 的文件：
    1. 创建 FileVersion 记录（保留版本号、备注、路径、大小）
    2. 将 is_current 标记为 False

    注意：此函数不执行 commit，由外层 save_uploaded_file 统一提交。
    """
    old_files = (
        File.query
        .filter_by(
            original_filename=original_filename,
            project_id=project_id,
            is_current=True,
        )
        .all()
    )

    for old in old_files:
        version = FileVersion(
            file_id=old.id,
            version_number=old.version_number,
            version_note=old.version_note,
            file_path=old.file_path,
            file_size=old.file_size,
            uploaded_by=uploader_id,
        )
        db.session.add(version)
        old.is_current = False
```

- [ ] **Step 3: 验证当前测试仍然通过**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 20
```

预期：全部通过（新增的 `_archive_existing_file` 尚未被调用，不影响现有逻辑）。

- [ ] **Step 4: 提交**

```powershell
git add services/file_service.py
git commit -m "feat: add _archive_existing_file() helper for F5-1 version archiving"
```

---

## Task 2: 后端 — 重构 `save_uploaded_file()`（新增参数 + 删除旧逻辑 + 前置归档）

**Files:**
- Modify: `services/file_service.py`（修改 `save_uploaded_file` 签名；删除第 151-162 行；在第 140 行磁盘保存前插入新逻辑块）

- [ ] **Step 1: 修改函数签名，新增参数**

修改 `services/file_service.py` 第 74-75 行：

```diff
  def save_uploaded_file(file_storage, project_id, folder_id, uploader_id,
-                        version_number='I', version_note=None, tag_ids=None):
+                        version_number='I', version_note=None, tag_ids=None,
+                        duplicate_action=None, new_filename=None):
```

并在 docstring 的 Args 段中追加：

```python
        duplicate_action: 'override' | 'save_as_new' | None  (F5-1)
        new_filename:     另存为时的新文件名（含后缀）(F5-1)
```

- [ ] **Step 2: 删除旧的静默 is_current=False 逻辑**

删除 `services/file_service.py` 第 151-162 行（从 `# ── 标记同名同项目旧版本为非当前 ──` 到 `old.is_current = False` 的整段）：

```diff
-     # ── 标记同名同项目旧版本为非当前 ──
-     old_files = (
-         File.query
-         .filter_by(
-             original_filename=original_name,
-             project_id=project_id,
-             is_current=True,
-         )
-         .all()
-     )
-     for old in old_files:
-         old.is_current = False
-
      # ── 生成文件编号 ──
```

- [ ] **Step 3: 在磁盘保存前插入 F5-1 归档/重命名逻辑**

修改 `services/file_service.py`，在 `file_storage.save(disk_path)` 行（约第 140 行）之**前**插入：

```python
    # ── F5-1: 同名文件处理（须在磁盘保存前执行）──
    if duplicate_action == 'override':
        _archive_existing_file(original_name, project_id, uploader_id)
        version_number = next_version_number(original_name, project_id)

    if duplicate_action == 'save_as_new' and new_filename:
        original_name = new_filename
```

插入位置：在第 140 行 `file_storage.save(disk_path)` 之前（在生成 `safe_name`、`disk_name`、`disk_path` 等变量之后，实际保存文件之前）。确保 `original_name` 变量可以在此处被重新赋值（Python 局部变量可重新赋值）。

**注意：** `original_name` 是在第 100 行赋值的局部变量（`original_name = file_storage.filename or 'unknown'`），后面的 `safe_name`（第 134 行附近）依赖它。由于 `override` 路径不修改 `original_name`，`save_as_new` 路径在 `safe_name` 生成后修改 `original_name`，不影响 `disk_name`（UUID 前缀确保磁盘唯一）。DB 记录中的 `original_filename` 反映用户看到的文件名（覆盖时保持原名，另存时用带后缀的名称）。

- [ ] **Step 4: 运行全部测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 20
```

预期：全部通过。

- [ ] **Step 5: 提交**

```powershell
git add services/file_service.py
git commit -m "feat: refactor save_uploaded_file for F5-1 duplicate handling"
```

---

## Task 3: 后端 — 新增 `GET /api/files/check-duplicate` 端点

**Files:**
- Modify: `routes/files.py`（在 `api_next_version` 之后、`api_upload_file` 之前插入新路由）

- [ ] **Step 1: 新增检测端点代码**

在 `routes/files.py` 第 35 行之后（`api_next_version` 函数结束）、`api_upload_file`（第 37 行）之前插入：

```python
@files_bp.route('/check-duplicate')
@api_login_required
def api_check_duplicate():
    """GET /api/files/check-duplicate?filename=xxx&project_id=yyy
    → 检测目标项目中是否存在同名当前版本文件"""
    filename = request.args.get('filename', '').strip()
    project_id = request.args.get('project_id', type=int)

    if not filename or not project_id:
        return jsonify({
            'success': False,
            'errors': {'params': ['缺少 filename 或 project_id']},
        }), 400

    existing = (
        File.query
        .filter_by(
            original_filename=filename,
            project_id=project_id,
            is_current=True,
        )
        .first()
    )

    if not existing:
        return jsonify({'success': True, 'exists': False})

    return jsonify({
        'success': True,
        'exists': True,
        'existing_file': {
            'id': existing.id,
            'original_filename': existing.original_filename,
            'file_number': existing.file_number,
            'version_number': existing.version_number,
            'file_size': existing.file_size,
            'file_type': existing.file_type,
            'folder_id': existing.folder_id,
            'uploader_name': existing.uploader.display_name if existing.uploader else '',
            'uploaded_at': existing.created_at.strftime('%Y-%m-%d %H:%M'),
        },
    })
```

同时确认 `routes/files.py` 顶部已导入 `File`（目前 imports 行不包含 `File`，但通过 `file_service` 间接使用；需要补充）：

检查 `routes/files.py` 第 1 行起。当前 imports：

```python
from flask import Blueprint, jsonify, request, session, abort, current_app

from services.file_service import (
    generate_file_number,
    save_uploaded_file,
    get_files_by_folder,
)
from utils.decorators import api_login_required
```

需要新增 `from models import File` 导入。修改第 1-11 行为：

```diff
  from flask import Blueprint, jsonify, request, session, abort, current_app

+ from models import File
  from services.file_service import (
      generate_file_number,
      save_uploaded_file,
      get_files_by_folder,
  )
  from utils.decorators import api_login_required
```

- [ ] **Step 2: 新增 `File` import 到 `routes/files.py` 顶部**

在 `routes/files.py` 中，`from services.file_service import` 行**之前**加入 `from models import File`。

- [ ] **Step 3: 运行全部测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 20
```

预期：全部通过。新增端点尚未被调用，不影响现有逻辑。

- [ ] **Step 4: 提交**

```powershell
git add routes/files.py
git commit -m "feat: add GET /api/files/check-duplicate endpoint for F5-1"
```

---

## Task 4: 后端 — 修改 `POST /api/files/upload` 提取新表单字段

**Files:**
- Modify: `routes/files.py`（修改 `api_upload_file` 函数）

- [ ] **Step 1: 在 `api_upload_file` 中提取新增表单字段**

在 `routes/files.py` 的 `api_upload_file` 函数中，在现有 `tag_ids` 字段提取之后（约第 67-68 行）、参数校验之前插入：

```python
    # ── F5-1: 同名文件处理参数 ──
    duplicate_action = request.form.get('duplicate_action', '').strip() or None
    new_filename = request.form.get('new_filename', '').strip() or None

    # 参数校验
    if duplicate_action and duplicate_action not in ('override', 'save_as_new'):
        return jsonify({
            'success': False,
            'errors': {'duplicate_action': ['无效的操作']},
        }), 400

    if duplicate_action == 'save_as_new' and not new_filename:
        return jsonify({
            'success': False,
            'errors': {'new_filename': ['缺少新文件名']},
        }), 400
```

- [ ] **Step 2: 修改 `save_uploaded_file` 调用，传入新参数**

修改 `routes/files.py` 中 `save_uploaded_file()` 的调用（约第 78-86 行）：

```diff
      result = save_uploaded_file(
          file_storage=file_storage,
          project_id=project_id,
          folder_id=folder_id,
          uploader_id=int(session['user_id']),
          version_number=version_number,
          version_note=version_note,
          tag_ids=tag_ids,
+         duplicate_action=duplicate_action,
+         new_filename=new_filename,
      )
```

- [ ] **Step 3: 运行全部测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 20
```

预期：全部通过。`duplicate_action` 和 `new_filename` 默认 `None`，与旧行为完全兼容。

- [ ] **Step 4: 提交**

```powershell
git add routes/files.py
git commit -m "feat: accept duplicate_action and new_filename in upload endpoint"
```

---

## Task 5: 前端 — 创建 `duplicate_check_modal.js` 同名检测模态框

**Files:**
- Create: `static/js/duplicate_check_modal.js`

- [ ] **Step 1: 创建文件，遵循 `upload_intercept_modal.js` 的 IIFE 模式**

```javascript
/**
 * F5-1 同名文件检测确认模态框
 *
 * 用法：
 *   DuplicateCheck.show(file, existingInfo, projectId, folderId, onOverride, onSaveAsNew, onCancel)
 *
 * 参数：
 *   file            - 待上传的 File 对象 { name, size }
 *   existingInfo    - 服务端返回的 existing_file 对象
 *   onOverride()    - 用户选择"覆盖为新版本"
 *   onSaveAsNew()   - 用户选择"另存为新文件"
 *   onCancel()      - 用户取消
 */
var DuplicateCheck = (function () {
    'use strict';

    var $modal = null;
    var _onOverride = null;
    var _onSaveAsNew = null;
    var _onCancel = null;

    function init() {
        if ($modal) return;
        var html =
            '<div class="modal fade" id="duplicateCheckModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-warning text-dark">' +
            '<h5 class="modal-title">' + LanDocHub.ICONS.WARNING + ' 同名文件已存在</h5>' +
            '<button type="button" class="close" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<p id="dupMessage"></p>' +
            '<div id="dupExistingInfo" class="small text-muted mb-2"></div>' +
            '<p class="small mb-0">请选择处理方式：</p>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">取消</button>' +
            '<button type="button" class="btn btn-warning btn-sm" id="btnOverride">' +
            LanDocHub.ICONS.UPLOAD + ' 覆盖为新版本</button>' +
            '<button type="button" class="btn btn-info btn-sm" id="btnSaveAsNew">' +
            LanDocHub.ICONS.FILE_EMPTY + ' 另存为新文件</button>' +
            '</div>' +
            '</div></div></div>';
        $('body').append(html);
        $modal = $('#duplicateCheckModal');

        $modal.on('click', '#btnOverride', function () {
            $modal.modal('hide');
            if (_onOverride) _onOverride();
        });

        $modal.on('click', '#btnSaveAsNew', function () {
            $modal.modal('hide');
            if (_onSaveAsNew) _onSaveAsNew();
        });

        $modal.on('hidden.bs.modal', function () {
            if (_onCancel) _onCancel();
        });
    }

    /**
     * 显示同名文件确认弹窗
     *
     * @param {File}     file            待上传文件对象
     * @param {object}   existing        服务端返回的 existing_file
     * @param {number}   projectId       目标项目 ID
     * @param {number}   folderId        目标文件夹 ID
     * @param {function} onOverride      覆盖为新版本回调
     * @param {function} onSaveAsNew     另存为新文件回调
     * @param {function} onCancel        取消回调
     */
    function show(file, existing, projectId, folderId, onOverride, onSaveAsNew, onCancel) {
        init();
        _onOverride = onOverride;
        _onSaveAsNew = onSaveAsNew;
        _onCancel = onCancel;

        var msg = '文件 <strong>' + LanDocHub.Utils.escapeHtml(file.name) +
            '</strong> 已存在，请选择：';
        $('#dupMessage').html(msg);

        var infoParts = [];
        infoParts.push('当前版本：' + LanDocHub.Utils.escapeHtml(existing.version_number || 'I'));
        infoParts.push('编号：' + LanDocHub.Utils.escapeHtml(existing.file_number || '-'));
        infoParts.push('大小：' + LanDocHub.Utils.formatFileSize(existing.file_size || 0));
        infoParts.push('上传者：' + LanDocHub.Utils.escapeHtml(existing.uploader_name || '-'));
        infoParts.push('时间：' + LanDocHub.Utils.escapeHtml(existing.uploaded_at || '-'));
        $('#dupExistingInfo').html(infoParts.join(' &nbsp;|&nbsp; '));

        $modal.modal('show');
    }

    return { show: show };
})();
```

- [ ] **Step 2: 提交**

```powershell
git add static/js/duplicate_check_modal.js
git commit -m "feat: add DuplicateCheck modal for F5-1 duplicate detection"
```

---

## Task 6: 前端 — 修改 `uploadFile()` 为预检 + 上传两阶段

**Files:**
- Modify: `static/js/upload_handler.js`（重构 `uploadFile()` 函数；新增 `doUploadFile()` 和 `generateSuffixedName()`）

- [ ] **Step 1: 新增 `generateSuffixedName()` 辅助函数**

在 `upload_handler.js` 中，`uploadFile` 函数定义之前（约第 566 行）插入：

```javascript
    function generateSuffixedName(filename) {
        var dotIndex = filename.lastIndexOf('.');
        if (dotIndex === -1) {
            return filename + ' (1)';
        }
        var base = filename.substring(0, dotIndex);
        var ext = filename.substring(dotIndex);
        return base + ' (1)' + ext;
    }
```

- [ ] **Step 2: 提取现有上传逻辑为 `doUploadFile()`**

将现有 `uploadFile()` 函数体（第 568-618 行的全部 FormData 构建和 AJAX 发送逻辑）提取为新函数 `doUploadFile(file, projectId, folderId, duplicateAction, newFilename)`。

在第 618 行（原 `uploadFile` 函数结束的 `}`）之后插入：

```javascript
    function doUploadFile(file, projectId, folderId, duplicateAction, newFilename) {
        var formData = new FormData();
        formData.append('file', file);
        formData.append('project_id', projectId);
        formData.append('folder_id', folderId);
        formData.append('version_number', $('#inputVersionNumber').val() || 'I');
        formData.append('version_note', $('#inputVersionNote').val() || '');

        // F5-1: 同名文件处理参数
        if (duplicateAction) {
            formData.append('duplicate_action', duplicateAction);
        }
        if (newFilename) {
            formData.append('new_filename', newFilename);
        }

        // F4-1: 收集选中的标签 ID
        var tagIds = [];
        $('#uploadTagSelector input[type="checkbox"]:checked').each(function () {
            tagIds.push($(this).val());
        });
        if (tagIds.length > 0) {
            formData.append('tag_ids', tagIds.join(','));
        }

        var $statusEl = $('<div class="alert alert-info small py-1 mt-2">上传中...</div>');
        $('#fileListContainer').prepend($statusEl);

        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
        $.ajax({
            url: '/api/files/upload',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            headers: { 'X-CSRF-Token': csrfToken },
        })
        .done(function (resp) {
            $statusEl.remove();
            if (!resp.success) {
                var errs = resp.errors || {};
                var msg = Object.values(errs).flat().join('; ') || '上传失败';
                LanDocHub.Utils.showInlineError($('#fileListContainer'), msg);
                return;
            }
            var folderName = ($('#breadcrumbFolder').text() || '').replace(LanDocHub.ICONS.FOLDER_OPEN + ' ', '');
            $(document).trigger('folder-selected', {
                folderId: folderId,
                folderName: folderName || '文件夹',
            });
        })
        .fail(function (jqXHR) {
            $statusEl.remove();
            var msg = '上传失败';
            if (jqXHR.status === 413) {
                msg = '文件太大，超过 ' + LanDocHub.CONFIG.MAX_FILE_SIZE_MB + ' MB 限制';
            }
            LanDocHub.Utils.showInlineError($('#fileListContainer'), msg);
        });
    }
```

- [ ] **Step 3: 重写 `uploadFile()` 为预检包装函数**

用以下代码替换现有的 `uploadFile()` 函数体（保留函数签名第 567 行）：

```javascript
    function uploadFile(file, projectId, folderId) {
        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';

        // F5-1: 先检测同名文件
        $.ajax({
            url: '/api/files/check-duplicate',
            method: 'GET',
            data: { filename: file.name, project_id: projectId },
            headers: { 'X-CSRF-Token': csrfToken },
            dataType: 'json',
        }).done(function (resp) {
            if (resp.success && resp.exists) {
                // 有同名文件 → 弹出确认弹窗
                DuplicateCheck.show(
                    file,
                    resp.existing_file,
                    projectId,
                    folderId,
                    // 覆盖为新版本
                    function () {
                        doUploadFile(file, projectId, folderId, 'override', null);
                    },
                    // 另存为新文件
                    function () {
                        var newName = generateSuffixedName(file.name);
                        doUploadFile(file, projectId, folderId, 'save_as_new', newName);
                    },
                    // 取消 — 什么都不做
                    function () {}
                );
            } else {
                // 无同名文件 → 直接上传
                doUploadFile(file, projectId, folderId, null, null);
            }
        }).fail(function () {
            // 检测失败 → 降级为直接上传（不阻塞用户）
            doUploadFile(file, projectId, folderId, null, null);
        });
    }
```

- [ ] **Step 4: 删除原有的 `uploadFile` 函数体（已被替换）**

确保旧的 `uploadFile()` 函数体代码完全被上述新代码替换，不留残留。

- [ ] **Step 5: 运行全部测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 20
```

预期：全部通过。前端变更不影响后端测试。

- [ ] **Step 6: 提交**

```powershell
git add static/js/upload_handler.js
git commit -m "feat: add pre-upload duplicate check flow in uploadFile for F5-1"
```

---

## Task 7: 前端 — 修改 `uploadBatch()` 添加批量上传的同名检测

**Files:**
- Modify: `static/js/upload_handler.js`（修改 `uploadBatch()` 内的 `uploadNext()` 函数）

- [ ] **Step 1: 在 `uploadNext()` 中，XHR 发送前插入同名检测 AJAX 调用**

修改 `uploadBatch()` 内的 `uploadNext()` 函数。在构建 `formData`（约第 1226-1240 行）之后、创建 `xhr`（约第 1242 行）之前，插入一次 AJAX 预检。将 XHR 发送逻辑移入 AJAX 的 done/fail 回调：

需要将第 1226-1273 行（从 `var formData = new FormData();` 到 `xhr.send(formData);`）重构为新的结构。完整替换 `uploadNext` 函数体如下：

```javascript
        function uploadNext(index) {
            if (index >= total) {
                $('#batchUploadModal').modal('hide');

                var folderName = '';
                if (folderId) {
                    var $activeNode = $('#folderTree').find('.tree-node.active');
                    if ($activeNode.length) {
                        folderName = $activeNode.find('.tree-name').text().trim();
                    }
                }
                $('body').trigger('folder-selected', [{ folderId: folderId, folderName: folderName }]);

                if (failed > 0) {
                    alert('上传完成：' + completed + ' 个成功，' + failed + ' 个失败');
                }
                return;
            }

            var file = fileArray[index];
            var $status = $('#batchStatus' + index);
            var $progressWrap = $('#batchProgressWrap' + index);
            var $progressBar = $('#batchProgress' + index);

            $status.removeClass('status-pending').addClass('status-uploading').text('上传中…');
            $progressWrap.show();
            $progressBar.css('width', '0%');

            // F5-1: 批量上传前检测同名文件
            $.ajax({
                url: '/api/files/check-duplicate',
                method: 'GET',
                data: { filename: file.name, project_id: projectId },
                headers: { 'X-CSRF-Token': csrfToken },
                dataType: 'json',
            }).done(function (resp) {
                var dupAction = null;
                var newFilename = null;

                if (resp.success && resp.exists) {
                    dupAction = 'override';
                }

                _sendBatchFile(index, file, projectId, folderId,
                    Array.isArray(versionNumbers) ? versionNumbers[index] : versionNumbers,
                    versionNote, dupAction, newFilename);
            }).fail(function () {
                // 检测失败 → 降级为直接上传
                _sendBatchFile(index, file, projectId, folderId,
                    Array.isArray(versionNumbers) ? versionNumbers[index] : versionNumbers,
                    versionNote, null, null);
            });
        }

        function _sendBatchFile(index, file, projectId, folderId, versionNumber, versionNote,
                               duplicateAction, newFilename) {
            var $status = $('#batchStatus' + index);
            var $progressWrap = $('#batchProgressWrap' + index);
            var $progressBar = $('#batchProgress' + index);

            var formData = new FormData();
            formData.append('file', file);
            formData.append('project_id', projectId);
            formData.append('folder_id', folderId);
            formData.append('version_number', versionNumber);
            formData.append('version_note', versionNote);

            // F5-1: 同名文件处理参数
            if (duplicateAction) {
                formData.append('duplicate_action', duplicateAction);
            }
            if (newFilename) {
                formData.append('new_filename', newFilename);
            }

            // F4-1: 收集批量标签 ID
            var batchTagIds = [];
            $('#batchTagSelector input[type="checkbox"]:checked').each(function () {
                batchTagIds.push($(this).val());
            });
            if (batchTagIds.length > 0) {
                formData.append('tag_ids', batchTagIds.join(','));
            }

            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/files/upload', true);
            xhr.setRequestHeader('X-CSRF-Token', csrfToken);

            xhr.upload.onprogress = function (e) {
                if (e.lengthComputable) {
                    var pct = Math.round((e.loaded / e.total) * 100);
                    $progressBar.css('width', pct + '%');
                }
            };

            xhr.onload = function () {
                if (xhr.status === 201) {
                    completed++;
                    $status.removeClass('status-uploading').addClass('status-done').text('✓ 完成');
                    $progressBar.css('width', '100%');
                } else {
                    failed++;
                    $status.removeClass('status-uploading').addClass('status-fail').text('✗ 失败');
                    $progressBar.css('background', '#dc3545');
                }
                uploadNext(index + 1);
            };

            xhr.onerror = function () {
                failed++;
                $status.removeClass('status-uploading').addClass('status-fail').text('✗ 失败');
                $progressBar.css('background', '#dc3545');
                uploadNext(index + 1);
            };

            xhr.send(formData);
        }
```

**注意：** `_sendBatchFile` 定义在 `uploadBatch` 函数体内，作为内部辅助函数。它复用 `uploadBatch` 闭包中的 `csrfToken`、`failed`、`completed`、`total` 等变量。

- [ ] **Step 2: 运行全部测试确认无回归**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 20
```

预期：全部通过。

- [ ] **Step 3: 提交**

```powershell
git add static/js/upload_handler.js
git commit -m "feat: add duplicate check to batch upload for F5-1"
```

---

## Task 8: 前端 — 注册新 JS 文件并添加 CSS 样式

**Files:**
- Modify: `templates/base.html`
- Modify: `static/css/app.css`

- [ ] **Step 1: 在 `base.html` 中注册 `duplicate_check_modal.js`**

在 `templates/base.html` 中，找到 `upload_intercept_modal.js` 的 `<script>` 标签行，在其**之后**、`upload_handler.js` 的 `<script>` 标签**之前**插入：

```html
<!-- F5-1 同名文件检测弹窗 JS -->
<script src="{{ url_for('static', filename='js/duplicate_check_modal.js') }}"></script>
```

具体位置：在 `<script src="{{ url_for('static', filename='js/upload_intercept_modal.js') }}"></script>` 之后、`<script src="{{ url_for('static', filename='js/upload_handler.js') }}"></script>` 之前。

- [ ] **Step 2: 在 `app.css` 中添加 `#dupExistingInfo` 样式**

在 `static/css/app.css` 末尾追加：

```css
/* ── F5-1 同名文件检测模态框 ── */
#dupExistingInfo {
    background: #f8f9fa;
    border-radius: 4px;
    padding: 8px 12px;
    border-left: 3px solid #ffc107;
}
```

- [ ] **Step 3: 提交**

```powershell
git add templates/base.html static/css/app.css
git commit -m "feat: register duplicate_check_modal.js and add CSS for F5-1"
```

---

## Task 9: 测试 — 编写后端测试

**Files:**
- Create: `tests/test_duplicate_detection.py`

- [ ] **Step 1: 确认路由已注册到测试应用**

在 Task 9 开始前，需要确认 `check-duplicate` 路由能被测试应用加载。检查 `app.py` 中是否已注册 `files_bp` 蓝图：运行 `grep "files_bp" app.py` 确认。

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
Select-String -Path app.py -Pattern 'files_bp|register_blueprint.*files' 2>&1
```

预期：已有 `register_blueprint(files_bp)`。

- [ ] **Step 2: 编写测试文件**

```python
"""F5-1: 同名文件检测 + 覆盖/另存为 测试"""

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


def _seed_project_and_folder(app, project_model='F5TEST', project_name='测试项目'):
    """创建测试用的项目和根文件夹，返回 (project_id, folder_id)"""
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


# ═══════════════════════════════════════════
# check-duplicate 端点测试
# ═══════════════════════════════════════════

class TestCheckDuplicate:

    def test_no_duplicate_returns_false(self, app):
        """目标项目中无同名文件时返回 exists=False"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, _ = _seed_project_and_folder(app)

        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'nonexistent.pdf', 'project_id': proj_id},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['exists'] is False

    def test_existing_file_returns_true_and_details(self, app):
        """目标项目中存在同名文件时返回 exists=True 及详细信息"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传一个文件
        resp = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'test content'), 'report.pdf'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'version_number': 'I',
            },
        )
        assert resp.status_code == 201

        # 检测同名文件
        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'report.pdf', 'project_id': proj_id},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['exists'] is True
        assert data['existing_file']['original_filename'] == 'report.pdf'
        assert data['existing_file']['version_number'] == 'I'

    def test_missing_params_returns_400(self, app):
        """缺少参数时返回 400"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'test.pdf'},
        )
        assert resp.status_code == 400

        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'project_id': 1},
        )
        assert resp.status_code == 400

    def test_different_project_no_conflict(self, app):
        """不同项目中的同名文件不算冲突"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app, 'F5TEST', '测试项目')

        # 创建第二个项目
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            other_project = Project(model='PRJ002', name='其他项目')
            _db.session.add(other_project)
            _db.session.flush()
            other_folder = Folder(
                name='PRJ002_其他项目',
                is_project_root=True,
                project_id=other_project.id,
                parent_id=None,
                created_by=admin.id,
            )
            _db.session.add(other_folder)
            _db.session.commit()
            other_proj_id = other_project.id
            other_folder_id = other_folder.id

        # 在第一个项目中上传
        client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'test'), 'shared.pdf'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
            },
        )

        # 在另一个项目中检测 — 应不冲突
        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'shared.pdf', 'project_id': other_proj_id},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['exists'] is False


# ═══════════════════════════════════════════
# 覆盖为新版本测试
# ═══════════════════════════════════════════

class TestOverrideUpload:

    def test_override_archives_to_file_versions(self, app):
        """覆盖上传时应将旧版本归档到 file_versions 表"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传 v1
        resp = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'version one'), 'doc.pdf'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'version_number': 'I',
                'version_note': 'first version',
            },
        )
        assert resp.status_code == 201
        file_id_v1 = json.loads(resp.data)['file']['id']

        # 覆盖为 v2
        resp2 = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'version two'), 'doc.pdf'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'version_number': 'I',
                'duplicate_action': 'override',
            },
        )
        assert resp2.status_code == 201

        # 验证旧版本已归档
        with app.app_context():
            versions = (
                FileVersion.query
                .filter_by(file_id=file_id_v1)
                .all()
            )
            assert len(versions) == 1
            assert versions[0].version_number == 'I'
            assert versions[0].version_note == 'first version'
            assert versions[0].file_size == len(b'version one')

            # 验证旧文件 is_current=False
            old = _db.session.get(File, file_id_v1)
            assert old.is_current is False

            # 验证新文件 version_number=II
            new_id = json.loads(resp2.data)['file']['id']
            new = _db.session.get(File, new_id)
            assert new.is_current is True
            assert new.version_number == 'II'

    def test_override_increments_version_roman(self, app):
        """多次覆盖的版本号应依次递增 I → II → III"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        def upload_version(content, dup_action=None, version='I'):
            data = {
                'file': (io.BytesIO(content), 'doc.pdf'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'version_number': version,
            }
            if dup_action:
                data['duplicate_action'] = dup_action
            return client.post('/api/files/upload', data=data)

        r1 = upload_version(b'v1')
        assert r1.status_code == 201
        assert json.loads(r1.data)['file']['version_number'] == 'I'

        r2 = upload_version(b'v2', 'override')
        assert r2.status_code == 201
        assert json.loads(r2.data)['file']['version_number'] == 'II'

        r3 = upload_version(b'v3', 'override')
        assert r3.status_code == 201
        assert json.loads(r3.data)['file']['version_number'] == 'III'


# ═══════════════════════════════════════════
# 另存为新文件测试
# ═══════════════════════════════════════════

class TestSaveAsNewUpload:

    def test_save_as_new_uses_suffixed_name(self, app):
        """另存为新文件时 original_filename 应包含后缀"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传原文件
        resp = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'original'), 'report.pdf'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
            },
        )
        assert resp.status_code == 201

        # 另存为新文件
        resp2 = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'new content'), 'report.pdf'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'duplicate_action': 'save_as_new',
                'new_filename': 'report (1).pdf',
            },
        )
        assert resp2.status_code == 201
        new_file = json.loads(resp2.data)['file']
        assert new_file['original_filename'] == 'report (1).pdf'
        assert new_file['version_number'] == 'I'

    def test_save_as_new_does_not_archive_old(self, app):
        """另存为新文件时不应归档原文件（原文件保持 is_current=True）"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传原文件
        resp = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'original'), 'data.xlsx'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
            },
        )
        assert resp.status_code == 201
        file_id_v1 = json.loads(resp.data)['file']['id']

        # 另存为新文件
        client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'new data'), 'data.xlsx'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'duplicate_action': 'save_as_new',
                'new_filename': 'data (1).xlsx',
            },
        )

        # 原文件仍为当前版本
        with app.app_context():
            old = _db.session.get(File, file_id_v1)
            assert old.is_current is True

            # 无新增 FileVersion 记录
            versions = (
                FileVersion.query
                .filter_by(file_id=file_id_v1)
                .all()
            )
            assert len(versions) == 0

    def test_save_as_new_missing_new_filename_returns_400(self, app):
        """save_as_new 但未提供 new_filename 时返回 400"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'test'), 'test.txt'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'duplicate_action': 'save_as_new',
            },
        )
        assert resp.status_code == 400

    def test_invalid_duplicate_action_returns_400(self, app):
        """无效的 duplicate_action 返回 400"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = client.post(
            '/api/files/upload',
            data={
                'file': (io.BytesIO(b'test'), 'test.txt'),
                'project_id': str(proj_id),
                'folder_id': str(folder_id),
                'duplicate_action': 'invalid_action',
            },
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: 运行新测试验证失败（TDD）**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/test_duplicate_detection.py -v --tb=short 2>&1 | Select-Object -Last 30
```

可能需要先确认 `tests/conftest.py` 中是否有 `test_project` 和 `test_folder` fixture。如果没有，需确认现有 fixtures 的命名。检查现有测试 fixtures：

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ --co 2>&1 | Select-Object -Last 5
```

如果 fixture 名称不同（如 `sample_project`、`sample_folder`），调整测试中的 fixture 名称以匹配。

- [ ] **Step 3: 提交**

```powershell
git add tests/test_duplicate_detection.py
git commit -m "test: add duplicate detection and override/save-as-new tests for F5-1"
```

---

## Task 10: 验证 — 运行全部测试并确认通过

- [ ] **Step 1: 运行完整测试套件**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 30
```

预期：所有测试通过（包括新增的 10 个 F5-1 测试和原有的 ~132 个测试）。

- [ ] **Step 2: 检查是否有 lint 问题**

```powershell
cd 'e:\Apps\Trae CN\Trae_work_document\lan-doc-hub'
python -m py_compile services/file_service.py routes/files.py 2>&1
```

预期：无输出（编译通过）。

- [ ] **Step 3: 最终提交**

```powershell
git add -A
git commit -m "feat: complete F5-1 duplicate filename detection with confirmation modal"
```

---

## 假设与决策

1. **同名匹配范围**：`original_filename + project_id + is_current=True` — 与现有 `next_version_number()` 逻辑一致。
2. **批量上传策略**：自动选择 `override`（版本迭代），不弹出逐文件确认。批量场景适合自动策略。
3. **FileVersion.file_path**：存旧文件的磁盘路径（原路径），版本记录作为审计元数据。
4. **FileVersion.uploaded_by**：存当前上传者 ID（谁触发了覆盖），不是原上传者。便于追溯谁做了版本替换。
5. **文件名后缀**：固定 `(1)` 格式，不做唯一性链式检测（如 `(1) → (2)`）。磁盘文件名有 UUID 前缀保证物理唯一。
6. **降级策略**：`check-duplicate` 端点失败时直接上传（非阻塞），确保网络抖动不影响正常上传。
7. **向后兼容**：`duplicate_action` 和 `new_filename` 为可选参数，`None` 时行为与旧版完全一致。
8. **无外部依赖**：纯 Flask + jQuery + Bootstrap 实现，无需下载第三方库。

## 验证步骤

1. 运行 `pytest tests/ -v` 确认全部测试通过（预计 ~142 个测试）
2. 手动验证场景：
   - 上传新文件（无同名）→ 直接上传成功
   - 上传同名文件 → 弹窗显示 → 选择"覆盖" → 旧版本归档到 file_versions，新版本号递增
   - 上传同名文件 → 弹窗显示 → 选择"另存为新文件" → 新文件带 `(1)` 后缀，原文件不受影响
   - 上传同名文件 → 弹窗显示 → 取消 → 不执行任何操作
   - 批量上传含同名文件 → 自动覆盖，版本号递增
3. 检查 `file_versions` 表是否有归档记录：`python -c "from app import create_app; from models import db, FileVersion; app=create_app(); app.app_context().push(); print(FileVersion.query.all())"`
