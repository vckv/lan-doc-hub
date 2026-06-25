/**
 * F3-1 文件视图 —— 监听文件夹选中事件，AJAX 加载文件列表
 */
$(function () {
    'use strict';

    var ICONS = LanDocHub.ICONS;
    var $container = $('#fileListContainer');
    var $breadcrumb = $('#breadcrumbFolder');

    var _highlightFileId = null;
    var _highlightDismissTimer = null;

    $(document).on('folder-selected', function (e, data) {
        // 切换文件夹时清除旧高亮
        if (_highlightFileId) {
            $container.find('tr.row-hover').removeClass('row-hover');
            _highlightFileId = null;
            clearTimeout(_highlightDismissTimer);
        }
        _highlightFileId = data.highlightFileId || null;
        // 记住文件夹位置，刷新页面后恢复
        sessionStorage.setItem('lanhub_active_folder', data.folderId);
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
            // F4-1: 标签 Badges
            var tagBadges = '';
            if (f.tags && f.tags.length > 0) {
                tagBadges = '<span class="file-tags">';
                $.each(f.tags, function (_ti, tag) {
                    var color = LanDocHub.Utils.escapeHtml(tag.color || '#3b82f6');
                    var name = LanDocHub.Utils.escapeHtml(tag.name || '');
                    tagBadges +=
                        '<span class="tag-badge" style="background:' + color + '20;color:' + color + ';border:1px solid ' + color + '40;">' +
                        '<span class="tag-dot" style="background:' + color + ';"></span>' +
                        name + '</span>';
                });
                tagBadges += '</span>';
            }
            return '<tr data-file-id="' + f.id + '">' +
                '<td class="file-name">' + f.original_filename + shortcut + tagBadges + '</td>' +
                '<td><span class="file-number">' + f.file_number + '</span></td>' +
                '<td><span class="badge badge-info">' + (f.project_model || '') + '</span></td>' +
                '<td class="text-center" style="white-space:nowrap;">' +
                '<span class="badge badge-secondary mr-1">' + (f.version_number || 'I') + '</span>' +
                '<a href="/files/' + f.id + '/versions?from=' + folderId + '&file=' + f.id + '" class="badge badge-pill small" target="_blank" ' +
                'style="border:1px solid #6c757d;color:#6c757d;font-size:0.7rem;text-decoration:none;" ' +
                'title="历史版次">历史</a>' +
                '</td>' +
                '<td><span class="badge badge-light badge-type">' + f.file_type + '</span></td>' +
                '<td class="file-meta">' + LanDocHub.Utils.formatFileSize(f.file_size) + '</td>' +
                '<td class="file-meta">' + (f.uploader_name || '') + '</td>' +
                '<td class="file-meta">' + f.uploaded_at + '</td>' +
                '</tr>';
        });

        $container.html([
            '<div class="file-table"><table class="table table-hover mb-0">',
            '<thead><tr>',
            '<th>文件名称</th><th>编号</th><th>型号</th><th>版本</th><th>类型</th><th>大小</th><th>上传者</th><th>时间</th>',
            '</tr></thead><tbody>',
            rows.join(''),
            '</tbody></table></div>'
        ].join(''));

        if (_highlightFileId) {
            var $row = $container.find('tr[data-file-id="' + _highlightFileId + '"]');
            if ($row.length) {
                $row.addClass('row-hover');
                $row[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        } else {
            var savedScroll = sessionStorage.getItem('lanhub_scroll_top');
            if (savedScroll) {
                requestAnimationFrame(function () {
                    $('.main-content').scrollTop(parseInt(savedScroll));
                });
            }
        }
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

    // 监听子窗口（历史版本页）关闭时的 postMessage，直接高亮对应行
    $(window).on('message', function (e) {
        var evt = e.originalEvent;
        if (evt.origin !== window.location.origin) return;
        var data = evt.data;
        if (!data || data.action !== 'highlight-file' || !data.fileId) return;

        clearTimeout(_highlightDismissTimer);
        $container.find('tr.row-hover').removeClass('row-hover');
        _highlightFileId = data.fileId;

        var $row = $container.find('tr[data-file-id="' + _highlightFileId + '"]');
        if ($row.length) {
            $row.addClass('row-hover');
            $row[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });

    // 其他行进入 hover 态时，200ms 后自动解除高亮行
    $container.on('mouseenter', 'tr[data-file-id]', function () {
        if (!_highlightFileId) return;
        var hoveredId = parseInt($(this).attr('data-file-id'));
        if (hoveredId === _highlightFileId) return;
        clearTimeout(_highlightDismissTimer);
        _highlightDismissTimer = setTimeout(function () {
            $container.find('tr.row-hover').removeClass('row-hover');
            _highlightFileId = null;
        }, 200);
    });

    // ── 记住滚动位置（实时更新 + 离开前保底），刷新页面后恢复 ──
    var _scrollSaveTimer = null;
    $('.main-content').on('scroll', function () {
        clearTimeout(_scrollSaveTimer);
        _scrollSaveTimer = setTimeout(function () {
            sessionStorage.setItem('lanhub_scroll_top', $('.main-content').scrollTop());
        }, 80);
    });
    $(window).on('beforeunload', function () {
        sessionStorage.setItem('lanhub_scroll_top', $('.main-content').scrollTop());
    });
});
