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
        loadFiles(data.folderId, data.folderName, data.page || 1);
        loadBreadcrumb(data.folderId, data.folderName);
    });

    function loadFiles(folderId, folderName, page) {
        page = page || 1;
        var sortBy = $container.data('sortBy') || 'created_at';
        var sortOrder = $container.data('sortOrder') || 'asc';
        $.ajax({
            url: '/api/files',
            method: 'GET',
            data: { folder_id: folderId, page: page, per_page: 20, sort_by: sortBy, sort_order: sortOrder },
            dataType: 'json',
        })
        .done(function (resp) {
            if (!resp.success) {
                LanDocHub.Utils.showInlineError($container, '加载失败');
                return;
            }
            // 后端可能回退排序参数，以 resp 为准更新本地状态
            if (resp.sort_by) $container.data('sortBy', resp.sort_by);
            if (resp.sort_order) $container.data('sortOrder', resp.sort_order);
            renderFileList(resp.files || [], folderId, resp.page || 1, resp.pages || 1, resp.total || 0,
                           resp.sort_by || 'created_at', resp.sort_order || 'asc');
        })
        .fail(function () {
            LanDocHub.Utils.showInlineError($container, '加载失败，请刷新页面后重试');
        });
    }

    var FILE_TYPE_ICONS = {
        'PDF':        '\uD83D\uDCD5',
        'Word':       '\uD83D\uDCDD',
        'Excel':      '\uD83D\uDCCA',
        'PowerPoint': '\uD83D\uDCCA',
        'Image':      '\uD83D\uDDBC\uFE0F',
        'TXT':        '\uD83D\uDCC4',
        'CSV':        '\uD83D\uDCCA',
        'Video':      '\uD83C\uDFAC',
        'Audio':      '\uD83C\uDFB5',
        'Archive':    '\uD83D\uDCE6',
        'CAD':        '\uD83D\uDCD0',
    };
    var FILE_TYPE_ICON_DEFAULT = '\uD83D\uDCCE';

    function renderFileList(files, folderId, page, pages, total, sortBy, sortOrder) {
        $container.data('currentFolderId', folderId);
        $container.data('currentPage', page);
        $container.data('totalPages', pages);

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
            var typeIcon = FILE_TYPE_ICONS[f.file_type] || FILE_TYPE_ICON_DEFAULT;
            var shortcut = f.is_shortcut ? ' ' + ICONS.LINK : '';

            // 标签 Badges（独立列）
            var tagBadges = '<span class="file-tags">';
            if (f.tags && f.tags.length > 0) {
                $.each(f.tags, function (_ti, tag) {
                    var color = LanDocHub.Utils.escapeHtml(tag.color || '#3b82f6');
                    var name = LanDocHub.Utils.escapeHtml(tag.name || '');
                    tagBadges +=
                        '<span class="tag-badge" style="background:' + color + '20;color:' + color + ';border:1px solid ' + color + '40;">' +
                        '<span class="tag-dot" style="background:' + color + ';"></span>' +
                        name + '</span>';
                });
            }
            tagBadges += '</span>';

            // 操作列
            var operations =
                '<button class="btn btn-outline-secondary btn-xs btn-preview-file" ' +
                'data-file-id="' + f.id + '" title="预览文件">预览</button>' +
                '<button class="btn btn-outline-primary btn-xs btn-download-file" ' +
                'data-file-id="' + f.id + '" title="下载文件">下载</button>';

            return '<tr data-file-id="' + f.id + '">' +
                '<td class="file-type-icon" title="' + LanDocHub.Utils.escapeHtml(f.file_type) + '">' + typeIcon + '</td>' +
                '<td class="file-name">' + shortcut + f.original_filename + '</td>' +
                '<td class="text-center" style="white-space:nowrap;">' +
                '<span class="badge badge-secondary mr-1">' + (f.version_number || 'I') + '</span>' +
                (f.has_versions
                    ? '<button class="btn btn-sm btn-outline-secondary btn-history" ' +
                      'data-file-id="' + f.id + '" title="查看历史版本" ' +
                      'style="font-size:0.7rem;padding:1px 6px;">历史</button>'
                    : '') +
                (f.version_note ? '<div class="small text-muted">' + LanDocHub.Utils.escapeHtml(f.version_note) + '</div>' : '') +
                '</td>' +
                '<td><span class="badge badge-info">' + (f.project_model || '') + '</span></td>' +
                '<td class="file-meta">' + LanDocHub.Utils.formatFileSize(f.file_size) + '</td>' +
                '<td>' + tagBadges + '</td>' +
                '<td class="file-meta">' + (f.uploader_name || '') + '</td>' +
                '<td class="file-meta">' + f.uploaded_at + '</td>' +
                '<td class="file-operations">' + operations + '</td>' +
                '</tr>';
        });

        var tableHtml = [
            '<div class="file-table"><table class="table table-hover mb-0">',
            '<thead><tr>',
            '<th class="col-type-icon sortable-header" data-sort="file_type">类型 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="original_filename">文件名 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="version_number">版本 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="model">型号 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="file_size">大小 <span class="sort-arrow"></span></th>',
            '<th>标签</th>',
            '<th class="sortable-header" data-sort="uploader_name">上传者 <span class="sort-arrow"></span></th>',
            '<th class="sortable-header" data-sort="created_at">时间 <span class="sort-arrow"></span></th>',
            '<th class="col-operations">操作</th>',
            '</tr></thead><tbody>',
            rows.join(''),
            '</tbody></table></div>',
            renderPagination(page, pages, total, folderId),
        ].join('');

        $container.html(tableHtml);

        // 更新排序箭头状态
        updateSortArrows(sortBy, sortOrder);

        // 恢复滚动 + 高亮
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

    function updateSortArrows(sortBy, sortOrder) {
        $container.find('.sortable-header .sort-arrow').text('');
        var $active = $container.find('.sortable-header[data-sort="' + sortBy + '"] .sort-arrow');
        $active.text(sortOrder === 'asc' ? ' ▲' : ' ▼');
    }

    function renderPagination(page, pages, total, folderId) {
        if (pages <= 1) return '';

        var html = '<nav class="file-pagination mt-3"><ul class="pagination pagination-sm justify-content-center flex-wrap mb-0">';

        // 上一页
        html += '<li class="page-item' + (page <= 1 ? ' disabled' : '') + '">';
        html += '<a class="page-link" href="#" data-page="' + (page - 1) + '">&laquo;</a></li>';

        // 页码
        var start = Math.max(1, page - 2);
        var end = Math.min(pages, page + 2);
        if (start > 1) {
            html += '<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>';
            if (start > 2) html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
        }
        for (var p = start; p <= end; p++) {
            html += '<li class="page-item' + (p === page ? ' active' : '') + '">';
            html += '<a class="page-link" href="#" data-page="' + p + '">' + p + '</a></li>';
        }
        if (end < pages) {
            if (end < pages - 1) html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
            html += '<li class="page-item"><a class="page-link" href="#" data-page="' + pages + '">' + pages + '</a></li>';
        }

        // 下一页
        html += '<li class="page-item' + (page >= pages ? ' disabled' : '') + '">';
        html += '<a class="page-link" href="#" data-page="' + (page + 1) + '">&raquo;</a></li>';

        html += '<li class="page-item disabled ml-2"><span class="page-link border-0">共 ' + total + ' 个文件</span></li>';
        html += '</ul></nav>';

        return html;
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

    // F5-2: 历史版本按钮点击
    $(document).on('click', '.btn-history', function () {
        var fileId = $(this).data('file-id');
        if (fileId) {
            VersionHistoryModal.show(fileId);
        }
    });

    // F6-1: 排序表头点击
    $(document).on('click', '.sortable-header', function () {
        var sortBy = $(this).data('sort');
        if (!sortBy) return;

        var currentSortBy = $container.data('sortBy') || 'created_at';
        var currentOrder = $container.data('sortOrder') || 'asc';

        if (sortBy === currentSortBy) {
            // 同列切换方向
            $container.data('sortOrder', currentOrder === 'asc' ? 'desc' : 'asc');
        } else {
            // 不同列，默认升序
            $container.data('sortBy', sortBy);
            $container.data('sortOrder', 'asc');
        }

        var folderId = $container.data('currentFolderId');
        if (folderId) {
            loadFiles(folderId, '', 1);  // 排序时回到第 1 页
        }
    });

    // F6-1: 分页点击
    $(document).on('click', '.file-pagination .page-link', function (e) {
        e.preventDefault();
        var p = parseInt($(this).data('page'));
        if (isNaN(p)) return;
        var folderId = $container.data('currentFolderId');
        if (folderId) {
            loadFiles(folderId, '', p);
        }
    });

    // F6-1: 操作列 — 预览按钮
    $(document).on('click', '.btn-preview-file', function () {
        var fileId = $(this).data('file-id');
        if (fileId) {
            window.open('/preview/' + fileId, '_blank');
        }
    });

    // F6-1: 操作列 — 下载按钮（占位，路由由 F8-1 实现）
    $(document).on('click', '.btn-download-file', function () {
        alert('文件下载功能即将开放（F8-1 阶段）');
    });
});
