/**
 * F5-2 历史版本面板
 *
 * 用法：
 *   VersionHistoryModal.show(fileId)
 *
 * 加载 GET /api/files/<fileId>/versions，弹出 Bootstrap Modal
 * 展示版本时间线列表：版本序号、备注、上传者、时间、大小
 */
var VersionHistoryModal = (function () {
    'use strict';

    var $modal = null;
    var _fileId = null;

    function init() {
        if ($modal) return;
        var html =
            '<div class="modal fade" id="versionHistoryModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered modal-lg" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-primary text-white">' +
            '<h5 class="modal-title">' + LanDocHub.ICONS.FILE_EMPTY + ' <span id="vhTitle">版本历史</span></h5>' +
            '<button type="button" class="close text-white" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body" style="max-height:500px;overflow-y:auto;">' +
            '<div id="vhFileInfo" class="small text-muted mb-3"></div>' +
            '<div id="vhLoading" class="text-center py-4 text-muted">加载中...</div>' +
            '<div id="vhVersionList" style="display:none;"></div>' +
            '<div id="vhEmpty" style="display:none;" class="text-center py-4 text-muted">暂无历史版本</div>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">关闭</button>' +
            '</div>' +
            '</div></div></div>';
        $('body').append(html);
        $modal = $('#versionHistoryModal');

        $modal.on('hidden.bs.modal', function () {
            _fileId = null;
        });

        // 绑定按钮事件（仅一次，委托到 #vhVersionList）
        $('#vhVersionList').on('click', '.vh-btn-preview', function () {
            alert('在线预览功能即将开放（F6 阶段）');
        });
        $('#vhVersionList').on('click', '.vh-btn-download', function () {
            alert('单文件下载功能即将开放（F8-1 阶段）');
        });
        $('#vhVersionList').on('click', '.vh-btn-delete', function () {
            alert('版本删除功能即将开放（F11-1 阶段）');
        });
    }

    /**
     * 显示历史版本面板
     * @param {number} fileId 文件 ID
     */
    function show(fileId) {
        init();
        _fileId = fileId;

        $('#vhTitle').text('版本历史');
        $('#vhFileInfo').text('');
        $('#vhVersionList').hide().empty();
        $('#vhEmpty').hide();
        $('#vhLoading').show();

        $modal.modal('show');

        var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
        $.ajax({
            url: '/api/files/' + fileId + '/versions',
            method: 'GET',
            headers: { 'X-CSRF-Token': csrfToken },
            dataType: 'json',
        }).done(function (resp) {
            $('#vhLoading').hide();
            if (!resp.success) {
                $('#vhEmpty').text('加载失败').show();
                return;
            }
            var cur = resp.current_file || {};
            $('#vhTitle').text(LanDocHub.Utils.escapeHtml(cur.original_filename || '版本历史'));
            $('#vhFileInfo').html(
                '编号：' + LanDocHub.Utils.escapeHtml(cur.file_number || '-') +
                ' &nbsp;|&nbsp; 项目：' + LanDocHub.Utils.escapeHtml(cur.project_model || '') +
                ' ' + LanDocHub.Utils.escapeHtml(cur.project_name || '')
            );

            var history = resp.history || [];
            if (history.length === 0) {
                $('#vhEmpty').show();
                return;
            }

            var html = '<div class="vh-timeline">';
            $.each(history, function (i, v) {
                var isCurrent = v.is_current;
                var versionLabel = isCurrent
                    ? '<span class="badge badge-success">当前</span>'
                    : '';
                html +=
                    '<div class="vh-item' + (isCurrent ? ' vh-item-current' : '') + '">' +
                    '<div class="vh-item-header">' +
                    '<span class="vh-version-badge">' +
                    LanDocHub.Utils.escapeHtml(v.version_number || '-') +
                    '</span>' +
                    versionLabel +
                    '<span class="small text-muted ml-2">' +
                    LanDocHub.Utils.escapeHtml(v.version_note || '') +
                    '</span>' +
                    '<span class="float-right small text-muted">' +
                    LanDocHub.Utils.escapeHtml(v.uploaded_at || '') +
                    '</span>' +
                    '</div>' +
                    '<div class="vh-item-body">' +
                    '<span class="small text-muted">' +
                    LanDocHub.Utils.formatFileSize(v.file_size || 0) +
                    ' &nbsp;|&nbsp; ' + LanDocHub.Utils.escapeHtml(v.uploader_name || '') +
                    '</span>' +
                    '</div>' +
                    '<div class="vh-item-actions">' +
                    '<button class="btn btn-outline-secondary btn-xs vh-btn-preview" ' +
                    'data-file-id="' + v.id + '" title="在线预览（即将开放）">' +
                    LanDocHub.ICONS.FILE_EMPTY + ' 预览</button>' +
                    '<button class="btn btn-outline-primary btn-xs vh-btn-download" ' +
                    'data-file-id="' + v.id + '" title="下载该版本（即将开放）">' +
                    LanDocHub.ICONS.UPLOAD + ' 下载</button>' +
                    '<button class="btn btn-outline-danger btn-xs vh-btn-delete" ' +
                    'data-file-id="' + v.id + '" title="删除该版本（即将开放）">\uD83D\uDDD1 删除</button>' +
                    '</div>' +
                    '</div>';
            });
            html += '</div>';
            $('#vhVersionList').html(html).show();
        }).fail(function () {
            $('#vhLoading').hide();
            $('#vhEmpty').text('加载失败，请稍后重试').show();
        });
    }

    return { show: show };
})();
