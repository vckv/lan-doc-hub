/**
 * F2-2 跨项目上传拦截模态框
 *
 * 用法（由 F3-1 上传表单调用）：
 *   UploadIntercept.show(folderId, declaredProjectId, onCorrect, onShortcut)
 *
 * 回调参数：
 *   onCorrect({ declaredProjectId, targetFolderId })
 *   onShortcut({ declaredProjectId })
 */
var UploadIntercept = (function () {
    'use strict';

    var $modal = null;
    var _onCorrect = null;
    var _onShortcut = null;

    function init() {
        if ($modal) return;
        var html =
            '<div class="modal fade" id="uploadInterceptModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-warning text-dark">' +
            '<h5 class="modal-title">⚠ 跨项目上传提示</h5>' +
            '<button type="button" class="close" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<p id="interceptMessage"></p>' +
            '<p class="text-muted small">请选择文件的存放方式：</p>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary" data-dismiss="modal">取消</button>' +
            '<button type="button" class="btn btn-warning" id="btnSaveToCorrect">' + LanDocHub.ICONS.FOLDER_CLOSED + ' 保存到正确项目文件夹</button>' +
            '<button type="button" class="btn btn-info" id="btnSaveWithShortcut">' + LanDocHub.ICONS.FOLDER_CLOSED + ' 保存到正确项目，并在此创建快捷方式</button>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>';
        $('body').append(html);
        $modal = $('#uploadInterceptModal');

        $modal.on('click', '#btnSaveToCorrect', function () {
            var declaredProjectId = $modal.data('declaredProjectId');
            if (_onCorrect) {
                _onCorrect({ declaredProjectId: declaredProjectId });
            }
            $modal.modal('hide');
        });

        $modal.on('click', '#btnSaveWithShortcut', function () {
            var declaredProjectId = $modal.data('declaredProjectId');
            if (_onShortcut) {
                _onShortcut({ declaredProjectId: declaredProjectId });
            }
            $modal.modal('hide');
        });
    }

    /**
     * 显示跨项目拦截模态框
     *
     * @param {number}   folderId
     * @param {number}   declaredProjectId
     * @param {function} onCorrect    选择"保存到正确项目"的回调
     * @param {function} onShortcut   选择"存正确+快捷方式"的回调
     */
    function show(folderId, declaredProjectId, onCorrect, onShortcut) {
        init();
        _onCorrect = onCorrect;
        _onShortcut = onShortcut;

        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
        $.ajax({
            url: '/api/validate-upload',
            method: 'POST',
            contentType: 'application/json',
            headers: { 'X-CSRF-Token': csrfToken },
            data: JSON.stringify({
                folder_id: folderId,
                project_id: declaredProjectId,
            }),
        })
        .done(function (resp) {
            if (resp.match) {
                if (onCorrect) {
                    onCorrect({ declaredProjectId: declaredProjectId, targetFolderId: folderId });
                }
                return;
            }

            var fp = resp.folder_project || {};
            var dp = resp.declared_project || {};
            var msg = '该文件属于项目 <strong>' +
                (dp.model + '_' + dp.name) +
                '</strong>，不允许保存在项目 <strong>' +
                (fp.model + '_' + fp.name) +
                '</strong> 文件夹中。';
            $('#interceptMessage').html(msg);
            $modal.data('declaredProjectId', declaredProjectId);
            $modal.data('currentFolderId', folderId);
            $modal.modal('show');
        })
        .fail(function () {
            alert('校验请求失败，请刷新页面后重试。');
        });
    }

    return { show: show };
})();
