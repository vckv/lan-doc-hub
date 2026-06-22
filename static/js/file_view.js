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
