/**
 * F3-1 文件视图 —— 监听文件夹选中事件，AJAX 加载文件列表
 */
$(function () {
    'use strict';

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
                showError('\u52A0\u8F7D\u5931\u8D25');
                return;
            }
            renderFileList(resp.files || [], folderId);
        })
        .fail(function () {
            showError('\u52A0\u8F7D\u5931\u8D25\uFF0C\u8BF7\u5237\u65B0\u9875\u9762\u540E\u91CD\u8BD5');
        });
    }

    function renderFileList(files, folderId) {
        // 无论空/非空，先记录当前选中的文件夹 ID, 确保"上传文件"能读取
        $container.data('currentFolderId', folderId);

        if (files.length === 0) {
            $container.html(
                '<div class="file-empty">' +
                '<div class="icon">\uD83D\uDCC4</div>' +
                '<p>\u6B64\u6587\u4EF6\u5939\u4E2D\u6682\u65E0\u6587\u4EF6</p>' +
                '<small>\u70B9\u51FB\u4E0A\u65B9\u201C\u4E0A\u4F20\u6587\u4EF6\u201D\u6309\u94AE\u6DFB\u52A0</small>' +
                '</div>'
            );
            return;
        }

        var html = '<div class="file-table"><table class="table table-hover mb-0">' +
            '<thead><tr>' +
            '<th>\u6587\u4EF6\u540D\u79F0</th>' +
            '<th>\u7F16\u53F7</th>' +
            '<th>\u7C7B\u578B</th>' +
            '<th>\u5927\u5C0F</th>' +
            '<th>\u4E0A\u4F20\u8005</th>' +
            '<th>\u65F6\u95F4</th>' +
            '</tr></thead><tbody>';

        $.each(files, function (i, f) {
            var sizeStr = formatFileSize(f.file_size);
            var shortcutIcon = f.is_shortcut ? ' \uD83D\uDD17' : '';
            html += '<tr>' +
                '<td class="file-name">' + f.original_filename + shortcutIcon + '</td>' +
                '<td><span class="file-number">' + f.file_number + '</span></td>' +
                '<td><span class="badge badge-light badge-type">' + f.file_type + '</span></td>' +
                '<td class="file-meta">' + sizeStr + '</td>' +
                '<td class="file-meta">' + (f.uploader_name || '') + '</td>' +
                '<td class="file-meta">' + f.uploaded_at + '</td>' +
                '</tr>';
        });

        html += '</tbody></table></div>';
        $container.html(html);
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function showError(msg) {
        $container.html('<div class="file-empty"><p class="text-danger">' + msg + '</p></div>');
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
                $breadcrumb.html('\uD83D\uDCC2 ' + fallbackName);
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
            $breadcrumb.html('\uD83D\uDCC2 ' + parts.join(' <span class="breadcrumb-sep">/</span> '));
        })
        .fail(function () {
            $breadcrumb.html('\uD83D\uDCC2 ' + fallbackName);
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
