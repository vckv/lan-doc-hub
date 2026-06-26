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
