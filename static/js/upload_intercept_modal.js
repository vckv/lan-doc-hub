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
            '<h5 class="modal-title">\u26A0 \u8DE8\u9879\u76EE\u4E0A\u4F20\u63D0\u793A</h5>' +
            '<button type="button" class="close" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<p id="interceptMessage"></p>' +
            '<p class="text-muted small">\u8BF7\u9009\u62E9\u6587\u4EF6\u7684\u5B58\u653E\u65B9\u5F0F\uFF1A</p>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary" data-dismiss="modal">\u53D6\u6D88</button>' +
            '<button type="button" class="btn btn-warning" id="btnSaveToCorrect">\uD83D\uDCC1 \u4FDD\u5B58\u5230\u6B63\u786E\u9879\u76EE\u6587\u4EF6\u5939</button>' +
            '<button type="button" class="btn btn-info" id="btnSaveWithShortcut">\uD83D\uDCC1 \u4FDD\u5B58\u5230\u6B63\u786E\u9879\u76EE\uFF0C\u5E76\u5728\u6B64\u521B\u5EFA\u5FEB\u6377\u65B9\u5F0F</button>' +
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
            var msg = '\u8BE5\u6587\u4EF6\u5C5E\u4E8E\u9879\u76EE <strong>' +
                (dp.model + '_' + dp.name) +
                '</strong>\uFF0C\u4E0D\u5141\u8BB8\u4FDD\u5B58\u5728\u9879\u76EE <strong>' +
                (fp.model + '_' + fp.name) +
                '</strong> \u6587\u4EF6\u5939\u4E2D\u3002';
            $('#interceptMessage').html(msg);
            $modal.data('declaredProjectId', declaredProjectId);
            $modal.data('currentFolderId', folderId);
            $modal.modal('show');
        })
        .fail(function () {
            alert('\u6821\u9A8C\u8BF7\u6C42\u5931\u8D25\uFF0C\u8BF7\u5237\u65B0\u9875\u9762\u540E\u91CD\u8BD5\u3002');
        });
    }

    return { show: show };
})();
