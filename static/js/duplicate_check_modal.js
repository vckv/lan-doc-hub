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
