/**
 * F3-1 文件上传全流程
 *
 * 流程：
 *   点击上传按钮 → 文件选择对话框 → 上传信息弹窗（项目/编号/上传者）
 *   → 用户确认 → F2-2 跨项目校验 → 上传 → 刷新文件列表
 */
$(function () {
    'use strict';

    var $btnUpload = $('#btnUploadFile');
    var $fileInput = null;
    var $folderInput = null;
    var _showRelPath = false;

    // ── F3-3：批量上传队列 ──
    var _batchFiles = [];
    var _batchFolderId = null;

    function getCurrentFolderId() {
        return $('#fileListContainer').data('currentFolderId');
    }

    function ensureFileInput() {
        if ($fileInput) return;
        $fileInput = $(
            '<input type="file" style="display:none;" ' +
            'accept="' + LanDocHub.CONFIG.ACCEPTED_FILE_TYPES + '" multiple>'
        );
        $('body').append($fileInput);

        $fileInput.on('change', function () {
            var files = this.files;
            if (!files || files.length === 0) return;

            if (files.length === 1) {
                // ── 单文件：保持现有流程不变 ──
                onFileSelected(files[0]);
            } else {
                // ── 多文件：走自动上传 ──
                var folderId = getCurrentFolderId();
                if (!folderId) {
                    alert('请先在左侧选择一个文件夹');
                    $fileInput.val('');
                    return;
                }
                var fileArray = [];
                for (var i = 0; i < files.length; i++) {
                    fileArray.push(files[i]);
                }
                _showRelPath = false;
                autoUpload(fileArray, folderId, false);
            }

            $fileInput.val('');
        });
    }

    function ensureFolderInput() {
        if ($folderInput) return;
        $folderInput = $(
            '<input type="file" style="display:none;" webkitdirectory>'
        );
        $('body').append($folderInput);

        $folderInput.on('change', function () {
            var files = this.files;
            if (!files || files.length === 0) return;

            var fileArray = [];
            for (var i = 0; i < files.length; i++) {
                var file = files[i];
                var parts = (file.webkitRelativePath || '').split('/');
                if (parts.length > 1) {
                    parts.shift();
                    file.relativePath = parts.join('/');
                } else {
                    file.relativePath = '';
                }
                fileArray.push(file);
            }

            var folderId = getCurrentFolderId();
            if (!folderId) {
                alert('请先在左侧选择一个文件夹');
                $folderInput.val('');
                return;
            }
            autoUpload(fileArray, folderId, true);
            $folderInput.val('');
        });
    }

    $btnUpload.on('click', function () {
        $('#uploadMethodModal').modal('show');
    });

    $('#btnPickFiles').on('click', function () {
        $('#uploadMethodModal').modal('hide');
        ensureFileInput();
        $fileInput.click();
    });

    $('#btnPickFolder').on('click', function () {
        $('#uploadMethodModal').modal('hide');
        ensureFolderInput();
        $folderInput.click();
    });

    // ── F3-3：拖放上传 ──
    function ensureDropZone() {
        if ($('#dropZoneOverlay').length) return;
        var $overlay = $(
            '<div id="dropZoneOverlay" class="drop-zone-overlay">' +
            '<div class="drop-zone-hint">' +
            '<div class="icon">&#128229;</div>' +
            '<div class="title">释放文件以上传</div>' +
            '<div class="sub">支持拖拽一个或多个文件</div>' +
            '</div></div>'
        );
        $('body').append($overlay);
    }

    var dragCounter = 0;
    $(document).on('dragover', function (e) {
        e.preventDefault();
        e.stopPropagation();
    });
    $(document).on('dragenter', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter++;
        if (dragCounter === 1) {
            ensureDropZone();
            $('#dropZoneOverlay').addClass('active');
        }
    });
    $(document).on('dragleave', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            $('#dropZoneOverlay').removeClass('active');
        }
    });
    $(document).on('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter = 0;
        $('#dropZoneOverlay').removeClass('active');

        var items = e.originalEvent.dataTransfer.items;
        var hasDirectory = false;
        if (items && items.length > 0) {
            for (var i = 0; i < items.length; i++) {
                var entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
                if (entry && entry.isDirectory) {
                    hasDirectory = true;
                    break;
                }
            }
        }

        if (hasDirectory) {
            traverseDroppedItems(items, function (fileArray) {
                if (fileArray.length === 0) {
                    alert('所选文件夹中没有文件');
                    return;
                }
                var folderId = getCurrentFolderId();
                if (!folderId) {
                    alert('请先在左侧选择一个文件夹');
                    return;
                }
                _showRelPath = true;
                showBatchUploadModal(fileArray, folderId);
            });
        } else {
            var files = e.originalEvent.dataTransfer.files;
            if (files && files.length > 0) {
                _showRelPath = false;
                handleFilesSelected(files);
            }
        }
    });

    function onFileSelected(file) {
        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
        $.ajax({
            url: '/api/files/pre-number',
            method: 'POST',
            headers: { 'X-CSRF-Token': csrfToken },
            dataType: 'json',
        }).done(function (resp) {
            var fileNumber = resp.file_number || 'F-UNKNOWN';
            if (getCurrentFolderId()) {
                showUploadModal(file, fileNumber);
            } else {
                showFolderPickerModal(file, fileNumber);
            }
        }).fail(function () {
            LanDocHub.Utils.showInlineError($('#fileListContainer'), '文件编号生成失败，请刷新页面后重试');
        });
    }

    function showUploadModal(file, fileNumber) {
        // 移除旧弹窗
        $('#uploadInfoModal').remove();

        var fileSizeStr = LanDocHub.Utils.formatFileSize(file.size);
        var uploaderName = LanDocHub.Utils.getUserDisplayName();

        var html =
            '<div class="modal fade" id="uploadInfoModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-primary text-white">' +
            '<h5 class="modal-title">\uD83D\uDCE4 文件上传</h5>' +
            '<button type="button" class="close text-white" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<div class="form-group">' +
            '<label>文件名称</label>' +
            '<input type="text" class="form-control-plaintext" readonly ' +
            'value="' + file.name + ' (' + fileSizeStr + ')">' +
            '</div>' +
            '<div class="form-row">' +
            '<div class="form-group col-md-6">' +
            '<label>文件编号</label>' +
            '<input type="text" class="form-control form-control-sm" id="inputFileNumber" ' +
            'value="' + fileNumber + '" readonly>' +
            '</div>' +
            '<div class="form-group col-md-6">' +
            '<label>上传者</label>' +
            '<input type="text" class="form-control form-control-sm" id="inputUploader" ' +
            'value="' + uploaderName + '" readonly>' +
            '</div>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>所属项目 ' +
            '<small class="text-muted">(输入型号或名称搜索)</small></label>' +
            '<input type="text" class="form-control form-control-sm" id="inputProjectSearch" ' +
            'placeholder="搜索已有项目..." autocomplete="off">' +
            '<input type="hidden" id="inputProjectId">' +
            '</div>' +
            '<div class="form-row">' +
            '<div class="form-group col-md-4">' +
            '<label>版本号 <small class="text-muted">(自动迭代)</small></label>' +
            '<select class="form-control form-control-sm" id="inputVersionNumber">' +
            '<option value="I">I</option><option value="II">II</option>' +
            '<option value="III">III</option><option value="IV">IV</option>' +
            '<option value="V">V</option><option value="VI">VI</option>' +
            '<option value="VII">VII</option><option value="VIII">VIII</option>' +
            '<option value="IX">IX</option><option value="X">X</option>' +
            '</select>' +
            '</div>' +
            '<div class="form-group col-md-8">' +
            '<label>版本备注 <small class="text-muted">(可选)</small></label>' +
            '<input type="text" class="form-control form-control-sm" id="inputVersionNote" ' +
            'placeholder="修改说明，最多 200 字" maxlength="200">' +
            '</div>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>标签 <small class="text-muted">(可选，多选)</small></label>' +
            '<div class="tag-selector" id="uploadTagSelector">' +
            '<span class="text-muted small">加载中...</span>' +
            '</div>' +
            '</div>' +
            '<div class="alert alert-warning py-2 mb-0 mt-2 small" id="alertProjectMismatch" ' +
            'style="display:none;">' +
            '⚠ 当前文件夹不属于所选项目，提交后将触发跨项目拦截。' +
            '</div>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">' +
            '取消</button>' +
            '<button type="button" class="btn btn-primary btn-sm" id="btnConfirmUpload">' +
            '确认上传</button>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>';

        $('body').append(html);
        var $modal = $('#uploadInfoModal');

        // F4-1: 加载标签选择器
        (function loadTagSelector() {
            var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
            $.ajax({
                url: '/api/tags',
                method: 'GET',
                headers: { 'X-CSRF-Token': csrfToken },
                dataType: 'json',
            }).done(function (resp) {
                var $sel = $('#uploadTagSelector').empty();
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
        })();

        // 标签多选点击切换
        $(document).off('click', '#uploadTagSelector .tag-check-label').on('click', '#uploadTagSelector .tag-check-label', function (e) {
            e.preventDefault();
            var $label = $(this);
            var $cb = $label.find('input[type="checkbox"]');
            var checked = !$cb.prop('checked');
            $cb.prop('checked', checked);
            $label.toggleClass('selected', checked);
        });

        // F4-2: 初始化项目 autocomplete
        initProjectAutocomplete();

        // 自动检索下一个版本号
        function fetchNextVersion() {
            var projectId = parseInt($('#inputProjectId').val());
            if (!projectId) {
                console.warn('[版本号] 项目未选中，跳过自动检索');
                return;
            }
            var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
            $.ajax({
                url: '/api/files/next-version',
                method: 'GET',
                data: { filename: file.name, project_id: projectId },
                headers: { 'X-CSRF-Token': csrfToken },
                dataType: 'json',
            }).done(function (resp) {
                if (resp.success && resp.version_number) {
                    $('#inputVersionNumber').val(resp.version_number);
                } else {
                    console.warn('[版本号] 响应异常:', resp);
                }
            }).fail(function (jqXHR, textStatus) {
                console.warn('[版本号] 检索失败 (' + textStatus + ')，使用默认值 I');
            });
        }

        // F4-2: 项目切换时版本号更新已由 autocomplete onSelect 处理，无需额外绑定 change 事件

        $('#btnConfirmUpload').on('click', function () {
            var projectId = parseInt($('#inputProjectId').val());
            if (!projectId) {
                $('#inputProjectSearch').addClass('is-invalid');
                return;
            }
            $('#inputProjectSearch').removeClass('is-invalid');
            $modal.modal('hide');

            var folderId = getCurrentFolderId();
            if (typeof UploadIntercept !== 'undefined') {
                UploadIntercept.show(folderId, projectId,
                    function (result) {
                        uploadFile(file, result.declaredProjectId, folderId);
                    },
                    function (result) {
                        uploadFile(file, result.declaredProjectId, folderId);
                    }
                );
            } else {
                uploadFile(file, projectId, folderId);
            }
        });

        $modal.on('hidden.bs.modal', function () {
            $modal.remove();
        });

        // 弹窗显示后再检索版本号（确保 DOM 完全就绪）
        $modal.on('shown.bs.modal', function () {
            var pid = parseInt($('#inputProjectId').val());
            if (pid) fetchNextVersion();
        });

        $modal.modal('show');
    }

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
                if ($node.length) defaultDisplay = $node.find('.tree-name').text().trim();
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
                checkProjectMatch(getCurrentFolderId(), item.id);
                fetchNextVersion();
            },
            onCreateNew: function (query, onCreated) {
                showCreateProjectInline(query, function (newProject) {
                    onCreated(newProject);
                    $hidden.val(newProject.id);
                    $acInput.val(newProject.display);
                    fetchNextVersion();
                });
            },
        });

        function fetchNextVersion() {
            var projectId = parseInt($hidden.val());
            if (!projectId) return;
            $.ajax({
                url: '/api/files/next-version',
                method: 'GET',
                data: { filename: file.name, project_id: projectId },
                headers: { 'X-CSRF-Token': csrfToken },
                dataType: 'json',
            }).done(function (resp) {
                if (resp.success && resp.version_number) {
                    $('#inputVersionNumber').val(resp.version_number);
                }
            }).fail(function () {
                // 静默失败，使用默认值
            });
        }
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
            'value="' + LanDocHub.Utils.escapeHtml(defaultModel || '') + '">' +
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

    function checkProjectMatch(folderId, projectId) {
        if (!folderId || !projectId) return;
        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
        $.ajax({
            url: '/api/validate-upload',
            method: 'POST',
            contentType: 'application/json',
            headers: { 'X-CSRF-Token': csrfToken },
            data: JSON.stringify({ folder_id: folderId, project_id: projectId }),
        }).done(function (resp) {
            var $alert = $('#alertProjectMismatch');
            if (resp.success && !resp.match) {
                $alert.show();
            } else {
                $alert.hide();
            }
        }).fail(function () {
            // 静默忽略校验失败——不阻塞用户操作
        });
    }

    function uploadFile(file, projectId, folderId) {
        var formData = new FormData();
        formData.append('file', file);
        formData.append('project_id', projectId);
        formData.append('folder_id', folderId);
        formData.append('version_number', $('#inputVersionNumber').val() || 'I');
        formData.append('version_note', $('#inputVersionNote').val() || '');

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



    // ── 文件夹选择器模态框（Task 3）──
    function showFolderPickerModal(file, fileNumber) {
        $('#folderPickerModal').remove();

        var html =
            '<div class="modal fade" id="folderPickerModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered modal-lg" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-primary text-white">' +
            '<h5 class="modal-title">\uD83D\uDCC2 选择目标文件夹</h5>' +
            '<button type="button" class="close text-white" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body" style="max-height:400px;overflow-y:auto;">' +
            '<p class="text-muted small mb-2">文件：<strong>' + file.name + '</strong> （' + LanDocHub.Utils.formatFileSize(file.size) + '）</p>' +
            '<p class="text-muted small mb-3">编号：' + fileNumber + '</p>' +
            '<div id="folderPickerList" class="list-group list-group-flush"></div>' +
            '<div id="newFolderForm" style="display:none;" class="mt-2 p-2 bg-light rounded">' +
            '<div class="input-group input-group-sm">' +
            '<input type="text" class="form-control" id="inputNewFolderName" ' +
            'placeholder="新文件夹名称，最多 32 字符" maxlength="32">' +
            '<div class="input-group-append">' +
            '<button class="btn btn-success" id="btnCreateFolder">创建</button>' +
            '<button class="btn btn-outline-secondary" id="btnCancelCreate">取消</button>' +
            '</div>' +
            '</div>' +
            '<div class="invalid-feedback d-block" id="newFolderError" style="display:none;"></div>' +
            '</div>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" id="btnToggleNewFolder">\uD83D\uDCC1 新建文件夹</button>' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">取消</button>' +
            '<button type="button" class="btn btn-primary btn-sm" id="btnConfirmFolder" disabled>确认选择</button>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>';

        $('body').append(html);
        var $modal = $('#folderPickerModal');
        var selectedFolderId = null;

        // 加载文件夹列表
        $.ajax({
            url: '/api/folders/tree',
            method: 'GET',
            dataType: 'json',
        }).done(function (resp) {
            if (!resp.success || !resp.tree || resp.tree.length === 0) {
                $('#folderPickerList').html(
                    '<div class="text-center text-muted py-4">暂无可用文件夹</div>'
                );
                return;
            }
            var flat = LanDocHub.Utils.flattenTree(resp.tree);
            var html2 = '';
            $.each(flat, function (i, f) {
                var indent = '&nbsp;&nbsp;&nbsp;&nbsp;'.repeat(f.depth);
                var icon = f.is_project_root ? '\uD83D\uDCC1' : '\uD83D\uDCC2';
                html2 += '<a href="#" class="list-group-item list-group-item-action folder-picker-item" ' +
                    'data-folder-id="' + f.id + '" data-project-id="' + f.project_id + '">' +
                    indent + icon + ' ' + f.name + '</a>';
            });
            $('#folderPickerList').html(html2);
        });

        // 点击选中文件夹
        $modal.on('click', '.folder-picker-item', function (e) {
            e.preventDefault();
            $modal.find('.folder-picker-item').removeClass('active');
            $(this).addClass('active');
            selectedFolderId = $(this).data('folder-id');
            var projectId = $(this).data('project-id');
            $('#btnConfirmFolder').prop('disabled', false);
            $modal.data('selected-project-id', projectId);
        });

        // 切换"新建文件夹"表单
        $('#btnToggleNewFolder').on('click', function () {
            var $form = $('#newFolderForm');
            if ($form.is(':visible')) {
                $form.slideUp(150);
            } else {
                $form.slideDown(150);
                $('#inputNewFolderName').val('').focus();
                $('#newFolderError').hide();
            }
        });

        // 取消创建
        $('#btnCancelCreate').on('click', function () {
            $('#newFolderForm').slideUp(150);
        });

        // 创建新文件夹
        $('#btnCreateFolder').on('click', function () {
            var name = $('#inputNewFolderName').val().trim();
            if (!name) {
                $('#newFolderError').text('文件夹名称不能为空').show();
                return;
            }

            var parentId = selectedFolderId;
            if (!parentId) {
                parentId = $('.tree-node[data-is-root="true"]').first().data('folder-id');
            }

            var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
            $.ajax({
                url: '/api/folders',
                method: 'POST',
                contentType: 'application/json',
                headers: { 'X-CSRF-Token': csrfToken },
                data: JSON.stringify({ name: name, parent_id: parentId }),
            })
            .done(function (resp) {
                if (!resp.success) {
                    var errs = resp.errors || {};
                    var msg = Object.values(errs).flat().join('; ');
                    $('#newFolderError').text(msg).show();
                    return;
                }
                $('#newFolderForm').slideUp(150);
                $.ajax({
                    url: '/api/folders/tree',
                    method: 'GET',
                    dataType: 'json',
                }).done(function (treeResp) {
                    if (treeResp.success && treeResp.tree) {
                        var flat = LanDocHub.Utils.flattenTree(treeResp.tree);
                        var html2 = '';
                        var newFolderId = resp.folder.id;
                        $.each(flat, function (i, f) {
                            var indent = '&nbsp;&nbsp;&nbsp;&nbsp;'.repeat(f.depth);
                            var icon = f.is_project_root ? '\uD83D\uDCC1' : '\uD83D\uDCC2';
                            html2 += '<a href="#" class="list-group-item list-group-item-action folder-picker-item' +
                                (f.id === newFolderId ? ' active' : '') +
                                '" data-folder-id="' + f.id + '" data-project-id="' + f.project_id + '">' +
                                indent + icon + ' ' + f.name + '</a>';
                        });
                        $('#folderPickerList').html(html2);
                        if (newFolderId) {
                            selectedFolderId = newFolderId;
                            $('#btnConfirmFolder').prop('disabled', false);
                            var $newItem = $('#folderPickerList .folder-picker-item[data-folder-id="' + newFolderId + '"]');
                            if ($newItem.length) {
                                $('#folderPickerList').scrollTop($newItem.position().top + $('#folderPickerList').scrollTop() - 50);
                            }
                        }
                    }
                });
            })
            .fail(function () {
                $('#newFolderError').text('创建失败，请重试').show();
            });
        });

        // 确认选择
        $('#btnConfirmFolder').on('click', function () {
            if (!selectedFolderId) return;

            $('#fileListContainer').data('currentFolderId', selectedFolderId);
            $('.tree-node.active').removeClass('active');
            $('.tree-node[data-folder-id="' + selectedFolderId + '"]').addClass('active');

            $modal.modal('hide');
            showUploadModal(file, fileNumber);
        });

        $modal.on('hidden.bs.modal', function () {
            $modal.remove();
        });
        $modal.modal('show');
    }

    // ═══════════════════════════════════════════════════════════
    // F3-4：文件夹上传 —— 递归遍历
    // ═══════════════════════════════════════════════════════════

    /**
     * 递归遍历单个 Entry（文件或目录），将文件压入 fileArray
     */
    function traverseEntry(entry, basePath, fileArray, done) {
        if (entry.isFile) {
            entry.file(function (file) {
                file.relativePath = basePath;
                fileArray.push(file);
                done();
            }, function () {
                done();
            });
        } else if (entry.isDirectory) {
            var dirReader = entry.createReader();
            var dirPath = basePath ? basePath + '/' + entry.name : entry.name;
            var allEntries = [];
            function readBatch() {
                dirReader.readEntries(function (entries) {
                    if (entries.length === 0) {
                        if (allEntries.length === 0) {
                            done();  // 空文件夹：跳过
                            return;
                        }
                        var pending = allEntries.length;
                        for (var i = 0; i < allEntries.length; i++) {
                            traverseEntry(allEntries[i], dirPath, fileArray, function () {
                                pending--;
                                if (pending === 0) done();
                            });
                        }
                    } else {
                        allEntries = allEntries.concat(Array.prototype.slice.call(entries));
                        readBatch();
                    }
                }, function () {
                    done();
                });
            }
            readBatch();
        } else {
            done();
        }
    }

    /**
     * 遍历拖放的 items 列表，提取所有文件（含文件夹递归）
     */
    function traverseDroppedItems(items, callback) {
        var fileArray = [];
        var pending = 0;
        var entries = [];

        for (var i = 0; i < items.length; i++) {
            var entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
            if (entry) {
                entries.push(entry);
            }
        }

        if (entries.length === 0) {
            callback(fileArray);
            return;
        }

        pending = entries.length;
        for (var j = 0; j < entries.length; j++) {
            traverseEntry(entries[j], '', fileArray, function () {
                pending--;
                if (pending === 0) callback(fileArray);
            });
        }
    }

    // ═══════════════════════════════════════════════════════════
    // F3-4：自动上传
    // ═══════════════════════════════════════════════════════════

    /**
     * 自动上传 —— 跳过确认弹窗，直接用默认项目+默认版本上传
     * @param {File[]} fileArray
     * @param {number} folderId
     * @param {boolean} showRelPath 是否显示相对路径列
     */
    function autoUpload(fileArray, folderId, showRelPath) {
        if (fileArray.length === 0) {
            alert('没有可上传的文件');
            return;
        }

        var projectId = $('.tree-node[data-folder-id="' + folderId + '"]').data('project-id');
        if (!projectId) {
            alert('无法确定当前文件夹所属项目，请先创建项目');
            return;
        }

        _showRelPath = showRelPath;
        _batchFiles = fileArray;
        _batchFolderId = folderId;

        var $list = $('#batchFileList').empty();
        var totalSize = 0;

        var rowsHtml = '<table class="batch-upload-table"><thead><tr>' +
            '<th>文件名</th>';
        if (showRelPath) {
            rowsHtml += '<th>相对路径</th>';
        }
        rowsHtml += '<th>大小</th><th class="version-col">版本</th><th class="status-col">状态</th></tr></thead><tbody>';

        fileArray.forEach(function (file, idx) {
            var sizeStr = LanDocHub.Utils.formatFileSize(file.size);
            totalSize += file.size;
            var nameMaxLen = showRelPath ? 30 : 40;
            rowsHtml += '<tr id="batchRow' + idx + '">' +
                '<td><span title="' + LanDocHub.Utils.escapeHtml(file.name) + '">' +
                LanDocHub.Utils.escapeHtml(truncateFileName(file.name, nameMaxLen)) + '</span></td>';
            if (showRelPath) {
                var relPath = file.relativePath || '';
                rowsHtml += '<td class="file-relpath">' + LanDocHub.Utils.escapeHtml(relPath) + '</td>';
            }
            rowsHtml += '<td class="file-size">' + sizeStr + '</td>' +
                '<td class="version-col"><select class="form-control form-control-sm batch-version-select" id="batchVersion' + idx + '">' +
                '<option value="I">I</option><option value="II">II</option>' +
                '<option value="III">III</option><option value="IV">IV</option>' +
                '<option value="V">V</option><option value="VI">VI</option>' +
                '<option value="VII">VII</option><option value="VIII">VIII</option>' +
                '<option value="IX">IX</option><option value="X">X</option>' +
                '</select></td>' +
                '<td class="status-col"><span class="status-pending" id="batchStatus' + idx + '">等待上传</span>' +
                '<div class="upload-progress-wrap" style="display:none;" id="batchProgressWrap' + idx + '">' +
                '<div class="upload-progress-bar" id="batchProgress' + idx + '"></div></div></td>' +
                '</tr>';
        });
        rowsHtml += '</tbody></table>';

        rowsHtml += '<div style="font-size:0.82rem;color:#6b7280;margin-bottom:12px;">' +
            '共 <strong>' + fileArray.length + '</strong> 个文件，总大小 <strong>' +
            LanDocHub.Utils.formatFileSize(totalSize) + '</strong></div>';

        $list.html(rowsHtml);

        $('#batchUploadModal .modal-title').text(showRelPath ? '\u{1F4C1} 文件夹上传' : '批量上传');
        $('#batchUploadModal .modal-dialog').css('max-width', showRelPath ? '720px' : '620px');

        // 隐藏确认表单，直接开始上传
        $('#inputBatchProjectId, #inputBatchVersionNote, #btnBatchConfirmUpload')
            .closest('.form-group, .mt-3').hide();

        $('#batchUploadModal').modal('show');

        uploadBatch(fileArray, projectId, folderId, 'I', '');
    }

    // ═══════════════════════════════════════════════════════════
    // F3-3：批量上传
    // ═══════════════════════════════════════════════════════════

    /**
     * 处理多文件选择或拖放
     * @param {FileList|File[]} files
     */
    function handleFilesSelected(files) {
        var fileArray = [];
        for (var i = 0; i < files.length; i++) {
            fileArray.push(files[i]);
        }

        var folderId = getCurrentFolderId();
        if (!folderId) {
            alert('请先在左侧选择一个文件夹');
            return;
        }
        showBatchUploadModal(fileArray, folderId);
    }

    /**
     * 显示批量上传弹窗
     * @param {File[]} fileArray
     * @param {number} folderId
     */
    function fetchBatchNextVersions(projectId) {
        if (!projectId || !_batchFiles || _batchFiles.length === 0) return;

        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';

        for (var i = 0; i < _batchFiles.length; i++) {
            (function (idx) {
                var filename = _batchFiles[idx].name;
                $.ajax({
                    url: '/api/files/next-version',
                    method: 'GET',
                    data: { filename: filename, project_id: projectId },
                    headers: { 'X-CSRF-Token': csrfToken },
                    dataType: 'json'
                }).done(function (resp) {
                    if (resp.success && resp.version_number) {
                        var $select = $('#batchVersion' + idx);
                        if ($select.length && resp.version_number !== 'I') {
                            $select.val(resp.version_number);
                        }
                    }
                }).fail(function () {
                    // 检索失败保持默认 "I"
                });
            })(i);
        }
    }

    function showBatchUploadModal(fileArray, folderId) {
        _batchFiles = fileArray;
        _batchFolderId = folderId;

        var $list = $('#batchFileList').empty();
        var totalSize = 0;
        var showRelPath = _showRelPath;

        var rowsHtml = '<table class="batch-upload-table"><thead><tr>' +
            '<th>文件名</th>';
        if (showRelPath) {
            rowsHtml += '<th>相对路径</th>';
        }
        rowsHtml += '<th>大小</th><th class="version-col">版本</th><th class="status-col">状态</th></tr></thead><tbody>';

        fileArray.forEach(function (file, idx) {
            var sizeStr = LanDocHub.Utils.formatFileSize(file.size);
            totalSize += file.size;
            var nameMaxLen = showRelPath ? 30 : 40;
            rowsHtml += '<tr id="batchRow' + idx + '">' +
                '<td><span title="' + LanDocHub.Utils.escapeHtml(file.name) + '">' +
                LanDocHub.Utils.escapeHtml(truncateFileName(file.name, nameMaxLen)) + '</span></td>';
            if (showRelPath) {
                var relPath = file.relativePath || '';
                rowsHtml += '<td class="file-relpath">' + LanDocHub.Utils.escapeHtml(relPath) + '</td>';
            }
            rowsHtml += '<td class="file-size">' + sizeStr + '</td>' +
                '<td class="version-col"><select class="form-control form-control-sm batch-version-select" id="batchVersion' + idx + '">' +
                '<option value="I">I</option><option value="II">II</option>' +
                '<option value="III">III</option><option value="IV">IV</option>' +
                '<option value="V">V</option><option value="VI">VI</option>' +
                '<option value="VII">VII</option><option value="VIII">VIII</option>' +
                '<option value="IX">IX</option><option value="X">X</option>' +
                '</select></td>' +
                '<td class="status-col"><span class="status-pending" id="batchStatus' + idx + '">等待上传</span>' +
                '<div class="upload-progress-wrap" style="display:none;" id="batchProgressWrap' + idx + '">' +
                '<div class="upload-progress-bar" id="batchProgress' + idx + '"></div></div></td>' +
                '</tr>';
        });
        rowsHtml += '</tbody></table>';

        rowsHtml += '<div style="font-size:0.82rem;color:#6b7280;margin-bottom:12px;">' +
            '共 <strong>' + fileArray.length + '</strong> 个文件，总大小 <strong>' +
            LanDocHub.Utils.formatFileSize(totalSize) + '</strong></div>';

        $list.html(rowsHtml);

        // F4-1: 批量上传标签选择（所有文件共用）
        var tagSelectorHtml =
            '<div class="form-group mt-3" id="batchTagSelectorGroup">' +
            '<label>标签 <small class="text-muted">(可选，多选，所有文件共用)</small></label>' +
            '<div class="tag-selector" id="batchTagSelector">' +
            '<span class="text-muted small">加载中...</span>' +
            '</div>' +
            '</div>';

        $('#inputBatchVersionNote').closest('.form-group').after(tagSelectorHtml);

        // 加载标签
        (function loadBatchTagSelector() {
            var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
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
        })();

        // 批量标签多选点击事件
        $(document).off('click', '#batchTagSelector .tag-check-label').on('click', '#batchTagSelector .tag-check-label', function (e) {
            e.preventDefault();
            var $label = $(this);
            var $cb = $label.find('input[type="checkbox"]');
            var checked = !$cb.prop('checked');
            $cb.prop('checked', checked);
            $label.toggleClass('selected', checked);
        });

        // 调整弹窗标题和宽度
        $('#batchUploadModal .modal-title').text(showRelPath ? '\u{1F4C1} 文件夹上传' : '批量上传');
        $('#batchUploadModal .modal-dialog').css('max-width', showRelPath ? '720px' : '620px');

        // 恢复确认表单（autoUpload 可能已隐藏）
        $('#inputBatchProjectSearch, #inputBatchProjectId, #inputBatchVersionNote, #btnBatchConfirmUpload')
            .closest('.form-group, .form-row, .mt-3').show();

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
            // 逐文件自动检索最新迭代版本号
            fetchBatchNextVersions(defaultProjectId);
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
                fetchBatchNextVersions(item.id);
            },
            onCreateNew: function (query, onCreated) {
                showCreateProjectInline(query, function (newProject) {
                    onCreated(newProject);
                    $batchHidden.val(newProject.id);
                    $batchAcInput.val(newProject.display);
                    fetchBatchNextVersions(newProject.id);
                });
            },
        });

        // 重置按钮
        var $confirmBtn = $('#btnBatchConfirmUpload');
        $confirmBtn.prop('disabled', false);
        $confirmBtn.off('click').on('click', function () {
            var projectId = $('#inputBatchProjectId').val();
            if (!projectId) {
                alert('请选择所属项目');
                return;
            }

            var versionNote = $('#inputBatchVersionNote').val() || '';
            var fid = _batchFolderId;

            // 从每行收集各自的版本号
            var batchVersions = [];
            for (var i = 0; i < _batchFiles.length; i++) {
                var v = $('#batchVersion' + i).val() || 'I';
                batchVersions.push(v);
            }

            $(this).prop('disabled', true);
            uploadBatch(_batchFiles, projectId, fid, batchVersions, versionNote);
        });

        $('#batchUploadModal').modal('show');
    }

    /**
     * 串行批量上传
     */
    function uploadBatch(fileArray, projectId, folderId, versionNumbers, versionNote) {
        var total = fileArray.length;
        var completed = 0;
        var failed = 0;
        var csrfToken = $('meta[name="csrf-token"]').attr('content');

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

            var formData = new FormData();
            formData.append('file', file);
            formData.append('project_id', projectId);
            formData.append('folder_id', folderId);
            formData.append('version_number', Array.isArray(versionNumbers) ? versionNumbers[index] : versionNumbers);
            formData.append('version_note', versionNote);

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

        uploadNext(0);
    }

    /**
     * 截断文件名用于显示
     */
    function truncateFileName(name, maxLen) {
        if (name.length <= maxLen) return name;
        var extIndex = name.lastIndexOf('.');
        if (extIndex === -1) return name.substring(0, maxLen - 3) + '...';
        var ext = name.substring(extIndex);
        var base = name.substring(0, extIndex);
        var avail = maxLen - ext.length - 3;
        if (avail < 5) return name.substring(0, maxLen - 3) + '...';
        return base.substring(0, avail) + '...' + ext;
    }
});
