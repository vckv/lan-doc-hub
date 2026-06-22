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

    function getCurrentFolderId() {
        return $('#fileListContainer').data('currentFolderId');
    }

    function ensureFileInput() {
        if ($fileInput) return;
        $fileInput = $(
            '<input type="file" style="display:none;" ' +
            'accept="' + LanDocHub.CONFIG.ACCEPTED_FILE_TYPES + '">'
        );
        $('body').append($fileInput);

        $fileInput.on('change', function () {
            var file = this.files[0];
            if (!file) return;
            onFileSelected(file);
            $fileInput.val('');
        });
    }

    $btnUpload.on('click', function () {
        ensureFileInput();
        $fileInput.click();
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
            '<small class="text-muted">(默认为当前文件夹所属项目)</small></label>' +
            '<select class="form-control form-control-sm" id="inputProjectId">' +
            '<option value="">加载中...</option>' +
            '</select>' +
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

        // 加载项目下拉
        loadProjectOptions(function (selectedId) {
            $('#inputProjectId').val(selectedId);
        });

        $('#inputProjectId').on('change', function () {
            checkProjectMatch(getCurrentFolderId(), parseInt($(this).val()));
        });

        $('#btnConfirmUpload').on('click', function () {
            var projectId = parseInt($('#inputProjectId').val());
            if (!projectId) {
                $('#inputProjectId').addClass('is-invalid');
                return;
            }
            $('#inputProjectId').removeClass('is-invalid');
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

        $modal.modal('show');
    }

    function loadProjectOptions(callback) {
        var $select = $('#inputProjectId');
        $select.empty();

        // 从文件夹树提取项目选项（根节点）
        var added = {};
        var defaultProjectId = null;
        var activeNode = $('.tree-node.active');

        $('.tree-node[data-is-root="true"]').each(function () {
            var name = $(this).find('.tree-name').text();
            var projectId = $(this).data('project-id');
            if (added[projectId]) return;
            added[projectId] = true;
            $select.append('<option value="' + projectId + '">' + name + '</option>');
        });

        // 尝试匹配当前文件夹到项目
        if (activeNode.length) {
            var currentId = activeNode.data('folder-id');
            // 向上查根节点
            var $root = activeNode.closest('.folder-tree').find('.tree-node[data-is-root="true"]').first();
            if ($root.length && added[$root.data('project-id')]) {
                defaultProjectId = $root.data('project-id');
            } else if (added[activeNode.data('project-id')]) {
                defaultProjectId = activeNode.data('project-id');
            }
        }

        if (defaultProjectId) {
            $select.val(defaultProjectId);
        } else {
            // 取第一个选项
            var firstVal = $select.find('option').first().val();
            if (firstVal) $select.val(firstVal);
        }

        if (callback) callback(defaultProjectId || parseInt($select.val()));
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
});
